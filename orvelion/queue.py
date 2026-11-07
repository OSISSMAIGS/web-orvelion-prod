from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from typing import Any
from urllib.parse import quote

from flask import Flask, g, jsonify, redirect, request

# DB Path untuk persistensi multi-worker (Passenger / Gunicorn)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nordelia.db")

_mem_lock = threading.Lock()
_mem_sessions: dict[str, float] = {}


def _now() -> float:
    return time.time()


def _get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    # synchronous=NORMAL aman bersama WAL dan jauh lebih cepat untuk
    # tabel tracker sesi (data ini sembuh-sendiri / tidak kritis).
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_queue_db():
    try:
        with _get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queue_active_sessions (
                    session_id TEXT PRIMARY KEY,
                    last_seen REAL NOT NULL
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[QueueDB] Init table error: {e}")


def cleanup_expired(ttl: int) -> int:
    cutoff = _now() - ttl
    # 1. Bersihkan SQLite
    try:
        with _get_db() as conn:
            conn.execute("DELETE FROM queue_active_sessions WHERE last_seen < ?", (cutoff,))
            cur = conn.execute("SELECT COUNT(*) FROM queue_active_sessions")
            count = cur.fetchone()[0]
            conn.commit()
            return count
    except Exception:
        pass

    # 2. Fallback memory
    with _mem_lock:
        expired = [sid for sid, last in _mem_sessions.items() if last < cutoff]
        for sid in expired:
            del _mem_sessions[sid]
        return len(_mem_sessions)


def try_acquire_slot(session_id: str, max_users: int, ttl: int) -> dict[str, Any]:
    now = _now()
    cutoff = now - ttl

    try:
        with _get_db() as conn:
            # Hapus yang kedaluwarsa
            conn.execute("DELETE FROM queue_active_sessions WHERE last_seen < ?", (cutoff,))

            # Cek apakah session_id ini sudah terdaftar
            cur = conn.execute("SELECT session_id FROM queue_active_sessions WHERE session_id = ?", (session_id,))
            exists = cur.fetchone() is not None

            if exists:
                conn.execute("UPDATE queue_active_sessions SET last_seen = ? WHERE session_id = ?", (now, session_id))
                cur_cnt = conn.execute("SELECT COUNT(*) FROM queue_active_sessions").fetchone()[0]
                conn.commit()
                return {"allowed": True, "activeCount": cur_cnt, "maxAllowed": max_users}

            # Cek total active
            cur_cnt = conn.execute("SELECT COUNT(*) FROM queue_active_sessions").fetchone()[0]
            if cur_cnt < max_users:
                conn.execute("INSERT OR REPLACE INTO queue_active_sessions (session_id, last_seen) VALUES (?, ?)", (session_id, now))
                conn.commit()
                return {"allowed": True, "activeCount": cur_cnt + 1, "maxAllowed": max_users}

            conn.commit()
            return {"allowed": False, "activeCount": cur_cnt, "maxAllowed": max_users}
    except Exception:
        pass

    # Fallback In-Memory Thread-Safe
    cleanup_expired(ttl)
    with _mem_lock:
        if session_id in _mem_sessions:
            _mem_sessions[session_id] = now
            return {"allowed": True, "activeCount": len(_mem_sessions), "maxAllowed": max_users}
        if len(_mem_sessions) < max_users:
            _mem_sessions[session_id] = now
            return {"allowed": True, "activeCount": len(_mem_sessions), "maxAllowed": max_users}
        return {"allowed": False, "activeCount": len(_mem_sessions), "maxAllowed": max_users}


def get_status(session_id: str | None, max_users: int, ttl: int) -> dict[str, Any]:
    active = cleanup_expired(ttl)
    now = _now()
    cutoff = now - ttl

    if session_id:
        try:
            with _get_db() as conn:
                cur = conn.execute("SELECT session_id FROM queue_active_sessions WHERE session_id = ? AND last_seen >= ?", (session_id, cutoff))
                if cur.fetchone() is not None:
                    return {"allowed": True, "activeCount": active, "maxAllowed": max_users}
        except Exception:
            with _mem_lock:
                if session_id in _mem_sessions and _mem_sessions[session_id] >= cutoff:
                    return {"allowed": True, "activeCount": active, "maxAllowed": max_users}

    allowed = active < max_users
    return {
        "allowed": allowed,
        "activeCount": active,
        "maxAllowed": max_users,
    }


def _is_exempt(path: str) -> bool:
    # 1. Bypass asset statis & queue endpoints
    if path.startswith("/static") or path.startswith("/api/queue-status"):
        return True
    if path.startswith("/waiting-room"):
        return True

    # 2. BYPASS MUTLAK UNTUK SPREADSHEET & DATA PENTING PANITIA OSIS
    if path.startswith("/nordelia/spreadsheet") or path.startswith("/api/nordelia/export") or path.startswith("/api/nordelia/format-pendaftaran"):
        return True

    # 3. Bypass file statis berekstensi (ico, svg, png, jpg, css, js, json, csv)
    last_seg = path.rsplit("/", 1)[-1]
    if "." in last_seg:
        return True

    return False


def init_queue(app: Flask) -> None:
    _init_queue_db()

    @app.before_request
    def protect_capacity():
        if _is_exempt(request.path):
            return None

        cookie_name = app.config.get("SESSION_COOKIE_NAME", "orvelion_session")
        max_users = app.config.get("MAX_ACTIVE_USERS", 150)
        ttl = app.config.get("SESSION_TTL_SECONDS", 90)

        session_id = request.cookies.get(cookie_name) or f"guest_{uuid.uuid4().hex[:12]}"
        slot = try_acquire_slot(session_id, max_users, ttl)

        g.orvelion_session = session_id
        g.orvelion_slot = slot
        g.orvelion_set_cookie = cookie_name not in request.cookies

        if not slot["allowed"]:
            target = quote(request.full_path if request.query_string else request.path)
            return redirect(f"/waiting-room?returnUrl={target}")

        return None

    @app.after_request
    def attach_capacity_headers(response):
        slot = getattr(g, "orvelion_slot", None)
        if slot:
            max_users = app.config.get("MAX_ACTIVE_USERS", 150)
            response.headers["X-Orvelion-Active-Users"] = f"{slot['activeCount']}/{max_users}"
            response.headers["X-Orvelion-Capacity-Limit"] = f"{max_users} Users"
            if getattr(g, "orvelion_set_cookie", False):
                response.set_cookie(
                    app.config.get("SESSION_COOKIE_NAME", "orvelion_session"),
                    g.orvelion_session,
                    max_age=app.config.get("SESSION_COOKIE_MAX_AGE", 7200),
                    httponly=True,
                    samesite="Lax",
                    path="/",
                )
        return response

    @app.get("/api/queue-status")
    def queue_status():
        cookie_name = app.config.get("SESSION_COOKIE_NAME", "orvelion_session")
        max_users = app.config.get("MAX_ACTIVE_USERS", 150)
        ttl = app.config.get("SESSION_TTL_SECONDS", 90)

        session_id = request.cookies.get(cookie_name)
        payload = get_status(session_id, max_users, ttl)
        return jsonify(payload)
