import json
import logging
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ================= CONFIG =================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

SHOP_NAME = "AsmarHandmade"
CITY = os.getenv("CITY", "Amsterdam")
INSTAGRAM = os.getenv("INSTAGRAM", "")
PHONE = os.getenv("PHONE", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пустой")

if not WEBAPP_URL.lower().startswith("https://"):
    raise RuntimeError("WEBAPP_URL должен начинаться с https://")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asmar-bot")

# ================= KEYBOARD =================


def menu_kb(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("🛍️ Каталог", web_app=WebAppInfo(url=WEBAPP_URL))],
        [KeyboardButton("✨ О бренде"), KeyboardButton("📩 Контакты")],
    ]

    # Админ видит панель
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👑 Админ панель")])

    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )


# ================= TEXTS =================

def welcome_text(username: str | None) -> str:
    name = f", {username}" if username else ""
    return (
        f"✨ *Добро пожаловать{name}*\n\n"
        f"*{SHOP_NAME}* — премиальная кожгалантерея ручной работы.\n\n"
        "🪡 Натуральная кожа\n"
        "🧵 Ручные швы\n"
        "🏛 Вдохновение: Milano & Dubai\n\n"
        "Открой каталог и оформи заказ — "
        "я лично свяжусь с вами для подтверждения 🤍"
    )


BRAND_TEXT = (
    "✨ *О бренде AsmarHandmade*\n\n"
    "Это не просто аксессуары — это эстетика статуса.\n\n"
    "Каждое изделие создаётся вручную:\n"
    "• премиальная натуральная кожа\n"
    "• идеальная геометрия\n"
    "• минимализм и роскошь\n\n"
    "Малые партии. Максимум качества.\n"
    f"📍 {CITY}"
)


def contacts_text() -> str:
    text = "📩 *Связаться с нами*\n\n"
    if PHONE:
        text += f"📞 Телефон: `{PHONE}`\n"
    if INSTAGRAM:
        text += f"📸 Instagram: {INSTAGRAM}\n"
    text += "\nНапишите нам — подберём идеальную модель ✨"
    return text


# ================= HANDLERS =================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.first_name if user else None

    await update.message.reply_text(
        welcome_text(username),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=menu_kb(user.id),
    )


async def show_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        BRAND_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=menu_kb(update.effective_user.id),
    )


async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        contacts_text(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=menu_kb(update.effective_user.id),
    )


# ================= ADMIN PANEL =================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "👑 *Админ панель*\n\n"
        "Здесь отображаются все новые заказы.\n"
        "Вы получаете их автоматически при оформлении.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ================= WEBAPP ORDERS =================

async def on_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    raw = msg.web_app_data.data if msg.web_app_data else ""

    try:
        payload = json.loads(raw)
    except Exception:
        await msg.reply_text("Ошибка обработки заказа.")
        return

    items = payload.get("items", [])
    customer = payload.get("customer", {})
    total = payload.get("total_sum", 0)

    if not items:
        await msg.reply_text("Корзина пустая.")
        return

    # --------- Формируем текст для админа ---------

    lines = [
        "🧾 *НОВЫЙ ЗАКАЗ*",
        "",
        f"👤 Клиент: {customer.get('name', '-')}",
        f"📞 Телефон: {customer.get('phone', '-')}",
        f"📍 Адрес: {customer.get('address', '-')}",
        f"💬 Комментарий: {customer.get('comment', '-')}",
        "",
        "*Позиции:*",
    ]

    for i, item in enumerate(items, start=1):
        lines.append(
            f"{i}. {item['name']} — {item['qty']} × {item['price']} ₽"
        )

    lines.append("")
    lines.append(f"💎 *Итого:* {total} ₽")
    lines.append(f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    order_text = "\n".join(lines)

    # Отправка админу
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=order_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    # Подтверждение клиенту
    await msg.reply_text(
        "✨ *Ваш заказ принят!*\n\n"
        "Спасибо за выбор AsmarHandmade.\n"
        "Я свяжусь с вами в ближайшее время для подтверждения деталей 🤍",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=menu_kb(update.effective_user.id),
    )


# ================= TEXT ROUTER =================

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").lower()

    if "бренд" in text:
        await show_brand(update, context)
    elif "конт" in text:
        await show_contacts(update, context)
    elif "админ" in text:
        await admin_panel(update, context)
    else:
        await update.message.reply_text(
            "Используйте кнопки меню 👇",
            reply_markup=menu_kb(update.effective_user.id),
        )


# ================= MAIN =================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_webapp_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()