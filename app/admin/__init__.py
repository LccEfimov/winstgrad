from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from ..db import db
from ..models import User, Product, Service, Order, OrderItem, Review, Feedback, Category

class SecuredModelView(ModelView):
    def is_accessible(self):
        from flask import current_app, request, session

        hdr = request.headers.get("X-Telegram-Admin")
        if hdr and hdr == str(current_app.config["TELEGRAM_ADMIN_ID"]):
            return True

        uid = session.get("uid")
        if uid:
            user = User.query.get(uid)
            if user and getattr(user, "role", "client") == "admin":
                return True
        return False

def init_admin(app):
    admin = Admin(app, name="Winst-Grad Admin", template_mode="bootstrap4", url="/admin")
    for mdl in (User, Category, Product, Service, Order, OrderItem, Review, Feedback):
        admin.add_view(SecuredModelView(mdl, db.session))
