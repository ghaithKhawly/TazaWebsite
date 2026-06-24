"""
bot.py – Taza Telegram Bot
Full HTML UI redesign. ParseMode.HTML throughout.
"""

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from functools import partial
from typing import Optional
from urllib.parse import parse_qsl, urlparse

from aiohttp import web

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from scheduler import setup_scheduler
from sheets import db

load_dotenv()

# ──────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("taza.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("ADMIN_CHAT_IDS", "").split(",")
    if x.strip().isdigit()
]
ADMIN_GROUP_CHAT_ID = os.environ.get("ADMIN_GROUP_CHAT_ID", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8443))
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"

WEBAPP_BASE_URL = os.environ.get(
    "WEBAPP_BASE_URL", "https://<username>.github.io/taza-webapp"
).rstrip("/")
CUSTOMER_WEBAPP_URL = f"{WEBAPP_BASE_URL}/index.html"
RESTAURANT_WEBAPP_URL = f"{WEBAPP_BASE_URL}/restaurant.html"
_parsed_webapp = urlparse(WEBAPP_BASE_URL)
_default_origin = (
    f"{_parsed_webapp.scheme}://{_parsed_webapp.netloc}"
    if _parsed_webapp.scheme and _parsed_webapp.netloc
    else "*"
)
WEBAPP_CORS_ORIGIN = os.environ.get("WEBAPP_CORS_ORIGIN", _default_origin)
VENDOR_LEAD_RATE_LIMIT = 5
VENDOR_LEAD_RATE_WINDOW = 60 * 60
VENDOR_CLAIM_MAX_AGE = timedelta(days=7)

# Logo: set via /setlogo or replace manually here
LOGO_FILE_ID = os.environ.get("TAZA_LOGO_FILE_ID", "")

# In-memory dev role overrides
_dev_role_overrides: dict[int, str] = {}
_vendor_lead_requests: dict[str, list[float]] = {}

# ──────────────────────────────────────────────────────
# Static data
# ──────────────────────────────────────────────────────
AREAS = [
    "دمشق – المزة",
    "دمشق – المالكي",
    "دمشق – باب توما",
    "دمشق – الميدان",
    "دمشق – ركن الدين",
    "حلب – الشهباء الجديدة",
    "حلب – العزيزية",
    "حلب – الجميلية",
    "حمص – الوعر",
    "حمص – عكرمة",
    "اللاذقية – الزراعة",
    "طرطوس المدينة",
]

BAG_TYPES = {
    "وجبات": "🍲",
    "حلويات": "🍰",
    "مخبوزات": "🍞",
    "عصائر": "🧃",
    "مشكل": "🍱",
}

VENDOR_CATEGORIES = [
    "مطعم ووجبات",
    "مخبز ومخبوزات",
    "وجبات سريعة",
    "خضار وفواكه",
    "بقالة وتموين",
    "حلويات ومعجنات",
    "قهوة ومشروبات",
]

VENDOR_INTEREST_LEVELS = [
    "جاهز للتجربة",
    "مهتم وأحتاج تفاصيل",
    "أريد معرفة المزيد فقط",
]

VENDOR_CONCERNS = [
    "تأثير الخصم على البراند",
    "التعقيد والوقت",
    "التوصيل",
    "شكاوى الزبائن",
    "الدفع والعمولة",
    "لا يوجد قلق واضح",
]

STATUS_AR = {
    "reserved": ("⏳", "محجوز"),
    "picked_up": ("✅", "تم الاستلام"),
    "cancelled": ("❌", "ملغي"),
    "no_show": ("⚠️", "لم يُستلم"),
}

# Conversation states
(
    CUST_NAME,
    CUST_PHONE,
    RES_CONFIRM,
    BAG_TYPE,
    BAG_HINT,
    BAG_ORIG,
    BAG_DISC,
    BAG_QTY,
    BAG_START,
    BAG_END,
    BAG_PHOTO,
    BAG_CONFIRM,
    ADMIN_REST_NAME,
    ADMIN_REST_AREA,
    ADMIN_REST_ADDR,
    ADMIN_REST_MGRID,
    BROADCAST_TARGET,
    BROADCAST_MSG,
    EDIT_BAG_FIELD,
    EDIT_BAG_VALUE,
    SET_LOGO,
    VENDOR_SHOP_NAME,
    VENDOR_CATEGORY,
    VENDOR_AREA,
    VENDOR_ADDRESS,
    VENDOR_CONTACT_NAME,
    VENDOR_PHONE,
    VENDOR_CLOSING_TIME,
    VENDOR_SURPLUS,
    VENDOR_INTEREST,
    VENDOR_CONCERN,
    REST_PICKUP_CODE,
) = range(32)

HTML = ParseMode.HTML

# ══════════════════════════════════════════════════════
# HTML HELPERS
# ══════════════════════════════════════════════════════


def e(text) -> str:
    """Escape user-generated content for HTML."""
    return html.escape(str(text))


def b(text) -> str:
    return f"<b>{text}</b>"


def i(text) -> str:
    return f"<i>{text}</i>"


def s(text) -> str:
    return f"<s>{text}</s>"


def code(text) -> str:
    return f"<code>{text}</code>"


LINE = "━━━━━━━━━━━━━━"


# ══════════════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════════════


def main_menu_kb(show_rest_panel: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "🛍️ فتح تطبيق تازا", web_app=WebAppInfo(url=CUSTOMER_WEBAPP_URL)
            )
        ]
    ]
    if show_rest_panel:
        rows.append(
            [
                InlineKeyboardButton(
                    "🍽️ لوحة المطعم", web_app=WebAppInfo(url=RESTAURANT_WEBAPP_URL)
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton("📍 تحديد المنطقة", callback_data="setlocation"),
                InlineKeyboardButton("ℹ️ كيف تعمل تازا", callback_data="howto"),
            ],
            [InlineKeyboardButton("🍽️ انضم كتاجر", callback_data="vendor_info")],
            [InlineKeyboardButton("📋 طلباتي", callback_data="my_orders")],
        ]
    )
    return InlineKeyboardMarkup(rows)


def open_app_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛍️ فتح تطبيق تازا", web_app=WebAppInfo(url=CUSTOMER_WEBAPP_URL)
                )
            ]
        ]
    )


def restaurant_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🍽️ فتح لوحة المطعم", web_app=WebAppInfo(url=RESTAURANT_WEBAPP_URL)
                )
            ]
        ]
    )


def vendor_intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ سجّل اهتمام متجرك", callback_data="vendor_signup")]]
    )


def area_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(AREAS), 2):
        row = [InlineKeyboardButton(AREAS[i], callback_data=f"area_{AREAS[i]}")]
        if i + 1 < len(AREAS):
            row.append(
                InlineKeyboardButton(AREAS[i + 1], callback_data=f"area_{AREAS[i+1]}")
            )
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def bag_type_kb() -> InlineKeyboardMarkup:
    items = list(BAG_TYPES.items())
    rows = []
    for i in range(0, len(items), 2):
        row = [
            InlineKeyboardButton(
                f"{items[i][1]} {items[i][0]}", callback_data=f"bagtype_{items[i][0]}"
            )
        ]
        if i + 1 < len(items):
            row.append(
                InlineKeyboardButton(
                    f"{items[i+1][1]} {items[i+1][0]}",
                    callback_data=f"bagtype_{items[i+1][0]}",
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def restaurant_area_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(AREAS), 2):
        row = [InlineKeyboardButton(AREAS[i], callback_data=f"restarea_{AREAS[i]}")]
        if i + 1 < len(AREAS):
            row.append(
                InlineKeyboardButton(
                    AREAS[i + 1], callback_data=f"restarea_{AREAS[i+1]}"
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def vendor_category_kb() -> InlineKeyboardMarkup:
    rows = []
    for i, category in enumerate(VENDOR_CATEGORIES):
        rows.append([InlineKeyboardButton(category, callback_data=f"vendorcat_{i}")])
    return InlineKeyboardMarkup(rows)


def vendor_area_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(AREAS), 2):
        row = [InlineKeyboardButton(AREAS[i], callback_data=f"vendorarea_{i}")]
        if i + 1 < len(AREAS):
            row.append(InlineKeyboardButton(AREAS[i + 1], callback_data=f"vendorarea_{i+1}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def vendor_interest_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=f"vendorinterest_{idx}")]
            for idx, label in enumerate(VENDOR_INTEREST_LEVELS)
        ]
    )


def vendor_concern_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(VENDOR_CONCERNS), 2):
        row = [InlineKeyboardButton(VENDOR_CONCERNS[i], callback_data=f"vendorconcern_{i}")]
        if i + 1 < len(VENDOR_CONCERNS):
            row.append(
                InlineKeyboardButton(
                    VENDOR_CONCERNS[i + 1], callback_data=f"vendorconcern_{i+1}"
                )
            )
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def vendor_intro_text() -> str:
    return (
        f"🍽️ {b('انضم إلى تازا كتاجر')}\n{LINE}\n\n"
        f"حوّل فائض آخر النهار إلى مبيعات إضافية بدون توصيل وبدون عرض خصم علني على قائمتك.\n\n"
        f"⬣ أنت تختار محتوى كيس المفاجأة.\n"
        f"⬣ أنت تحدد الكمية ووقت الاستلام.\n"
        f"⬣ الزبون يستلم من متجرك مباشرة.\n"
        f"⬣ تازا يساعدك تجيب زبائن جدد وتقلل الهدر."
    )


# ══════════════════════════════════════════════════════
# ROLE HELPERS
# ══════════════════════════════════════════════════════


def get_effective_role(user_id: int) -> str:
    if DEV_MODE and user_id in _dev_role_overrides:
        return _dev_role_overrides[user_id]
    if user_id in ADMIN_IDS:
        return "admin"
    if db.get_restaurant_by_manager(user_id):
        return "restaurant"
    return "customer"


def is_admin(uid: int) -> bool:
    return get_effective_role(uid) == "admin"


def is_restaurant(uid: int) -> bool:
    return get_effective_role(uid) == "restaurant"


def validate_syrian_phone(phone: str) -> bool:
    return bool(re.match(r"^09\d{8}$", phone.strip()))


def normalize_contact_phone(phone: str) -> str:
    cleaned = re.sub(r"[\s().-]", "", phone.strip())
    if cleaned.startswith("00"):
        return f"+{cleaned[2:]}"
    return cleaned


def validate_contact_phone(phone: str) -> bool:
    cleaned = normalize_contact_phone(phone)
    return bool(re.match(r"^(09\d{8}|\+?\d{8,15})$", cleaned))


def valid_time(t: str) -> bool:
    try:
        datetime.strptime(t.strip(), "%H:%M")
        return True
    except ValueError:
        return False


def normalize_order_code(value: str) -> str:
    text = (value or "").strip().upper().replace(" ", "")
    if text.isdigit():
        return f"TAZA-{int(text):05d}"
    if re.match(r"^TAZA-\d{5}$", text):
        return text
    return text


def is_truthy(value) -> bool:
    return str(value).lower() in ("true", "1", "yes")


def order_status_label(status: str) -> str:
    st_emoji, st_text = STATUS_AR.get(status, ("?", "Unknown"))
    return f"{st_emoji} {st_text}"


def get_restaurant_for_manager(user_id: int) -> Optional[dict]:
    return db.get_restaurant_by_manager(user_id)


def is_manager_for_bag(user_id: int, bag_id: int) -> bool:
    return db.manager_owns_bag(user_id, bag_id)


def is_manager_for_order(user_id: int, order_id: int) -> bool:
    return db.manager_owns_order(user_id, order_id)


def pickup_window_is_valid(start: str, end: str) -> bool:
    try:
        start_time = datetime.strptime(start.strip(), "%H:%M")
        end_time = datetime.strptime(end.strip(), "%H:%M")
    except ValueError:
        return False
    return end_time > start_time


def vendor_claim_is_expired(lead: dict, now: Optional[datetime] = None) -> bool:
    try:
        created_at = datetime.fromisoformat(str(lead.get("created_at", "")))
    except (TypeError, ValueError):
        return True
    return (now or datetime.now()) - created_at > VENDOR_CLAIM_MAX_AGE


def parse_vendor_claim_payload(payload: str) -> Optional[tuple[int, str]]:
    match = re.fullmatch(r"vendor_claim_(\d+)_([A-Za-z0-9_-]+)", payload or "")
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def vendor_lead_review_error(lead: dict) -> str:
    if lead.get("status") != "new":
        return "لا يمكن معالجة هذا الطلب قبل ربطه بحساب تيليغرام، أو بعد إغلاقه."
    if not str(lead.get("user_id", "")).lstrip("-").isdigit():
        return "لا يوجد حساب تيليغرام مرتبط بهذا الطلب."
    return ""


def normalize_vendor_lead_payload(payload: dict) -> tuple[dict, list[str]]:
    limits = {
        "shop_name": 100,
        "category": 80,
        "area": 100,
        "pickup_address": 240,
        "contact_name": 100,
        "whatsapp": 30,
        "closing_time": 5,
        "surplus_notes": 500,
    }
    cleaned = {
        key: re.sub(r"\s+", " ", str(payload.get(key, "") or "")).strip()
        for key in limits
    }
    errors = []
    required = (
        "shop_name",
        "category",
        "area",
        "pickup_address",
        "contact_name",
        "whatsapp",
        "closing_time",
    )
    if any(not cleaned[field] for field in required):
        errors.append("يرجى تعبئة جميع الحقول المطلوبة.")
    for field, limit in limits.items():
        if len(cleaned[field]) > limit:
            errors.append(f"الحقل {field} أطول من الحد المسموح.")
    if cleaned["category"] not in VENDOR_CATEGORIES:
        errors.append("نوع النشاط غير صالح.")
    if cleaned["area"] not in AREAS:
        errors.append("المنطقة غير صالحة.")
    cleaned["whatsapp"] = normalize_contact_phone(cleaned["whatsapp"])
    if not validate_contact_phone(cleaned["whatsapp"]):
        errors.append("رقم واتساب غير صالح.")
    if not valid_time(cleaned["closing_time"]):
        errors.append("وقت الإغلاق يجب أن يكون بصيغة HH:MM.")
    return cleaned, errors


def vendor_lead_client_ip(request: web.Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",", 1)[0].strip() or request.remote or "unknown")[:100]


