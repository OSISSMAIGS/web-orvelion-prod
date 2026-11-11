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

# Optimasi: Cache in-memory dan interval pembersihan berkala
# Mengurangi operasi disk I/O SQLite hingga 95% agar web tidak lagging
_last_cleanup_time = 0.0
_cleanup_interval = 30.0  # Pembersihan SQLite tiap 30 detik (bukan di setiap request)
_cached_active_count = 1
_session_verified: dict[str, float] = {}
_verified_lock = threading.Lock()


def _now() -> float:
    return time.time()


def _get_db():
    conn = sqlite3.connect(DB_PATH, timeout=3.0)
    conn.execute("PRAGMA journal_mode=WAL")
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
    global _last_cleanup_time, _cached_active_count
    now = _now()
    cutoff = now - ttl

    # 1. Bersihkan SQLite (hanya jika sudah melewati interval 30s agar disk tidak terbebani)
    try:
        with _get_db() as conn:
            if now - _last_cleanup_time > _cleanup_interval:
                conn.execute("DELETE FROM queue_active_sessions WHERE last_seen < ?", (cutoff,))
                _last_cleanup_time = now
            cur = conn.execute("SELECT COUNT(*) FROM queue_active_sessions")
            count = cur.fetchone()[0]
            conn.commit()
            _cached_active_count = count
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
    global _last_cleanup_time, _cached_active_count
    now = _now()

    # 1. Fast Path In-Memory: Jika sesi ini baru saja divalidasi (< 15 detik lalu),
    # langsung izinkan dari memori tanpa menyentuh disk SQLite sama sekali (0ms latency).
    with _verified_lock:
        last_v = _session_verified.get(session_id)
        if last_v and (now - last_v < 15.0):
            return {
                "allowed": True,
                "activeCount": max(1, _cached_active_count),
                "maxAllowed": max_users,
            }

    cutoff = now - ttl

    try:
        with _get_db() as conn:
            # Hapus yang kedaluwarsa secara berkala (bukan di setiap request)
            if now - _last_cleanup_time > _cleanup_interval:
                conn.execute("DELETE FROM queue_active_sessions WHERE last_seen < ?", (cutoff,))
                _last_cleanup_time = now

            # Cek apakah session_id ini sudah terdaftar
            cur = conn.execute("SELECT session_id FROM queue_active_sessions WHERE session_id = ?", (session_id,))
            exists = cur.fetchone() is not None

            if exists:
                conn.execute("UPDATE queue_active_sessions SET last_seen = ? WHERE session_id = ?", (now, session_id))
                cur_cnt = conn.execute("SELECT COUNT(*) FROM queue_active_sessions").fetchone()[0]
                conn.commit()
                with _verified_lock:
                    _session_verified[session_id] = now
                    _cached_active_count = cur_cnt
                    if len(_session_verified) > 2000:
                        _session_verified.clear()
                return {"allowed": True, "activeCount": cur_cnt, "maxAllowed": max_users}

            # Cek total active
            cur_cnt = conn.execute("SELECT COUNT(*) FROM queue_active_sessions").fetchone()[0]
            if cur_cnt < max_users:
                conn.execute("INSERT OR REPLACE INTO queue_active_sessions (session_id, last_seen) VALUES (?, ?)", (session_id, now))
                conn.commit()
                with _verified_lock:
                    _session_verified[session_id] = now
                    _cached_active_count = cur_cnt + 1
                    if len(_session_verified) > 2000:
                        _session_verified.clear()
                return {"allowed": True, "activeCount": cur_cnt + 1, "maxAllowed": max_users}

            conn.commit()
            return {"allowed": False, "activeCount": cur_cnt, "maxAllowed": max_users}
    except Exception:
        pass

    # Fallback In-Memory Thread-Safe jika SQLite sibuk atau terkunci
    cleanup_expired(ttl)
    with _mem_lock:
        if session_id in _mem_sessions:
            _mem_sessions[session_id] = now
            with _verified_lock:
                _session_verified[session_id] = now
            return {"allowed": True, "activeCount": len(_mem_sessions), "maxAllowed": max_users}
        if len(_mem_sessions) < max_users:
            _mem_sessions[session_id] = now
            with _verified_lock:
                _session_verified[session_id] = now
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
