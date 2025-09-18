import os
from flask import Flask
from .db import db, migrate_setup
from .config import Config
from .admin import init_admin
from .routes.public import bp as public_bp
from .routes.webapp import bp as webapp_bp

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    db.init_app(app)
    migrate_setup(app)
    init_admin(app)

    app.register_blueprint(public_bp)
    app.register_blueprint(webapp_bp, url_prefix="/app")

    @app.after_request
    def sec_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
        return resp

    return app
