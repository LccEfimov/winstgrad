from flask import Blueprint, render_template, request, jsonify, current_app, session
from sqlalchemy import desc, or_
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from ..db import db
from ..models import User, Product, Service, Order, OrderItem, Review, Feedback
from ..utils.telegram_webapp import verify_webapp_init_data, user_from_verified
from ..auth import create_tokens, set_auth_cookies, jwt_required


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
    user = request.user
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    services = Service.query.filter_by(is_active=True).order_by(Service.name).all()

    visible_reviews = Review.query.filter(
        or_(Review.is_moderated.is_(True), Review.user_id == user.id)
    ).order_by(desc(Review.created_at)).all()

    reviews_map = {"product": defaultdict(list), "service": defaultdict(list)}
    for rv in visible_reviews:
        bucket = reviews_map.get(rv.target_type)
        if bucket is not None:
            bucket[rv.target_id].append(rv)

    review_stats = {"product": {}, "service": {}}
    for rtype, bucket in reviews_map.items():
        for target_id, items in bucket.items():
            avg = sum(item.rating for item in items) / max(len(items), 1)
            review_stats[rtype][target_id] = {
                "items": items,
                "average": avg,
                "count": len(items),
            }

    return render_template(
        "catalog.html",
        products=products,
        services=services,
        review_stats=review_stats,
        user=user,
        is_admin=(getattr(user, "role", "client") == "admin"),
        nav_active="catalog",
    )

@bp.get("/orders")
@jwt_required
def orders():
    user = request.user
    orders = (
        Order.query.filter_by(user_id=user.id)
        .order_by(desc(Order.created_at))
        .all()
    )

    order_ids = [o.id for o in orders]
    raw_items = (
        OrderItem.query.filter(OrderItem.order_id.in_(order_ids)).all()
        if order_ids
        else []
    )

    product_ids = {it.item_id for it in raw_items if it.item_type == "product"}
    service_ids = {it.item_id for it in raw_items if it.item_type == "service"}
    products = (
        {p.id: p for p in Product.query.filter(Product.id.in_(product_ids))}
        if product_ids
        else {}
    )
    services = (
        {s.id: s for s in Service.query.filter(Service.id.in_(service_ids))}
        if service_ids
        else {}
    )

    items_map = defaultdict(list)
    for it in raw_items:
        info = {
            "type": it.item_type,
            "qty": it.qty,
            "unit_price": it.unit_price,
            "total": it.total,
        }
        if it.item_type == "product":
            prod = products.get(it.item_id)
            if prod:
                info["name"] = prod.name
                info["unit"] = prod.unit
        elif it.item_type == "service":
            srv = services.get(it.item_id)
            if srv:
                info["name"] = srv.name
                info["unit"] = "услуга"
        items_map[it.order_id].append(info)

    items_map = dict(items_map)

    return render_template(
        "orders.html",
        orders=orders,
        items_map=items_map,
        user=user,
        is_admin=(getattr(user, "role", "client") == "admin"),
        nav_active="orders",
    )

@bp.post("/order")
@jwt_required
def create_order():
    payload = request.get_json(force=True)
    items = payload.get("items") or []
    comment = (payload.get("comment") or "").strip()
    delivery_price = payload.get("delivery_price")

    if not items:
        return jsonify({"ok": False, "error": "empty_order"}), 400

    def to_decimal(value) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    order = Order(
        user_id=request.user.id,
        status="new",
        comment=comment or None,
        delivery_price=to_decimal(delivery_price or 0),
        total=Decimal("0.00"),
    )
    db.session.add(order)
    db.session.flush()

    total = Decimal("0.00")
    added = 0
    for it in items:
        item_type = it.get("type")
        item_id = int(it.get("id", 0))
        qty_raw = it.get("qty", 1)
        try:
            qty = Decimal(str(qty_raw))
        except Exception:
            return jsonify({"ok": False, "error": "invalid_qty"}), 400
        if qty <= 0:
            return jsonify({"ok": False, "error": "invalid_qty"}), 400

        if item_type == "product":
            obj = Product.query.get(item_id)
            if not obj or not obj.is_active:
                return jsonify({"ok": False, "error": "unknown_product"}), 400
            unit_price = to_decimal(obj.price)
        elif item_type == "service":
            obj = Service.query.get(item_id)
            if not obj or not obj.is_active:
                return jsonify({"ok": False, "error": "unknown_service"}), 400
            unit_price = to_decimal(obj.base_price)
        else:
            return jsonify({"ok": False, "error": "invalid_type"}), 400

        line_total = (unit_price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db.session.add(
            OrderItem(
                order_id=order.id,
                item_type=item_type,
                item_id=item_id,
                qty=qty,
                unit_price=unit_price,
                total=line_total,
            )
        )
        added += 1
        total += line_total

    if not added:
        return jsonify({"ok": False, "error": "empty_order"}), 400

    order.total = (total + (order.delivery_price or Decimal("0.00"))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    db.session.commit()
    return jsonify({"ok": True, "order_id": order.id, "total": float(order.total)})

@bp.get("/profile")
@jwt_required
def profile_get():
    user = request.user
    return render_template(
        "profile.html",
        user=user,
        is_admin=(getattr(user, "role", "client") == "admin"),
        nav_active="profile",
    )

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
    return jsonify({
        "ok": True,
        "user": {
            "email": u.email,
            "phone": u.phone,
            "delivery_address": u.delivery_address,
        },
    })

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
    user = request.user
    return render_template(
        "feedback.html",
        user=user,
        is_admin=(getattr(user, "role", "client") == "admin"),
        nav_active="feedback",
    )

@bp.post("/feedback")
@jwt_required
def feedback_post():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    message = (data.get("message") or "").strip()
    if not name or not message:
        return jsonify({"ok": False, "error":"Заполните имя и сообщение"}), 400
    fb = Feedback(
        user_id=request.user.id,
        name=name,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        subject=(data.get("subject") or "").strip() or None,
        message=message,
        status="new",
    )
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