def vendor_lead_rate_allowed(client_ip: str, now: Optional[float] = None) -> bool:
    timestamp = now if now is not None else time.monotonic()
    cutoff = timestamp - VENDOR_LEAD_RATE_WINDOW
    recent = [value for value in _vendor_lead_requests.get(client_ip, []) if value >= cutoff]
    if len(recent) >= VENDOR_LEAD_RATE_LIMIT:
        _vendor_lead_requests[client_ip] = recent
        return False
    recent.append(timestamp)
    _vendor_lead_requests[client_ip] = recent
    return True


# ══════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════


async def notify_admin_group(
    bot: Bot, message: str, reply_markup: Optional[InlineKeyboardMarkup] = None
):
    if ADMIN_GROUP_CHAT_ID:
        try:
            await bot.send_message(
                int(ADMIN_GROUP_CHAT_ID),
                text=message,
                parse_mode=HTML,
                reply_markup=reply_markup,
            )
        except Exception as ex:
            logger.warning("Admin group notify failed: %s", ex)


async def alert_admins(bot: Bot, message: str):
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid,
                text=f"⚠️ {b('خطأ في النظام:')}\n{code(e(message))}",
                parse_mode=HTML,
            )
        except Exception:
            pass


async def send_logo(target, caption: str, kb=None, chat_id: Optional[int] = None):
    """Send logo photo + caption, or fall back to text."""
    global LOGO_FILE_ID
    if LOGO_FILE_ID:
        try:
            if hasattr(target, "reply_photo"):
                await target.reply_photo(
                    photo=LOGO_FILE_ID,
                    caption=caption,
                    parse_mode=HTML,
                    reply_markup=kb,
                )
            elif hasattr(target, "send_photo") and chat_id is not None:
                await target.send_photo(
                    chat_id=chat_id,
                    photo=LOGO_FILE_ID,
                    caption=caption,
                    parse_mode=HTML,
                    reply_markup=kb,
                )
            else:
                raise BadRequest("Invalid target for send_logo")
            return
        except BadRequest as ex:
            logger.warning("Logo send failed (%s), falling back to text", ex)
            LOGO_FILE_ID = ""
    if hasattr(target, "reply_text"):
        await target.reply_text(caption, parse_mode=HTML, reply_markup=kb)
    elif hasattr(target, "send_message") and chat_id is not None:
        await target.send_message(
            chat_id=chat_id, text=caption, parse_mode=HTML, reply_markup=kb
        )


# ══════════════════════════════════════════════════════
# DEV MODE
# ══════════════════════════════════════════════════════


async def devmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not DEV_MODE:
        await update.message.reply_text("🚫 وضع التطوير غير مفعّل.")
        return
    uid = update.effective_user.id
    current = get_effective_role(uid)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👤 زبون", callback_data="devrole_customer"),
                InlineKeyboardButton("🍽️ مطعم", callback_data="devrole_restaurant"),
                InlineKeyboardButton("👑 مدير", callback_data="devrole_admin"),
            ],
            [InlineKeyboardButton("🔄 إعادة تعيين", callback_data="devrole_reset")],
        ]
    )
    await update.message.reply_text(
        f"🛠️ {b('وضع التطوير')}\n{LINE}\n\n"
        f"الدور الحالي: {code(current)}\n\n"
        f"اختر دوراً للاختبار:",
        parse_mode=HTML,
        reply_markup=kb,
    )


async def devrole_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not DEV_MODE:
        await update.callback_query.answer("وضع التطوير غير مفعّل", show_alert=True)
        return
    await update.callback_query.answer()
    uid = update.effective_user.id
    role = update.callback_query.data.replace("devrole_", "")
    if role == "reset":
        _dev_role_overrides.pop(uid, None)
        real = get_effective_role(uid)
        await update.callback_query.message.edit_text(
            f"✅ تم الإعادة للدور الحقيقي: {code(real)}\n\nأرسل /start لتحديث الواجهة.",
            parse_mode=HTML,
        )
    else:
        _dev_role_overrides[uid] = role
        labels = {"customer": "زبون 👤", "restaurant": "مطعم 🍽️", "admin": "مدير 👑"}
        await update.callback_query.message.edit_text(
            f"✅ دورك الآن: {b(labels.get(role, role))}\n\nأرسل /start لتجربة الواجهة الجديدة.",
            parse_mode=HTML,
        )


# ══════════════════════════════════════════════════════
# /setlogo  (admin)
# ══════════════════════════════════════════════════════


async def setlogo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "📸 أرسل صورة شعار تازا وسأحفظ الـ file_id تلقائياً:",
    )
    return SET_LOGO


async def setlogo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LOGO_FILE_ID
    if not update.message.photo:
        await update.message.reply_text("❌ يرجى إرسال صورة.")
        return SET_LOGO
    LOGO_FILE_ID = update.message.photo[-1].file_id
    # Persist in config sheet
    try:
        db.set_config("logo_file_id", LOGO_FILE_ID)
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ تم حفظ الشعار!\n{code(LOGO_FILE_ID)}", parse_mode=HTML
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith("vendor_"):
        return
    uid = update.effective_user.id
    first_name = e(update.effective_user.first_name or "صديقي")

    user = db.get_user(uid)
    if not user:
        db.upsert_user(uid, role="admin" if uid in ADMIN_IDS else "customer")

    role = get_effective_role(uid)
    dev_tag = f"  {code('[DEV]')}" if (DEV_MODE and uid in _dev_role_overrides) else ""

    # ── Admin ──
    if role == "admin":
        txt = (
            f"👑 {b('لوحة إدارة تازا')}{dev_tag}\n{LINE}\n\n"
            f"أهلاً {b(first_name)} 👋\n\n"
            f"⬣ /addrestaurant — إضافة مطعم جديد\n"
            f"⬣ /allorders — ملخص طلبات اليوم\n"
            f"⬣ /vendorleads — طلبات انضمام التجار\n"
            f"⬣ /broadcast — رسالة جماعية\n"
            f"⬣ /initsheets — تهيئة قاعدة البيانات\n"
            f"⬣ /setlogo — رفع شعار تازا\n"
            + (f"\n🛠️ /devmode — تغيير الدور" if DEV_MODE else "")
        )
        await update.message.reply_text(txt, parse_mode=HTML)
        return

    # ── Restaurant ──
    if role == "restaurant":
        rest = db.get_restaurant_by_manager(uid)
        rest_name = e(rest["name"]) if rest else "مطعمك"
        txt = (
            f"👋 {b(f'أهلاً بـ {rest_name}')}{dev_tag}\n{LINE}\n\n"
            f"يسعدنا وجودك في مجتمع الحد من هدر الطعام. 🌱\n\n"
            f"⬣ /newbag — إضافة كيس جديد اليوم\n"
            f"⬣ /mybags — عرض وإدارة أكياسك\n"
            f"⬣ /panel — لوحة المطعم التفاعلية\n"
            + (f"\n🛠️ /devmode — تغيير الدور" if DEV_MODE else "")
        )
        await update.message.reply_text(
            txt, parse_mode=HTML, reply_markup=main_menu_kb(show_rest_panel=True)
        )
        return

    # ── Customer ──
    user_data = db.get_user(uid)
    area = user_data.get("default_area", "") if user_data else ""
    area_line = f"📍 منطقتك: {b(e(area))}" if area else "📍 <i>لم تحدد منطقتك بعد</i>"
    dev_line = f"\n🛠️ /devmode — تغيير الدور للاختبار" if DEV_MODE else ""

    caption = (
        f"أهلاً بك في {b('تازا')}! 🥙\n"
        f"أكياس مفاجآت من مطاعمك المفضلة بسعر أقل — Save the food. Save the mood.\n\n"
        f"{area_line}\n\n"
        f"🛍️ افتح التطبيق لتجربة تصفح أسرع وأسهل.\n"
        f"🍽️ صاحب متجر؟ اكتب /vendor للانضمام كتاجر.{dev_line}"
    )
    await send_logo(update.message, caption, kb=main_menu_kb())


# ══════════════════════════════════════════════════════
# How It Works
# ══════════════════════════════════════════════════════


async def howto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🛍️ فتح تطبيق تازا", web_app=WebAppInfo(url=CUSTOMER_WEBAPP_URL)
                )
            ],
            [InlineKeyboardButton("📍 تحديد المنطقة", callback_data="setlocation")],
            [InlineKeyboardButton("🛍️ تصفح هنا", callback_data="browse")],
        ]
    )
    await update.callback_query.message.reply_text(
        f"💡 {b('كيف تعمل تازا؟')}\n{LINE}\n\n"
        f"1️⃣ اختر منطقتك من داخل البوت.\n"
        f"2️⃣ افتح تطبيق تازا وتصفح الأكياس المتاحة اليوم.\n"
        f"3️⃣ احجز كيساً وادفع عند الاستلام.\n\n"
        f"🕒 أوقات الاستلام محددة من المطعم.\n"
        f"♻️ كل كيس تشتريه يقلل هدر الطعام.",
        parse_mode=HTML,
        reply_markup=kb,
    )


# ══════════════════════════════════════════════════════
# Vendor interest flow
# ══════════════════════════════════════════════════════


async def vendor_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        f"{vendor_intro_text()}\n\n"
        f"التسجيل الأولي يستغرق دقيقة واحدة ويساعدنا نعرف إن كان متجرك مناسباً لإطلاق تازا.",
        parse_mode=HTML,
        reply_markup=vendor_intro_kb(),
    )


async def vendor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source = context.user_data.get("vendor_source", "command:/vendor")
    context.user_data.clear()
    context.user_data["vendor_source"] = source
    await update.message.reply_text(
        f"{vendor_intro_text()}\n\n"
        f"📝 {b('الخطوة 1/10')}\n"
        f"ما اسم المتجر أو المطعم؟",
        parse_mode=HTML,
    )
    return VENDOR_SHOP_NAME


async def vendor_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source_arg = context.args[0] if context.args else "vendor"
    context.user_data["vendor_source"] = f"start:{source_arg}"
    return await vendor_command(update, context)


async def vendor_claim_start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    payload = context.args[0] if context.args else ""
    parsed_claim = parse_vendor_claim_payload(payload)
    if not parsed_claim:
        await update.message.reply_text("رابط ربط الطلب غير صالح.")
        return

    lead_id, claim_token = parsed_claim
    lead = db.get_vendor_lead_by_id(lead_id)
    if not lead:
        await update.message.reply_text("طلب الانضمام غير موجود.")
        return

    current_user_id = str(lead.get("user_id", "") or "")
    if current_user_id and not lead.get("claim_token"):
        if current_user_id == str(update.effective_user.id):
            await update.message.reply_text(
                "✅ تم ربط هذا الطلب بحسابك مسبقاً. سيقوم فريق تازا بمراجعته قريباً."
            )
        else:
            await update.message.reply_text("تم ربط هذا الطلب بحساب تيليغرام آخر.")
        return

    if vendor_claim_is_expired(lead):
        logger.info("Vendor lead claim expired: %s", lead_id)
        await update.message.reply_text(
            "انتهت صلاحية رابط الربط. أرسل طلباً جديداً من موقع تازا."
        )
        return

    result, claimed_lead = db.claim_vendor_lead(
        lead_id,
        claim_token,
        update.effective_user.id,
        update.effective_user.username or "",
    )
    if result == "already_claimed":
        await update.message.reply_text(
            "✅ تم ربط هذا الطلب بحسابك مسبقاً. سيقوم فريق تازا بمراجعته قريباً."
        )
        return
    if result == "claimed_by_other":
        await update.message.reply_text("تم ربط هذا الطلب بحساب تيليغرام آخر.")
        return
    if result != "claimed" or not claimed_lead:
        await update.message.reply_text("رابط ربط الطلب غير صالح أو تم استخدامه.")
        return

    if not db.get_user(update.effective_user.id):
        db.upsert_user(update.effective_user.id, role="customer")
    logger.info(
        "Vendor lead claimed: %s by Telegram user %s",
        lead_id,
        update.effective_user.id,
    )
    await update.message.reply_text(
        f"✅ {b('تم ربط طلب متجرك بحساب تيليغرام')}\n{LINE}\n\n"
        f"المتجر: {b(e(claimed_lead.get('shop_name', '')))}\n"
        f"سيقوم فريق تازا بمراجعة الطلب، وستصلك رسالة هنا عند تفعيله.",
        parse_mode=HTML,
    )
    await notify_vendor_lead(context.bot, claimed_lead)


async def vendor_signup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.clear()
    context.user_data["vendor_source"] = "telegram_cta"
    await update.callback_query.message.reply_text(
        f"📝 {b('تسجيل متجر في تازا')}\n{LINE}\n\n"
        f"الخطوة 1/10 — ما اسم المتجر أو المطعم؟",
        parse_mode=HTML,
    )
    return VENDOR_SHOP_NAME


async def vendor_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shop_name = update.message.text.strip()
    if len(shop_name) < 2:
        await update.message.reply_text("❌ الاسم قصير جداً. اكتب اسم المتجر:")
        return VENDOR_SHOP_NAME
    context.user_data["vendor_shop_name"] = shop_name
    await update.message.reply_text(
        f"🏷️ {b('الخطوة 2/10')}\n"
        f"اختر نوع النشاط الأقرب لمتجرك:",
        parse_mode=HTML,
        reply_markup=vendor_category_kb(),
    )
    return VENDOR_CATEGORY


async def vendor_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try:
        idx = int(update.callback_query.data.replace("vendorcat_", ""))
        category = VENDOR_CATEGORIES[idx]
    except (ValueError, IndexError):
        await update.callback_query.message.reply_text("❌ اختيار غير صالح. جرّب مرة أخرى.")
        return VENDOR_CATEGORY
    context.user_data["vendor_category"] = category
    await update.callback_query.message.reply_text(
        f"📍 {b('الخطوة 3/10')}\n"
        f"اختر منطقة المتجر:",
        parse_mode=HTML,
        reply_markup=vendor_area_kb(),
    )
    return VENDOR_AREA


