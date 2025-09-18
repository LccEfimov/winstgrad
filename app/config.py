import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY","dev")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.getenv("REDIS_URL","redis://127.0.0.1:6379/0")
    WEBAPP_URL = os.getenv("WEBAPP_URL")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID","0"))
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS","").split(",") if os.getenv("ALLOWED_ORIGINS") else []
    JWT_SECRET = os.getenv("JWT_SECRET", "change_me_long_random")
    JWT_ACCESS_TTL_MIN = int(os.getenv("JWT_ACCESS_TTL_MIN", "15"))
    JWT_REFRESH_TTL_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "30"))
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "winstgrad.ru")
    COOKIE_SECURE = True  # у нас https
