import os

from flask import Flask, render_template, request

from orvelion.config import Config
from orvelion.content import NAV_LINKS, SITE, SOCIAL_LINKS
from orvelion.queue import init_queue
from orvelion.routes import bp as pages_bp


def _asset_version(static_folder: str) -> str:
    """Versi aset = mtime termutakhir di static/ (hex).

    Dipakai sebagai query ?v= pada URL CSS/JS di base.html. Begitu file
    berganti (deploy baru), versi ikut berubah sehingga cache browser
    otomatis dibatalkan tanpa perlu ganti nama file.
    """
    newest = 0.0
    for root, _dirs, files in os.walk(static_folder):
        for name in files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(root, name)))
            except OSError:
                pass
    return format(int(newest), "x")


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    init_queue(app)
    app.register_blueprint(pages_bp)

    asset_v = _asset_version(app.static_folder)

    @app.context_processor
    def inject_asset_version():
        return {"asset_v": asset_v}

    @app.after_request
    def set_cache_policy(response):
        ctype = response.headers.get("Content-Type", "")
        if ctype.startswith("text/html"):
            # Halaman selalu divalidkan ulang (penting untuk limiter kapasitas
            # dan fetch soft-nav), tapi boleh disimpan untuk pemakaian offline.
            response.headers["Cache-Control"] = "no-cache"
        elif request.path.startswith("/static"):
            if request.path.endswith((".css", ".js")):
                if request.args.get("v"):
                    # URL ber-versi (?v=mtime) -> aman di-cache setahun penuh
                    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                else:
                    response.headers["Cache-Control"] = "public, max-age=600"
            else:
                # Gambar & lainnya: cache sedang, 1 jam
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response

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
