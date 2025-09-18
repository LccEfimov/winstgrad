import time
import jwt
from typing import Optional, Tuple, Dict
from flask import current_app, request, make_response, g
from functools import wraps


ACCESS_COOKIE = "wg_at"
REFRESH_COOKIE = "wg_rt"

def _now() -> int:
    return int(time.time())

def _encode(payload: Dict, ttl_seconds: int) -> str:
    data = payload.copy()
    data["iat"] = _now()
    data["exp"] = _now() + ttl_seconds
    return jwt.encode(data, current_app.config["JWT_SECRET"], algorithm="HS256")

def create_tokens(user_id: int, role: str = "client") -> Tuple[str, str]:
    access = _encode({"sub": user_id, "role": role, "typ": "access"},
                     current_app.config["JWT_ACCESS_TTL_MIN"] * 60)
    refresh = _encode({"sub": user_id, "role": role, "typ": "refresh"},
                      current_app.config["JWT_REFRESH_TTL_DAYS"] * 24 * 3600)
    return access, refresh

def _decode(token: str, verify_exp: bool = True) -> Optional[Dict]:
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"],
                          algorithms=["HS256"], options={"verify_exp": verify_exp})
    except jwt.ExpiredSignatureError:
        if verify_exp:
            raise
        return None
    except jwt.PyJWTError:
        return None

def set_auth_cookies(resp, access: str, refresh: str):
    params = {
        "domain": current_app.config["COOKIE_DOMAIN"],
        "secure": current_app.config["COOKIE_SECURE"],
        "httponly": True,
        "samesite": "None",  # WebView ок. Если что, можно Lax.
        "path": "/",
    }
    resp.set_cookie(ACCESS_COOKIE, access, **params)
    # refresh обычно «длинный»
    resp.set_cookie(REFRESH_COOKIE, refresh, **params)

def clear_auth_cookies(resp):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        resp.delete_cookie(name, domain=current_app.config["COOKIE_DOMAIN"], path="/", samesite="None")

def _extract_tokens():
    return request.cookies.get(ACCESS_COOKIE), request.cookies.get(REFRESH_COOKIE)

def jwt_required(view):
    """Достаёт пользователя из access; если access истёк — обновляет по refresh.
       ВАЖНО: request.user и g.user ставим ДО вызова view().
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        from .models import User  # локальный импорт, чтобы избежать циклов
        access, refresh = _extract_tokens()
        user = None
        new_tokens = None

        # -- пытаемся декодировать access
        if access:
            try:
                data = _decode(access, verify_exp=True)
                if data and data.get("typ") == "access":
                    user = User.query.get(int(data["sub"]))
            except jwt.ExpiredSignatureError:
                # ок, попробуем по refresh
                pass
            except jwt.PyJWTError:
                pass

        # -- если не вышло, пробуем refresh
        if user is None and refresh:
            try:
                data = _decode(refresh, verify_exp=True)
                if data and data.get("typ") == "refresh":
                    user = User.query.get(int(data["sub"]))
                    if user:
                        new_tokens = create_tokens(user.id, getattr(user, "role", "client"))
            except jwt.PyJWTError:
                pass

        if user is None:
            from flask import jsonify
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        # УСТАНАВЛИВАЕМ ПОЛЬЗОВАТЕЛЯ ДО ВЫЗОВА view
        g.user = user
        request.user = user

        resp = make_response(view(*args, **kwargs))
        if new_tokens:
            set_auth_cookies(resp, *new_tokens)
        return resp
    return wrapper