async def vendor_area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try:
        idx = int(update.callback_query.data.replace("vendorarea_", ""))
        area = AREAS[idx]
    except (ValueError, IndexError):
        await update.callback_query.message.reply_text("❌ اختيار غير صالح. جرّب مرة أخرى.")
        return VENDOR_AREA
    context.user_data["vendor_area"] = area
    await update.callback_query.message.reply_text(
        f"📌 {b('الخطوة 4/10')}\n"
        f"اكتب عنوان الاستلام بالتفصيل:\n"
        f"{i('مثال: المزة، قرب جامع الأكرم، بجانب ...')}",
        parse_mode=HTML,
    )
    return VENDOR_ADDRESS


async def vendor_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    if len(address) < 5:
        await update.message.reply_text("❌ العنوان قصير. اكتب عنواناً أوضح:")
        return VENDOR_ADDRESS
    context.user_data["vendor_address"] = address
    await update.message.reply_text(
        f"👤 {b('الخطوة 5/10')}\n"
        f"ما اسم الشخص المسؤول الذي سنتواصل معه؟",
        parse_mode=HTML,
    )
    return VENDOR_CONTACT_NAME


async def vendor_contact_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_name = update.message.text.strip()
    if len(contact_name) < 2:
        await update.message.reply_text("❌ الاسم قصير. اكتب اسم المسؤول:")
        return VENDOR_CONTACT_NAME
    context.user_data["vendor_contact_name"] = contact_name
    await update.message.reply_text(
        f"📱 {b('الخطوة 6/10')}\n"
        f"رقم واتساب أو هاتف المتجر:\n"
        f"{i('مثال: 0933123456 أو +963933123456')}",
        parse_mode=HTML,
    )
    return VENDOR_PHONE


async def vendor_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = normalize_contact_phone(update.message.text)
    if not validate_contact_phone(phone):
        await update.message.reply_text(
            f"❌ الرقم غير واضح. استخدم صيغة مثل {code('09xxxxxxxx')} أو {code('+9639xxxxxxxx')}",
            parse_mode=HTML,
        )
        return VENDOR_PHONE
    context.user_data["vendor_phone"] = phone
    await update.message.reply_text(
        f"⏰ {b('الخطوة 7/10')}\n"
        f"ما وقت الإغلاق أو الوقت المعتاد لظهور الفائض؟\n"
        f"{i('مثال: 22:00')}",
        parse_mode=HTML,
    )
    return VENDOR_CLOSING_TIME


async def vendor_closing_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    closing_time = update.message.text.strip()
    if not valid_time(closing_time):
        await update.message.reply_text(
            f"❌ اكتب الوقت بصيغة {code('HH:MM')} مثل {code('22:00')}",
            parse_mode=HTML,
        )
        return VENDOR_CLOSING_TIME
    context.user_data["vendor_closing_time"] = closing_time
    await update.message.reply_text(
        f"🥐 {b('الخطوة 8/10')}\n"
        f"ما نوع الفائض الذي يظهر غالباً آخر اليوم؟\n"
        f"{i('مثال: مخبوزات، سندويشات، حلويات، عصائر... أو اكتب تخطي')}",
        parse_mode=HTML,
    )
    return VENDOR_SURPLUS


async def vendor_surplus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["vendor_surplus"] = "" if text in ("/skip", "تخطي") else text
    await update.message.reply_text(
        f"🤝 {b('الخطوة 9/10')}\n"
        f"ما مستوى اهتمامك بتجربة تازا؟",
        parse_mode=HTML,
        reply_markup=vendor_interest_kb(),
    )
    return VENDOR_INTEREST


async def vendor_interest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try:
        idx = int(update.callback_query.data.replace("vendorinterest_", ""))
        interest = VENDOR_INTEREST_LEVELS[idx]
    except (ValueError, IndexError):
        await update.callback_query.message.reply_text("❌ اختيار غير صالح. جرّب مرة أخرى.")
        return VENDOR_INTEREST
    context.user_data["vendor_interest"] = interest
    await update.callback_query.message.reply_text(
        f"💬 {b('الخطوة 10/10')}\n"
        f"ما أكبر سؤال أو قلق عندك؟",
        parse_mode=HTML,
        reply_markup=vendor_concern_kb(),
    )
    return VENDOR_CONCERN


async def vendor_concern_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try:
        idx = int(update.callback_query.data.replace("vendorconcern_", ""))
        concern = VENDOR_CONCERNS[idx]
    except (ValueError, IndexError):
        await update.callback_query.message.reply_text("❌ اختيار غير صالح. جرّب مرة أخرى.")
        return VENDOR_CONCERN

    uid = update.effective_user.id
    username = update.effective_user.username or ""
    lead = db.add_vendor_lead(
        user_id=uid,
        username=username,
        shop_name=context.user_data.get("vendor_shop_name", ""),
        category=context.user_data.get("vendor_category", ""),
        area=context.user_data.get("vendor_area", ""),
        pickup_address=context.user_data.get("vendor_address", ""),
        contact_name=context.user_data.get("vendor_contact_name", ""),
        whatsapp=context.user_data.get("vendor_phone", ""),
        closing_time=context.user_data.get("vendor_closing_time", ""),
        surplus_notes=context.user_data.get("vendor_surplus", ""),
        interest_level=context.user_data.get("vendor_interest", ""),
        main_concern=concern,
        source=context.user_data.get("vendor_source", "telegram_bot"),
    )

    await update.callback_query.message.reply_text(
        f"✅ {b('تم تسجيل اهتمامك بنجاح')}\n{LINE}\n\n"
        f"شكراً لك. فريق تازا سيتواصل معك لتأكيد التفاصيل وتجربة أول أكياس مفاجآت.\n\n"
        f"ملخص الطلب:\n"
        f"المتجر: {b(e(lead['shop_name']))}\n"
        f"النوع: {e(lead['category'])}\n"
        f"المنطقة: {e(lead['area'])}\n"
        f"وقت الإغلاق: {code(e(lead['closing_time']))}\n\n"
        f"تازا: {i('Save the food. Save the mood.')}",
        parse_mode=HTML,
    )
    await notify_vendor_lead(context.bot, lead)
    context.user_data.clear()
    return ConversationHandler.END


async def notify_vendor_lead(bot: Bot, lead: dict):
    username = f"@{lead['username']}" if lead.get("username") else "—"
    status = lead.get("status", "new")
    actions = None
    if status == "new" and str(lead.get("user_id", "")).lstrip("-").isdigit():
        actions = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ موافقة",
                        callback_data=f"lead_approve_{lead['lead_id']}",
                    ),
                    InlineKeyboardButton(
                        "❌ رفض",
                        callback_data=f"lead_reject_{lead['lead_id']}",
                    ),
                ]
            ]
        )
    message = (
        f"🍽️ {b('طلب انضمام تاجر جديد')}\n{LINE}\n\n"
        f"#{lead['lead_id']} | user_id: {code(lead.get('user_id') or 'بانتظار الربط')} | {e(username)}\n"
        f"المتجر: {b(e(lead['shop_name']))}\n"
        f"النوع: {e(lead['category'])}\n"
        f"المنطقة: {e(lead['area'])}\n"
        f"العنوان: {e(lead['pickup_address'])}\n"
        f"المسؤول: {e(lead['contact_name'])}\n"
        f"واتساب: {code(e(lead['whatsapp']))}\n"
        f"وقت الإغلاق: {code(e(lead['closing_time']))}\n"
        f"الفائض: {e(lead.get('surplus_notes') or '—')}\n"
        f"الاهتمام: {e(lead.get('interest_level') or '—')}\n"
        f"القلق الأساسي: {e(lead.get('main_concern') or '—')}\n"
        f"الحالة: {code(status)}\n"
        f"المصدر: {code(e(lead.get('source', 'telegram_bot')))}"
    )
    if ADMIN_GROUP_CHAT_ID:
        await notify_admin_group(bot, message, reply_markup=actions)
        return
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid, text=message, parse_mode=HTML, reply_markup=actions
            )
        except Exception:
            pass


async def vendorleads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    leads = db.get_vendor_leads()
    if not leads:
        await update.message.reply_text("📭 لا توجد طلبات انضمام تجار بعد.")
        return

    latest = list(reversed(leads[-10:]))
    new_count = len([lead for lead in leads if lead.get("status") == "new"])
    pending_count = len(
        [lead for lead in leads if lead.get("status") == "pending_telegram"]
    )
    await update.message.reply_text(
        f"🍽️ {b('طلبات انضمام التجار')}\n{LINE}\n\n"
        f"الإجمالي: {b(str(len(leads)))}\n"
        f"جاهزة للمراجعة: {b(str(new_count))}\n"
        f"بانتظار ربط تيليغرام: {b(str(pending_count))}",
        parse_mode=HTML,
    )

    for lead in latest:
        status = lead.get("status", "new")
        rows = []
        if status == "new":
            lead_id = lead.get("lead_id", "")
            rows.append(
                [
                    InlineKeyboardButton(
                        "✅ موافقة", callback_data=f"lead_approve_{lead_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ رفض", callback_data=f"lead_reject_{lead_id}"
                    ),
                ]
            )
        await update.message.reply_text(
            f"{code(lead.get('lead_id', ''))} — {b(e(lead.get('shop_name', '')))}\n"
            f"{e(lead.get('category', ''))} | {e(lead.get('area', ''))} | {code(e(lead.get('whatsapp', '')))}\n"
            f"المسؤول: {e(lead.get('contact_name', ''))}\n"
            f"العنوان: {e(lead.get('pickup_address', ''))}\n"
            f"الحالة: {code(status)}",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )


async def vendor_lead_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        await query.message.reply_text("غير مصرح.")
        return

    _, action, lead_id_raw = query.data.split("_")
    if not lead_id_raw.isdigit():
        await query.message.reply_text("طلب غير صالح.")
        return

    lead_id = int(lead_id_raw)
    lead = db.get_vendor_lead_by_id(lead_id)
    if not lead:
        await query.message.reply_text("طلب الانضمام غير موجود.")
        return

    status = lead.get("status", "new")
    if status == action.replace("approve", "approved").replace("reject", "rejected"):
        await query.message.reply_text("تم تنفيذ هذا الإجراء مسبقاً.")
        return
    review_error = vendor_lead_review_error(lead)
    if review_error:
        await query.message.reply_text(review_error)
        return

    if action == "reject":
        db.update_vendor_lead_status(lead_id, "rejected")
        logger.info("Vendor lead rejected: %s", lead_id)
        try:
            await context.bot.send_message(
                int(lead["user_id"]),
                "شكراً لاهتمامك بتازا. تمت مراجعة طلبك، ولن يتم تفعيله في مرحلة التجربة الحالية.",
            )
        except Exception:
            pass
        await query.message.reply_text(
            f"تم رفض الطلب {code(lead_id)}.", parse_mode=HTML
        )
        return

    if action != "approve":
        await query.message.reply_text("إجراء غير معروف.")
        return

    manager_id = int(lead["user_id"])
    existing = db.get_restaurant_by_manager(manager_id)
    if existing:
        rest = existing
    else:
        rest = db.add_restaurant(
            name=lead.get("shop_name", ""),
            area=lead.get("area", ""),
            pickup_address=lead.get("pickup_address", ""),
            manager_chat_id=manager_id,
        )
    db.upsert_user(manager_id, role="restaurant")

    db.update_vendor_lead_status(lead_id, "approved")
    logger.info("Vendor lead approved: %s -> restaurant %s", lead_id, rest.get("restaurant_id"))
    welcome_caption = (
        f"✅ {b('أهلاً بك في تازا')}\n{LINE}\n\n"
        f"تم تفعيل {b(e(rest['name']))} ضمن التجربة.\n\n"
        f"استخدم /panel للوحة العمل اليومية.\n"
        f"استخدم /newbag لنشر أكياس اليوم.\n"
        f"استخدم /mybags لتعديل الأكياس أو إيقافها."
    )
    try:
        await send_logo(context.bot, welcome_caption, chat_id=manager_id)
    except Exception as ex:
        logger.warning("Approved restaurant welcome failed: %s", ex)

    await query.message.reply_text(
        f"تمت الموافقة على الطلب {code(lead_id)} وتفعيل المطعم {code(rest['restaurant_id'])}.",
        parse_mode=HTML,
    )


# Location
# ══════════════════════════════════════════════════════


async def setlocation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📍 اختر منطقتك لنظهر الأكياس القريبة:", parse_mode=HTML, reply_markup=area_kb()
    )


async def setlocation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data

    if data == "setlocation":
        await update.callback_query.message.reply_text(
            "📍 اختر منطقتك:", parse_mode=HTML, reply_markup=area_kb()
        )
        return

    area = data.replace("area_", "")
    db.set_user_area(update.effective_user.id, area)
    await update.callback_query.message.reply_text(
        f"✅ تم حفظ منطقتك: {b(e(area))}\n\n"
        f"افتح التطبيق لتصفح الأكياس بسرعة، أو اكتب /menu للتصفح هنا.",
        parse_mode=HTML,
        reply_markup=open_app_kb(),
    )


# ══════════════════════════════════════════════════════
# Restaurant Mini App
# ══════════════════════════════════════════════════════


