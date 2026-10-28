import asyncio
import html
import logging
import os
import re
import sqlite3
import time
from datetime import datetime

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    KeyboardButton,
    ReplyKeyboardMarkup,
    SwitchInlineQueryChosenChat,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

# ============================================================
# الإعدادات
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()  # ضعه في متغيرات البيئة في الاستضافة
OWNER_ID = 7683201905
DB_FILE = "fourth_scientific_bot_v3.db"
DEFAULT_CHANNEL = "@Kii_8i"
DEFAULT_FOOTER = (
    "#رابعيون : @Kii_8i\n"
    "رابط بوت ملازم الرابع العلمي : @Tiuezbot\n\n"
    "🕊️ شارك فربما تكون سبباً في تغيير مستقبل ."
)
SUB_CACHE_SECONDS = 300

HOME_TEXT = "هلا بيك ببوت الرابع العلمي 🎓\nاختر من الأزرار بالأسفل:"
GATE_TEXT = "حتى تستخدم البوت، اشترك بالقناة أولاً، ثم اضغط التحقق من الاشتراك."
MAINT_TEXT = "البوت تحت الصيانة، سيتم اضافة مميزات جديدة."
BACK = "🔙 رجوع"
CANCEL = "❌ إلغاء"
CONFIRM = "✅ تأكيد"
SKIP = "⏭ تخطي"
DONE = "✅ تم"
PAUSE_ON = "⏸ إيقاف البوت مؤقتاً"
PAUSE_OFF = "▶️ تشغيل البوت"
COLORS = {"🟢 أخضر": "success", "🔵 أزرق": "primary", "🔴 أحمر": "danger"}
COLOR_ROW = [("🟢 أخضر", "success"), ("🔵 أزرق", "primary"), ("🔴 أحمر", "danger")]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

# ============================================================
# البيانات الثابتة
# ============================================================

# الاسم، الإيموجي، اللون، النوع (ch = فصول، unit = وحدات)
SUBJECTS = [
    ("رياضيات", "📐", "primary", "ch"),
    ("كيمياء", "🧪", "primary", "ch"),
    ("فيزياء", "⚡", "primary", "ch"),
    ("أحياء", "🧬", "success", "ch"),
    ("الحاسوب", "💻", "success", "ch"),
    ("English", "🇬🇧", "danger", "unit"),
    ("اللغة العربية", "📚", "success", "unit"),
    ("التربية الإسلامية", "📖", "danger", "unit"),
    ("جرائم حزب البعث", "⚖️", "danger", "ch"),
]

CH_LABELS = {"ch1": "الفصل الأول", "ch2": "الفصل الثاني", "ch3": "الفصل الثالث"}
UNIT_LABELS = {"u1": "الوحدة الأولى", "u2": "الوحدة الثانية", "u3": "الوحدة الثالثة"}
Q_SECTIONS = {
    "ch1": "الفصل الأول",
    "half": "نصف السنة",
    "ch2": "الفصل الثاني",
    "end": "اسئلة نهاية السنه",
}
Q_MONTHS = {"m1": "الشهر الأول", "m2": "الشهر الثاني"}
Q_NEEDS_MONTH = {"ch1", "ch2"}
KIND_NAMES = {"book": "كتاب", "note": "ملزمة", "summary": "ملخص", "question": "أسئلة"}
FILE_KINDS = {"📘 كتاب": "book", "📙 ملزمة": "note"}

