from flask import Flask, render_template

from orvelion.config import Config
from orvelion.content import NAV_LINKS, SITE, SOCIAL_LINKS
from orvelion.queue import init_queue
from orvelion.routes import bp as pages_bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    init_queue(app)
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
