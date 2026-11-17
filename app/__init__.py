"""QuestionIQ Flask app: the dashboard (Phase 8) and the labelling page (Phase 4).

Run from the project root: flask --app app run
"""

from flask import Flask

from questioniq.config import load_config


def create_app(cfg: dict | None = None) -> Flask:
    """Build the Flask app and register its routes. Tests pass their own config."""
    from app.dashboard import bp as dashboard
    from app.routes import bp as labelling

    app = Flask(__name__)
    app.config["QIQ"] = cfg if cfg is not None else load_config()
    upload_mb = app.config["QIQ"].get("dashboard", {}).get("upload_max_mb", 20)
    app.config["MAX_CONTENT_LENGTH"] = upload_mb * 1024 * 1024  # bigger uploads are refused
    app.register_blueprint(dashboard)
    app.register_blueprint(labelling)
    return app
