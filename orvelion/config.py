import os


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "orvelion-osis-igs-2026-2027")
    MAX_ACTIVE_USERS = 90
    SESSION_TTL_SECONDS = 40
    SESSION_COOKIE_NAME = "orvelion_session"
    SESSION_COOKIE_MAX_AGE = 3600