# (النوع، المادة، القسم، الشهر، الاسم، الأستاذ، الـ ID، نوع الملف)
SEED_FILES = [
    ("book", "أحياء", None, None, "كتاب احياء 2026", None, "BQACAgIAAxkBAANjatJ_BlFWtJXog_uzbiRZcHDCvbIAAvmZAAIKWthLPB8esHug98I9BA", "document"),
    ("book", "التربية الإسلامية", None, None, "كتاب الأسلامية [2026]", None, "BQACAgQAAxkBAAIMDGrTcf86EWrsjrLCMOSoCuWyO9PBAAJNHQACI1sZUODQkEjwnva0PQQ", "document"),
    ("book", "اللغة العربية", None, None, "عربي الجزء الاول", None, "BQACAgQAAxkBAAIMDWrTcf-V58DTnf3FLrwV8Io2yc4dAAIoGwACDJ5oUKxZrmMPKeL0PQQ", "document"),
    ("book", "English", None, None, "انكليزي كتاب الطالب [2026]", None, "BQACAgQAAxkBAAIMD2rTcf9lMkJhjKxcOHghJNvLlOgIAAKqHgACLelYUCyIMVKYPttsPQQ", "document"),
    ("book", "رياضيات", None, None, "كتاب الرياضيات [2027]", None, "BQACAgQAAxkBAAIMEWrTcf-UfPStSBEcwu4O6-1UpbosAAKaIgACdIcZUjTphOSX_D_gPQQ", "document"),
    ("book", "كيمياء", None, None, "كيمياء [2026]", None, "BQACAgQAAxkBAAIMEmrTcf91NimvmNTMtVFNsLkV_ZxuAALcGwACLelQUBGFuxEWLZ8AAT0E", "document"),
    ("book", "فيزياء", None, None, "فيزياء[2026]", None, "BQACAgQAAxkBAAIME2rTcf-kFrO9ndiKQBbSlswlcZB_AALYGwACLelQUOryeBETtY9cPQQ", "document"),
    ("book", "الحاسوب", None, None, "الحاسوب [2026]", None, "BQACAgQAAxkBAAIMFGrTcf9SISexmrNm0npLMkITC5_kAALNGwACLelQUBvxgSA4uyxuPQQ", "document"),
    ("book", "جرائم حزب البعث", None, None, "كتاب الجرائم [2026]", None, "BQACAgQAAxkBAAIMFWrTcf-_zGchW7tUWpzexT82K_IIAAIOHAACLelQUFXdEILcCpwKPQQ", "document"),
    ("book", "أحياء", None, None, "كتاب احياء 2026", None, "BQACAgQAAxkBAAIja2rhBn6U_jlutinz21mhchFPUtOEAALUGwACLelQUOcd62MAAW6qsD0E", "document"),
    ("note", "التربية الإسلامية", None, None, "ملزمة التربية الإسلامية", None, "BQACAgQAAxkBAAIMt2rTdH0RfTYKY3wk8hRGR7d35CtxAAJJHAACDJ5wUKyuhgcaKePNPQQ", "document"),
    ("note", "التربية الإسلامية", None, None, "ملزمة التربية الإسلامية", None, "BQACAgQAAxkBAAIMuGrTdH0FJ7tsjGZyYi4XVazezONjAAKaIAACwWsxU4gqXUwm6wI1PQQ", "document"),
    ("note", "اللغة العربية", None, None, "ملزمة العربي الجزء الاول", "أ. عمار السلامي", "BQACAgQAAxkBAAINA2rTdikjrRAAATgQDrNtk8eXFiJI6QACHB8AAnxQWVCOr3n_md_AlT0E", "document"),
    ("note", "اللغة العربية", None, None, "ملزمة العربي الجزء الاول", "الست سمر علي", "BQACAgQAAxkBAAINBGrTdinKTeLh9q1LsnX7xBzDeZcaAAIZIgACcMpoUFyg7ClDAp6CPQQ", "document"),
    ("note", "اللغة العربية", None, None, "ملزمة العربي الجزء الثاني", "أ. عمار السلامي", "BQACAgQAAxkBAAINBWrTdikLeFGsv6JIrqF-HWEx-CSoAAKbHAACKX3JUFPRr_fQdc4JPQQ", "document"),
    ("note", "اللغة العربية", None, None, "ملزمة العربي الجزء الثاني", "الست سمر علي", "BQACAgQAAxkBAAINBmrTdil8lej0jOr-LWGeMxakiY8MAAJlHwACNPfJUa3ZFRKEEbIRPQQ", "document"),
    ("note", "اللغة العربية", None, None, "ملزمة العربي الجزء الاول", "الست رفل الزبيدي", "BQACAgQAAxkBAAINVmrTd6wD3wweRUbpvC-VSbmuPbMTAAIYGwAC4MKRUzQ2SpWHZDRRPQQ", "document"),
    ("note", "اللغة العربية", None, None, "ملزمة العربي الجزء الثاني", "الست رفل الزبيدي", "BQACAgQAAxkBAAINB2rTdiktwTFq1h1oz8vEIbWvDNoMAAJ7HAAC4MKJUw2Oku9xZQABiz0E", "document"),
    ("note", "English", None, None, "ملزمة الانكليزي", "أ. محمد النوفلي", "BQACAgQAAxkBAAINpWrTeHaA0V0XOSUHQQcK79cYwNtCAAKfGgACdLfBUOo3DSPMegV3PQQ", "document"),
    ("note", "English", None, None, "ملزمة الانكليزي", "أ. علي الغرابي", "BQACAgQAAxkBAAINpmrTeHbySP29YFl8DXIbOQABRTYRUQACmRoAAnS3wVBJn4uc0469AAE9BA", "document"),
    ("note", "English", None, None, "ملزمة الانكليزي", "أ. طه حسين", "BQACAgQAAxkBAAINp2rTeHZsqo-76x5nC8KD4_tD9UOxAAKWGgACdLfBUI50M_H1A3BHPQQ", "document"),
    ("note", "أحياء", None, None, "ملزمة الاحياء", "أ. احمد الجاف", "BQACAgQAAxkBAAIN5mrTeUPp90D6LAZrYLFIDDWyeFetAAJHHgACc5_RUEnOH7sNOOugPQQ", "document"),
    ("note", "أحياء", None, None, "ملزمة الاحياء", "أ. قاسم منتصر", "BQACAgQAAxkBAAIN52rTeUPQrHiyFB-r3U81Bc-dg5hLAAJFHgACc5_RULcQFdWU5YYaPQQ", "document"),
    ("note", "كيمياء", None, None, "ملزمة الكيمياء", "أ. دانيار الجاف", "BQACAgQAAxkBAAIOE2rTeeQEHH_XW70bWlGSZnmGLFWWAAJDHgACc5_RUBkWydg-5mtdPQQ", "document"),
    ("note", "كيمياء", None, None, "ملزمة الكيمياء", "أ. مهند السوداني", "BQACAgQAAxkBAAIOFGrTeeScWMz2_RJiIW1MrqbUaSDzAAJRJQAC4xPwUVOXebAX5QzKPQQ", "document"),
    ("note", "كيمياء", None, None, "ملزمة الكيمياء", "أ. حسين حمزة", "BQACAgQAAxkBAAIOFWrTeeTLlagz87vO0hnfc8SHZU3bAAIWHAACDJ5wUE2at2pYdJVBPQQ", "document"),
    ("note", "جرائم حزب البعث", None, None, "ملزمة جرائم حزب البعث", "أ. ابراهيم قاسم", "BQACAgIAAxkBAAIOUmrTeqgqBBxnmE6VQnEFrRrDPMHRAAJ5rwACAey5SdF_EHaXaKiSPQQ", "document"),
    ("note", "فيزياء", None, None, "ملزمة فيزياء", "أ. ابراهيم الخالدي", "BQACAgIAAxkBAAIOaGrTe-RjhG9xIqnmZ2WLL_zKOCxEAALTrAACClrQS2j4-y5NFvb3PQQ", "document"),
    ("note", "أحياء", None, None, "ملزمة احياء", "أ. جاسم الموالي", "BQACAgIAAxkBAAIOaWrTe-TsZzdSL8iwD72VGSfD7VV7AAJRowACxTBoSu6az6X2r7bgPQQ", "document"),
    ("note", "فيزياء", None, None, "ملزمة الفيزياء", "أ. علي الذهبي", "BQACAgQAAxkBAAIOnmrTfcMsCNcLdECgiaKgw2W8NivYAAJgGwACH-xIUym-W1EyQYCnPQQ", "document"),
    ("note", "فيزياء", None, None, "ملزمة فيزياء", "أ. دانيار الجاف", "BQACAgQAAxkBAAIOnWrTfcO3JeIoYotm6oCfX9a0vb4SAAJkGgACKX25UPkGW0tPJQkePQQ", "document"),
    ("note", "فيزياء", None, None, "ملزمة فيزياء", "أ. علي السوداني", "BQACAgQAAxkBAAIOn2rTfcNrbHmwzCHgbyOyEzU0xrmhAAIWHwACfFBZUKz_UZO7N5ZwPQQ", "document"),
    ("note", "الحاسوب", None, None, "ملزمة الحاسوب", "الست عواطف عبدالله", "BQACAgQAAxkBAAIO1GrTfo7E8skAAYYNCN6IkA7cKguMVgACwB4AAp6IAVG9ny7t_-JyRj0E", "document"),
    ("summary", "فيزياء", "ch1", None, "ملخص فيزياء - الفصل الأول", None, "BQACAgIAAxkBAAIO8GrTfvWitC4uXu-YFeS2HXLCCsI4AAKGqAACYRkQStqQOPL06-8GPQQ", "document"),
    ("summary", "فيزياء", "ch2", None, "ملخص فيزياء - الفصل الثاني", None, "BQACAgIAAxkBAAIO8WrTfvVdDCcpz88D85jSD23d5T4OAAK6pgACdnZoSihXFvx0p5jXPQQ", "document"),
    ("summary", "English", "u1", None, "ملخص English - الوحدة الأولى", None, "BQACAgIAAxkBAAIPLWrTgkP69GkEIANwVq8rLvqNxog5AALfqQACIR6YShAbpWq12ikzPQQ", "document"),
    ("summary", "English", "u2", None, "ملخص English - الوحدة الثانية", None, "BQACAgIAAxkBAAIPLmrTgkOL73qgCVQcJU4iz1ScTsidAALmqQACIR6YSs_4molH88vpPQQ", "document"),
    ("summary", "English", "u3", None, "ملخص English - الوحدة الثالثة", None, "BQACAgIAAxkBAAIPL2rTgkM-GVxFKnDVsfgTBpqZLMeWAALpqQACIR6YSgplyiu7Ecf9PQQ", "document"),
    ("summary", "فيزياء", "ch3", None, "ملخص فيزياء - الفصل الثالث", None, "BQACAgIAAxkBAAIPb2rTiCXaBNpwzOKE2_5_If0CkaApAAJ7qwACDUCZSqhZ21Ktq9yuPQQ", "document"),
    ("summary", "التربية الإسلامية", "u1", None, "ملخص التربية الإسلامية - الوحدة الأولى", None, "BQACAgIAAxkBAAIP32rTmJX09vS-G2W_RbsZnnGIk_1xAAI-qwACIR6YSgtzbzRKbP9HPQQ", "document"),
    ("summary", "التربية الإسلامية", "u2", None, "ملخص التربية الإسلامية - الوحدة الثانية", None, "BQACAgIAAxkBAAIP4GrTmJUEnaM_WXnVB8eHcfbpnA67AAJAqwACIR6YSnuNU1_vcXuQPQQ", "document"),
    ("summary", "جرائم حزب البعث", "ch1", None, "ملخص جرائم حزب البعث - الفصل الأول", None, "BQACAgIAAxkBAAIQCGrTnUQAAUfBzeyT7QQSwunz5FsaTQACKKwAAg1AmUrCHBjDf_p_bT0E", "document"),
    ("summary", "جرائم حزب البعث", "ch2", None, "ملخص جرائم حزب البعث - الفصل الثاني", None, "BQACAgIAAxkBAAIQCWrTnUSKwnnMiElZ8WQVuQABPVVnkAACO6wAAg1AmUo_ixVH5We0yz0E", "document"),
    ("summary", "جرائم حزب البعث", "ch3", None, "ملخص جرائم حزب البعث - الفصل الثالث", None, "BQACAgIAAxkBAAIQCmrTnUSvIK6_i5Zqkli1JwfGMQ8uAAI_rAACDUCZSsNsVQWP8eSCPQQ", "document"),
    ("summary", "كيمياء", "ch1", None, "ملخص كيمياء - الفصل الأول", None, "BQACAgIAAxkBAAIQm2rTuULfkWDX5yGqlbbBRQ3WGKPiAAJorQACDUCZSoW8OcPRWm1oPQQ", "document"),
    ("summary", "كيمياء", "ch2", None, "ملخص كيمياء - الفصل الثاني", None, "BQACAgIAAxkBAAIQnGrTuUIUyTSiWzG9bRS9NIHHgf-tAAJrrQACDUCZShDZUd_OdCexPQQ", "document"),
    ("summary", "كيمياء", "ch3", None, "ملخص كيمياء - الفصل الثالث", None, "BQACAgIAAxkBAAIQnWrTuULRRfjFZqLYGFXKoEwCNxDiAAJwrQACDUCZSqKDWnWlR5nnPQQ", "document"),
    ("question", "أحياء", "ch1", "m1", "أسئلة الفصل الأول - الشهر الأول - أحياء", None, "AgACAgIAAx0CWg6CuwACAsJq31Pc46xLbs9xC3NWu4SP6GiL2AACtydrG7xk8EoggmtM2Hxj3QEAAwIAA3kAAz0E", "photo"),
    ("question", "كيمياء", "ch1", "m1", "أسئلة الفصل الأول - الشهر الأول - كيمياء", None, "AgACAgIAAx0CWg6CuwACArlq3yEqfkfewaya0k4wQzd8aQABiwsAAsMnaxu8ZPBKZPsIEPypHHcBAAMCAAN5AAM9BA", "photo"),
]

OWNER_ACTIONS = {
    "🛠 لوحة المالك": ("panel",),
    "🏠 القائمة الرئيسية": ("home",),
    "🆔 جميع الـ IDs": ("ids",),
    "📊 الإحصائيات": ("stats",),
    "⚙️ تشغيل/إيقاف الاشتراك": ("subtoggle",),
    PAUSE_ON: ("pause",),
    PAUSE_OFF: ("pause",),
    "➕ إضافة ملف": ("flow", "addfile"),
    "🆔 إضافة ملف بـ ID": ("flow", "addfile"),
    "➕ إضافة اسئلة": ("flow", "addquestion"),
    "➕ إضافة ملخصات": ("flow", "addsummary"),
    "➕ إضافة قسم جديد": ("flow", "addsection"),
    "🧩 تعديل الأزرار": ("flow", "edit"),
    "✏️ تعديل ملف": ("flow", "editfile"),
    "🔁 استبدال ملف": ("flow", "replacefile"),
    "🗑 حذف ملف": ("flow", "deletefile"),
    "👁 إخفاء/إظهار ملف": ("flow", "togglefile"),
    "➕ إضافة مادة": ("flow", "addsubject"),
    "✏️ تعديل مادة": ("flow", "editsubject"),
    "🗑 حذف مادة": ("flow", "delsubject"),
    "🗑 حذف قسم": ("flow", "delsection"),
    "🔎 التعرف على ID": ("flow", "identify"),
    "🔗 إنشاء رابط": ("flow", "genlink"),
    "📝 تعديل الوصف": ("flow", "footer"),
    "📣 تغيير القناة": ("flow", "channel"),
    "📢 إعلان": ("flow", "broadcast"),
    "👥 إدارة المشرفين": ("flow", "admins"),
}
OWNER_ONLY = {"📢 إعلان", "👥 إدارة المشرفين", PAUSE_ON, PAUSE_OFF}

FLOW_FIRST = {
    "addfile": "target", "addquestion": "qsec", "addsummary": "subj", "addsection": "cname",
    "addsubject": "sname", "editsubject": "subj", "delsubject": "subj", "delsection": "csec",
    "editfile": "file", "replacefile": "file", "deletefile": "file", "togglefile": "file",
    "identify": "wait", "genlink": "file", "footer": "ftext", "channel": "ctext",
    "broadcast": "btext", "admins": "amenu", "edit": "root",
}

BACK_STEP = {
    "node": "root", "blist": "node", "bnode": "blist", "bnew": "node", "bcolor": "node",
    "bname": "bnode", "color": "bnode", "content": "bnode", "input": "node",
}

