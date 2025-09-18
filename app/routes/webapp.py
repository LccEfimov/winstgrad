from flask import Blueprint, render_template, request, jsonify, current_app, session
from sqlalchemy import desc
from functools import wraps
from ..db import db
from ..models import User, Product, Service, Order, OrderItem, Review, Feedback
from ..utils.telegram_webapp import verify_webapp_init_data, user_from_verified, parse_init_data
from ..auth import create_tokens, set_auth_cookies, clear_auth_cookies, jwt_required


bp = Blueprint("webapp", __name__)

# --------- вспомогалки ---------
def _session_user():
    uid = session.get("uid")
    return User.query.get(uid) if uid else None

def _login_with_init(init_data: str):
    ok, data = verify_webapp_init_data(init_data, current_app.config["TELEGRAM_BOT_TOKEN"])
    if not ok:
        return None
    uinfo = user_from_verified(data)
    if not uinfo.get("id"):
        return None
    user = User.query.filter_by(telegram_id=uinfo["id"]).first()
    if not user:
        user = User(
            telegram_id=uinfo["id"],
            username=uinfo.get("username"),
            first_name=uinfo.get("first_name"),
            last_name=uinfo.get("last_name"),
        )
        db.session.add(user); db.session.commit()
    else:
        # легкое обновление профиля
        user.username = uinfo.get("username") or user.username
        user.first_name = uinfo.get("first_name") or user.first_name
        user.last_name = uinfo.get("last_name") or user.last_name
        db.session.commit()
    session["uid"] = user.id
    return user