async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rest = get_restaurant_for_manager(uid)
    if not rest:
        await update.message.reply_text("هذه اللوحة متاحة للمطاعم المفعّلة فقط.")
        return
    bags = db.get_bags_for_restaurant(rest["restaurant_id"])
    orders = db.get_orders_for_restaurant_today(rest["restaurant_id"])
    total_qty = sum(int(bag.get("quantity", 0) or 0) for bag in bags)
    remaining = sum(int(bag.get("remaining", 0) or 0) for bag in bags)
    sold = max(total_qty - remaining, 0)
    reserved = len([order for order in orders if order.get("status") == "reserved"])
    picked_up = len([order for order in orders if order.get("status") == "picked_up"])
    cancelled = len([order for order in orders if order.get("status") == "cancelled"])
    revenue = sum(
        int((db.get_bag_by_id(order["bag_id"]) or {}).get("discounted_price", 0) or 0)
        for order in orders
        if order.get("status") in ("reserved", "picked_up")
    )
    rest_name = e(rest["name"])
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("طلبات اليوم", callback_data="rest_orders"),
                InlineKeyboardButton("أكياس اليوم", callback_data="rest_bags"),
            ],
            [
                InlineKeyboardButton(
                    "فتح لوحة المطعم",
                    web_app=WebAppInfo(url=RESTAURANT_WEBAPP_URL),
                )
            ],
        ]
    )
    await update.message.reply_text(
        f"🍽️ {b(f'لوحة {rest_name}')}\n{LINE}\n\n"
        f"عروض الأكياس اليوم: {b(str(len(bags)))}\n"
        f"الكمية: {total_qty} | المباع: {sold} | المتبقي: {remaining}\n"
        f"الطلبات: محجوز {reserved}، مستلم {picked_up}، ملغي {cancelled}\n"
        f"الإيراد المتوقع: {b(f'{revenue:,} ل.س')}\n\n"
        f"/newbag لنشر كيس جديد\n"
        f"/mybags لإدارة الأكياس\n"
        f"/restorders للتحقق من رموز الاستلام",
        parse_mode=HTML,
        reply_markup=kb,
    )


# Menu / Browse
# ══════════════════════════════════════════════════════


def _bag_card_html(bag: dict, rest: dict, index: int = None) -> str:
    emoji = BAG_TYPES.get(bag["type"], "📦")
    orig = int(bag["original_price"])
    disc = int(bag["discounted_price"])
    pct = round((1 - disc / orig) * 100) if orig else 0
    remaining = int(bag.get("remaining", 0))
    hint_line = f"\n{e(bag['hint'])}\n" if bag.get("hint") else "\n"
    num = f"{index}. " if index else ""

    return (
        f"{num}{b(e(rest['name']))} {emoji}\n"
        f"{LINE}\n"
        f"{hint_line}"
        f"💰 السعر الأصلي: {s(f'{orig:,} ل.س')}\n"
        f"💸 سعر تازا: {b(f'{disc:,} ل.س')}  {i(f'(وفّر {pct}%)')}\n"
        f"🕒 الاستلام: {bag['pickup_start']} – {bag['pickup_end']}\n"
        f"🟢 الكمية المتبقية: {b(str(remaining))}\n"
        f"📍 {e(rest.get('pickup_address', '—'))}"
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = db.get_user(uid)
    area = user.get("default_area") if user else None

    msg_target = update.message or update.callback_query.message
    if update.callback_query:
        await update.callback_query.answer()

    if not area:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📍 تحديد المنطقة", callback_data="setlocation")]]
        )
        await msg_target.reply_text(
            "📍 حدد منطقتك أولاً لنعرض أقرب الأكياس إليك:",
            parse_mode=HTML,
            reply_markup=kb,
        )
        return

    if not context.user_data.get("webapp_tip_shown"):
        await msg_target.reply_text(
            f"✨ {b('تجربة أسرع')}\n"
            f"افتح تطبيق تازا المصغّر لتصفح الأكياس بسهولة:",
            parse_mode=HTML,
            reply_markup=open_app_kb(),
        )
        context.user_data["webapp_tip_shown"] = True

    bags = db.get_available_bags(area=area)

    if not bags:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📍 تغيير المنطقة", callback_data="setlocation")]]
        )
        await msg_target.reply_text(
            f"😔 لا توجد أكياس متاحة حالياً في {b(e(area))}.\n"
            f"تحقق بعد الساعة 6 مساءً!",
            parse_mode=HTML,
            reply_markup=kb,
        )
        return

    await msg_target.reply_text(
        f"🛍️ {b(f'الأكياس المتاحة في {e(area)}')}\n{LINE}\n\n"
        f"وجدنا {b(str(len(bags)))} {'كيس' if len(bags) == 1 else 'أكياس'} شهية اليوم! 🎉",
        parse_mode=HTML,
    )

    for i_idx, bag in enumerate(bags, 1):
        rest = db.get_restaurant_by_id(bag["restaurant_id"])
        if not rest:
            continue
        text = _bag_card_html(bag, rest, index=i_idx)
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "احجز 🛒", callback_data=f"reserve_{bag['bag_id']}"
                    )
                ]
            ]
        )
        photo = bag.get("photo_file_id", "")
        if photo:
            try:
                await msg_target.reply_photo(
                    photo=photo, caption=text, parse_mode=HTML, reply_markup=kb
                )
                continue
            except BadRequest as ex:
                logger.warning("Bag photo failed: %s", ex)
        await msg_target.reply_text(text, parse_mode=HTML, reply_markup=kb)


async def browse_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await menu_command(update, context)


async def my_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await orders_command(update, context, from_callback=True)


# ══════════════════════════════════════════════════════
# Reservation flow
# ══════════════════════════════════════════════════════


def build_order_receipt(order: dict, bag: dict, rest: dict) -> tuple[str, InlineKeyboardMarkup]:
    rest_addr = e(rest.get("pickup_address", "—")) if rest else "—"
    pickup_start = bag.get("pickup_start", "—") if bag else "—"
    pickup_end = bag.get("pickup_end", "—") if bag else "—"
    disc = int(bag.get("discounted_price", 0)) if bag else 0
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📋 طلباتي", callback_data="my_orders")]]
    )
    text = (
        f"🎉 {b('تم الحجز بنجاح!')}\n{LINE}\n\n"
        f"📦 رمز الطلب: {code(order['order_code'])}\n"
        f"💵 المبلغ: {b(f'{disc:,} ل.س')} (نقداً عند الاستلام)\n"
        f"📍 العنوان: {rest_addr}\n"
        f"🕒 وقت الاستلام: {pickup_start} – {pickup_end}\n\n"
        f"⚠️ أظهر هذا الرمز للمطعم عند الاستلام."
    )
    return text, kb


async def notify_reservation(bot: Bot, order: dict, bag: dict, rest: dict, user: dict):
    if not bag:
        return
    if rest and rest.get("manager_chat_id"):
        remaining = int(bag.get("remaining", 0)) if bag else 0
        emoji = BAG_TYPES.get(bag["type"], "📦") if bag else "📦"
        rest_kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ تم الاستلام",
                        callback_data=f"pickup_{order['order_id']}_{bag['bag_id']}",
                    ),
                    InlineKeyboardButton(
                        "❌ إلغاء الطلب",
                        callback_data=(
                            f"restcancel_{order['order_id']}_{bag['bag_id']}_"
                            f"{order['user_id']}"
                        ),
                    ),
                ]
            ]
        )
        try:
            await bot.send_message(
                chat_id=int(rest["manager_chat_id"]),
                text=(
                    f"🔔 {b('طلب جديد!')}\n{LINE}\n\n"
                    f"📦 الرمز: {code(order['order_code'])}\n"
                    f"🛒 النوع: {emoji} {e(bag['type'])}\n"
                    f"👤 الزبون: {b(e(user.get('name','—')))} ({e(user.get('phone','—'))})\n"
                    f"🕒 الاستلام: {bag['pickup_start']} – {bag['pickup_end']}\n"
                    f"🟢 المتبقي: {b(str(remaining))}"
                ),
                parse_mode=HTML,
                reply_markup=rest_kb,
            )
        except Exception as ex:
            logger.warning("Restaurant notify failed: %s", ex)

    emoji = BAG_TYPES.get(bag["type"], "📦") if bag else "📦"
    disc = int(bag["discounted_price"]) if bag else 0
    rest_name = e(rest["name"]) if rest else "المطعم"
    await notify_admin_group(
        bot,
        f"📋 {b('طلب جديد')} — {rest_name}\n"
        f"{code(order['order_code'])} | {e(user.get('name',''))} | {e(user.get('phone',''))}\n"
        f"{emoji} {e(bag['type'])} | {disc:,} ل.س | {bag['pickup_start']}–{bag['pickup_end']}",
    )


async def reserve_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bag_id = int(query.data.replace("reserve_", ""))
    context.user_data["pending_bag_id"] = bag_id
    uid = update.effective_user.id
    user = db.get_user(uid)

    if user and user.get("name") and user.get("phone"):
        return await _show_summary(update, context, user)

    await query.message.reply_text(
        f"📝 {b('إكمال ملفك الشخصي')}\n{LINE}\n\n"
        f"نحتاج اسمك ورقمك مرة واحدة فقط.\n\n"
        f"📝 الرجاء إدخال اسمك الكامل:",
        parse_mode=HTML,
    )
    return CUST_NAME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("❌ الاسم قصير جداً. أعد المحاولة:")
        return CUST_NAME
    context.user_data["new_name"] = name
    await update.message.reply_text(
        f"👍 مرحباً {b(e(name))}!\n\n"
        f"📱 رقم هاتفك (يبدأ بـ 09):\n"
        f"{i('مثال: 0933123456')}",
        parse_mode=HTML,
    )
    return CUST_PHONE


async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not validate_syrian_phone(phone):
        await update.message.reply_text(
            f"❌ رقم غير صحيح. استخدم صيغة {code('09xxxxxxxx')}",
            parse_mode=HTML,
        )
        return CUST_PHONE
    db.upsert_user(
        update.effective_user.id,
        name=context.user_data["new_name"],
        phone=phone,
        role="customer",
    )
    user = db.get_user(update.effective_user.id)
    return await _show_summary(update, context, user)


async def _show_summary(update, context, user):
    bag_id = context.user_data["pending_bag_id"]
    bag = db.get_bag_by_id(bag_id)

    if not bag or int(bag.get("remaining", 0)) <= 0:
        target = update.message or update.callback_query.message
        await target.reply_text(
            "😔 عذراً، نفذت الكمية. جرب كيساً آخر عبر /menu",
            parse_mode=HTML,
        )
        return ConversationHandler.END

    rest = db.get_restaurant_by_id(bag["restaurant_id"])
    rest_name = e(rest["name"]) if rest else "المطعم"
    rest_addr = e(rest.get("pickup_address", "—")) if rest else "—"
    disc = int(bag["discounted_price"])
    bag_type = e(bag["type"])

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تأكيد", callback_data="confirm_reserve"),
                InlineKeyboardButton("❌ إلغاء", callback_data="cancel_reserve"),
            ]
        ]
    )
    target = update.message or update.callback_query.message
    await target.reply_text(
        f"🛒 {b('تأكيد الحجز')}\n{LINE}\n\n"
        f"المطعم: {b(rest_name)}\n"
        f"النوع: {bag_type}\n"
        f"السعر: {b(f'{disc:,} ل.س')}\n"
        f"وقت الاستلام: {bag['pickup_start']} – {bag['pickup_end']}\n\n"
        f"الاسم: {e(user.get('name','—'))} | الهاتف: {e(user.get('phone','—'))}",
        parse_mode=HTML,
        reply_markup=kb,
    )
    return RES_CONFIRM


async def confirm_reserve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    bag_id = context.user_data.get("pending_bag_id")

    if not bag_id:
        await query.message.reply_text("حدث خطأ. ابدأ من /menu")
        return ConversationHandler.END

    user = db.get_user(uid)
    await query.message.reply_text("⏳ جاري تأكيد حجزك...")

    success, order, msg_ar = await db.atomic_reserve(
        bag_id, uid, user.get("name", ""), user.get("phone", "")
    )

    if not success:
        await query.message.reply_text(
            f"😔 {b(e(msg_ar))}\n\nجرب كيساً آخر عبر /menu", parse_mode=HTML
        )
        return ConversationHandler.END

    bag = db.get_bag_by_id(bag_id)
    rest = db.get_restaurant_by_id(bag["restaurant_id"]) if bag else None

    receipt_text, receipt_kb = build_order_receipt(order, bag, rest)
    await context.bot.send_message(
        chat_id=uid,
        text=receipt_text,
        parse_mode=HTML,
        reply_markup=receipt_kb,
    )

    await notify_reservation(context.bot, order, bag, rest, user)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_reserve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "تم الإلغاء 👌\n\nيمكنك العودة للتصفح عبر /menu"
    )
    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
# WebApp data handler
# ══════════════════════════════════════════════════════


async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_raw = update.message.web_app_data.data if update.message else ""
    try:
        payload = json.loads(data_raw)
    except json.JSONDecodeError:
        await update.message.reply_text("❌ بيانات غير صالحة من التطبيق المصغّر.")
        return

    if payload.get("action") != "reserve":
        await update.message.reply_text("ℹ️ تم استلام بيانات من التطبيق المصغّر.")
        return

    order_code = payload.get("order_code", "")
    if not order_code:
        await update.message.reply_text("❌ تعذر العثور على رمز الطلب.")
        return

    order = db.get_order_by_code(order_code)
    if not order or str(order.get("user_id")) != str(update.effective_user.id):
        await update.message.reply_text("❌ لم نعثر على الطلب. جرّب مجدداً.")
        return

    bag = db.get_bag_by_id(order["bag_id"])
    rest = db.get_restaurant_by_id(order["restaurant_id"]) if bag else None
    user = db.get_user(order["user_id"]) or {}

    receipt_text, receipt_kb = build_order_receipt(order, bag, rest)
    await context.bot.send_message(
        chat_id=order["user_id"],
        text=receipt_text,
        parse_mode=HTML,
        reply_markup=receipt_kb,
    )

    await notify_reservation(context.bot, order, bag, rest, user)


# ══════════════════════════════════════════════════════
# /orders
# ══════════════════════════════════════════════════════


