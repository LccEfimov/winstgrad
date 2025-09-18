from flask import Blueprint, render_template

bp = Blueprint("public", __name__)

@bp.get("/")
def landing():
    # Заглушка для прямых заходов
    return render_template("landing_only_telegram.html")
