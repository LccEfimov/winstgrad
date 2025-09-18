from flask_sqlalchemy import SQLAlchemy
from flask import current_app
from alembic import command
from alembic.config import Config as AlembicConfig
import os

db = SQLAlchemy()

def migrate_setup(app):
    # ленивый вариант: создаём таблицы, если миграции не настроены
    with app.app_context():
        from . import models  # noqa
        db.create_all()