async def orders_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False
):
    uid = update.effective_user.id
    orders = db.get_user_orders(uid)
    msg_target = update.callback_query.message if from_callback else update.message

    if not orders:
        await msg_target.reply_text(
            f"📭 لا توجد طلبات حالية.\n\nابدأ بتصفح الأكياس عبر /menu 🛍️",
            parse_mode=HTML,
        )
        return

    upcoming = [o for o in orders if o.get("status") == "reserved"]
    past = [o for o in orders if o.get("status") != "reserved"]

    if upcoming:
        await msg_target.reply_text(f"⏳ {b('طلباتك الحالية')}", parse_mode=HTML)
        for o in upcoming:
            bag = db.get_bag_by_id(o["bag_id"])
            rest = db.get_restaurant_by_id(o["restaurant_id"])
            rest_name = e(rest["name"]) if rest else "—"
            st_emoji, st_text = STATUS_AR.get(o.get("status", ""), ("❓", "غير معروف"))

            text = (
                f"📦 {code(o['order_code'])} – {b(rest_name)}\n"
                f"الحالة: {st_emoji} {st_text}\n"
                f"🕒 {bag['pickup_start']} – {bag['pickup_end']}"
                if bag
                else f"📦 {code(o['order_code'])} – {b(rest_name)}\nالحالة: {st_emoji} {st_text}"
            )

            buttons = []
            if bag:
                try:
                    pickup_start = datetime.strptime(
                        f"{datetime.now().date()} {bag['pickup_start']}",
                        "%Y-%m-%d %H:%M",
                    )
                    if pickup_start - datetime.now() > timedelta(hours=1):
                        buttons.append(
                            [
                                InlineKeyboardButton(
                                    "❌ إلغاء الحجز",
                                    callback_data=f"custcancel_{o['order_id']}_{bag['bag_id']}",
                                )
                            ]
                        )
                except ValueError:
                    pass

            await msg_target.reply_text(
                text,
                parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            )

    if past:
        await msg_target.reply_text(f"🕐 {b('السجل السابق')}", parse_mode=HTML)
        for o in reversed(past[-5:]):
            bag = db.get_bag_by_id(o["bag_id"])
            rest = db.get_restaurant_by_id(o["restaurant_id"])
            rest_name = e(rest["name"]) if rest else "—"
            st_emoji, st_text = STATUS_AR.get(o.get("status", ""), ("❓", "غير معروف"))
            bag_type = e(bag["type"]) if bag else "—"
            await msg_target.reply_text(
                f"📦 {code(o['order_code'])} – {b(rest_name)}\n"
                f"الحالة: {st_emoji} {st_text}\n"
                f"🛒 {bag_type}  |  {o.get('created_at','')[:10]}",
                parse_mode=HTML,
            )


async def customer_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, order_id, bag_id = update.callback_query.data.split("_")
    order = db.get_order_by_id(int(order_id))
    if not order or str(order.get("user_id")) != str(update.effective_user.id):
        await update.callback_query.message.reply_text("هذا الطلب لا يتبع لك.")
        return
    if order.get("status") == "picked_up":
        await update.callback_query.message.reply_text(
            "لا يمكن إلغاء طلب تم استلامه."
        )
        return
    success = await db.cancel_reservation(int(order_id), int(bag_id))
    if success:
        await update.callback_query.message.reply_text(
            "✅ تم إلغاء طلبك بنجاح. تم استعادة الكمية للكيس.", parse_mode=HTML
        )
    else:
        await update.callback_query.message.reply_text("❌ تعذّر الإلغاء. حاول مجدداً.")


# ══════════════════════════════════════════════════════
# Restaurant callbacks (cancel)
# ══════════════════════════════════════════════════════


async def rest_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    order_id = int(parts[1])
    bag_id = int(parts[2])
    customer_id = int(parts[3])
    if not is_manager_for_order(update.effective_user.id, order_id):
        await update.callback_query.message.reply_text("هذا الطلب لا يتبع لمطعمك.")
        return
    success = await db.cancel_reservation(order_id, bag_id)
    if success:
        order = db.get_order_by_id(order_id)
        code_str = order["order_code"] if order else ""
        await update.callback_query.message.reply_text(
            "✅ تم إلغاء الطلب وإعادة الكمية للكيس."
        )
        try:
            await context.bot.send_message(
                chat_id=customer_id,
                text=(
                    f"⚠️ {b('تنبيه من تازا')}\n\n"
                    f"تم إلغاء طلبك {code(code_str)} من قبل المطعم.\n\n"
                    f"يمكنك حجز كيس آخر عبر /menu 🛍️"
                ),
                parse_mode=HTML,
            )
        except Exception:
            pass
    else:
        await update.callback_query.message.reply_text("❌ تعذّر الإلغاء.")


# ══════════════════════════════════════════════════════
# Rating
# ══════════════════════════════════════════════════════


async def rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    sentiment = update.callback_query.data.split("_")[1]
    if sentiment == "good":
        await update.callback_query.message.reply_text(
            "🌟 شكراً على تقييمك الرائع!\n\nنتطلع لخدمتك مجدداً في تازا 💚"
        )
    else:
        await update.callback_query.message.reply_text(
            "🙏 نأسف لتجربتك.\n\nملاحظتك مهمة جداً لنا وسنعمل على التحسين."
        )


# ══════════════════════════════════════════════════════
# NEW BAG Wizard
# ══════════════════════════════════════════════════════


async def newbag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rest = db.get_restaurant_by_manager(uid)

    if not rest and DEV_MODE and get_effective_role(uid) == "restaurant":
        rest = {
            "restaurant_id": 0,
            "name": "مطعم تجريبي [DEV]",
            "area": AREAS[0],
            "pickup_address": "شارع الاختبار، دمشق",
            "manager_chat_id": uid,
        }

    if not rest:
        await update.message.reply_text(
            "❌ غير مسجّل كمطعم. تواصل مع إدارة تازا للتسجيل.", parse_mode=HTML
        )
        return ConversationHandler.END

    context.user_data["restaurant"] = rest
    await update.message.reply_text(
        f"🛍️ {b('إضافة كيس جديد')}\n{LINE}\n\n"
        f"المطعم: {b(e(rest['name']))}\n\n"
        f"اختر نوع الكيس:",
        parse_mode=HTML,
        reply_markup=bag_type_kb(),
    )
    return BAG_TYPE


async def bag_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    bag_type = update.callback_query.data.replace("bagtype_", "")
    context.user_data["bag_type"] = bag_type
    emoji = BAG_TYPES.get(bag_type, "📦")
    await update.callback_query.message.reply_text(
        f"{emoji} {b(bag_type)}\n\n"
        f"تلميح عن المحتويات (اختياري):\n"
        f"{i('اكتب تلميحاً أو أرسل تخطي')}\n\n"
        f"{i('مثال: كنافة ومعمول وبسبوسة')}",
        parse_mode=HTML,
    )
    return BAG_HINT


async def bag_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["bag_hint"] = "" if text in ("/skip", "تخطي") else text
    await update.message.reply_text(
        f"💰 السعر الأصلي للكيس (ل.س):\n{i('مثال: 15000')}", parse_mode=HTML
    )
    return BAG_ORIG


async def bag_orig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً أكبر من صفر:")
        return BAG_ORIG
    context.user_data["bag_orig"] = int(text)
    await update.message.reply_text(
        f"💸 سعر البيع على تازا (ل.س):\n" f"السعر الأصلي: {b(f'{int(text):,} ل.س')}",
        parse_mode=HTML,
    )
    return BAG_DISC


async def bag_disc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً أكبر من صفر:")
        return BAG_DISC
    disc = int(text)
    orig = context.user_data.get("bag_orig", disc + 1)
    if disc >= orig:
        await update.message.reply_text(
            f"❌ السعر المخفّض ({disc:,}) يجب أن يكون أقل من الأصلي ({orig:,}):"
        )
        return BAG_DISC
    pct = round((1 - disc / orig) * 100)
    context.user_data["bag_disc"] = disc
    await update.message.reply_text(
        f"📦 عدد الأكياس المتاحة:\n{i(f'الخصم: {pct}% 🎉')}", parse_mode=HTML
    )
    return BAG_QTY


async def bag_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ أدخل عدداً صحيحاً أكبر من صفر:")
        return BAG_QTY
    context.user_data["bag_qty"] = int(text)
    await update.message.reply_text(
        f"⏰ وقت بدء الاستلام (HH:MM):\n{i('مثال: 20:00')}", parse_mode=HTML
    )
    return BAG_START


async def bag_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if not valid_time(t):
        await update.message.reply_text(
            f"❌ صيغة خاطئة. مثال: {code('20:00')}", parse_mode=HTML
        )
        return BAG_START
    context.user_data["bag_start"] = t
    await update.message.reply_text(
        f"⏰ وقت انتهاء الاستلام (HH:MM):\n{i(f'يبدأ الاستلام: {t}')}",
        parse_mode=HTML,
    )
    return BAG_END


async def bag_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if not valid_time(t):
        await update.message.reply_text(
            f"❌ صيغة الوقت غير صحيحة. مثال: {code('21:00')}",
            parse_mode=HTML,
        )
        return BAG_END
    start = context.user_data.get("bag_start", "")
    if not pickup_window_is_valid(start, t):
        await update.message.reply_text("يجب أن يكون وقت انتهاء الاستلام بعد وقت بدايته.")
        return BAG_END
    context.user_data["bag_end"] = t
    await update.message.reply_text(
        f"📸 أرسل صورة اختيارية للكيس أو المطعم، أو اكتب {i('تخطي')}.",
        parse_mode=HTML,
    )
    return BAG_PHOTO


async def bag_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo_file_id"] = update.message.photo[-1].file_id if update.message.photo else ""
    return await _preview_bag(update, context)


async def bag_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo_file_id"] = ""
    return await _preview_bag(update, context)


async def _preview_bag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    rest = ud["restaurant"]
    pct = round((1 - ud["bag_disc"] / ud["bag_orig"]) * 100)
    disc_str = f"{ud['bag_disc']:,} ل.س"
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ نشر", callback_data="bag_confirm_publish"),
                InlineKeyboardButton("إلغاء", callback_data="bag_confirm_cancel"),
            ]
        ]
    )
    await update.message.reply_text(
        f"📋 {b('راجع الكيس قبل النشر')}\n{LINE}\n\n"
        f"المطعم: {b(e(rest['name']))}\n"
        f"النوع: {e(ud['bag_type'])}\n"
        f"التلميح: {e(ud.get('bag_hint') or '—')}\n"
        f"السعر الأصلي: {ud['bag_orig']:,} ل.س\n"
        f"سعر تازا: {b(disc_str)} (خصم {pct}%)\n"
        f"الكمية: {b(str(ud['bag_qty']))}\n"
        f"الاستلام: {ud['bag_start']} – {ud['bag_end']}\n\n"
        f"هل تريد نشره الآن؟",
        parse_mode=HTML,
        reply_markup=kb,
    )
    return BAG_CONFIRM


async def bag_confirm_publish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _finalize_bag(update, context, context.user_data.get("photo_file_id", ""))


async def bag_confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.clear()
    await update.callback_query.message.reply_text("تم إلغاء إنشاء الكيس، ولم يتم نشر شيء.")
    return ConversationHandler.END


