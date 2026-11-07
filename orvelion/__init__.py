import os

from flask import Flask, render_template

from orvelion.config import Config
from orvelion.content import NAV_LINKS, SITE, SOCIAL_LINKS
from orvelion.optimizations import init_optimizations
from orvelion.queue import init_queue
from orvelion.routes import bp as pages_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)

    # Bytecode cache Jinja2: template tidak di-parse ulang saat proses
    # Passenger baru di-spawn (cold start lebih cepat). Gagal → abaikan
    # (hanya berpengaruh ke kecepatan, bukan fungsi).
    try:
        import tempfile
        from jinja2 import FileSystemBytecodeCache

        _jinja_cache_dir = os.path.join(tempfile.gettempdir(), "orvelion_jinja_cache")
        os.makedirs(_jinja_cache_dir, exist_ok=True)
        app.jinja_env.bytecode_cache = FileSystemBytecodeCache(_jinja_cache_dir, "%s.cache")
    except Exception:
        pass

    # Versi aset otomatis dari mtime file: setiap deploy baru otomatis
    # mem-bust cache browser (?v= berubah sendiri), tanpa perlu ganti
    # angka manual di template. URL pola sama seperti sebelumnya.
    @app.context_processor
    def _asset_version():
        def asset_v(filename: str) -> str:
            try:
                return str(int(os.path.getmtime(os.path.join(app.static_folder, filename))))
            except OSError:
                return "0"

        return {"asset_v": asset_v}

    init_queue(app)
    init_optimizations(app)
    app.register_blueprint(pages_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "404.html",
            site=SITE,
            nav_links=NAV_LINKS,
            social_links=SOCIAL_LINKS,
            active_page="404",
            show_chrome=True,
        ), 404

    return app