# ============================================================
# قاعدة البيانات
# ============================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, joined TEXT, blocked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY, added TEXT);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
    emoji TEXT NOT NULL DEFAULT '📚', color TEXT NOT NULL DEFAULT 'success',
    stype TEXT NOT NULL DEFAULT 'ch', pos INTEGER NOT NULL DEFAULT 0,
    visible INTEGER NOT NULL DEFAULT 1, hidden TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS csections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
    emoji TEXT NOT NULL DEFAULT '📁', color TEXT NOT NULL DEFAULT 'success',
    pos INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1,
    message TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS cbuttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ptype TEXT NOT NULL, pid INTEGER NOT NULL,
    name TEXT NOT NULL, color TEXT NOT NULL DEFAULT 'success',
    pos INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cbutton_id INTEGER NOT NULL REFERENCES cbuttons(id) ON DELETE CASCADE,
    ctype TEXT NOT NULL, body TEXT, file_id TEXT, pos INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, section TEXT, month TEXT, title TEXT NOT NULL,
    teacher TEXT, file_id TEXT UNIQUE NOT NULL, ftype TEXT NOT NULL DEFAULT 'document',
    visible INTEGER NOT NULL DEFAULT 1, created TEXT);
CREATE INDEX IF NOT EXISTS ix_files_subject ON files(subject_id, kind, section, month);
CREATE INDEX IF NOT EXISTS ix_cbuttons_parent ON cbuttons(ptype, pid);
CREATE INDEX IF NOT EXISTS ix_content_button ON content(cbutton_id);
"""

DB = sqlite3.connect(DB_FILE, check_same_thread=False)
DB.row_factory = sqlite3.Row
DB.execute("PRAGMA foreign_keys=ON")
DB.execute("PRAGMA journal_mode=WAL")
DB.execute("PRAGMA synchronous=NORMAL")
SETTINGS = {}


def q(sql, p=()):
    return DB.execute(sql, p).fetchall()


def q1(sql, p=()):
    return DB.execute(sql, p).fetchone()


def x(sql, p=()):
    cur = DB.execute(sql, p)
    DB.commit()
    return cur


def now():
    return datetime.now().isoformat(timespec="seconds")


def setting(key, default=""):
    v = SETTINGS.get(key)
    return default if v is None else v


def set_setting(key, value):
    x(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    SETTINGS[key] = value


def init_db():
    DB.executescript(SCHEMA)
    for key, value in (("channel", DEFAULT_CHANNEL), ("sub_on", "1"), ("bot_on", "1"), ("footer", DEFAULT_FOOTER)):
        x("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, value))
    if not q1("SELECT 1 FROM settings WHERE key='seed_v2'"):
        for i, (name, emoji, color, stype) in enumerate(SUBJECTS, 1):
            x("INSERT OR IGNORE INTO subjects(name, emoji, color, stype, pos) VALUES(?, ?, ?, ?, ?)",
              (name, emoji, color, stype, i))
        for kind, subject, section, month, title, teacher, fid, ftype in SEED_FILES:
            s = q1("SELECT id FROM subjects WHERE name=?", (subject,))
            if s:
                x(
                    "INSERT OR IGNORE INTO files(subject_id, kind, section, month, title, teacher, file_id, ftype, created) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (s["id"], kind, section, month, title, teacher, fid, ftype, now()),
                )
        set_setting("seed_v2", "1")
    SETTINGS.update({r["key"]: r["value"] for r in q("SELECT key, value FROM settings")})
    log.info("Database ready.")


# ============================================================
# مساعدات عامة
# ============================================================

SUB_CACHE = {}


def is_staff(uid):
    return uid == OWNER_ID or q1("SELECT 1 FROM admins WHERE user_id=?", (uid,)) is not None


def upsert_user(uid):
    x("INSERT OR IGNORE INTO users(user_id, joined) VALUES(?, ?)", (uid, now()))


def subject_label(s):
    return f"{s['emoji']} {s['name']}"


def csec_label(c):
    return f"{c['emoji']} {c['name']}"


def label_of_subject(text):
    for s in q("SELECT * FROM subjects ORDER BY pos, id"):
        if subject_label(s) == text:
            return s
    return None


def hidden_set(raw):
    return {h for h in (raw or "").split(",") if h}


def pair(items):
    return [items[i:i + 2] for i in range(0, len(items), 2)]


def kb(rows):
    out = []
    for row in rows:
        line = []
        for item in row:
            text, style = item if isinstance(item, tuple) else (item, "success")
            line.append(KeyboardButton(text, style=style))
        out.append(line)
    return ReplyKeyboardMarkup(out, resize_keyboard=True, is_persistent=True)


def style_for(label):
    return "danger" if any(w in label for w in ("حذف", "رجوع", "إلغاء")) else "primary"


def share_markup(token, label="📤 مشاركة الملف"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        label,
        switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
            query=token, allow_user_chats=True, allow_group_chats=True, allow_channel_chats=True),
        style="success",
    )]])


def gate_markup(token=""):
    ch = setting("channel", DEFAULT_CHANNEL).lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 اشترك بالقناة", url=f"https://t.me/{ch}", style="primary")],
        [InlineKeyboardButton("✅ التحقق من الاشتراك", callback_data=f"chk:{token}", style="primary")],
    ])


def media_payload(msg):
    if msg.photo:
        return msg.photo[-1].file_id, "photo"
    if msg.document:
        return msg.document.file_id, "document"
    return None, None


def media_name(msg):
    if msg.document and msg.document.file_name:
        return msg.document.file_name
    if msg.photo:
        return "صورة"
    return "ملف"


def looks_like_id(text):
    return len(text) >= 20 and re.fullmatch(r"[A-Za-z0-9_\-]+", text) is not None


def ftype_from_id(fid):
    return "photo" if fid.startswith("AgAC") else "document"


def read_file_payload(text, media):
    if media[0]:
        return media
    if looks_like_id(text):
        return text, ftype_from_id(text)
    return None, None


def resolve_file(f, text):
    if text in f.get("map", {}):
        return f["map"][text]
    m = re.match(r"#(\d+)", text)
    if m and q1("SELECT 1 FROM files WHERE id=?", (int(m.group(1)),)):
        return int(m.group(1))
    return None


def insert_file(sid, kind, section, month, title, teacher, fid, ftype):
    try:
        x(
            "INSERT INTO files(subject_id, kind, section, month, title, teacher, file_id, ftype, created) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, kind, section, month, title, teacher, fid, ftype, now()),
        )
        return True, None
    except sqlite3.IntegrityError:
        return False, "هذا الملف موجود مسبقاً."


def insert_content(cbid, ctype, body, fid):
    x(
        "INSERT INTO content(cbutton_id, ctype, body, file_id, pos) VALUES(?, ?, ?, ?, "
        "(SELECT COALESCE(MAX(pos), 0) + 1 FROM content WHERE cbutton_id=?))",
        (cbid, ctype, body, fid, cbid),
    )


def content_step(cbid, text, media):
    if text == DONE:
        return "done"
    if media[0]:
        insert_content(cbid, "photo" if media[1] == "photo" else "document", None, media[0])
        return "added"
    if text.startswith("ID:"):
        fid = text[3:].strip()
        if not looks_like_id(fid):
            return "bad"
        insert_content(cbid, "photo" if ftype_from_id(fid) == "photo" else "document", None, fid)
        return "added"
    if text:
        insert_content(cbid, "text", text, None)
        return "added"
    return "bad"


def build_menu(ctx, items, back=True):
    choices, flat, seen = {}, [], set()
    for label, style, action in items:
        text, n = label[:60], 2
        while text in seen:
            text = f"{label[:55]} ({n})"
            n += 1
        seen.add(text)
        choices[text] = action
        flat.append((text, style))
    rows = pair(flat)
    if back:
        rows.append([(BACK, "danger")])
    ctx.user_data["choices"] = choices
    return kb(rows)


# ============================================================
# شاشات الطالب
# ============================================================

def build_home(ctx, staff):
    items = []
    for s in q("SELECT * FROM subjects WHERE visible=1 ORDER BY pos, id"):
        items.append((subject_label(s), s["color"], ("nav", ("subject", s["id"]))))
    for c in q("SELECT * FROM csections WHERE visible=1 ORDER BY pos, id"):
        items.append((csec_label(c), c["color"], ("nav", ("csec", c["id"]))))
    items.append(("❓ الاسئلة", "primary", ("nav", ("questions",))))
    if staff:
        items.append(("🛠 لوحة المالك", "primary", ("panel",)))
    return HOME_TEXT, build_menu(ctx, items, back=False)


def build_subject(ctx, sid):
    s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
    if not s:
        return "القسم غير متاح حالياً.", build_menu(ctx, [])
    hidden = hidden_set(s["hidden"])
    items = []
    if "book" not in hidden:
        items.append(("📘 الكتب", "success", ("nav", ("list", sid, "book"))))
    if "note" not in hidden:
        items.append(("📙 الملازم", "success", ("nav", ("list", sid, "note"))))
    if "summary" not in hidden:
        items.append(("🧾 الملخصات", "success", ("nav", ("summaries", sid))))
    for b in q("SELECT * FROM cbuttons WHERE ptype='s' AND pid=? AND visible=1 ORDER BY pos, id", (sid,)):
        items.append((b["name"], b["color"], ("content", b["id"])))
    return f"{subject_label(s)}\nاختر:", build_menu(ctx, items)


def build_list(ctx, sid, kind):
    s = q1("SELECT name FROM subjects WHERE id=?", (sid,))
    icon = "📘" if kind == "book" else "📙"
    title = ("📘 الكتب" if kind == "book" else "📙 الملازم") + (f" — {s['name']}" if s else "")
    items = []
    for r in q("SELECT * FROM files WHERE subject_id=? AND kind=? AND visible=1 ORDER BY id", (sid, kind)):
        name = r["teacher"] if kind == "note" and r["teacher"] else r["title"]
        items.append((f"{icon} {name}", "success", ("file", r["id"])))
    if not items:
        title += "\nلا توجد ملفات حالياً."
    return title, build_menu(ctx, items)


def build_summaries(ctx, sid):
    s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
    labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
    items = [(v, "success", ("summ", sid, k)) for k, v in labels.items()]
    return f"🧾 الملخصات — {s['name']}\nاختر:", build_menu(ctx, items)


def build_csec(ctx, cid):
    c = q1("SELECT * FROM csections WHERE id=?", (cid,))
    if not c:
        return "القسم غير متاح حالياً.", build_menu(ctx, [])
    buttons = q("SELECT * FROM cbuttons WHERE ptype='c' AND pid=? AND visible=1 ORDER BY pos, id", (cid,))
    if not buttons:
        return (c["message"] or "لا يوجد محتوى حالياً."), build_menu(ctx, [])
    items = [(b["name"], b["color"], ("content", b["id"])) for b in buttons]
    return f"{csec_label(c)}\nاختر:", build_menu(ctx, items)


def build_questions(ctx):
    items = []
    for key, label in Q_SECTIONS.items():
        action = ("nav", ("qmonths", key)) if key in Q_NEEDS_MONTH else ("nav", ("qsubs", key, None))
        items.append((label, "primary", action))
    return "❓ الاسئلة\nاختر:", build_menu(ctx, items)


def build_qmonths(ctx, sec):
    items = [(label, "primary", ("nav", ("qsubs", sec, key))) for key, label in Q_MONTHS.items()]
    return f"❓ {Q_SECTIONS[sec]}\nاختر الشهر:", build_menu(ctx, items)


def build_qsubs(ctx, sec, month):
    items = [(subject_label(s), s["color"], ("qans", sec, month, s["id"]))
             for s in q("SELECT * FROM subjects WHERE visible=1 ORDER BY pos, id")]
    title = Q_SECTIONS[sec] + (f" — {Q_MONTHS[month]}" if month else "")
    return f"❓ {title}\nاختر المادة:", build_menu(ctx, items)


async def render(chat, ctx, screen, uid):
    staff = is_staff(uid)
    k = screen[0]
    if k == "subject":
        text, markup = build_subject(ctx, screen[1])
    elif k == "list":
        text, markup = build_list(ctx, screen[1], screen[2])
    elif k == "summaries":
        text, markup = build_summaries(ctx, screen[1])
    elif k == "csec":
        text, markup = build_csec(ctx, screen[1])
    elif k == "questions":
        text, markup = build_questions(ctx)
    elif k == "qmonths":
        text, markup = build_qmonths(ctx, screen[1])
    elif k == "qsubs":
        text, markup = build_qsubs(ctx, screen[1], screen[2])
    else:
        screen = ("home",)
        text, markup = build_home(ctx, staff)
    ctx.user_data["screen"] = screen
    await ctx.bot.send_message(chat, text, reply_markup=markup)


def parent_of(screen):
    k = screen[0]
    if k in ("list", "summaries"):
        return ("subject", screen[1])
    if k == "qmonths":
        return ("questions",)
    if k == "qsubs":
        return ("qmonths", screen[1]) if screen[2] else ("questions",)
    return ("home",)


async def send_file(ctx, chat, row_id, uid):
    row = q1("SELECT * FROM files WHERE id=?", (row_id,))
    if not row or (not row["visible"] and not is_staff(uid)):
        await ctx.bot.send_message(chat, "الملف غير متاح حالياً.")
        return
    head = row["teacher"] if row["kind"] == "note" and row["teacher"] else row["title"]
    footer = setting("footer", DEFAULT_FOOTER)
    caption = (f"{head}\n\n{footer}" if footer else head)[:1024]
    markup = share_markup(f"f{row['id']}")
    try:
        if row["ftype"] == "photo":
            await ctx.bot.send_photo(chat, row["file_id"], caption=caption, reply_markup=markup)
        else:
            await ctx.bot.send_document(chat, row["file_id"], caption=caption, reply_markup=markup)
    except TelegramError as e:
        log.error("Send failed for file %s: %s", row["id"], e)
        await ctx.bot.send_message(chat, "تعذر إرسال الملف. أبلغ المالك.")


async def send_content(ctx, chat, cbid):
    items = q("SELECT * FROM content WHERE cbutton_id=? ORDER BY pos, id", (cbid,))
    if not items:
        await ctx.bot.send_message(chat, "لا يوجد محتوى حالياً.")
        return
    footer = setting("footer", DEFAULT_FOOTER)
    cap = footer[:1024] if footer else None
    for it in items:
        try:
            if it["ctype"] == "text":
                await ctx.bot.send_message(chat, it["body"])
            elif it["ctype"] == "photo":
                await ctx.bot.send_photo(chat, it["file_id"], caption=cap)
            else:
                await ctx.bot.send_document(chat, it["file_id"], caption=cap)
        except TelegramError as e:
            log.error("Content send failed for item %s: %s", it["id"], e)
    await ctx.bot.send_message(chat, "📤 يمكنك مشاركة هذا المحتوى:",
                               reply_markup=share_markup(f"c{cbid}", "📤 مشاركة المحتوى"))


async def send_question_items(ctx, chat, sec, month, sid, uid):
    rows = q(
        "SELECT id FROM files WHERE kind='question' AND section=? AND subject_id=? AND month IS ? AND visible=1 ORDER BY id",
        (sec, sid, month),
    )
    if not rows:
        await ctx.bot.send_message(chat, "سيتم إضافة الأسئلة لاحقاً.")
        return
    for r in rows:
        await send_file(ctx, chat, r["id"], uid)


async def send_summary_items(ctx, chat, sid, sec, uid):
    rows = q(
        "SELECT id FROM files WHERE kind='summary' AND subject_id=? AND section=? AND visible=1 ORDER BY id",
        (sid, sec),
    )
    if not rows:
        await ctx.bot.send_message(chat, "سيتم إضافة الملخصات لاحقاً.")
        return
    for r in rows:
        await send_file(ctx, chat, r["id"], uid)


async def do_action(chat, ctx, action, uid):
    k = action[0]
    if k == "nav":
        await render(chat, ctx, action[1], uid)
    elif k == "file":
        await send_file(ctx, chat, action[1], uid)
    elif k == "content":
        await send_content(ctx, chat, action[1])
    elif k == "qans":
        await send_question_items(ctx, chat, action[1], action[2], action[3], uid)
    elif k == "summ":
        await send_summary_items(ctx, chat, action[1], action[2], uid)
    elif k == "panel":
        await open_panel(chat, ctx, uid == OWNER_ID)


async def deliver(ctx, chat, token, uid):
    if not re.fullmatch(r"[fc]\d+", token or ""):
        return
    if token[0] == "f":
        await send_file(ctx, chat, int(token[1:]), uid)
    else:
        await send_content(ctx, chat, int(token[1:]))


# ============================================================
# الاشتراك الإجباري
# ============================================================

async def is_member(bot, uid):
    if is_staff(uid) or setting("sub_on") != "1":
        return True
    if SUB_CACHE.get(uid, 0) > time.time():
        return True
    try:
        member = await bot.get_chat_member(setting("channel", DEFAULT_CHANNEL), uid)
    except TelegramError as e:
        log.warning("Subscription check failed: %s", e)
        return False
    ok = member.status in ("member", "administrator", "creator")
    if ok:
        SUB_CACHE[uid] = time.time() + SUB_CACHE_SECONDS
    return ok


# ============================================================
# لوحة المالك
# ============================================================

def owner_markup(is_owner):
    pause = PAUSE_OFF if setting("bot_on") == "0" else PAUSE_ON
    rows = [
        [("➕ إضافة ملف", "success"), ("🆔 إضافة ملف بـ ID", "success")],
        [("➕ إضافة اسئلة", "success"), ("➕ إضافة ملخصات", "success")],
        [("➕ إضافة قسم جديد", "success"), ("🧩 تعديل الأزرار", "success")],
        [("✏️ تعديل ملف", "success"), ("🔁 استبدال ملف", "success")],
        [("🗑 حذف ملف", "danger"), ("👁 إخفاء/إظهار ملف", "primary")],
        [("➕ إضافة مادة", "success"), ("✏️ تعديل مادة", "success")],
        [("🗑 حذف مادة", "danger"), ("🗑 حذف قسم", "danger")],
        [("🆔 جميع الـ IDs", "primary"), ("🔎 التعرف على ID", "primary")],
        [("🔗 إنشاء رابط", "success"), ("📊 الإحصائيات", "primary")],
        [("📝 تعديل الوصف", "primary"), ("📣 تغيير القناة", "primary")],
        [("⚙️ تشغيل/إيقاف الاشتراك", "primary")],
    ]
    if is_owner:
        rows.append([("📢 إعلان", "primary"), (pause, "primary")])
        rows.append([("👥 إدارة المشرفين", "primary")])
    rows.append([("🏠 القائمة الرئيسية", "danger")])
    return kb(rows)


async def open_panel(chat, ctx, is_owner):
    ctx.user_data.pop("flow", None)
    await ctx.bot.send_message(chat, "🛠 لوحة المالك", reply_markup=owner_markup(is_owner))


def send_all_ids_lines():
    lines = []
    for r in q("SELECT f.*, s.name AS sn FROM files f LEFT JOIN subjects s ON s.id=f.subject_id ORDER BY f.id"):
        parts = [r["sn"] or "-", KIND_NAMES.get(r["kind"], r["kind"])]
        if r["section"]:
            parts.append(CH_LABELS.get(r["section"]) or UNIT_LABELS.get(r["section"]) or Q_SECTIONS.get(r["section"], ""))
        if r["month"]:
            parts.append(Q_MONTHS.get(r["month"], ""))
        name = r["teacher"] if r["kind"] == "note" and r["teacher"] else r["title"]
        lines.append(f"#{r['id']} | " + " | ".join(html.escape(p) for p in parts if p)
                     + f" | {html.escape(name)}\n<code>{r['file_id']}</code>")
    for it in q(
        "SELECT ct.*, cb.name AS bn, COALESCE(sj.name, cs.name) AS pn FROM content ct "
        "JOIN cbuttons cb ON cb.id=ct.cbutton_id "
        "LEFT JOIN subjects sj ON cb.ptype='s' AND sj.id=cb.pid "
        "LEFT JOIN csections cs ON cb.ptype='c' AND cs.id=cb.pid "
        "WHERE ct.ctype<>'text' ORDER BY ct.id"
    ):
        lines.append(f"C#{it['id']} | محتوى | {html.escape(it['pn'] or '-')} | {html.escape(it['bn'])}\n"
                     f"<code>{it['file_id']}</code>")
    return lines


async def send_all_ids(chat, ctx, is_owner):
    lines = send_all_ids_lines()
    if not lines:
        await ctx.bot.send_message(chat, "لا توجد ملفات.", reply_markup=owner_markup(is_owner))
        return
    chunk = ""
    for line in lines:
        block = line + "\n\n"
        if len(chunk) + len(block) > 3500:
            await ctx.bot.send_message(chat, chunk, parse_mode=ParseMode.HTML)
            chunk = ""
        chunk += block
    if chunk.strip():
        await ctx.bot.send_message(chat, chunk, parse_mode=ParseMode.HTML, reply_markup=owner_markup(is_owner))


async def send_stats(chat, ctx, is_owner):
    def count(sql, p=()):
        return q1(sql, p)[0]

    text = (
        "📊 الإحصائيات\n\n"
        f"المستخدمون: {count('SELECT COUNT(*) FROM users')}\n"
        f"المحظورون: {count('SELECT COUNT(*) FROM users WHERE blocked=1')}\n"
        f"المشرفون: {count('SELECT COUNT(*) FROM admins')}\n"
        f"المواد الظاهرة: {count('SELECT COUNT(*) FROM subjects WHERE visible=1')}\n"
        f"الأقسام الجديدة: {count('SELECT COUNT(*) FROM csections')}\n"
        f"الكتب: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('book',))}\n"
        f"الملازم: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('note',))}\n"
        f"الملخصات: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('summary',))}\n"
        f"الأسئلة: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('question',))}\n"
        f"الملفات المخفية: {count('SELECT COUNT(*) FROM files WHERE visible=0')}"
    )
    await ctx.bot.send_message(chat, text, reply_markup=owner_markup(is_owner))


async def do_broadcast(ctx, text):
    ok = fail = 0
    for u in q("SELECT user_id FROM users WHERE blocked=0"):
        try:
            await ctx.bot.send_message(u["user_id"], text)
            ok += 1
        except Forbidden:
            fail += 1
            x("UPDATE users SET blocked=1 WHERE user_id=?", (u["user_id"],))
        except TelegramError:
            fail += 1
        await asyncio.sleep(0.05)
    return ok, fail


async def run_owner_action(msg, ctx, uid, text):
    chat, is_owner = msg.chat_id, uid == OWNER_ID
    spec = OWNER_ACTIONS[text]
    ctx.user_data.pop("flow", None)
    k = spec[0]
    if k == "panel":
        await open_panel(chat, ctx, is_owner)
    elif k == "home":
        await render(chat, ctx, ("home",), uid)
    elif k == "ids":
        await send_all_ids(chat, ctx, is_owner)
    elif k == "stats":
        await send_stats(chat, ctx, is_owner)
    elif k == "subtoggle":
        set_setting("sub_on", "0" if setting("sub_on") == "1" else "1")
        SUB_CACHE.clear()
        status = "مفعّل" if setting("sub_on") == "1" else "معطّل"
        await msg.reply_text(f"الاشتراك الإجباري الآن: {status}", reply_markup=owner_markup(is_owner))
    elif k == "pause":
        set_setting("bot_on", "0" if setting("bot_on") == "1" else "1")
        status = "يعمل" if setting("bot_on") == "1" else "تحت الصيانة"
        await msg.reply_text(f"البوت الآن: {status}", reply_markup=owner_markup(is_owner))
    elif k == "flow":
        await start_flow(chat, ctx, spec[1])


# ============================================================
# محرك التدفقات (إضافة ملفات، تعديل، حذف، إعدادات، المحرر)
# ============================================================

async def flow_prompt(chat, ctx):
    f = ctx.user_data["flow"]
    text, rows = flow_build(f)
    rows = list(rows) + [[(CANCEL, "danger")]]
    await ctx.bot.send_message(chat, text, reply_markup=kb(rows))


async def goto(chat, ctx, step):
    ctx.user_data["flow"]["step"] = step
    await flow_prompt(chat, ctx)


async def start_flow(chat, ctx, typ, **extra):
    ctx.user_data["flow"] = {"type": typ, "step": FLOW_FIRST[typ], **extra}
    await flow_prompt(chat, ctx)


def file_choice_rows(f):
    f["map"] = {}
    rows = []
    for r in q("SELECT * FROM files ORDER BY id"):
        label = f"#{r['id']} {r['title']}"[:60]
        f["map"][label] = r["id"]
        rows.append([(label, "success")])
    return rows


def editor_root(f):
    f["map"], items = {}, []
    for s in q("SELECT * FROM subjects ORDER BY pos, id"):
        f["map"][subject_label(s)] = ("s", s["id"])
        items.append((subject_label(s), s["color"]))
    for c in q("SELECT * FROM csections ORDER BY pos, id"):
        f["map"][csec_label(c)] = ("c", c["id"])
        items.append((csec_label(c), c["color"]))
    return "🧩 اختر المادة أو القسم:", pair(items)


def editor_node(f):
    if f["kind"] == "s":
        s = q1("SELECT * FROM subjects WHERE id=?", (f["id"],))
        hidden = hidden_set(s["hidden"])
        title = subject_label(s)
        f["opts"] = {}
        for key, name in (("book", "📘 الكتب"), ("note", "📙 الملازم"), ("summary", "🧾 الملخصات")):
            f["opts"][f"{name}: {'مخفي' if key in hidden else 'ظاهر'}"] = ("tog", key)
        f["opts"]["➕ زر جديد داخل المادة"] = ("newbtn",)
        f["opts"]["🗂 الأزرار الإضافية"] = ("blist",)
    else:
        c = q1("SELECT * FROM csections WHERE id=?", (f["id"],))
        title = csec_label(c)
        f["opts"] = {
            "✏️ اسم القسم": ("field", "name"),
            "😀 إيموجي القسم": ("field", "emoji"),
            "📝 رسالة القسم": ("field", "message"),
            "👁 إظهار/إخفاء القسم": ("tvis",),
            "➕ زر جديد داخل القسم": ("newbtn",),
            "🗂 الأزرار الداخلية": ("blist",),
            "🗑 حذف القسم": ("delnode",),
        }
    items = [(label, style_for(label)) for label in f["opts"]]
    rows = pair(items) + [[(BACK, "danger")]]
    return f"⚙️ {title}\nاختر:", rows


def editor_blist(f):
    f["map"], items = {}, []
    for b in q("SELECT * FROM cbuttons WHERE ptype=? AND pid=? ORDER BY pos, id", (f["kind"], f["id"])):
        label = b["name"] if b["visible"] else f"🙈 {b['name']}"
        f["map"][label] = b["id"]
        items.append((label, b["color"]))
    text = "🗂 الأزرار الداخلية:" if items else "🗂 لا توجد أزرار داخلية بعد."
    return text, pair(items) + [[(BACK, "danger")]]


def editor_bnode(f):
    b = q1("SELECT * FROM cbuttons WHERE id=?", (f["bid"],))
    if not b:
        return "الزر غير موجود.", [[(BACK, "danger")]]
    f["opts"] = {
        "✏️ اسم الزر": ("bname",),
        "🎨 لون الزر": ("color",),
        "👁 إظهار/إخفاء الزر": ("tbtn",),
        "📥 إضافة محتوى": ("content",),
        "🧹 حذف المحتوى": ("clear",),
        "🗑 حذف الزر": ("delb",),
    }
    items = [(label, style_for(label)) for label in f["opts"]]
    return f"🔘 {b['name']}\nاختر:", pair(items) + [[(BACK, "danger")]]


def flow_build(f):
    t, step = f["type"], f["step"]

    if step == "target":
        f["map"], items = {}, []
        for s in q("SELECT * FROM subjects ORDER BY pos, id"):
            f["map"][subject_label(s)] = ("s", s["id"])
            items.append((subject_label(s), s["color"]))
        for c in q("SELECT * FROM csections ORDER BY pos, id"):
            f["map"][csec_label(c)] = ("c", c["id"])
            items.append((csec_label(c), c["color"]))
        return "اختر المادة أو القسم:", pair(items)

    if step == "cbtn":
        f["map"], items = {}, []
        for b in q("SELECT * FROM cbuttons WHERE ptype='c' AND pid=? ORDER BY pos, id", (f["cid"],)):
            f["map"][b["name"]] = b["id"]
            items.append((b["name"], b["color"]))
        return "اختر الزر داخل القسم:", pair(items)

    if step == "kind":
        return "اختر النوع:", [[("📘 كتاب", "success"), ("📙 ملزمة", "success")]]

    if step == "payload":
        if f.get("mode") == "content":
            text = "أرسل المحتوى: نص أو صورة أو ملف.\nلـ ID اكتب ID: ثم الـ ID.\nأرسل التالي، ثم اضغط تم."
        else:
            text = "أرسل الملف أو الصورة، أو أرسل الـ ID كنص."
        if f.get("loop"):
            return text, [[(DONE, "success")]]
        return text, []

    if step == "title":
        return "أرسل اسم الملف:", []

    if step == "teacher":
        return "أرسل اسم الأستاذ، أو اضغط تخطي:", [[(SKIP, "primary")]]

    if step == "qsec":
        return "اختر القسم:", pair([(v, "primary") for v in Q_SECTIONS.values()])

    if step == "qmonth":
        return "اختر الشهر:", [[(v, "primary") for v in Q_MONTHS.values()]]

    if step == "subj":
        return "اختر المادة:", pair([(subject_label(s), s["color"])
                                      for s in q("SELECT * FROM subjects ORDER BY pos, id")])

    if step == "ssec":
        s = q1("SELECT * FROM subjects WHERE id=?", (f["sid"],))
        labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
        return "اختر الفصل أو الوحدة:", pair([(v, "primary") for v in labels.values()])

    if step == "cname":
        return "أرسل اسم القسم الجديد:", []

    if step == "cemoji":
        return "أرسل إيموجي القسم:", []

    if step == "cmsg":
        return "أرسل الرسالة التي تظهر للطالب إذا كان القسم فارغاً، أو اضغط تخطي:", [[(SKIP, "primary")]]

    if step == "ccolor":
        return "اختر لون القسم والأزرار الجديدة فيه:", [COLOR_ROW]

    if step == "cbtns":
        listed = "\n".join(f"- {n}" for n in f["buttons"]) or "لا يوجد بعد"
        return f"أرسل اسم زر داخل القسم، وعند الانتهاء اضغط تم.\nالأزرار:\n{listed}", [[(DONE, "success")]]

    if step == "sname":
        return "أرسل اسم المادة الجديدة:", []

    if step == "semoji":
        return "أرسل إيموجي المادة:", []

    if step == "stype":
        return "اختر نوع المادة:", [[("📘 فصول", "success"), ("📗 وحدات", "success")]]

    if step == "sfield":
        return "اختر ما تريد تعديله:", [[("✏️ الاسم", "success"), ("😀 الإيموجي", "success")]]

    if step == "svalue":
        return "أرسل القيمة الجديدة:", []

    if step == "file":
        return "اختر الملف، أو أرسل رقمه مثل #12:", file_choice_rows(f)

    if step == "ffield":
        return "اختر ما تريد تعديله:", [[("✏️ الاسم", "success"), ("👨‍🏫 الأستاذ", "success")]]

    if step == "fvalue":
        rows = [[(SKIP, "primary")]] if f.get("col") == "teacher" else []
        return "أرسل القيمة الجديدة:", rows

    if step == "confirm":
        return "هل تؤكد هذه العملية؟", [[(CONFIRM, "danger")]]

    if step == "csec":
        f["map"], items = {}, []
        for c in q("SELECT * FROM csections ORDER BY pos, id"):
            f["map"][csec_label(c)] = c["id"]
            items.append((csec_label(c), c["color"]))
        return "اختر القسم:", pair(items)

    if step == "wait":
        return "أرسل أي ملف أو صورة لأستخرج الـ ID:", []

    if step == "ftext":
        return f"الوصف الحالي:\n\n{setting('footer')}\n\nأرسل الوصف الجديد:", [[("🗑 حذف الوصف", "danger")]]

    if step == "ctext":
        return "أرسل معرف القناة مثل @Channel:", []

    if step == "btext":
        return "أرسل نص الإعلان:", []

    if step == "amenu":
        return "👥 إدارة المشرفين", [
            [("➕ إضافة مشرف", "success"), ("🗑 حذف مشرف", "danger")],
            [("📋 قائمة المشرفين", "primary")],
        ]

    if step == "aid":
        return "أرسل Telegram ID للمشرف الجديد:", []

    if step == "apick":
        f["map"], items = {}, []
        for a in q("SELECT user_id FROM admins"):
            items.append((f"#{a['user_id']}", "danger"))
        return "اختر المشرف للحذف:", pair(items)

    # ----- المحرر -----
    if step == "root":
        return editor_root(f)

    if step == "node":
        return editor_node(f)

    if step == "blist":
        return editor_blist(f)

    if step == "bnode":
        return editor_bnode(f)

    if step == "bnew":
        return "أرسل اسم الزر الجديد:", []

    if step == "bcolor":
        return "اختر لون الزر الجديد:", [COLOR_ROW]

    if step == "bname":
        return "أرسل الاسم الجديد للزر:", []

    if step == "color":
        return "اختر اللون الجديد:", [COLOR_ROW]

    if step == "content":
        return "📥 أرسل المحتوى: نص أو صورة أو ملف، أو ID: ثم الـ ID.\nبعد الانتهاء اضغط تم.", [[(DONE, "success")]]

    if step == "input":
        return "أرسل القيمة الجديدة:", []

    return "اختر من الأزرار:", []


async def fail(msg, ctx, hint):
    await msg.reply_text(hint)
    await flow_prompt(msg.chat_id, ctx)


async def finish(msg, ctx, text, uid):
    ctx.user_data.pop("flow", None)
    await msg.reply_text(text, reply_markup=owner_markup(uid == OWNER_ID))


def run_do(do):
    k = do[0]
    if k == "delsub":
        x("DELETE FROM cbuttons WHERE ptype='s' AND pid=?", (do[1],))
        x("DELETE FROM subjects WHERE id=?", (do[1],))
    elif k == "delcs":
        x("DELETE FROM cbuttons WHERE ptype='c' AND pid=?", (do[1],))
        x("DELETE FROM csections WHERE id=?", (do[1],))
    elif k == "delfile":
        x("DELETE FROM files WHERE id=?", (do[1],))
    elif k == "deladmin":
        x("DELETE FROM admins WHERE user_id=?", (do[1],))
    elif k == "footer":
        set_setting("footer", do[1])
    elif k == "delb":
        x("DELETE FROM cbuttons WHERE id=?", (do[1],))
    elif k == "clearc":
        x("DELETE FROM content WHERE cbutton_id=?", (do[1],))


async def h_confirm(msg, ctx, uid, f, text):
    if text != CONFIRM:
        return await fail(msg, ctx, "اضغط ✅ تأكيد أو ❌ إلغاء.")
    run_do(f["do"])
    if f["type"] == "edit":
        f["step"] = f.get("after", "root")
        await msg.reply_text("✅ تم التنفيذ.")
        return await flow_prompt(msg.chat_id, ctx)
    await finish(msg, ctx, "✅ تم التنفيذ.", uid)


async def h_addfile(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "target":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر من الأزرار.")
        kind, tid = f["map"][text]
        if kind == "s":
            f["sid"], f["mode"] = tid, "file"
            return await goto(chat, ctx, "kind")
        f["cid"], f["mode"], f["loop"] = tid, "content", True
        if not q1("SELECT 1 FROM cbuttons WHERE ptype='c' AND pid=?", (tid,)):
            return await finish(msg, ctx, "أضف زراً داخل القسم أولاً من تعديل الأزرار.", uid)
        return await goto(chat, ctx, "cbtn")
    if step == "cbtn":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الزر من الأزرار.")
        f["cbid"] = f["map"][text]
        if f.get("fid"):
            insert_content(f["cbid"], "photo" if f["ftype"] == "photo" else "document", None, f["fid"])
            return await finish(msg, ctx, "✅ تمت الإضافة.", uid)
        return await goto(chat, ctx, "payload")
    if step == "kind":
        k = FILE_KINDS.get(text)
        if not k:
            return await fail(msg, ctx, "اختر النوع من الأزرار.")
        f["kind"] = k
        return await goto(chat, ctx, "title" if f.get("fid") else "payload")
    if step == "payload":
        if f.get("mode") == "content":
            res = content_step(f["cbid"], text, media)
            if res == "done":
                return await finish(msg, ctx, "✅ انتهت الإضافة.", uid)
            if res == "added":
                await msg.reply_text("✅ تمت الإضافة، أرسل التالي أو اضغط تم.")
                return await flow_prompt(chat, ctx)
            return await fail(msg, ctx, "أرسل نصاً أو صورة أو ملفاً، أو ID بعد كلمة ID:")
        fid, ftype = read_file_payload(text, media)
        if not fid:
            return await fail(msg, ctx, "أرسل الملف أو الـ ID.")
        f["fid"], f["ftype"] = fid, ftype
        return await goto(chat, ctx, "title")
    if step == "title":
        if not text:
            return await fail(msg, ctx, "أرسل الاسم كنص.")
        f["title"] = text
        if f["kind"] == "note":
            return await goto(chat, ctx, "teacher")
        ok, err = insert_file(f["sid"], f["kind"], None, None, text, None, f["fid"], f["ftype"])
        return await finish(msg, ctx, "✅ تمت إضافة الملف." if ok else err, uid)
    if step == "teacher":
        teacher = None if text == SKIP else text
        ok, err = insert_file(f["sid"], f["kind"], None, None, f["title"], teacher, f["fid"], f["ftype"])
        return await finish(msg, ctx, "✅ تمت إضافة الملزمة." if ok else err, uid)


async def h_addquestion(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "qsec":
        key = next((k for k, v in Q_SECTIONS.items() if v == text), None)
        if not key:
            return await fail(msg, ctx, "اختر القسم من الأزرار.")
        f["sec"], f["month"] = key, None
        return await goto(chat, ctx, "qmonth" if key in Q_NEEDS_MONTH else "subj")
    if step == "qmonth":
        mk = next((k for k, v in Q_MONTHS.items() if v == text), None)
        if not mk:
            return await fail(msg, ctx, "اختر الشهر من الأزرار.")
        f["month"] = mk
        return await goto(chat, ctx, "subj")
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"], f["loop"] = s["id"], True
        return await goto(chat, ctx, "payload")
    if step == "payload":
        if text == DONE:
            return await finish(msg, ctx, "✅ انتهت الإضافة.", uid)
        fid, ftype = read_file_payload(text, media)
        if not fid:
            return await fail(msg, ctx, "أرسل الملف أو الـ ID، أو اضغط تم.")
        s = q1("SELECT name FROM subjects WHERE id=?", (f["sid"],))
        title = f"أسئلة {Q_SECTIONS[f['sec']]}"
        if f.get("month"):
            title += f" - {Q_MONTHS[f['month']]}"
        title += f" - {s['name']}"
        ok, err = insert_file(f["sid"], "question", f["sec"], f.get("month"), title, None, fid, ftype)
        await msg.reply_text("✅ تمت الإضافة، أرسل التالي أو اضغط تم." if ok else err)
        return await flow_prompt(chat, ctx)


async def h_addsummary(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"] = s["id"]
        return await goto(chat, ctx, "ssec")
    if step == "ssec":
        s = q1("SELECT * FROM subjects WHERE id=?", (f["sid"],))
        labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
        key = next((k for k, v in labels.items() if v == text), None)
        if not key:
            return await fail(msg, ctx, "اختر من الأزرار.")
        f["sec"], f["loop"] = key, True
        return await goto(chat, ctx, "payload")
    if step == "payload":
        if text == DONE:
            return await finish(msg, ctx, "✅ انتهت الإضافة.", uid)
        fid, ftype = read_file_payload(text, media)
        if not fid:
            return await fail(msg, ctx, "أرسل الملف أو الـ ID، أو اضغط تم.")
        s = q1("SELECT * FROM subjects WHERE id=?", (f["sid"],))
        labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
        title = f"ملخص {s['name']} - {labels[f['sec']]}"
        ok, err = insert_file(f["sid"], "summary", f["sec"], None, title, None, fid, ftype)
        await msg.reply_text("✅ تمت الإضافة، أرسل التالي أو اضغط تم." if ok else err)
        return await flow_prompt(chat, ctx)


async def h_addsection(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "cname":
        if not text:
            return await fail(msg, ctx, "أرسل اسم القسم.")
        f["cname"] = text
        return await goto(chat, ctx, "cemoji")
    if step == "cemoji":
        if not text:
            return await fail(msg, ctx, "أرسل إيموجي القسم.")
        f["cemoji"] = text
        return await goto(chat, ctx, "cmsg")
    if step == "cmsg":
        f["cmsg"] = "" if text == SKIP else text
        return await goto(chat, ctx, "ccolor")
    if step == "ccolor":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        f["ccolor"], f["buttons"] = COLORS[text], []
        return await goto(chat, ctx, "cbtns")
    if step == "cbtns":
        if text == DONE:
            try:
                pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM csections")["p"]
                cur = DB.execute(
                    "INSERT INTO csections(name, emoji, color, pos, message) VALUES(?, ?, ?, ?, ?)",
                    (f["cname"], f["cemoji"], f["ccolor"], pos, f["cmsg"]),
                )
                for i, name in enumerate(f["buttons"], 1):
                    DB.execute(
                        "INSERT INTO cbuttons(ptype, pid, name, color, pos) VALUES('c', ?, ?, ?, ?)",
                        (cur.lastrowid, name, f["ccolor"], i),
                    )
                DB.commit()
            except sqlite3.IntegrityError:
                DB.rollback()
                return await finish(msg, ctx, "اسم القسم مستخدم من قبل.", uid)
            return await finish(msg, ctx, f"✅ تم إنشاء القسم: {f['cemoji']} {f['cname']}", uid)
        if not text:
            return await fail(msg, ctx, "أرسل اسم الزر.")
        if text in f["buttons"]:
            return await fail(msg, ctx, "هذا الزر موجود مسبقاً.")
        f["buttons"].append(text)
        return await flow_prompt(chat, ctx)


async def h_addsubject(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "sname":
        if not text:
            return await fail(msg, ctx, "أرسل اسم المادة.")
        f["sname"] = text
        return await goto(chat, ctx, "semoji")
    if step == "semoji":
        if not text:
            return await fail(msg, ctx, "أرسل إيموجي المادة.")
        f["semoji"] = text
        return await goto(chat, ctx, "stype")
    if step == "stype":
        st = {"📘 فصول": "ch", "📗 وحدات": "unit"}.get(text)
        if not st:
            return await fail(msg, ctx, "اختر النوع من الأزرار.")
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM subjects")["p"]
        try:
            x("INSERT INTO subjects(name, emoji, color, stype, pos) VALUES(?, ?, 'success', ?, ?)",
              (f["sname"], f["semoji"], st, pos))
            return await finish(msg, ctx, "✅ تمت إضافة المادة.", uid)
        except sqlite3.IntegrityError:
            return await finish(msg, ctx, "هذه المادة موجودة مسبقاً.", uid)


async def h_editsubject(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"] = s["id"]
        return await goto(chat, ctx, "sfield")
    if step == "sfield":
        col = {"✏️ الاسم": "name", "😀 الإيموجي": "emoji"}.get(text)
        if not col:
            return await fail(msg, ctx, "اختر من الأزرار.")
        f["col"] = col
        return await goto(chat, ctx, "svalue")
    if step == "svalue":
        if not text:
            return await fail(msg, ctx, "أرسل القيمة.")
        try:
            x(f"UPDATE subjects SET {f['col']}=? WHERE id=?", (text, f["sid"]))
        except sqlite3.IntegrityError:
            return await finish(msg, ctx, "هذا الاسم مستخدم من مادة أخرى.", uid)
        return await finish(msg, ctx, "✅ تم التعديل.", uid)


async def h_delsubject(msg, ctx, uid, f, text, media):
    s = label_of_subject(text)
    if not s:
        return await fail(msg, ctx, "اختر المادة من الأزرار.")
    f["do"] = ("delsub", s["id"])
    return await goto(msg.chat_id, ctx, "confirm")


async def h_delsection(msg, ctx, uid, f, text, media):
    if text not in f.get("map", {}):
        return await fail(msg, ctx, "اختر القسم من الأزرار.")
    f["do"] = ("delcs", f["map"][text])
    return await goto(msg.chat_id, ctx, "confirm")


async def h_editfile(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "file":
        rid = resolve_file(f, text)
        if rid is None:
            return await fail(msg, ctx, "اختر الملف من الأزرار أو أرسل رقمه مثل #12.")
        f["rid"] = rid
        return await goto(chat, ctx, "ffield")
    if step == "ffield":
        col = {"✏️ الاسم": "title", "👨‍🏫 الأستاذ": "teacher"}.get(text)
        if not col:
            return await fail(msg, ctx, "اختر من الأزرار.")
        f["col"] = col
        return await goto(chat, ctx, "fvalue")
    if step == "fvalue":
        if f["col"] == "teacher" and text == SKIP:
            value = None
        elif not text:
            return await fail(msg, ctx, "أرسل القيمة.")
        else:
            value = text
        x(f"UPDATE files SET {f['col']}=? WHERE id=?", (value, f["rid"]))
        return await finish(msg, ctx, "✅ تم التعديل.", uid)


async def h_replacefile(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "file":
        rid = resolve_file(f, text)
        if rid is None:
            return await fail(msg, ctx, "اختر الملف من الأزرار.")
        f["rid"] = rid
        return await goto(chat, ctx, "payload")
    if step == "payload":
        fid, ftype = read_file_payload(text, media)
        if not fid:
            return await fail(msg, ctx, "أرسل الملف أو الـ ID.")
        try:
            x("UPDATE files SET file_id=?, ftype=? WHERE id=?", (fid, ftype, f["rid"]))
        except sqlite3.IntegrityError:
            return await finish(msg, ctx, "هذا الملف مستخدم في ملف آخر.", uid)
        return await finish(msg, ctx, "✅ تم استبدال الملف.", uid)


async def h_deletefile(msg, ctx, uid, f, text, media):
    rid = resolve_file(f, text)
    if rid is None:
        return await fail(msg, ctx, "اختر الملف من الأزرار.")
    f["do"] = ("delfile", rid)
    return await goto(msg.chat_id, ctx, "confirm")


async def h_togglefile(msg, ctx, uid, f, text, media):
    rid = resolve_file(f, text)
    if rid is None:
        return await fail(msg, ctx, "اختر الملف من الأزرار.")
    x("UPDATE files SET visible = 1 - visible WHERE id=?", (rid,))
    row = q1("SELECT visible FROM files WHERE id=?", (rid,))
    state = "ظاهر" if row["visible"] else "مخفي"
    return await finish(msg, ctx, f"✅ تم. الحالة الآن: {state}", uid)


async def h_identify(msg, ctx, uid, f, text, media):
    if not media[0]:
        return await fail(msg, ctx, "أرسل ملفاً أو صورة.")
    ctx.user_data["pending"] = media
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(
        "➕ إضافة هذا الملف للبوت", callback_data="idadd", style="success")]])
    await msg.reply_text(
        f"📄 الاسم: {html.escape(media_name(msg))}\n🆔 الـ ID (اضغط عليه للنسخ):\n<code>{media[0]}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=markup,
    )
    return await flow_prompt(msg.chat_id, ctx)


async def h_genlink(msg, ctx, uid, f, text, media):
    rid = resolve_file(f, text)
    if rid is None:
        row = q1("SELECT id FROM files WHERE file_id=?", (text,))
        rid = row["id"] if row else None
    if rid is None:
        return await fail(msg, ctx, "لم أجد هذا الملف. أرسل الـ ID أو رقم الملف.")
    link = f"https://t.me/{msg.get_bot().username}?start=f{rid}"
    return await finish(msg, ctx, f"🔗 رابط الملف:\n{link}", uid)


async def h_footer(msg, ctx, uid, f, text, media):
    if text == "🗑 حذف الوصف":
        f["do"] = ("footer", "")
        return await goto(msg.chat_id, ctx, "confirm")
    if not text:
        return await fail(msg, ctx, "أرسل الوصف الجديد كنص.")
    set_setting("footer", text)
    return await finish(msg, ctx, "✅ تم تحديث الوصف.", uid)


async def h_channel(msg, ctx, uid, f, text, media):
    if not text.startswith("@") or len(text) < 2:
        return await fail(msg, ctx, "الصيغة الصحيحة: @Channel")
    set_setting("channel", text)
    SUB_CACHE.clear()
    return await finish(msg, ctx, "✅ تم تغيير القناة.", uid)


async def h_broadcast(msg, ctx, uid, f, text, media):
    if not text:
        return await fail(msg, ctx, "أرسل نص الإعلان.")
    ok, bad = await do_broadcast(ctx, text)
    return await finish(msg, ctx, f"✅ تم الإرسال.\nنجح: {ok}\nفشل: {bad}", uid)


async def h_admins(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "amenu":
        if text == "➕ إضافة مشرف":
            return await goto(chat, ctx, "aid")
        if text == "🗑 حذف مشرف":
            return await goto(chat, ctx, "apick")
        if text == "📋 قائمة المشرفين":
            listed = "\n".join(f"#{a['user_id']}" for a in q("SELECT user_id FROM admins")) or "لا يوجد مشرفون."
            return await finish(msg, ctx, f"👥 المشرفون:\n{listed}", uid)
        return await fail(msg, ctx, "اختر من الأزرار.")
    if step == "aid":
        if not text.isdigit():
            return await fail(msg, ctx, "أرسل Telegram ID رقمياً.")
        x("INSERT OR IGNORE INTO admins(user_id, added) VALUES(?, ?)", (int(text), now()))
        return await finish(msg, ctx, "✅ تمت إضافة المشرف.", uid)
    if step == "apick":
        m = re.match(r"#(\d+)", text)
        if not m:
            return await fail(msg, ctx, "اختر المشرف من الأزرار.")
        f["do"] = ("deladmin", int(m.group(1)))
        return await goto(chat, ctx, "confirm")


async def h_broadcast_or_channel_placeholder(msg, ctx, uid, f, text, media):
    return await fail(msg, ctx, "اختر من الأزرار.")


async def h_edit(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if text == BACK and step in BACK_STEP:
        return await goto(chat, ctx, BACK_STEP[step])

    if step == "root":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر من الأزرار.")
        f["kind"], f["id"] = f["map"][text]
        return await goto(chat, ctx, "node")

    if step == "node":
        act = f.get("opts", {}).get(text)
        if not act:
            return await fail(msg, ctx, "اختر من الأزرار.")
        k = act[0]
        if k == "tog":
            s = q1("SELECT hidden FROM subjects WHERE id=?", (f["id"],))
            hidden = hidden_set(s["hidden"]) ^ {act[1]}
            x("UPDATE subjects SET hidden=? WHERE id=?", (",".join(sorted(hidden)), f["id"]))
            return await goto(chat, ctx, "node")
        if k == "tvis":
            x("UPDATE csections SET visible = 1 - visible WHERE id=?", (f["id"],))
            return await goto(chat, ctx, "node")
        if k == "newbtn":
            return await goto(chat, ctx, "bnew")
        if k == "blist":
            return await goto(chat, ctx, "blist")
        if k == "field":
            f["field"] = act[1]
            return await goto(chat, ctx, "input")
        if k == "delnode":
            f["do"], f["after"] = ("delcs", f["id"]), "root"
            return await goto(chat, ctx, "confirm")

    if step == "input":
        if not text:
            return await fail(msg, ctx, "أرسل القيمة.")
        col = f["field"]
        try:
            if col == "name":
                x("UPDATE csections SET name=? WHERE id=?", (text, f["id"]))
            elif col == "emoji":
                x("UPDATE csections SET emoji=? WHERE id=?", (text, f["id"]))
            else:
                x("UPDATE csections SET message=? WHERE id=?", (text, f["id"]))
        except sqlite3.IntegrityError:
            return await fail(msg, ctx, "هذا الاسم مستخدم من قسم آخر.")
        return await goto(chat, ctx, "node")

    if step == "bnew":
        if not text:
            return await fail(msg, ctx, "أرسل اسم الزر.")
        f["bname"] = text
        return await goto(chat, ctx, "bcolor")

    if step == "bcolor":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM cbuttons WHERE ptype=? AND pid=?",
                 (f["kind"], f["id"]))["p"]
        x("INSERT INTO cbuttons(ptype, pid, name, color, pos) VALUES(?, ?, ?, ?, ?)",
          (f["kind"], f["id"], f["bname"], COLORS[text], pos))
        await msg.reply_text("✅ تمت إضافة الزر.")
        return await goto(chat, ctx, "node")

    if step == "blist":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الزر من الأزرار.")
        f["bid"] = f["map"][text]
        return await goto(chat, ctx, "bnode")

    if step == "bnode":
        act = f.get("opts", {}).get(text)
        if not act:
            return await fail(msg, ctx, "اختر من الأزرار.")
        k = act[0]
        if k == "bname":
            return await goto(chat, ctx, "bname")
        if k == "color":
            return await goto(chat, ctx, "color")
        if k == "tbtn":
            x("UPDATE cbuttons SET visible = 1 - visible WHERE id=?", (f["bid"],))
            return await goto(chat, ctx, "bnode")
        if k == "content":
            return await goto(chat, ctx, "content")
        if k == "clear":
            f["do"], f["after"] = ("clearc", f["bid"]), "bnode"
            return await goto(chat, ctx, "confirm")
        if k == "delb":
            f["do"], f["after"] = ("delb", f["bid"]), "blist"
            return await goto(chat, ctx, "confirm")

    if step == "bname":
        if not text:
            return await fail(msg, ctx, "أرسل الاسم.")
        x("UPDATE cbuttons SET name=? WHERE id=?", (text, f["bid"]))
        return await goto(chat, ctx, "bnode")

    if step == "color":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        x("UPDATE cbuttons SET color=? WHERE id=?", (COLORS[text], f["bid"]))
        return await goto(chat, ctx, "bnode")

    if step == "content":
        res = content_step(f["bid"], text, media)
        if res == "done":
            return await goto(chat, ctx, "bnode")
        if res == "added":
            await msg.reply_text("✅ تمت الإضافة.")
            return await flow_prompt(chat, ctx)
        return await fail(msg, ctx, "أرسل نصاً أو صورة أو ملفاً، أو ID بعد كلمة ID:")

    return await fail(msg, ctx, "اختر من الأزرار.")


FLOW_HANDLERS = {
    "addfile": h_addfile,
    "addquestion": h_addquestion,
    "addsummary": h_addsummary,
    "addsection": h_addsection,
    "addsubject": h_addsubject,
    "editsubject": h_editsubject,
    "delsubject": h_delsubject,
    "delsection": h_delsection,
    "editfile": h_editfile,
    "replacefile": h_replacefile,
    "deletefile": h_deletefile,
    "togglefile": h_togglefile,
    "identify": h_identify,
    "genlink": h_genlink,
    "footer": h_footer,
    "channel": h_channel,
    "broadcast": h_broadcast,
    "admins": h_admins,
    "edit": h_edit,
}


async def handle_flow(msg, ctx, uid):
    f = ctx.user_data.get("flow")
    if not f:
        return False
    text = (msg.text or "").strip()
    media = media_payload(msg)
    if f["step"] == "confirm":
        await h_confirm(msg, ctx, uid, f, text)
        return True
    handler = FLOW_HANDLERS.get(f["type"])
    if handler is None:
        ctx.user_data.pop("flow", None)
        return False
    await handler(msg, ctx, uid, f, text, media)
    return True


# ============================================================
# أوامر وأحداث البوت
# ============================================================

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user:
        return
    uid = user.id
    upsert_user(uid)
    ctx.user_data.pop("flow", None)
    token = ctx.args[0] if ctx.args else ""
    if not is_staff(uid) and setting("bot_on") == "0":
        await msg.reply_text(MAINT_TEXT)
        return
    if not await is_member(ctx.bot, uid):
        await msg.reply_text(GATE_TEXT, reply_markup=gate_markup(token if re.fullmatch(r"[fc]\d+", token) else ""))
        return
    if re.fullmatch(r"[fc]\d+", token):
        await deliver(ctx, msg.chat_id, token, uid)
    await render(msg.chat_id, ctx, ("home",), uid)


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_staff(user.id):
        await open_panel(update.effective_chat.id, ctx, user.id == OWNER_ID)


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_staff(user.id):
        ctx.user_data.pop("flow", None)
        await update.effective_message.reply_text("تم الإلغاء.", reply_markup=owner_markup(user.id == OWNER_ID))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user or not msg.text:
        return
    uid = user.id
    upsert_user(uid)
    text = msg.text.strip()
    staff, is_owner = is_staff(uid), uid == OWNER_ID

    if not staff and setting("bot_on") == "0":
        await msg.reply_text(MAINT_TEXT)
        return
    if not await is_member(ctx.bot, uid):
        await msg.reply_text(GATE_TEXT, reply_markup=gate_markup())
        return

    if staff:
        if text == CANCEL:
            ctx.user_data.pop("flow", None)
            await msg.reply_text("تم الإلغاء.", reply_markup=owner_markup(is_owner))
            return
        if text in OWNER_ACTIONS:
            if text in OWNER_ONLY and not is_owner:
                await msg.reply_text("هذا الزر للمالك فقط.")
                return
            await run_owner_action(msg, ctx, uid, text)
            return
        if await handle_flow(msg, ctx, uid):
            return

    if text == BACK:
        await render(msg.chat_id, ctx, parent_of(ctx.user_data.get("screen", ("home",))), uid)
        return
    action = (ctx.user_data.get("choices") or {}).get(text)
    if action:
        await do_action(msg.chat_id, ctx, action, uid)


async def on_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if msg and user and is_staff(user.id):
        await handle_flow(msg, ctx, user.id)


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    if not cb or not cb.data:
        return
    uid = cb.from_user.id
    chat = cb.message.chat_id
    upsert_user(uid)

    if cb.data.startswith("chk:"):
        token = cb.data[4:]
        if not is_staff(uid) and setting("bot_on") == "0":
            await cb.answer(MAINT_TEXT, show_alert=True)
            return
        if not await is_member(ctx.bot, uid):
            await cb.answer("لم تشترك بعد", show_alert=True)
            return
        await cb.answer("تم التحقق ✅")
        await deliver(ctx, chat, token, uid)
        await render(chat, ctx, ("home",), uid)
        return

    if cb.data == "idadd":
        await cb.answer()
        if not is_staff(uid):
            return
        pending = ctx.user_data.pop("pending", None)
        if not pending:
            await ctx.bot.send_message(chat, "انتهى الطلب، أعد التعرف على الملف.")
            return
        await start_flow(chat, ctx, "addfile", fid=pending[0], ftype=pending[1])
        return

    await cb.answer()


async def on_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    iq = update.inline_query
    if not iq:
        return
    token = iq.query.strip()
    results = []
    if setting("bot_on") == "1" and re.fullmatch(r"[fc]\d+", token):
        link = f"https://t.me/{ctx.bot.username}?start={token}"
        if token[0] == "f":
            row = q1("SELECT * FROM files WHERE id=? AND visible=1", (int(token[1:]),))
            if row:
                name = row["teacher"] if row["kind"] == "note" and row["teacher"] else row["title"]
                results.append(InlineQueryResultArticle(
                    id=token, title=name[:64], description="اضغط لإرسال رابط الملف",
                    input_message_content=InputTextMessageContent(f"{name}\n{link}"),
                ))
        else:
            cb = q1("SELECT * FROM cbuttons WHERE id=?", (int(token[1:]),))
            if cb:
                results.append(InlineQueryResultArticle(
                    id=token, title=f"📦 {cb['name']}"[:64], description="اضغط لإرسال رابط المحتوى",
                    input_message_content=InputTextMessageContent(f"{cb['name']}\n{link}"),
                ))
    await iq.answer(results, cache_time=0, is_personal=True)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.exception("Unhandled error", exc_info=ctx.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("صار خطأ غير متوقع، حاول مرة ثانية.")
    except TelegramError:
        pass


# ============================================================
# التشغيل
# ============================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("لم يتم ضبط BOT_TOKEN. أضف التوكن في متغيرات البيئة في الاستضافة.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler((filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND, on_media))
    app.add_error_handler(on_error)
    log.info("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