async def _finalize_bag(update, context, photo_file_id):
    ud = context.user_data
    rest = ud["restaurant"]
    target = update.message or update.callback_query.message
    is_dev = rest.get("restaurant_id") == 0

    if not is_dev:
        bag = db.add_bag(
            restaurant_id=rest["restaurant_id"],
            bag_type=ud["bag_type"],
            hint=ud.get("bag_hint", ""),
            original_price=ud["bag_orig"],
            discounted_price=ud["bag_disc"],
            quantity=ud["bag_qty"],
            pickup_start=ud["bag_start"],
            pickup_end=ud["bag_end"],
            photo_file_id=photo_file_id,
        )
        bag_id_str = f"رقم الكيس: {code(str(bag['bag_id']))}"
        logger.info("Bag created: %s restaurant=%s qty=%s", bag["bag_id"], rest["restaurant_id"], ud["bag_qty"])
    else:
        bag_id_str = code("[DEV — لم يُحفظ]")

    pct = round((1 - ud["bag_disc"] / ud["bag_orig"]) * 100)
    orig_str = f"{ud['bag_orig']:,} ل.س"
    disc_str = f"{ud['bag_disc']:,} ل.س"
    await target.reply_text(
        f"✅ {b('تم نشر الكيس بنجاح')}\n{LINE}\n\n"
        f"{b(e(ud['bag_type']))} — {e(rest['name'])}\n"
        f"التلميح: {e(ud.get('bag_hint') or '—')}\n"
        f"السعر: {s(orig_str)} ← {b(disc_str)} (خصم {pct}%)\n"
        f"الكمية: {b(str(ud['bag_qty']))}\n"
        f"الاستلام: {ud['bag_start']} – {ud['bag_end']}\n"
        f"{bag_id_str}",
        parse_mode=HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END


# /mybags  with edit buttons
# ══════════════════════════════════════════════════════


async def deactivate_bag_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    bag_id = int(update.callback_query.data.replace("deactivate_", ""))
    if not is_manager_for_bag(update.effective_user.id, bag_id):
        await update.callback_query.message.reply_text("هذا الكيس لا يتبع لمطعمك.")
        return
    db.deactivate_bag(bag_id)
    logger.info("Bag deactivated: %s by manager %s", bag_id, update.effective_user.id)
    await update.callback_query.message.reply_text(
        "🚫 تم إيقاف العرض وإخفاء الكيس من قائمة الزبائن."
    )


# ── Edit bag field ──


async def editbag_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split(
        "_"
    )  # editbag_qty_123 or editbag_price_123
    field = parts[1]  # qty / price
    bag_id = int(parts[2])
    if not is_manager_for_bag(update.effective_user.id, bag_id):
        await update.callback_query.message.reply_text("هذا الكيس لا يتبع لمطعمك.")
        return ConversationHandler.END
    context.user_data["edit_bag_id"] = bag_id
    context.user_data["edit_bag_field"] = field
    prompts = {
        "qty": "📦 أدخل الكمية الجديدة (عدد الأكياس):",
        "price": "💰 أدخل السعر الجديد بعد الخصم (ل.س):",
    }
    await update.callback_query.message.reply_text(
        prompts.get(field, "أدخل القيمة الجديدة:")
    )
    return EDIT_BAG_VALUE


async def editbag_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    field = context.user_data.get("edit_bag_field")
    bag_id = context.user_data.get("edit_bag_id")

    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً أكبر من صفر:")
        return EDIT_BAG_VALUE

    value = int(text)
    if not is_manager_for_bag(update.effective_user.id, int(bag_id)):
        await update.message.reply_text("هذا الكيس لا يتبع لمطعمك.")
        context.user_data.clear()
        return ConversationHandler.END
    if field == "qty":
        bag = db.get_bag_by_id(int(bag_id))
        sold = max(int(bag.get("quantity", 0) or 0) - int(bag.get("remaining", 0) or 0), 0) if bag else 0
        if value < sold:
            await update.message.reply_text(
                f"لا يمكن أن تكون الكمية أقل من العدد المباع ({sold})."
            )
            return EDIT_BAG_VALUE
        db.update_bag_field(bag_id, "remaining", value - sold)
        db.update_bag_field(bag_id, "quantity", value)
        db.update_bag_field(bag_id, "is_active", value > sold)
        await update.message.reply_text(
            f"✅ تم تحديث الكمية إلى {b(str(value))} كيس.", parse_mode=HTML
        )
    elif field == "price":
        db.update_bag_field(bag_id, "discounted_price", value)
        await update.message.reply_text(
            f"✅ تم تحديث السعر إلى {b(f'{value:,} ل.س')}.", parse_mode=HTML
        )
    else:
        await update.message.reply_text("❌ حقل غير معروف.")

    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
# ADMIN: /addrestaurant
# ══════════════════════════════════════════════════════


async def addrestaurant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ غير مصرح.")
        return ConversationHandler.END
    await update.message.reply_text(
        f"🍽️ {b('إضافة مطعم جديد')}\n{LINE}\n\n" f"الخطوة 1/4 — أدخل اسم المطعم:",
        parse_mode=HTML,
    )
    return ADMIN_REST_NAME


async def admin_rest_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rest_name"] = update.message.text.strip()
    await update.message.reply_text(
        "الخطوة 2/4 — اختر منطقة المطعم:",
        reply_markup=restaurant_area_kb(),
    )
    return ADMIN_REST_AREA


async def admin_rest_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["rest_area"] = update.callback_query.data.replace("restarea_", "")
    await update.callback_query.message.reply_text(
        "الخطوة 3/4 — عنوان الاستلام بالتفصيل:"
    )
    return ADMIN_REST_ADDR


async def admin_rest_addr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rest_addr"] = update.message.text.strip()
    await update.message.reply_text(
        f"الخطوة 4/4 — Telegram Chat ID لمدير المطعم:\n{i('من @userinfobot')}",
        parse_mode=HTML,
    )
    return ADMIN_REST_MGRID


async def admin_rest_mgrid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.lstrip("-").isdigit():
        await update.message.reply_text("❌ Chat ID يجب أن يكون رقماً:")
        return ADMIN_REST_MGRID

    manager_id = int(text)
    rest = db.add_restaurant(
        name=context.user_data["rest_name"],
        area=context.user_data["rest_area"],
        pickup_address=context.user_data["rest_addr"],
        manager_chat_id=manager_id,
    )
    await update.message.reply_text(
        f"✅ {b('تم تسجيل المطعم بنجاح!')}\n{LINE}\n\n"
        f"{b(e(rest['name']))}\n"
        f"المنطقة: {e(rest['area'])}\n"
        f"رقم المطعم: {code(str(rest['restaurant_id']))}",
        parse_mode=HTML,
    )
    try:
        welcome_caption = (
            f"👋 {b('أهلاً بك في تازا!')}\n{LINE}\n\n"
            f"أنت الآن جزء من مجتمع الحد من هدر الطعام. 🌱\n"
            f"ابدأ بإضافة أكياسك عبر /newbag\n\n"
            f"⬣ /newbag — إضافة كيس جديد\n"
            f"⬣ /mybags — عرض أكياسك اليوم"
        )
        await send_logo(context.bot, welcome_caption, chat_id=manager_id)
    except Exception as ex:
        logger.warning("Welcome message to restaurant failed: %s", ex)

    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
async def mybags_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    target = update.message or update.callback_query.message
    rest = get_restaurant_for_manager(uid)
    if not rest:
        await target.reply_text("هذا الأمر متاح للمطاعم المفعّلة فقط.")
        return

    bags = db.get_bags_for_restaurant(rest["restaurant_id"])
    if not bags:
        await target.reply_text("لا توجد أكياس اليوم. استخدم /newbag لنشر أول كيس.")
        return

    rest_name = e(rest["name"])
    await target.reply_text(
        f"📦 {b(f'أكياس {rest_name} اليوم')}\n{LINE}\n"
        f"إجمالي العروض: {b(str(len(bags)))}",
        parse_mode=HTML,
    )
    for bag in bags:
        remaining = int(bag.get("remaining", 0) or 0)
        quantity = int(bag.get("quantity", 0) or 0)
        sold = max(quantity - remaining, 0)
        active = is_truthy(bag.get("is_active"))
        if active and remaining > 0:
            status = "🟢 نشط"
        elif remaining <= 0:
            status = "🔴 نفد"
        else:
            status = "⚪ متوقف"
        text = (
            f"{b(e(bag.get('type', 'كيس')))} #{code(bag.get('bag_id', ''))}\n"
            f"الحالة: {status}\n"
            f"السعر: {int(bag.get('discounted_price', 0) or 0):,} ل.س\n"
            f"الاستلام: {e(bag.get('pickup_start', ''))} – {e(bag.get('pickup_end', ''))}\n"
            f"المباع: {sold}/{quantity} | المتبقي: {remaining}"
        )
        rows = []
        if active:
            rows.append(
                [
                    InlineKeyboardButton(
                        "تعديل الكمية",
                        callback_data=f"editbag_qty_{bag['bag_id']}",
                    ),
                    InlineKeyboardButton(
                        "تعديل السعر",
                        callback_data=f"editbag_price_{bag['bag_id']}",
                    ),
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        "إيقاف العرض",
                        callback_data=f"deactivate_{bag['bag_id']}",
                    )
                ]
            )
        await target.reply_text(
            text,
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )


async def restorders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    target = update.message or update.callback_query.message
    rest = get_restaurant_for_manager(uid)
    if not rest:
        await target.reply_text("هذا الأمر متاح للمطاعم المفعّلة فقط.")
        return
    orders = db.get_orders_for_restaurant_today(rest["restaurant_id"])
    if not orders:
        await target.reply_text("لا توجد طلبات اليوم بعد.")
        return

    counts = {}
    for order in orders:
        counts[order.get("status", "unknown")] = counts.get(order.get("status", "unknown"), 0) + 1
    rest_name = e(rest["name"])
    await target.reply_text(
        f"🧾 {b(f'طلبات {rest_name} اليوم')}\n{LINE}\n"
        f"محجوز: {counts.get('reserved', 0)} | مستلم: {counts.get('picked_up', 0)} | "
        f"ملغي: {counts.get('cancelled', 0)} | لم يحضر: {counts.get('no_show', 0)}",
        parse_mode=HTML,
    )

    for order in reversed(orders[-20:]):
        bag = db.get_bag_by_id(order["bag_id"])
        rows = []
        if order.get("status") == "reserved":
            rows.append(
                [
                    InlineKeyboardButton(
                        "تحقق من رمز الاستلام",
                        callback_data=f"pickup_{order['order_id']}_{order['user_id']}",
                    ),
                    InlineKeyboardButton(
                        "إلغاء",
                        callback_data=f"restcancel_{order['order_id']}_{order['bag_id']}_{order['user_id']}",
                    ),
                ]
            )
        text = (
            f"{code(order.get('order_code', ''))} — {order_status_label(order.get('status', ''))}\n"
            f"الزبون: {e(order.get('customer_name', ''))} | {e(order.get('customer_phone', ''))}\n"
            f"الكيس: {e((bag or {}).get('type', ''))}\n"
            f"الاستلام: {e((bag or {}).get('pickup_start', ''))} – {e((bag or {}).get('pickup_end', ''))}"
        )
        await target.reply_text(
            text,
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )


async def restaurant_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if update.callback_query.data == "rest_orders":
        return await restorders_command(update, context)
    if update.callback_query.data == "rest_bags":
        return await mybags_command(update, context)


async def pickup_code_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    order_id = int(parts[1])
    uid = update.effective_user.id
    if not is_manager_for_order(uid, order_id):
        await query.message.reply_text("هذا الطلب لا يتبع لمطعمك.")
        return ConversationHandler.END
    order = db.get_order_by_id(order_id)
    if not order:
        await query.message.reply_text("الطلب غير موجود.")
        return ConversationHandler.END
    if order.get("status") == "picked_up":
        await query.message.reply_text(
            f"تم تسجيل استلام الطلب {code(order.get('order_code', ''))} مسبقاً.",
            parse_mode=HTML,
        )
        return ConversationHandler.END
    if order.get("status") != "reserved":
        await query.message.reply_text("يمكن تسجيل الاستلام للطلبات المحجوزة فقط.")
        return ConversationHandler.END
    context.user_data["pickup_order_id"] = order_id
    await query.message.reply_text(
        f"أدخل رمز الطلب الذي يعرضه الزبون.\n"
        f"يمكن إدخال الرمز كاملاً مثل {code(order.get('order_code', ''))} أو الرقم فقط.",
        parse_mode=HTML,
    )
    return REST_PICKUP_CODE


async def pickup_code_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("pickup_order_id")
    if not order_id:
        await update.message.reply_text(
            "انتهت جلسة التحقق. افتح /restorders وحاول مجدداً."
        )
        return ConversationHandler.END
    uid = update.effective_user.id
    if not is_manager_for_order(uid, int(order_id)):
        await update.message.reply_text("هذا الطلب لا يتبع لمطعمك.")
        return ConversationHandler.END
    order = db.get_order_by_id(int(order_id))
    if not order:
        await update.message.reply_text("الطلب غير موجود.")
        return ConversationHandler.END
    submitted = normalize_order_code(update.message.text)
    expected = normalize_order_code(order.get("order_code", ""))
    if submitted != expected:
        await update.message.reply_text("❌ رمز الطلب غير صحيح. لم تتغير حالة الطلب.")
        return REST_PICKUP_CODE
    if order.get("status") == "picked_up":
        await update.message.reply_text("تم تسجيل استلام هذا الطلب مسبقاً.")
        return ConversationHandler.END
    if order.get("status") != "reserved":
        await update.message.reply_text("يمكن تسجيل الاستلام للطلبات المحجوزة فقط.")
        return ConversationHandler.END
    db.update_order_status(int(order_id), "picked_up")
    logger.info("Order picked up: %s by manager %s", order_id, uid)
    await update.message.reply_text(
        f"✅ تم تأكيد استلام الطلب {code(expected)}.",
        parse_mode=HTML,
    )
    context.user_data.pop("pickup_order_id", None)
    return ConversationHandler.END


# ADMIN: /allorders
# ══════════════════════════════════════════════════════


async def allorders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    orders = db.get_today_orders()
    today = datetime.now().strftime("%Y-%m-%d")

    if not orders:
        await update.message.reply_text(
            f"📊 {b(f'طلبات {today}')}\n\nلا توجد طلبات اليوم.", parse_mode=HTML
        )
        return

    total = len(orders)
    reserved = len([o for o in orders if o["status"] == "reserved"])
    picked_up = len([o for o in orders if o["status"] == "picked_up"])
    cancelled = len([o for o in orders if o["status"] == "cancelled"])

    lines = "\n".join(
        f"{code(o['order_code'])} — {e(o['customer_name'])} — "
        f"{STATUS_AR.get(o['status'],('❓',''))[0]} {STATUS_AR.get(o['status'],('','غير معروف'))[1]}"
        for o in orders[:20]
    )
    await update.message.reply_text(
        f"📊 {b(f'طلبات اليوم — {today}')}\n{LINE}\n\n"
        f"الإجمالي: {b(str(total))}\n"
        f"⏳ محجوز: {b(str(reserved))}\n"
        f"✅ تم الاستلام: {b(str(picked_up))}\n"
        f"❌ ملغي: {b(str(cancelled))}\n\n"
        f"{LINE}\n{lines}",
        parse_mode=HTML,
    )


# ══════════════════════════════════════════════════════
# ADMIN: /broadcast
# ══════════════════════════════════════════════════════


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👤 جميع الزبائن", callback_data="bc_customers")],
            [InlineKeyboardButton("🍽️ جميع المطاعم", callback_data="bc_restaurants")],
            [InlineKeyboardButton("🌐 الجميع", callback_data="bc_all")],
        ]
    )
    await update.message.reply_text(
        f"📢 {b('إرسال رسالة جماعية')}\n\nمن تريد إرسال الرسالة لهم؟",
        parse_mode=HTML,
        reply_markup=kb,
    )
    return BROADCAST_TARGET


async def broadcast_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["bc_target"] = update.callback_query.data
    labels = {
        "bc_customers": "👤 جميع الزبائن",
        "bc_restaurants": "🍽️ جميع المطاعم",
        "bc_all": "🌐 الجميع",
    }
    await update.callback_query.message.reply_text(
        f"المستهدفون: {b(labels.get(update.callback_query.data,''))}\n\naكتب نص الرسالة:",
        parse_mode=HTML,
    )
    return BROADCAST_MSG


async def broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text.strip()
    target = context.user_data.get("bc_target", "bc_all")
    users = db.get_all_users()
    restaurants = db.get_all_restaurants()

    recipients = set()
    if target in ("bc_customers", "bc_all"):
        recipients.update(
            int(u["user_id"]) for u in users if u.get("role") != "restaurant"
        )
    if target in ("bc_restaurants", "bc_all"):
        recipients.update(
            int(r["manager_chat_id"]) for r in restaurants if r.get("manager_chat_id")
        )

    await update.message.reply_text(f"⏳ جاري الإرسال لـ {len(recipients)} شخص...")
    sent, failed = 0, 0
    for uid in recipients:
        try:
            await context.bot.send_message(chat_id=uid, text=msg_text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📊 {b('نتيجة الإرسال:')}\n\n✅ تم: {sent}\n❌ فشل: {failed}", parse_mode=HTML
    )
    context.user_data.clear()
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
# ADMIN: /initsheets
# ══════════════════════════════════════════════════════


