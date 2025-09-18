# /opt/winstgrad/app/utils/telegram_webapp.py
import hmac
import hashlib
import urllib.parse
import json
import time
from typing import Tuple, Optional, Dict, Any

def parse_init_data(init_data: str) -> Dict[str, str]:
    # безопасный парсинг строки initData
    return dict(urllib.parse.parse_qsl(init_data or "", keep_blank_values=True))

def _secret_key(bot_token: str) -> bytes:
    # secret = HMAC_SHA256("WebAppData", bot_token)
    return hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

def _calc_hash(check_string: str, bot_token: str) -> str:
    # hash = HMAC_SHA256(secret, data_check_string)
    secret = _secret_key(bot_token)
    return hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()

def _verify(init_data: str, bot_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    try:
        data = parse_init_data(init_data)
        received_hash = data.pop("hash", None)
        if not received_hash:
            return False, None

        check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        calc_hash = _calc_hash(check_string, bot_token)
        if not hmac.compare_digest(calc_hash, received_hash):
            return False, None

        # не старше 24 часов
        auth_date = int(data.get("auth_date", "0") or "0")
        if auth_date and (time.time() - auth_date > 86400):
            return False, None

        # user обязателен
        user_raw = data.get("user")
        if not user_raw:
            return False, None
        data["user"] = json.loads(user_raw) if isinstance(user_raw, str) else user_raw
        return True, data
    except Exception:
        return False, None

# — экспортируем ДВА имени для совместимости —
def verify_webapp_init_data(init_data: str, bot_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    return _verify(init_data, bot_token)

def verify_init_data(init_data: str, bot_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    # alias (некоторые версии кода импортируют это имя)
    return _verify(init_data, bot_token)

def user_from_verified(data: Dict[str, Any]) -> Dict[str, Any]:
    u = data.get("user") or {}
    return {
        "id": u.get("id"),
        "username": u.get("username"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "language_code": u.get("language_code"),
        "is_premium": u.get("is_premium", False),
    }