def require_tg(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        u = _session_user()
        if u:
            request.user = u
            return view(*args, **kwargs)
        # пробуем initData из заголовка, query tgWebAppData, либо initData
        init_data = (
            request.headers.get("X-Telegram-Init-Data")
            or request.args.get("tgWebAppData")
            or request.args.get("initData")
            or ""
        )
        u = _login_with_init(init_data) if init_data else None
        if u:
            request.user = u
            return view(*args, **kwargs)
        return render_template("landing_only_telegram.html"), 403
    return wrapper

# --------- публичные / вход ---------
@bp.get("/")
def index():
    return render_template("webapp_index.html")


@bp.post("/auth")  # старый маршрут (совместимость)
def auth_header():
    init_data = request.headers.get("X-Telegram-Init-Data") or request.args.get("initData") or ""
    u = _login_with_init(init_data) if init_data else None
    if not u:
        return jsonify({"ok": False, "error": "not_authorized"}), 401
    return jsonify({"ok": True})

@bp.post("/api/telegram/auth")
def api_telegram_auth():
    payload = request.get_json(silent=True) or {}
    init_data = payload.get("initData") or ""
    ok, data = verify_webapp_init_data(init_data, current_app.config["TELEGRAM_BOT_TOKEN"])
    if not ok:
        return jsonify({"success": False, "error": "Invalid initData"}), 401

    uinfo = user_from_verified(data)
    if not uinfo.get("id"):
        return jsonify({"success": False, "error": "No user in initData"}), 401

    # найти/создать пользователя
    user = User.query.filter_by(telegram_id=uinfo["id"]).first()
    if not user:
        user = User(telegram_id=uinfo["id"],
                    username=uinfo.get("username"),
                    first_name=uinfo.get("first_name"),
                    last_name=uinfo.get("last_name"))
        db.session.add(user); db.session.commit()
    else:
        # легкое обновление
        user.username = uinfo.get("username") or user.username
        user.first_name = uinfo.get("first_name") or user.first_name
        user.last_name  = uinfo.get("last_name") or user.last_name
        db.session.commit()

    access, refresh = create_tokens(user.id, getattr(user, "role", "client"))
    resp = jsonify({"success": True, "user": {
        "id": user.id, "telegram_id": user.telegram_id, "username": user.username,
        "first_name": user.first_name, "last_name": user.last_name
    }})
    set_auth_cookies(resp, access, refresh)
    return resp


# регистрация от бота /start (создать/обновить заранее)
@bp.post("/api/telegram/register")
def api_telegram_register():
    data = request.get_json(force=True)
    tg_id = data.get("telegram_id")
    if not tg_id:
        return jsonify({"success": False, "error":"telegram_id required"}), 400
    user = User.query.filter_by(telegram_id=tg_id).first()
    if not user:
        user = User(
            telegram_id=tg_id,
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )
        db.session.add(user)
    else:
        user.username = data.get("username") or user.username
        user.first_name = data.get("first_name") or user.first_name
        user.last_name  = data.get("last_name")  or user.last_name
    db.session.commit()
    return jsonify({"success": True, "user_id": user.id})

# --------- webapp страницы ---------
@bp.get("/catalog")
@jwt_required
def catalog():
    # request.user уже установлен декоратором
    products = Product.query.filter_by(is_active=True).all()
    services = Service.query.filter_by(is_active=True).all()
    return render_template("catalog.html", products=products, services=services)

@bp.get("/orders")
@jwt_required
def orders():
    u = request.user
    orders = Order.query.filter_by(user_id=u.id).order_by(desc(Order.created_at)).all()
    items_map = {o.id: OrderItem.query.filter_by(order_id=o.id).all() for o in orders}
    return render_template("orders.html", orders=orders, items_map=items_map)

@bp.post("/order")
@jwt_required
def create_order():
    payload = request.get_json(force=True)
    items = payload.get("items", [])
    order = Order(user_id=request.user.id, status="new", total=0)
    db.session.add(order); db.session.flush()
    total = 0
    for it in items:
        qty = float(it.get("qty", 1))
        price = float(it.get("price", 0))
        oi = OrderItem(order_id=order.id, item_type=it["type"], item_id=it["id"],
                       qty=qty, unit_price=price, total=qty*price)
        total += oi.total; db.session.add(oi)
    order.total = total; db.session.commit()
    return jsonify({"ok": True, "order_id": order.id, "total": float(total)})

@bp.get("/profile")
@jwt_required
def profile_get():
    return render_template("profile.html", user=request.user)

@bp.post("/profile")
@jwt_required
def profile_post():
    u = request.user
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    addr  = (data.get("delivery_address") or "").strip()
    if email and "@" not in email: return jsonify({"ok": False, "error":"Некорректный email"}), 400
    if phone and len(phone) < 6:   return jsonify({"ok": False, "error":"Некорректный телефон"}), 400
    u.email = email or None; u.phone = phone or None; u.delivery_address = addr or None
    db.session.commit()
    return jsonify({"ok": True})

@bp.post("/reviews")
@jwt_required
def reviews_post():
    data = request.get_json(force=True)
    target_type = data.get("target_type")
    target_id   = int(data.get("target_id", 0))
    rating      = int(data.get("rating", 0))
    text        = (data.get("text") or "").strip()
    if target_type not in ("product","service") or target_id <= 0: return jsonify({"ok":False,"error":"Некорректная цель"}),400
    if rating < 1 or rating > 5: return jsonify({"ok":False,"error":"Рейтинг 1–5"}),400
    if len(text) < 5: return jsonify({"ok":False,"error":"Слишком короткий отзыв"}),400
    rv = Review(user_id=request.user.id, target_type=target_type, target_id=target_id,
                rating=rating, text=text, is_moderated=False)
    db.session.add(rv); db.session.commit()
    return jsonify({"ok": True})

@bp.get("/feedback")
@jwt_required
def feedback_get():
    return render_template("feedback.html")

@bp.post("/feedback")
@jwt_required
def feedback_post():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    message = (data.get("message") or "").strip()
    if not name or not message:
        return jsonify({"ok": False, "error":"Заполните имя и сообщение"}), 400
    fb = Feedback(user_id=request.user.id,  # <<< тут была session.get("uid")
                  name=name,
                  phone=(data.get("phone") or None),
                  email=(data.get("email") or None),
                  subject=(data.get("subject") or None),
                  message=message,
                  status="new")
    db.session.add(fb); db.session.commit()
    return jsonify({"ok": True})


@bp.get("/me")
@jwt_required
def me():
    u = request.user
    return jsonify({
        "id": u.id, "telegram_id": u.telegram_id, "username": u.username,
        "first_name": u.first_name, "last_name": u.last_name,
        "phone": u.phone, "email": u.email, "delivery_address": u.delivery_address
    })


@bp.get("/healthz")
def healthz():
    return "ok", 200