async def initsheets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        db.init_sheets()
        # Also try to load logo from config
        global LOGO_FILE_ID
        logo = db.get_config("logo_file_id")
        if logo:
            LOGO_FILE_ID = logo
        await update.message.reply_text("✅ تم إنشاء جداول البيانات وتهيئتها بنجاح!")
    except Exception as ex:
        await update.message.reply_text(f"❌ خطأ: {e(str(ex))}", parse_mode=HTML)


# ══════════════════════════════════════════════════════
# Error & cancel
# ══════════════════════════════════════════════════════


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception:", exc_info=context.error)
    await alert_admins(context.bot, str(context.error))


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("تم الإلغاء. /start للعودة للقائمة الرئيسية.")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
# Mini App API (aiohttp)
# ══════════════════════════════════════════════════════


def _get_webhook_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    return path if path.startswith("/") else f"/{path}"


def _parse_init_data(init_data: str) -> Optional[dict]:
    try:
        data = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = data.pop("hash", "")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        return None
    return data


def _extract_webapp_user_id(init_data: dict) -> Optional[int]:
    user_raw = init_data.get("user")
    if not user_raw:
        return None
    try:
        user_obj = json.loads(user_raw)
    except json.JSONDecodeError:
        return None
    uid = user_obj.get("id")
    return int(uid) if str(uid).isdigit() else None


def _get_auth_init_data(request: web.Request) -> str:
    header = request.headers.get("Authorization", "").strip()
    if header.lower().startswith("tma "):
        return header[4:].strip()
    return header


async def run_db(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    if kwargs:
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))
    return await loop.run_in_executor(None, fn, *args)


async def require_webapp_user(
    request: web.Request, expected_user_id: Optional[int] = None
):
    init_data = _get_auth_init_data(request)
    if not init_data:
        return None, web.json_response({"success": False, "message": "Missing auth"}, status=401)

    parsed = _parse_init_data(init_data)
    if not parsed:
        return None, web.json_response({"success": False, "message": "Invalid auth"}, status=401)

    uid = _extract_webapp_user_id(parsed)
    if not uid:
        return None, web.json_response({"success": False, "message": "Invalid user"}, status=401)

    if expected_user_id and int(expected_user_id) != int(uid):
        return None, web.json_response({"success": False, "message": "User mismatch"}, status=403)

    return uid, None


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = WEBAPP_CORS_ORIGIN or "*"
    response.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["Vary"] = "Origin"
    return response


async def health_handler(request: web.Request):
    sheets_connected = bool(db.spreadsheet)
    return web.json_response(
        {
            "status": "ok" if sheets_connected else "degraded",
            "sheets": "connected" if sheets_connected else "not_connected",
            "webhook": bool(WEBHOOK_URL),
        },
        status=200 if sheets_connected else 503,
    )


async def webhook_handler(request: web.Request):
    app: Application = request.app["ptb_app"]
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    update = Update.de_json(data, app.bot)
    await app.update_queue.put(update)
    return web.json_response({"ok": True})


async def api_vendor_lead(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {"success": False, "message": "بيانات الطلب غير صالحة."},
            status=400,
        )
    if not isinstance(payload, dict):
        return web.json_response(
            {"success": False, "message": "بيانات الطلب غير صالحة."},
            status=400,
        )

    bot_username = request.app["bot"].username
    if str(payload.get("company_website", "") or "").strip():
        logger.info(
            "Vendor lead blocked by honeypot from ip=%s",
            vendor_lead_client_ip(request),
        )
        return web.json_response(
            {
                "success": True,
                "lead_id": 0,
                "status": "pending_telegram",
                "telegram_url": f"https://t.me/{bot_username}",
            },
            status=201,
        )

    client_ip = vendor_lead_client_ip(request)
    if not vendor_lead_rate_allowed(client_ip):
        logger.info("Vendor lead rate limited from ip=%s", client_ip)
        response = web.json_response(
            {
                "success": False,
                "message": "تم إرسال عدة طلبات مؤخراً. حاول مجدداً بعد ساعة.",
            },
            status=429,
        )
        response.headers["Retry-After"] = str(VENDOR_LEAD_RATE_WINDOW)
        return response

    cleaned, errors = normalize_vendor_lead_payload(payload)
    if errors:
        return web.json_response(
            {"success": False, "message": errors[0], "errors": errors},
            status=400,
        )

    claim_token = secrets.token_urlsafe(18)
    try:
        lead = await run_db(
            db.add_vendor_lead,
            user_id=0,
            username="",
            shop_name=cleaned["shop_name"],
            category=cleaned["category"],
            area=cleaned["area"],
            pickup_address=cleaned["pickup_address"],
            contact_name=cleaned["contact_name"],
            whatsapp=cleaned["whatsapp"],
            closing_time=cleaned["closing_time"],
            surplus_notes=cleaned["surplus_notes"],
            interest_level="طلب من الموقع",
            main_concern="",
            source="landing_page",
            status="pending_telegram",
            claim_token=claim_token,
        )
    except Exception:
        logger.exception("Vendor lead persistence failed")
        return web.json_response(
            {
                "success": False,
                "message": "تعذر حفظ الطلب حالياً. حاول مجدداً بعد قليل.",
            },
            status=503,
        )

    telegram_url = (
        f"https://t.me/{bot_username}"
        f"?start=vendor_claim_{lead['lead_id']}_{claim_token}"
    )
    logger.info("Vendor lead accepted from landing page: %s", lead["lead_id"])
    await notify_vendor_lead(request.app["bot"], lead)
    return web.json_response(
        {
            "success": True,
            "lead_id": int(lead["lead_id"]),
            "status": "pending_telegram",
            "telegram_url": telegram_url,
        },
        status=201,
    )


