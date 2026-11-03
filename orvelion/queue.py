from __future__ import annotations

import threading
import time
import uuid
from typing import Any
from urllib.parse import quote

from flask import Flask, g, jsonify, redirect, request


_lock = threading.Lock()
_sessions: dict[str, float] = {}


def _now() -> float:
    return time.time()


def cleanup_expired(ttl: int) -> int:
    cutoff = _now() - ttl
    with _lock:
        expired = [sid for sid, last in _sessions.items() if last < cutoff]
        for sid in expired:
            del _sessions[sid]
        return len(_sessions)


def try_acquire_slot(session_id: str, max_users: int, ttl: int) -> dict[str, Any]:
    cleanup_expired(ttl)
    with _lock:
        if session_id in _sessions:
            _sessions[session_id] = _now()
            return {
                "allowed": True,
                "activeCount": len(_sessions),
                "maxAllowed": max_users,
            }
        if len(_sessions) < max_users:
            _sessions[session_id] = _now()
            return {
                "allowed": True,
                "activeCount": len(_sessions),
                "maxAllowed": max_users,
            }
        return {
            "allowed": False,
            "activeCount": len(_sessions),
            "maxAllowed": max_users,
        }


def get_status(session_id: str | None, max_users: int, ttl: int) -> dict[str, Any]:
    cleanup_expired(ttl)
    with _lock:
        active = len(_sessions)
        allowed = active < max_users or (session_id is not None and session_id in _sessions)
        return {
            "allowed": allowed,
            "activeCount": active,
            "maxAllowed": max_users,
        }


def _is_exempt(path: str) -> bool:
    if path.startswith("/static") or path.startswith("/api/queue-status"):
        return True
    if path.startswith("/waiting-room"):
        return True
    if "." in path.rsplit("/", 1)[-1]:
        return True
    return False


def init_queue(app: Flask) -> None:
    @app.before_request
    def protect_capacity():
        if _is_exempt(request.path):
            return None

        cookie_name = app.config["SESSION_COOKIE_NAME"]
        session_id = request.cookies.get(cookie_name) or f"guest_{uuid.uuid4().hex[:12]}"
        slot = try_acquire_slot(
            session_id,
            app.config["MAX_ACTIVE_USERS"],
            app.config["SESSION_TTL_SECONDS"],
        )
        g.orvelion_session = session_id
        g.orvelion_slot = slot
        g.orvelion_set_cookie = cookie_name not in request.cookies

        if not slot["allowed"]:
            target = quote(request.path)
            return redirect(f"/waiting-room?returnUrl={target}")
        return None

    @app.after_request
    def attach_capacity_headers(response):
        slot = getattr(g, "orvelion_slot", None)
        if slot:
            max_users = app.config["MAX_ACTIVE_USERS"]
            response.headers["X-Orvelion-Active-Users"] = f"{slot['activeCount']}/{max_users}"
            response.headers["X-Orvelion-Core-Protection"] = "2-Core Safe"
            if getattr(g, "orvelion_set_cookie", False):
                response.set_cookie(
                    app.config["SESSION_COOKIE_NAME"],
                    g.orvelion_session,
                    max_age=app.config["SESSION_COOKIE_MAX_AGE"],
                    httponly=True,
                    samesite="Lax",
                    path="/",
                )
        return response

    @app.get("/api/queue-status")
    def queue_status():
        cookie_name = app.config["SESSION_COOKIE_NAME"]
        payload = get_status(
            request.cookies.get(cookie_name),
            app.config["MAX_ACTIVE_USERS"],
            app.config["SESSION_TTL_SECONDS"],
        )
        return jsonify(payload)
