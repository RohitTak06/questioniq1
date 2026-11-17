"""QuestionIQ Flask app: the labelling page (Phase 4), later the dashboard (Phase 8).

Run from the project root: flask --app app run
"""

from flask import Flask

from questioniq.config import load_config


def create_app(cfg: dict | None = None) -> Flask:
    """Build the Flask app and register its routes. Tests pass their own config."""
    from app.routes import bp

    app = Flask(__name__)
    app.config["QIQ"] = cfg if cfg is not None else load_config()
    app.register_blueprint(bp)
    return app