async def api_get_bags(request: web.Request):
    user_id = request.query.get("user_id", "0")
    if not user_id.isdigit():
        return web.json_response({"success": False, "message": "Invalid user"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    user = await run_db(db.get_user, uid)
    if not user:
        user = await run_db(db.upsert_user, uid, role="customer")

    area = user.get("default_area", "")
    if not area:
        return web.json_response(
            {
                "success": True,
                "needs_area": True,
                "area": "",
                "bags": [],
            }
        )

    bags = await run_db(db.get_available_bags, area=area)
    rests = await asyncio.gather(
        *(run_db(db.get_restaurant_by_id, bag["restaurant_id"]) for bag in bags)
    )

    items = []
    for bag, rest in zip(bags, rests):
        if not rest:
            continue
        items.append(
            {
                "bag_id": int(bag["bag_id"]),
                "restaurant_id": int(bag["restaurant_id"]),
                "restaurant_name": rest.get("name", ""),
                "area": rest.get("area", ""),
                "pickup_address": rest.get("pickup_address", ""),
                "type": bag.get("type", ""),
                "emoji": BAG_TYPES.get(bag.get("type"), "📦"),
                "hint": bag.get("hint", ""),
                "original_price": int(bag.get("original_price", 0) or 0),
                "discounted_price": int(bag.get("discounted_price", 0) or 0),
                "remaining": int(bag.get("remaining", 0) or 0),
                "pickup_start": bag.get("pickup_start", ""),
                "pickup_end": bag.get("pickup_end", ""),
                "photo_file_id": bag.get("photo_file_id", ""),
            }
        )

    return web.json_response(
        {
            "success": True,
            "needs_area": False,
            "area": area,
            "bags": items,
        }
    )


async def api_get_orders(request: web.Request):
    user_id = request.query.get("user_id", "0")
    if not user_id.isdigit():
        return web.json_response({"success": False, "message": "Invalid user"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    orders = await run_db(db.get_user_orders, uid)
    items = []
    for order in orders:
        bag = await run_db(db.get_bag_by_id, order["bag_id"])
        rest = await run_db(db.get_restaurant_by_id, order["restaurant_id"])
        status = order.get("status", "")
        st_emoji, st_text = STATUS_AR.get(status, ("❓", "غير معروف"))
        items.append(
            {
                "order_id": int(order["order_id"]),
                "order_code": order.get("order_code", ""),
                "status": status,
                "status_label": st_text,
                "status_emoji": st_emoji,
                "bag_id": int(order.get("bag_id", 0) or 0),
                "bag_type": bag.get("type", "") if bag else "",
                "bag_emoji": BAG_TYPES.get(bag.get("type"), "📦") if bag else "📦",
                "restaurant_name": rest.get("name", "") if rest else "",
                "pickup_start": bag.get("pickup_start", "") if bag else "",
                "pickup_end": bag.get("pickup_end", "") if bag else "",
                "created_at": order.get("created_at", ""),
            }
        )

    return web.json_response({"success": True, "orders": items})


async def api_reserve(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    user_id = payload.get("user_id", 0)
    bag_id = payload.get("bag_id", 0)
    if not str(user_id).isdigit() or not str(bag_id).isdigit():
        return web.json_response({"success": False, "message": "Invalid payload"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    user = await run_db(db.get_user, uid)
    if not user or not user.get("name") or not user.get("phone"):
        return web.json_response(
            {
                "success": False,
                "message": "يرجى إكمال ملفك الشخصي عبر /start قبل الحجز.",
            },
            status=400,
        )

    bag = await run_db(db.get_bag_by_id, int(bag_id))
    if not bag:
        return web.json_response({"success": False, "message": "الكيس غير موجود."}, status=404)

    rest = await run_db(db.get_restaurant_by_id, bag["restaurant_id"])
    if rest and user.get("default_area") and rest.get("area") != user.get("default_area"):
        return web.json_response(
            {"success": False, "message": "هذا الكيس غير متاح في منطقتك."},
            status=403,
        )

    success, order, msg_ar = await db.atomic_reserve(
        int(bag_id), uid, user.get("name", ""), user.get("phone", "")
    )
    if not success or not order:
        return web.json_response({"success": False, "message": msg_ar}, status=409)

    return web.json_response(
        {
            "success": True,
            "order_code": order.get("order_code", ""),
            "order_id": int(order.get("order_id", 0) or 0),
            "bag_id": int(bag_id),
        }
    )


async def api_get_restaurant_bags(request: web.Request):
    user_id = request.query.get("user_id", "0")
    if not user_id.isdigit():
        return web.json_response({"success": False, "message": "Invalid user"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    rest = await run_db(db.get_restaurant_by_manager, uid)
    if not rest:
        return web.json_response({"success": False, "message": "Not allowed"}, status=403)

    bags = await run_db(db.get_bags_for_restaurant, rest["restaurant_id"])
    items = []
    for bag in bags:
        remaining = int(bag.get("remaining", 0) or 0)
        quantity = int(bag.get("quantity", 0) or 0)
        items.append(
            {
                "bag_id": int(bag["bag_id"]),
                "type": bag.get("type", ""),
                "emoji": BAG_TYPES.get(bag.get("type"), "📦"),
                "original_price": int(bag.get("original_price", 0) or 0),
                "discounted_price": int(bag.get("discounted_price", 0) or 0),
                "quantity": quantity,
                "remaining": remaining,
                "sold": max(quantity - remaining, 0),
                "pickup_start": bag.get("pickup_start", ""),
                "pickup_end": bag.get("pickup_end", ""),
                "is_active": str(bag.get("is_active", "")).lower() in ("true", "1"),
            }
        )

    return web.json_response({"success": True, "bags": items, "restaurant": rest})


async def api_get_restaurant_orders(request: web.Request):
    user_id = request.query.get("user_id", "0")
    if not user_id.isdigit():
        return web.json_response({"success": False, "message": "Invalid user"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    rest = await run_db(db.get_restaurant_by_manager, uid)
    if not rest:
        return web.json_response({"success": False, "message": "Not allowed"}, status=403)

    orders = await run_db(db.get_orders_for_restaurant_today, rest["restaurant_id"])
    items = []
    for order in orders:
        bag = await run_db(db.get_bag_by_id, order["bag_id"])
        status = order.get("status", "")
        st_emoji, st_text = STATUS_AR.get(status, ("❓", "غير معروف"))
        items.append(
            {
                "order_id": int(order["order_id"]),
                "order_code": order.get("order_code", ""),
                "status": status,
                "status_label": st_text,
                "status_emoji": st_emoji,
                "customer_name": order.get("customer_name", ""),
                "customer_phone": order.get("customer_phone", ""),
                "bag_type": bag.get("type", "") if bag else "",
                "bag_emoji": BAG_TYPES.get(bag.get("type"), "📦") if bag else "📦",
                "pickup_start": bag.get("pickup_start", "") if bag else "",
                "pickup_end": bag.get("pickup_end", "") if bag else "",
                "discounted_price": int(bag.get("discounted_price", 0) or 0)
                if bag
                else 0,
            }
        )

    return web.json_response({"success": True, "orders": items, "restaurant": rest})


async def api_bag_edit(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    user_id = payload.get("user_id", 0)
    bag_id = payload.get("bag_id", 0)
    field = payload.get("field", "")
    value = payload.get("value", 0)
    if not str(user_id).isdigit() or not str(bag_id).isdigit():
        return web.json_response({"success": False, "message": "Invalid payload"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    rest = await run_db(db.get_restaurant_by_manager, uid)
    if not rest:
        return web.json_response({"success": False, "message": "Not allowed"}, status=403)

    bag = await run_db(db.get_bag_by_id, int(bag_id))
    if not bag or str(bag.get("restaurant_id")) != str(rest["restaurant_id"]):
        return web.json_response({"success": False, "message": "Bag not found"}, status=404)

    if field == "qty":
        if not str(value).isdigit() or int(value) <= 0:
            return web.json_response({"success": False, "message": "Invalid quantity"}, status=400)
        qty = int(value)
        sold = max(int(bag.get("quantity", 0) or 0) - int(bag.get("remaining", 0) or 0), 0)
        if qty < sold:
            return web.json_response({"success": False, "message": "Quantity cannot be less than sold count"}, status=400)
        await run_db(db.update_bag_field, int(bag_id), "remaining", qty - sold)
        await run_db(db.update_bag_field, int(bag_id), "quantity", qty)
        await run_db(db.update_bag_field, int(bag_id), "is_active", qty > sold)
    elif field == "price":
        if not str(value).isdigit() or int(value) <= 0:
            return web.json_response({"success": False, "message": "Invalid price"}, status=400)
        await run_db(db.update_bag_field, int(bag_id), "discounted_price", int(value))
    else:
        return web.json_response({"success": False, "message": "Unknown field"}, status=400)

    return web.json_response({"success": True})


async def api_bag_deactivate(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    user_id = payload.get("user_id", 0)
    bag_id = payload.get("bag_id", 0)
    if not str(user_id).isdigit() or not str(bag_id).isdigit():
        return web.json_response({"success": False, "message": "Invalid payload"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    rest = await run_db(db.get_restaurant_by_manager, uid)
    if not rest:
        return web.json_response({"success": False, "message": "Not allowed"}, status=403)

    bag = await run_db(db.get_bag_by_id, int(bag_id))
    if not bag or str(bag.get("restaurant_id")) != str(rest["restaurant_id"]):
        return web.json_response({"success": False, "message": "Bag not found"}, status=404)

    await run_db(db.deactivate_bag, int(bag_id))
    return web.json_response({"success": True})


async def api_order_pickup(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    user_id = payload.get("user_id", 0)
    order_id = payload.get("order_id", 0)
    order_code = normalize_order_code(payload.get("order_code", ""))
    if not str(user_id).isdigit() or not str(order_id).isdigit():
        return web.json_response({"success": False, "message": "Invalid payload"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    rest = await run_db(db.get_restaurant_by_manager, uid)
    if not rest:
        return web.json_response({"success": False, "message": "Not allowed"}, status=403)

    order = await run_db(db.get_order_by_id, int(order_id))
    if not order or str(order.get("restaurant_id")) != str(rest["restaurant_id"]):
        return web.json_response({"success": False, "message": "Order not found"}, status=404)

    if order.get("status") == "picked_up":
        return web.json_response({"success": True, "message": "Already picked up"})
    if order.get("status") != "reserved":
        return web.json_response({"success": False, "message": "Only reserved orders can be picked up"}, status=409)
    if not order_code or order_code != normalize_order_code(order.get("order_code", "")):
        return web.json_response({"success": False, "message": "Wrong order code"}, status=403)

    await run_db(db.update_order_status, int(order_id), "picked_up")
    logger.info("Order picked up from Mini App: %s by manager %s", order_id, uid)
    try:
        await request.app["bot"].send_message(
            chat_id=int(rest.get("manager_chat_id")),
            text=(
                f"✅ {b('تم تسجيل الاستلام')}\n\n"
                f"الطلب {code(order.get('order_code', order_id))} تم استلامه بنجاح."
            ),
            parse_mode=HTML,
        )
    except Exception:
        pass

    return web.json_response({"success": True})


async def api_order_cancel(request: web.Request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"success": False, "message": "Invalid JSON"}, status=400)

    user_id = payload.get("user_id", 0)
    order_id = payload.get("order_id", 0)
    if not str(user_id).isdigit() or not str(order_id).isdigit():
        return web.json_response({"success": False, "message": "Invalid payload"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    rest = await run_db(db.get_restaurant_by_manager, uid)
    if not rest:
        return web.json_response({"success": False, "message": "Not allowed"}, status=403)

    order = await run_db(db.get_order_by_id, int(order_id))
    if not order or str(order.get("restaurant_id")) != str(rest["restaurant_id"]):
        return web.json_response({"success": False, "message": "Order not found"}, status=404)

    success = await db.cancel_reservation(int(order_id), int(order["bag_id"]))
    if not success:
        return web.json_response({"success": False, "message": "Cancel failed"}, status=409)

    code_str = order.get("order_code", "")
    try:
        await request.app["bot"].send_message(
            chat_id=int(order["user_id"]),
            text=(
                f"⚠️ {b('تنبيه من تازا')}\n\n"
                f"تم إلغاء طلبك {code(code_str)} من قبل المطعم.\n\n"
                f"يمكنك حجز كيس آخر عبر /menu 🛍️"
            ),
            parse_mode=HTML,
        )
    except Exception:
        pass

    return web.json_response({"success": True})


async def api_get_file(request: web.Request):
    user_id = request.query.get("user_id", "0")
    file_id = request.query.get("file_id", "")
    if not user_id.isdigit() or not file_id:
        return web.json_response({"success": False, "message": "Invalid request"}, status=400)

    uid, error = await require_webapp_user(request, int(user_id))
    if error:
        return error

    try:
        tg_file = await request.app["bot"].get_file(file_id)
        data = await tg_file.download_as_bytearray()
    except Exception:
        return web.json_response({"success": False, "message": "File not found"}, status=404)

    content_type = "image/jpeg"
    if tg_file.file_path and tg_file.file_path.endswith(".png"):
        content_type = "image/png"

    return web.Response(body=bytes(data), content_type=content_type)


def build_web_app(application: Application) -> web.Application:
    aio_app = web.Application(middlewares=[cors_middleware])
    aio_app["bot"] = application.bot
    aio_app["ptb_app"] = application

    aio_app.router.add_get("/health", health_handler)
    if WEBHOOK_URL:
        aio_app.router.add_post(_get_webhook_path(WEBHOOK_URL), webhook_handler)

    aio_app.router.add_post("/api/vendor_lead", api_vendor_lead)
    aio_app.router.add_get("/api/bags", api_get_bags)
    aio_app.router.add_get("/api/orders", api_get_orders)
    aio_app.router.add_post("/api/reserve", api_reserve)
    aio_app.router.add_get("/api/restaurant_bags", api_get_restaurant_bags)
    aio_app.router.add_get("/api/restaurant_orders", api_get_restaurant_orders)
    aio_app.router.add_post("/api/bag/edit", api_bag_edit)
    aio_app.router.add_post("/api/bag/deactivate", api_bag_deactivate)
    aio_app.router.add_post("/api/order/pickup", api_order_pickup)
    aio_app.router.add_post("/api/order/cancel", api_order_cancel)
    aio_app.router.add_get("/api/file", api_get_file)

    return aio_app


# ══════════════════════════════════════════════════════
# Build Application
# ══════════════════════════════════════════════════════


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    reservation_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(reserve_start, pattern=r"^reserve_\d+$")],
        states={
            CUST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
            CUST_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_phone)
            ],
            RES_CONFIRM: [
                CallbackQueryHandler(confirm_reserve, pattern="^confirm_reserve$"),
                CallbackQueryHandler(cancel_reserve, pattern="^cancel_reserve$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,
    )

    newbag_conv = ConversationHandler(
        entry_points=[CommandHandler("newbag", newbag_command)],
        states={
            BAG_TYPE: [CallbackQueryHandler(bag_type_callback, pattern=r"^bagtype_")],
            BAG_HINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bag_hint),
                CommandHandler("skip", bag_hint),
            ],
            BAG_ORIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, bag_orig)],
            BAG_DISC: [MessageHandler(filters.TEXT & ~filters.COMMAND, bag_disc)],
            BAG_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bag_qty)],
            BAG_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, bag_start)],
            BAG_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, bag_end)],
            BAG_PHOTO: [
                MessageHandler(filters.PHOTO, bag_photo),
                CommandHandler("skip", bag_skip_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, bag_skip_photo),
            ],
            BAG_CONFIRM: [
                CallbackQueryHandler(bag_confirm_publish, pattern="^bag_confirm_publish$"),
                CallbackQueryHandler(bag_confirm_cancel, pattern="^bag_confirm_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,
    )

    addrest_conv = ConversationHandler(
        entry_points=[CommandHandler("addrestaurant", addrestaurant_command)],
        states={
            ADMIN_REST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rest_name)
            ],
            ADMIN_REST_AREA: [
                CallbackQueryHandler(admin_rest_area, pattern=r"^restarea_")
            ],
            ADMIN_REST_ADDR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rest_addr)
            ],
            ADMIN_REST_MGRID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rest_mgrid)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_command)],
        states={
            BROADCAST_TARGET: [CallbackQueryHandler(broadcast_target, pattern=r"^bc_")],
            BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_msg)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    editbag_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(editbag_callback, pattern=r"^editbag_(qty|price)_\d+$")
        ],
        states={
            EDIT_BAG_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, editbag_value)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    rest_pickup_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pickup_code_start, pattern=r"^pickup_\d+_\d+$")],
        states={
            REST_PICKUP_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pickup_code_verify)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,
    )

    setlogo_conv = ConversationHandler(
        entry_points=[CommandHandler("setlogo", setlogo_command)],
        states={
            SET_LOGO: [MessageHandler(filters.PHOTO, setlogo_receive)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    vendor_conv = ConversationHandler(
        entry_points=[
            CommandHandler("vendor", vendor_command),
            CommandHandler(
                "start",
                vendor_start_command,
                filters.Regex(
                    r"^/start(?:@\w+)?\s+vendor(?!_claim_)(?:_\S+)?$"
                ),
            ),
            CallbackQueryHandler(vendor_signup_callback, pattern="^vendor_signup$"),
        ],
        states={
            VENDOR_SHOP_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendor_shop_name)
            ],
            VENDOR_CATEGORY: [
                CallbackQueryHandler(vendor_category_callback, pattern=r"^vendorcat_")
            ],
            VENDOR_AREA: [
                CallbackQueryHandler(vendor_area_callback, pattern=r"^vendorarea_")
            ],
            VENDOR_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendor_address)
            ],
            VENDOR_CONTACT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendor_contact_name)
            ],
            VENDOR_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendor_phone)
            ],
            VENDOR_CLOSING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendor_closing_time)
            ],
            VENDOR_SURPLUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, vendor_surplus),
                CommandHandler("skip", vendor_surplus),
            ],
            VENDOR_INTEREST: [
                CallbackQueryHandler(
                    vendor_interest_callback, pattern=r"^vendorinterest_"
                )
            ],
            VENDOR_CONCERN: [
                CallbackQueryHandler(
                    vendor_concern_callback, pattern=r"^vendorconcern_"
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        allow_reentry=True,
    )

    # Claim links and vendor signups are handled before the generic /start command.
    app.add_handler(
        CommandHandler(
            "start",
            vendor_claim_start_command,
            filters.Regex(r"^/start(?:@\w+)?\s+vendor_claim_\d+_[A-Za-z0-9_-]+$"),
        ),
        group=-2,
    )
    app.add_handler(vendor_conv, group=-1)

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("setlocation", setlocation_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("mybags", mybags_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("restorders", restorders_command))
    app.add_handler(CommandHandler("allorders", allorders_command))
    app.add_handler(CommandHandler("vendorleads", vendorleads_command))
    app.add_handler(CommandHandler("initsheets", initsheets_command))
    app.add_handler(CommandHandler("devmode", devmode_command))

    # Conversations
    app.add_handler(reservation_conv)
    app.add_handler(newbag_conv)
    app.add_handler(addrest_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(editbag_conv)
    app.add_handler(rest_pickup_conv)
    app.add_handler(setlogo_conv)

    # Callbacks
    app.add_handler(CallbackQueryHandler(howto_callback, pattern="^howto$"))
    app.add_handler(CallbackQueryHandler(vendor_info_callback, pattern="^vendor_info$"))
    app.add_handler(CallbackQueryHandler(vendor_lead_action_callback, pattern=r"^lead_(approve|reject)_\d+$"))
    app.add_handler(CallbackQueryHandler(restaurant_panel_callback, pattern=r"^rest_(orders|bags)$"))
    app.add_handler(CallbackQueryHandler(browse_callback, pattern="^browse$"))
    app.add_handler(CallbackQueryHandler(my_orders_callback, pattern="^my_orders$"))
    app.add_handler(
        CallbackQueryHandler(setlocation_callback, pattern=r"^(setlocation|area_.+)$")
    )
    app.add_handler(
        CallbackQueryHandler(rest_cancel_callback, pattern=r"^restcancel_\d+_\d+_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(customer_cancel_callback, pattern=r"^custcancel_\d+_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(deactivate_bag_callback, pattern=r"^deactivate_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(rate_callback, pattern=r"^rate_(good|bad)_\d+$")
    )
    app.add_handler(CallbackQueryHandler(devrole_callback, pattern=r"^devrole_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))

    app.add_error_handler(error_handler)
    return app


# ══════════════════════════════════════════════════════
# Entry point  (polling for local dev)
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    async def run():
        db.connect()
        logger.info("Sheets connected.")

        # Try loading logo from config sheet
        try:
            logo = db.get_config("logo_file_id")
            if logo:
                global LOGO_FILE_ID
                LOGO_FILE_ID = logo
                logger.info("Logo loaded from config.")
        except Exception:
            pass

        ptb_app = build_app()
        await ptb_app.initialize()
        await ptb_app.start()

        scheduler = setup_scheduler(ptb_app.bot)

        aio_app = build_web_app(ptb_app)
        runner = web.AppRunner(aio_app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
        await site.start()
        logger.info("HTTP server started on port %s", PORT)

        if WEBHOOK_URL:
            await ptb_app.bot.set_webhook(
                url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES
            )
            logger.info("Webhook mode enabled: %s", WEBHOOK_URL)
        else:
            await ptb_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("Polling mode enabled. (DEV_MODE=%s)", DEV_MODE)

        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        finally:
            if WEBHOOK_URL:
                await ptb_app.bot.delete_webhook(drop_pending_updates=False)
            else:
                await ptb_app.updater.stop()

            scheduler.shutdown(wait=False)
            await ptb_app.stop()
            await ptb_app.shutdown()
            await runner.cleanup()

    asyncio.run(run())
