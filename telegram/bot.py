import os
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButton, ReplyKeyboardMarkup
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0") or 0)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("winstgrad.bot")

def _require_env():
    missing = []
    if not BOT_TOKEN:   missing.append("TELEGRAM_BOT_TOKEN")
    if not WEBAPP_URL:  missing.append("WEBAPP_URL")
    if missing:
        raise SystemExit(f"env missing: {', '.join(missing)}")

async def register_user(user):
    """Регистрируем пользователя в веб-приложении (молча, без падений)."""
    if not WEBAPP_URL:
        return
    payload = {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": getattr(user, "language_code", None),
        "is_premium": getattr(user, "is_premium", False),
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{WEBAPP_URL}/app/api/telegram/register",
                              json=payload, timeout=10) as r:
                # бывают HTML-ответы, читаем аккуратно
                try:
                    j = await r.json(content_type=None)
                    if not j.get("success"):
                        log.warning("register failed: %s", j)
                except Exception:
                    txt = (await r.text())[:300].replace("\n", " ")
                    log.warning("register non-json [%s]: %s", r.status, txt)
    except Exception as e:
        log.error("register error: %s", e)

async def main():
    _require_env()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # команды в меню
    try:
        await bot.set_my_commands([
            ("start", "Главное меню"),
            ("open",  "Открыть приложение"),
            ("admin", "Админ-панель"),
            ("id",    "Показать мой Telegram ID"),
        ])
    except Exception:
        pass

    @dp.message(CommandStart())
    async def start(m: Message):
        # web_app-кнопка работает ТОЛЬКО в личном чате
        if m.chat.type != "private":
            await m.answer(
                "Откройте бота в личном чате, там появится кнопка WebApp:\n"
                "https://t.me/WinstGradBot?start=app"
            )
            return
        await register_user(m.from_user)
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(
                text="🏗️ Открыть приложение",
                web_app=WebAppInfo(url=WEBAPP_URL + "/app/")
            )]],
            resize_keyboard=True
        )
        await m.answer(
            "Добро пожаловать в Винст-Град.\nНажмите кнопку ниже, чтобы открыть приложение.",
            reply_markup=kb
        )

    @dp.message(Command("open"))
    async def open_app(m: Message):
        if m.chat.type != "private":
            await m.answer(
                "Эта кнопка доступна только в личном чате.\n"
                "Откройте: https://t.me/WinstGradBot?start=app"
            )
            return
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(
                text="🏗️ Открыть приложение",
                web_app=WebAppInfo(url=WEBAPP_URL + "/app/")
            )]],
            resize_keyboard=True
        )
        await m.answer("Открываем приложение:", reply_markup=kb)

    @dp.message(Command("admin"))
    async def admin(m: Message):
        if m.chat.type != "private":
            await m.answer("Админ-панель доступна только в личном чате с ботом.")
            return
        if m.from_user and m.from_user.id == ADMIN_ID:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Админ-панель",
                    web_app=WebAppInfo(url=WEBAPP_URL + "/app/?goto=admin")
                )]
            ])
            await m.answer("Админ-панель:", reply_markup=kb)
        else:
            await m.answer("Доступ запрещён.")

    @dp.message(Command("id"))
    async def my_id(m: Message):
        await m.answer(f"Ваш Telegram ID: <code>{m.from_user.id}</code>")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
