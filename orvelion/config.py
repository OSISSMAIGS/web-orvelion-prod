import os
from orvelion.sheets_service import load_env_file

# Muat variabel environment dari .env
load_env_file()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "orvelion-osis-igs-2026-2027")
    MAX_ACTIVE_USERS = int(os.environ.get("MAX_ACTIVE_USERS", 150))
    SESSION_TTL_SECONDS = int(os.environ.get('SESSION_TTL_SECONDS', 90))
    SESSION_COOKIE_NAME = "orvelion_session"
    SESSION_COOKIE_MAX_AGE = 3600
