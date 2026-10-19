import asyncio
import html
import io
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
    InputFile,
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

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # أدوات PDF تحتاج: pip install pypdf
    PdfReader = PdfWriter = None

# ============================================================
# الإعدادات
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "TELEGRAM_BOT_TOKEN").strip()  # ضعه في متغيرات البيئة في الاستضافة
OWNER_ID = 7683201905
DB_FILE = "fourth_scientific_bot.db"
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
BUTTON_KINDS = {"📘 الكتب": "book", "📙 الملازم": "note", "🧾 الملخصات": "summary"}
FILE_KINDS = {"📘 كتاب": "book", "📙 ملزمة": "note"}

# الملفات المرفوعة سابقاً: (النوع، المادة، القسم، الاسم، الأستاذ، الـ ID)
SEED_FILES = [
    ("book", "أحياء", None, "كتاب احياء 2026", None, "BQACAgIAAxkBAANjatJ_BlFWtJXog_uzbiRZcHDCvbIAAvmZAAIKWthLPB8esHug98I9BA"),
    ("book", "التربية الإسلامية", None, "كتاب الأسلامية [2026]", None, "BQACAgQAAxkBAAIMDGrTcf86EWrsjrLCMOSoCuWyO9PBAAJNHQACI1sZUODQkEjwnva0PQQ"),
    ("book", "اللغة العربية", None, "عربي الجزء الاول", None, "BQACAgQAAxkBAAIMDWrTcf-V58DTnf3FLrwV8Io2yc4dAAIoGwACDJ5oUKxZrmMPKeL0PQQ"),
    ("book", "English", None, "انكليزي كتاب الطالب [2026]", None, "BQACAgQAAxkBAAIMD2rTcf9lMkJhjKxcOHghJNvLlOgIAAKqHgACLelYUCyIMVKYPttsPQQ"),
    ("book", "رياضيات", None, "كتاب الرياضيات [2027]", None, "BQACAgQAAxkBAAIMEWrTcf-UfPStSBEcwu4O6-1UpbosAAKaIgACdIcZUjTphOSX_D_gPQQ"),
    ("book", "كيمياء", None, "كيمياء [2026]", None, "BQACAgQAAxkBAAIMEmrTcf91NimvmNTMtVFNsLkV_ZxuAALcGwACLelQUBGFuxEWLZ8AAT0E"),
    ("book", "فيزياء", None, "فيزياء[2026]", None, "BQACAgQAAxkBAAIME2rTcf-kFrO9ndiKQBbSlswlcZB_AALYGwACLelQUOryeBETtY9cPQQ"),
    ("book", "الحاسوب", None, "الحاسوب [2026]", None, "BQACAgQAAxkBAAIMFGrTcf9SISexmrNm0npLMkITC5_kAALNGwACLelQUBvxgSA4uyxuPQQ"),
    ("book", "جرائم حزب البعث", None, "كتاب الجرائم [2026]", None, "BQACAgQAAxkBAAIMFWrTcf-_zGchW7tUWpzexT82K_IIAAIOHAACLelQUFXdEILcCpwKPQQ"),
    ("note", "التربية الإسلامية", None, "التربية الاسلامية", None, "BQACAgQAAxkBAAIMt2rTdH0RfTYKY3wk8hRGR7d35CtxAAJJHAACDJ5wUKyuhgcaKePNPQQ"),
    ("note", "التربية الإسلامية", None, "التربية الاسلامية", None, "BQACAgQAAxkBAAIMuGrTdH0FJ7tsjGZyYi4XVazezONjAAKaIAACwWsxU4gqXUwm6wI1PQQ"),
    ("note", "اللغة العربية", None, "ملزمة العربي جزء الاول", None, "BQACAgQAAxkBAAINA2rTdikjrRAAATgQDrNtk8eXFiJI6QACHB8AAnxQWVCOr3n_md_AlT0E"),
    ("note", "اللغة العربية", None, "ملزمة العربي جزء الاول", None, "BQACAgQAAxkBAAINBGrTdinKTeLh9q1LsnX7xBzDeZcaAAIZIgACcMpoUFyg7ClDAp6CPQQ"),
    ("note", "اللغة العربية", None, "ملزمة العربي جزء الثاني", None, "BQACAgQAAxkBAAINBWrTdikLeFGsv6JIrqF-HWEx-CSoAAKbHAACKX3JUFPRr_fQdc4JPQQ"),
    ("note", "اللغة العربية", None, "ملزمة العربي جزء الثاني", None, "BQACAgQAAxkBAAINBmrTdil8lej0jOr-LWGeMxakiY8MAAJlHwACNPfJUa3ZFRKEEbIRPQQ"),
    ("note", "اللغة العربية", None, "ملزمة العربي جزء الاول", None, "BQACAgQAAxkBAAINVmrTd6wD3wweRUbpvC-VSbmuPbMTAAIYGwAC4MKRUzQ2SpWHZDRRPQQ"),
    ("note", "اللغة العربية", None, "ملزمة العربي جزء الثاني", None, "BQACAgQAAxkBAAINB2rTdiktwTFq1h1oz8vEIbWvDNoMAAJ7HAAC4MKJUw2Oku9xZQABiz0E"),
    ("note", "English", None, "ملزمة الانكليزي", None, "BQACAgQAAxkBAAINpWrTeHaA0V0XOSUHQQcK79cYwNtCAAKfGgACdLfBUOo3DSPMegV3PQQ"),
    ("note", "English", None, "ملزمة الانكليزي", None, "BQACAgQAAxkBAAINpmrTeHbySP29YFl8DXIbOQABRTYRUQACmRoAAnS3wVBJn4uc0469AAE9BA"),
    ("note", "English", None, "ملزمة الانكليزي", None, "BQACAgQAAxkBAAINp2rTeHZsqo-76x5nC8KD4_tD9UOxAAKWGgACdLfBUI50M_H1A3BHPQQ"),
    ("note", "أحياء", None, "ملزمة الاحياء", None, "BQACAgQAAxkBAAIN5mrTeUPp90D6LAZrYLFIDDWyeFetAAJHHgACc5_RUEnOH7sNOOugPQQ"),
    ("note", "أحياء", None, "ملزمة الاحياء", None, "BQACAgQAAxkBAAIN52rTeUPQrHiyFB-r3U81Bc-dg5hLAAJFHgACc5_RULcQFdWU5YYaPQQ"),
    ("note", "كيمياء", None, "ملزمة الكيمياء", None, "BQACAgQAAxkBAAIOE2rTeeQEHH_XW70bWlGSZnmGLFWWAAJDHgACc5_RUBkWydg-5mtdPQQ"),
    ("note", "كيمياء", None, "ملزمة الكيمياء", None, "BQACAgQAAxkBAAIOFGrTeeScWMz2_RJiIW1MrqbUaSDzAAJRJQAC4xPwUVOXebAX5QzKPQQ"),
    ("note", "كيمياء", None, "ملزمة الكيمياء", None, "BQACAgQAAxkBAAIOFWrTeeTLlagz87vO0hnfc8SHZU3bAAIWHAACDJ5wUE2at2pYdJVBPQQ"),
    ("note", "جرائم حزب البعث", None, "ملزمة جرائم حزب البعث", None, "BQACAgIAAxkBAAIOUmrTeqgqBBxnmE6VQnEFrRrDPMHRAAJ5rwACAey5SdF_EHaXaKiSPQQ"),
    ("note", "فيزياء", None, "ملزمة فيزياء", None, "BQACAgIAAxkBAAIOaGrTe-RjhG9xIqnmZ2WLL_zKOCxEAALTrAACClrQS2j4-y5NFvb3PQQ"),
    ("note", "أحياء", None, "ملزمة احياء", None, "BQACAgIAAxkBAAIOaWrTe-TsZzdSL8iwD72VGSfD7VV7AAJRowACxTBoSu6az6X2r7bgPQQ"),
    ("note", "فيزياء", None, "ملزمة الفيزياء", None, "BQACAgQAAxkBAAIOnmrTfcMsCNcLdECgiaKgw2W8NivYAAJgGwACH-xIUym-W1EyQYCnPQQ"),
    ("note", "فيزياء", None, "ملزمة فيزياء", None, "BQACAgQAAxkBAAIOnWrTfcO3JeIoYotm6oCfX9a0vb4SAAJkGgACKX25UPkGW0tPJQkePQQ"),
    ("note", "فيزياء", None, "ملزمة فيزياء", None, "BQACAgQAAxkBAAIOn2rTfcNrbHmwzCHgbyOyEzU0xrmhAAIWHwACfFBZUKz_UZO7N5ZwPQQ"),
    ("note", "الحاسوب", None, "ملزمة الحاسوب", None, "BQACAgQAAxkBAAIO1GrTfo7E8skAAYYNCN6IkA7cKguMVgACwB4AAp6IAVG9ny7t_-JyRj0E"),
    ("summary", "فيزياء", "ch1", "ملخص فيزياء - الفصل الأول", None, "BQACAgIAAxkBAAIO8GrTfvWitC4uXu-YFeS2HXLCCsI4AAKGqAACYRkQStqQOPL06-8GPQQ"),
    ("summary", "فيزياء", "ch2", "ملخص فيزياء - الفصل الثاني", None, "BQACAgIAAxkBAAIO8WrTfvVdDCcpz88D85jSD23d5T4OAAK6pgACdnZoSihXFvx0p5jXPQQ"),
    ("summary", "English", "u1", "ملخص English - الوحدة الأولى", None, "BQACAgIAAxkBAAIPLWrTgkP69GkEIANwVq8rLvqNxog5AALfqQACIR6YShAbpWq12ikzPQQ"),
    ("summary", "English", "u2", "ملخص English - الوحدة الثانية", None, "BQACAgIAAxkBAAIPLmrTgkOL73qgCVQcJU4iz1ScTsidAALmqQACIR6YSs_4molH88vpPQQ"),
    ("summary", "English", "u3", "ملخص English - الوحدة الثالثة", None, "BQACAgIAAxkBAAIPL2rTgkM-GVxFKnDVsfgTBpqZLMeWAALpqQACIR6YSgplyiu7Ecf9PQQ"),
    ("summary", "فيزياء", "ch3", "ملخص فيزياء - الفصل الثالث", None, "BQACAgIAAxkBAAIPb2rTiCXaBNpwzOKE2_5_If0CkaApAAJ7qwACDUCZSqhZ21Ktq9yuPQQ"),
    ("summary", "التربية الإسلامية", "u1", "ملخص التربية الإسلامية - الوحدة الأولى", None, "BQACAgIAAxkBAAIP32rTmJX09vS-G2W_RbsZnnGIk_1xAAI-qwACIR6YSgtzbzRKbP9HPQQ"),
    ("summary", "التربية الإسلامية", "u2", "ملخص التربية الإسلامية - الوحدة الثانية", None, "BQACAgIAAxkBAAIP4GrTmJUEnaM_WXnVB8eHcfbpnA67AAJAqwACIR6YSnuNU1_vcXuQPQQ"),
    ("summary", "جرائم حزب البعث", "ch1", "ملخص جرائم حزب البعث - الفصل الأول", None, "BQACAgIAAxkBAAIQCGrTnUQAAUfBzeyT7QQSwunz5FsaTQACKKwAAg1AmUrCHBjDf_p_bT0E"),
    ("summary", "جرائم حزب البعث", "ch2", "ملخص جرائم حزب البعث - الفصل الثاني", None, "BQACAgIAAxkBAAIQCWrTnUSKwnnMiElZ8WQVuQABPVVnkAACO6wAAg1AmUo_ixVH5We0yz0E"),
    ("summary", "جرائم حزب البعث", "ch3", "ملخص جرائم حزب البعث - الفصل الثالث", None, "BQACAgIAAxkBAAIQCmrTnUSvIK6_i5Zqkli1JwfGMQ8uAAI_rAACDUCZSsNsVQWP8eSCPQQ"),
    ("summary", "كيمياء", "ch1", "ملخص كيمياء - الفصل الأول", None, "BQACAgIAAxkBAAIQm2rTuULfkWDX5yGqlbbBRQ3WGKPiAAJorQACDUCZSoW8OcPRWm1oPQQ"),
    ("summary", "كيمياء", "ch2", "ملخص كيمياء - الفصل الثاني", None, "BQACAgIAAxkBAAIQnGrTuUIUyTSiWzG9bRS9NIHHgf-tAAJrrQACDUCZShDZUd_OdCexPQQ"),
    ("summary", "كيمياء", "ch3", "ملخص كيمياء - الفصل الثالث", None, "BQACAgIAAxkBAAIQnWrTuULRRfjFZqLYGFXKoEwCNxDiAAJwrQACDUCZSqKDWnWlR5nnPQQ"),
]

# خريطة أوامر لوحة المالك إلى نوع العملية
OWNER_FLOWS = {
    "➕ إضافة ملف": ("addfile", {"mode": "doc"}),
    "🆔 إضافة ملف بـ ID": ("addfile", {"mode": "id"}),
    "➕ إضافة اسئلة": ("addquestion", {}),
    "➕ إضافة ملخصات": ("addsummary", {}),
    "➕ إضافة قسم جديد": ("addsection", {}),
    "🗂 تعديل الأزرار": ("editbuttons", {}),
    "✏️ تعديل ملف": ("editfile", {}),
    "🔁 استبدال ملف": ("replacefile", {}),
    "🗑 حذف ملف": ("deletefile", {}),
    "👁 إخفاء/إظهار ملف": ("togglefile", {}),
    "➕ إضافة مادة": ("addsubject", {}),
    "✏️ تعديل مادة": ("editsubject", {}),
    "🗑 حذف مادة": ("deletesubject", {}),
    "🗑 حذف قسم": ("deletesection", {}),
    "🔎 التعرف على ID": ("identify", {}),
    "🔗 إنشاء رابط": ("genlink", {}),
    "📣 تغيير القناة": ("channel", {}),
    "📝 تعديل الوصف": ("footer", {}),
    "✂️ قص الملف": ("pdfcut", {}),
    "📝 تحويل اسم الملف": ("pdfrename", {}),
    "👥 إدارة المشرفين": ("admins", {}),
    "📢 إعلان": ("broadcast", {}),
}
OWNER_ONLY = {"📢 إعلان", "👥 إدارة المشرفين", PAUSE_ON, PAUSE_OFF}

FLOW_START = {
    "addfile": "target", "addquestion": "qsec", "addsummary": "subj",
    "addsection": "cname", "addsubject": "sname", "editsubject": "subj",
    "deletesubject": "subj", "deletesection": "csec", "editfile": "file",
    "replacefile": "file", "deletefile": "file", "togglefile": "file",
    "editbuttons": "bsec", "identify": "wait", "genlink": "file",
    "broadcast": "text", "channel": "text", "footer": "ftext",
    "admins": "amenu", "pdfcut": "pdf", "pdfrename": "pdf",
}

# ============================================================
# قاعدة البيانات
# ============================================================

DB = sqlite3.connect(DB_FILE, check_same_thread=False)
DB.row_factory = sqlite3.Row
DB.execute("PRAGMA foreign_keys=ON")

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
    emoji TEXT NOT NULL DEFAULT '📁', pos INTEGER NOT NULL DEFAULT 0,
    visible INTEGER NOT NULL DEFAULT 1, message TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS cbuttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER REFERENCES csections(id) ON DELETE CASCADE,
    name TEXT NOT NULL, pos INTEGER NOT NULL DEFAULT 0,
    visible INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    cbutton_id INTEGER REFERENCES cbuttons(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, section TEXT, month TEXT,
    title TEXT NOT NULL, teacher TEXT, file_id TEXT UNIQUE NOT NULL,
    ftype TEXT NOT NULL DEFAULT 'document', visible INTEGER NOT NULL DEFAULT 1,
    created TEXT);
"""

# أعمدة إضافية للقواعد القديمة (تُضاف دون حذف أي بيانات)
COLUMNS = {
    "users": {"joined": "TEXT", "blocked": "INTEGER NOT NULL DEFAULT 0"},
    "subjects": {
        "emoji": "TEXT NOT NULL DEFAULT '📚'", "color": "TEXT NOT NULL DEFAULT 'success'",
        "stype": "TEXT NOT NULL DEFAULT 'ch'", "pos": "INTEGER NOT NULL DEFAULT 0",
        "visible": "INTEGER NOT NULL DEFAULT 1", "hidden": "TEXT NOT NULL DEFAULT ''",
    },
    "files": {
        "subject_id": "INTEGER", "cbutton_id": "INTEGER", "kind": "TEXT NOT NULL DEFAULT 'book'",
        "section": "TEXT", "month": "TEXT", "teacher": "TEXT", "file_id": "TEXT",
        "ftype": "TEXT NOT NULL DEFAULT 'document'", "visible": "INTEGER NOT NULL DEFAULT 1",
        "created": "TEXT",
    },
}


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
    r = q1("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r and r["value"] is not None else default


def set_setting(key, value):
    x(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def seed_defaults():
    for i, (name, emoji, color, stype) in enumerate(SUBJECTS, 1):
        x(
            "INSERT OR IGNORE INTO subjects(name, emoji, color, stype, pos) VALUES(?, ?, ?, ?, ?)",
            (name, emoji, color, stype, i),
        )
    for kind, subject, section, title, teacher, fid in SEED_FILES:
        s = q1("SELECT id FROM subjects WHERE name=?", (subject,))
        if s:
            x(
                "INSERT OR IGNORE INTO files(subject_id, kind, section, title, teacher, file_id, ftype, created) "
                "VALUES(?, ?, ?, ?, ?, ?, 'document', ?)",
                (s["id"], kind, section, title, teacher, fid, now()),
            )


def init_db():
    DB.executescript(SCHEMA)
    for table, cols in COLUMNS.items():
        have = {r["name"] for r in q(f"PRAGMA table_info({table})")}
        for col, definition in cols.items():
            if col not in have:
                DB.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
    DB.commit()
    if not setting("seed_v1"):
        seed_defaults()
        set_setting("seed_v1", "1")
    for key, value in (
        ("channel", DEFAULT_CHANNEL), ("sub_on", "1"),
        ("bot_on", "1"), ("footer", DEFAULT_FOOTER),
    ):
        x("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, value))
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


def custom_label(c):
    return f"{c['emoji']} {c['name']}"


def label_of_subject(text, visible_only=False):
    sql = "SELECT * FROM subjects" + (" WHERE visible=1" if visible_only else "") + " ORDER BY pos, id"
    for s in q(sql):
        if subject_label(s) == text:
            return s
    return None


def hidden_set(raw):
    return {h for h in (raw or "").split(",") if h}


def find_file_by_id(row_id):
    return q1("SELECT * FROM files WHERE id=?", (row_id,))


def find_file_ref(text):
    m = re.match(r"#(\d+)", text.strip())
    if m:
        return find_file_by_id(int(m.group(1)))
    return q1("SELECT * FROM files WHERE file_id=?", (text.strip(),))


def insert_file(subject_id, cbutton_id, kind, section, month, title, teacher, fid, ftype):
    try:
        x(
            "INSERT INTO files(subject_id, cbutton_id, kind, section, month, title, teacher, file_id, ftype, created) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (subject_id, cbutton_id, kind, section, month, title, teacher, fid, ftype, now()),
        )
        return True, None
    except sqlite3.IntegrityError:
        return False, "هذا الملف موجود مسبقاً."


def media_payload(msg):
    if msg.photo:
        return msg.photo[-1].file_id, "photo"
    for obj in (msg.document, msg.video, msg.audio, msg.voice, msg.animation, msg.sticker):
        if obj:
            return obj.file_id, "document"
    return None, None


def read_payload(msg, mode="any"):
    if mode in ("any", "doc"):
        fid, ftype = media_payload(msg)
        if fid:
            return fid, ftype
    if mode in ("any", "id"):
        t = (msg.text or "").strip()
        if t and not re.search(r"\s", t):
            return t, "document"
    return None, None


def media_name(msg):
    if msg.document and msg.document.file_name:
        return msg.document.file_name
    if msg.photo:
        return "صورة"
    if msg.video:
        return "فيديو"
    if msg.audio:
        return "صوت"
    if msg.voice:
        return "رسالة صوتية"
    if msg.animation:
        return "متحركة"
    if msg.sticker:
        return "ملصق"
    return "ملف"


async def download_bytes(ctx, file_id):
    tg_file = await ctx.bot.get_file(file_id)
    return bytes(await tg_file.download_as_bytearray())


def run_action(do):
    kind = do[0]
    if kind == "delsub":
        x("DELETE FROM subjects WHERE id=?", (do[1],))
    elif kind == "delcs":
        x("DELETE FROM csections WHERE id=?", (do[1],))
    elif kind == "delfile":
        x("DELETE FROM files WHERE id=?", (do[1],))
    elif kind == "deladmin":
        x("DELETE FROM admins WHERE user_id=?", (do[1],))
    elif kind == "footer":
        set_setting("footer", do[1])
    elif kind == "tsub":
        s = q1("SELECT hidden FROM subjects WHERE id=?", (do[1],))
        hidden = hidden_set(s["hidden"])
        if do[2] in hidden:
            hidden.discard(do[2])
        else:
            hidden.add(do[2])
        x("UPDATE subjects SET hidden=? WHERE id=?", (",".join(sorted(hidden)), do[1]))
    elif kind == "tcb":
        x("UPDATE cbuttons SET visible = 1 - visible WHERE id=?", (do[1],))


# ============================================================
# الاشتراك الإجباري
# ============================================================

async def is_member(bot, uid):
    if is_staff(uid) or setting("sub_on") != "1":
        return True
    if SUB_CACHE.get(uid, 0) > time.time():
        return True
    try:
        member = await bot.get_chat_member(setting("channel") or DEFAULT_CHANNEL, uid)
    except TelegramError as e:
        log.warning("Subscription check failed: %s", e)
        return False
    ok = member.status in ("member", "administrator", "creator")
    if ok:
        SUB_CACHE[uid] = time.time() + SUB_CACHE_SECONDS
    return ok


def gate_markup(pending=0):
    ch = (setting("channel") or DEFAULT_CHANNEL).lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 اشترك بالقناة", url=f"https://t.me/{ch}", style="primary")],
        [InlineKeyboardButton("✅ التحقق من الاشتراك", callback_data=f"chk:{pending or 0}", style="primary")],
    ])


# ============================================================
# الأزرار (لوحة الكتابة السفلية)
# ============================================================

def kb(rows):
    out = []
    for row in rows:
        line = []
        for item in row:
            text, style = item if isinstance(item, tuple) else (item, "success")
            line.append(KeyboardButton(text, style=style))
        out.append(line)
    return ReplyKeyboardMarkup(out, resize_keyboard=True, is_persistent=True)


def pair(items):
    return [items[i:i + 2] for i in range(0, len(items), 2)]


def owner_markup(is_owner):
    pause_label = PAUSE_OFF if setting("bot_on") == "0" else PAUSE_ON
    rows = [
        [("➕ إضافة ملف", "success"), ("🆔 إضافة ملف بـ ID", "success")],
        [("➕ إضافة اسئلة", "success"), ("➕ إضافة ملخصات", "success")],
        [("➕ إضافة قسم جديد", "success"), ("🗂 تعديل الأزرار", "success")],
        [("✏️ تعديل ملف", "success"), ("🔁 استبدال ملف", "success")],
        [("🗑 حذف ملف", "danger"), ("👁 إخفاء/إظهار ملف", "primary")],
        [("➕ إضافة مادة", "success"), ("✏️ تعديل مادة", "success")],
        [("🗑 حذف مادة", "danger"), ("🗑 حذف قسم", "danger")],
        [("🆔 جميع الـ IDs", "primary"), ("🔎 التعرف على ID", "primary")],
        [("🔗 إنشاء رابط", "success"), ("📊 الإحصائيات", "primary")],
        [("✂️ قص الملف", "primary"), ("📝 تحويل اسم الملف", "primary")],
        [("📝 تعديل الوصف", "primary"), ("📣 تغيير القناة", "primary")],
        [("⚙️ تشغيل/إيقاف الاشتراك", "primary")],
    ]
    if is_owner:
        rows.append([("📢 إعلان", "primary"), (pause_label, "primary")])
        rows.append([("👥 إدارة المشرفين", "primary")])
    rows.append([("🏠 القائمة الرئيسية", "danger")])
    return kb(rows)


async def open_panel(chat, ctx, is_owner):
    await ctx.bot.send_message(chat, "🛠 لوحة المالك", reply_markup=owner_markup(is_owner))


# ============================================================
# بناء الشاشات للطالب
# ============================================================

def build_home(staff):
    items = [(subject_label(s), s["color"]) for s in q("SELECT * FROM subjects WHERE visible=1 ORDER BY pos, id")]
    items += [(custom_label(c), "success") for c in q("SELECT * FROM csections WHERE visible=1 ORDER BY pos, id")]
    rows = pair(items)
    rows.append([("❓ الاسئلة", "primary")])
    if staff:
        rows.append([("🛠 لوحة المالك", "primary")])
    return HOME_TEXT, kb(rows)


def build_subject(sid):
    s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
    hidden = hidden_set(s["hidden"])
    items = []
    if "book" not in hidden:
        items.append(("📘 الكتب", "success"))
    if "note" not in hidden:
        items.append(("📙 الملازم", "success"))
    rows = pair(items)
    if "summary" not in hidden:
        rows.append([("🧾 الملخصات", "success")])
    rows.append([(BACK, "danger")])
    return f"{subject_label(s)}\nاختر:", kb(rows)


def build_file_menu(ctx, files, header, icon):
    choices, items = {}, []
    for r in files:
        name = r["teacher"] if r["kind"] == "note" and r["teacher"] else r["title"]
        base = f"{icon} {name}"[:60]
        text, n = base, 2
        while text in choices:
            text = f"{base[:55]} ({n})"
            n += 1
        choices[text] = r["id"]
        items.append((text, "success"))
    ctx.user_data["choices"] = choices
    if not items:
        header += "\nلا توجد ملفات حالياً."
    rows = pair(items)
    rows.append([(BACK, "danger")])
    return header, kb(rows)


def build_summaries(sid):
    s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
    labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
    rows = pair([(v, "success") for v in labels.values()])
    rows.append([(BACK, "danger")])
    return f"🧾 الملخصات — {s['name']}\nاختر:", kb(rows)


def build_qmenu():
    rows = [
        [(Q_SECTIONS["ch1"], "primary"), (Q_SECTIONS["half"], "primary")],
        [(Q_SECTIONS["ch2"], "primary"), (Q_SECTIONS["end"], "primary")],
        [(BACK, "danger")],
    ]
    return "❓ الاسئلة\nاختر:", kb(rows)


def build_qmonths(sec):
    rows = [[(Q_MONTHS["m1"], "primary"), (Q_MONTHS["m2"], "primary")], [(BACK, "danger")]]
    return f"❓ {Q_SECTIONS[sec]}\nاختر الشهر:", kb(rows)


def build_qsubjects(sec, month):
    items = [(subject_label(s), s["color"]) for s in q("SELECT * FROM subjects WHERE visible=1 ORDER BY pos, id")]
    rows = pair(items)
    rows.append([(BACK, "danger")])
    title = Q_SECTIONS[sec] + (f" — {Q_MONTHS[month]}" if month else "")
    return f"❓ {title}\nاختر المادة:", kb(rows)


def build_custom(cid):
    c = q1("SELECT * FROM csections WHERE id=?", (cid,))
    buttons = q("SELECT * FROM cbuttons WHERE section_id=? AND visible=1 ORDER BY pos, id", (cid,))
    if not buttons:
        return (c["message"] or "لا يوجد محتوى حالياً."), kb([[(BACK, "danger")]])
    rows = pair([(b["name"], "success") for b in buttons])
    rows.append([(BACK, "danger")])
    return f"{custom_label(c)}\nاختر:", kb(rows)


def build_cfiles(ctx, cbid):
    b = q1("SELECT * FROM cbuttons WHERE id=?", (cbid,))
    files = q("SELECT * FROM files WHERE cbutton_id=? AND visible=1 ORDER BY id", (cbid,))
    return build_file_menu(ctx, files, b["name"], "📄")


async def render(chat, ctx, screen, staff):
    ctx.user_data["choices"] = {}
    k = screen[0]
    if k == "subject":
        text, markup = build_subject(screen[1])
    elif k == "list":
        sid, kind = screen[1], screen[2]
        s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
        files = q("SELECT * FROM files WHERE subject_id=? AND kind=? AND visible=1 ORDER BY id", (sid, kind))
        head = ("📘 الكتب" if kind == "book" else "📙 الملازم") + f" — {s['name']}"
        text, markup = build_file_menu(ctx, files, head, "📘" if kind == "book" else "📙")
    elif k == "summaries":
        text, markup = build_summaries(screen[1])
    elif k == "qmenu":
        text, markup = build_qmenu()
    elif k == "qmonths":
        text, markup = build_qmonths(screen[1])
    elif k == "qsubjects":
        text, markup = build_qsubjects(screen[1], screen[2])
    elif k == "custom":
        text, markup = build_custom(screen[1])
    elif k == "cfiles":
        text, markup = build_cfiles(ctx, screen[2])
    else:
        screen = ("home",)
        text, markup = build_home(staff)
    ctx.user_data["screen"] = screen
    await ctx.bot.send_message(chat, text, reply_markup=markup)


def parent_of(screen):
    k = screen[0]
    if k in ("list", "summaries"):
        return ("subject", screen[1])
    if k == "qmonths":
        return ("qmenu",)
    if k == "qsubjects":
        return ("qmonths", screen[1]) if screen[2] else ("qmenu",)
    if k == "cfiles":
        return ("custom", screen[1])
    return ("home",)


async def send_item(ctx, chat, row, staff=False):
    if row is None or (not row["visible"] and not staff):
        await ctx.bot.send_message(chat, "الملف غير متاح حالياً.")
        return
    head = row["teacher"] if row["kind"] == "note" and row["teacher"] else row["title"]
    footer = setting("footer", DEFAULT_FOOTER)
    caption = (f"{head}\n\n{footer}" if footer else head)[:1024]
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(
        "📤 مشاركة الملف",
        switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
            query=str(row["id"]), allow_user_chats=True,
            allow_group_chats=True, allow_channel_chats=True),
        style="success",
    )]])
    try:
        if row["ftype"] == "photo":
            await ctx.bot.send_photo(chat, row["file_id"], caption=caption, reply_markup=markup)
        else:
            await ctx.bot.send_document(chat, row["file_id"], caption=caption, reply_markup=markup)
    except TelegramError as e:
        log.error("Send failed for file %s: %s", row["id"], e)
        await ctx.bot.send_message(chat, "تعذر إرسال الملف. أبلغ المالك.")


async def handle_student(msg, ctx, text, staff):
    chat = msg.chat_id
    screen = ctx.user_data.get("screen", ("home",))
    k = screen[0]

    if text == BACK:
        await render(chat, ctx, parent_of(screen), staff)
        return

    choices = ctx.user_data.get("choices", {})
    if text in choices:
        await send_item(ctx, chat, find_file_by_id(choices[text]), staff)
        return

    if k == "home":
        if text == "❓ الاسئلة":
            await render(chat, ctx, ("qmenu",), staff)
            return
        s = label_of_subject(text, visible_only=True)
        if s:
            await render(chat, ctx, ("subject", s["id"]), staff)
            return
        for c in q("SELECT * FROM csections WHERE visible=1"):
            if custom_label(c) == text:
                await render(chat, ctx, ("custom", c["id"]), staff)
                return
        return

    if k == "subject":
        sid = screen[1]
        if text == "📘 الكتب":
            await render(chat, ctx, ("list", sid, "book"), staff)
        elif text == "📙 الملازم":
            await render(chat, ctx, ("list", sid, "note"), staff)
        elif text == "🧾 الملخصات":
            await render(chat, ctx, ("summaries", sid), staff)
        return

    if k == "summaries":
        sid = screen[1]
        s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
        labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
        key = next((kk for kk, v in labels.items() if v == text), None)
        if key:
            r = q1(
                "SELECT * FROM files WHERE subject_id=? AND kind='summary' AND section=? AND visible=1 "
                "ORDER BY id DESC LIMIT 1",
                (sid, key),
            )
            if r:
                await send_item(ctx, chat, r, staff)
            else:
                await ctx.bot.send_message(chat, "سيتم إضافة الملخصات لاحقاً.")
        return

    if k == "qmenu":
        key = next((kk for kk, v in Q_SECTIONS.items() if v == text), None)
        if key in Q_NEEDS_MONTH:
            await render(chat, ctx, ("qmonths", key), staff)
        elif key:
            await render(chat, ctx, ("qsubjects", key, None), staff)
        return

    if k == "qmonths":
        mkey = next((kk for kk, v in Q_MONTHS.items() if v == text), None)
        if mkey:
            await render(chat, ctx, ("qsubjects", screen[1], mkey), staff)
        return

    if k == "qsubjects":
        s = label_of_subject(text, visible_only=True)
        if s:
            sec, month = screen[1], screen[2]
            r = q1(
                "SELECT * FROM files WHERE kind='question' AND section=? AND subject_id=? "
                "AND visible=1 AND month IS ? ORDER BY id DESC LIMIT 1",
                (sec, s["id"], month),
            )
            if r:
                await send_item(ctx, chat, r, staff)
            else:
                await ctx.bot.send_message(chat, "سيتم إضافة الأسئلة لاحقاً.")
        return

    if k == "custom":
        cb = q1("SELECT * FROM cbuttons WHERE section_id=? AND name=? AND visible=1", (screen[1], text))
        if cb:
            await render(chat, ctx, ("cfiles", screen[1], cb["id"]), staff)
        return


# ============================================================
# لوحة المالك: الإجراءات المباشرة والتدفقات
# ============================================================

async def send_all_ids(chat, ctx):
    rows = q("SELECT f.*, s.name AS sn FROM files f LEFT JOIN subjects s ON s.id=f.subject_id ORDER BY f.id")
    if not rows:
        await ctx.bot.send_message(chat, "لا توجد ملفات.")
        return
    chunk = ""
    for r in rows:
        block = f"{html.escape(location_of(r))}\n<code>{r['file_id']}</code>\n\n"
        if len(chunk) + len(block) > 3500:
            await ctx.bot.send_message(chat, chunk, parse_mode=ParseMode.HTML)
            chunk = ""
        chunk += block
    if chunk.strip():
        await ctx.bot.send_message(chat, chunk, parse_mode=ParseMode.HTML)


def location_of(r):
    parts = []
    if r["subject_id"] and r["sn"]:
        parts.append(r["sn"])
    if r["cbutton_id"]:
        cb = q1(
            "SELECT cb.name AS bn, cs.name AS sn FROM cbuttons cb "
            "JOIN csections cs ON cs.id=cb.section_id WHERE cb.id=?",
            (r["cbutton_id"],),
        )
        if cb:
            parts += [cb["sn"], cb["bn"]]
    if r["section"]:
        parts.append(CH_LABELS.get(r["section"]) or UNIT_LABELS.get(r["section"]) or Q_SECTIONS.get(r["section"], ""))
    if r["month"]:
        parts.append(Q_MONTHS.get(r["month"], ""))
    name = r["teacher"] if r["kind"] == "note" and r["teacher"] else r["title"]
    kind_name = {"book": "كتاب", "note": "ملزمة", "summary": "ملخص", "question": "أسئلة", "custom": "ملف"}.get(
        r["kind"], r["kind"])
    return f"#{r['id']} | {kind_name} | " + " | ".join(p for p in parts if p) + f" | {name}"


async def send_stats(chat, ctx, is_owner):
    def count(sql):
        return q1(sql)[0]

    text = (
        "📊 الإحصائيات\n\n"
        f"المستخدمون: {count('SELECT COUNT(*) FROM users')}\n"
        f"المحظورون: {count('SELECT COUNT(*) FROM users WHERE blocked=1')}\n"
        f"المشرفون: {count('SELECT COUNT(*) FROM admins')}\n"
        f"المواد الظاهرة: {count('SELECT COUNT(*) FROM subjects WHERE visible=1')}\n"
        f"الأقسام الجديدة: {count('SELECT COUNT(*) FROM csections')}\n"
        f"الكتب: {count(chr(83)+'ELECT COUNT(*) FROM files WHERE kind=' + chr(39) + 'book' + chr(39))}\n"
        f"الملازم: {count(chr(83)+'ELECT COUNT(*) FROM files WHERE kind=' + chr(39) + 'note' + chr(39))}\n"
        f"الملخصات: {count(chr(83)+'ELECT COUNT(*) FROM files WHERE kind=' + chr(39) + 'summary' + chr(39))}\n"
        f"الأسئلة: {count(chr(83)+'ELECT COUNT(*) FROM files WHERE kind=' + chr(39) + 'question' + chr(39))}\n"
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


async def flow_send(chat, ctx, text, rows=None):
    rows = list(rows or [])
    rows.append([(CANCEL, "danger")])
    await ctx.bot.send_message(chat, text, reply_markup=kb(rows))


async def flow_prompt(chat, ctx):
    f = ctx.user_data["flow"]
    t, step = f["type"], f["step"]
    text, rows = "", []

    if step == "target":
        text = "اختر المادة أو القسم:"
        f["map"], items = {}, []
        for s in q("SELECT * FROM subjects ORDER BY pos, id"):
            f["map"][subject_label(s)] = ("s", s["id"])
            items.append((subject_label(s), s["color"]))
        for c in q("SELECT * FROM csections ORDER BY pos, id"):
            f["map"][custom_label(c)] = ("c", c["id"])
            items.append((custom_label(c), "success"))
        rows = pair(items)
    elif step == "cbtn":
        text = "اختر الزر داخل القسم:"
        f["map"] = {}
        items = []
        for b in q("SELECT * FROM cbuttons WHERE section_id=? ORDER BY pos, id", (f["cid"],)):
            f["map"][b["name"]] = b["id"]
            items.append((b["name"], "success"))
        rows = pair(items)
    elif step == "kind":
        text = "اختر النوع:"
        rows = [[("📘 كتاب", "success"), ("📙 ملزمة", "success")]]
    elif step == "payload":
        text = {
            "doc": "أرسل الملف الآن كـ Document.",
            "id": "أرسل الـ File ID كنص.",
        }.get(f.get("mode"), "أرسل الملف أو الصورة، أو أرسل الـ File ID كنص.")
    elif step == "title":
        text = "أرسل اسم الملف:"
    elif step == "teacher":
        text, rows = "أرسل اسم الأستاذ:", [[(SKIP, "primary")]]
    elif step == "qsec":
        text = "اختر القسم:"
        rows = pair([(v, "primary") for v in Q_SECTIONS.values()])
    elif step == "qmonth":
        text = "اختر الشهر:"
        rows = [[(v, "primary") for v in Q_MONTHS.values()]]
    elif step == "subj":
        text = "اختر المادة:"
        rows = pair([(subject_label(s), s["color"]) for s in q("SELECT * FROM subjects ORDER BY pos, id")])
    elif step == "ssec":
        s = q1("SELECT * FROM subjects WHERE id=?", (f["sid"],))
        labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
        text = "اختر الفصل أو الوحدة:"
        rows = pair([(v, "primary") for v in labels.values()])
    elif step == "cname":
        text = "أرسل اسم القسم الجديد:"
    elif step == "cemoji":
        text = "أرسل إيموجي القسم:"
    elif step == "cmsg":
        text, rows = "أرسل الرسالة التي تظهر للطالب إذا كان القسم فارغاً:", [[(SKIP, "primary")]]
    elif step == "cbtns":
        listed = "\n".join(f"- {n}" for n in f["buttons"]) or "لا يوجد بعد"
        text = f"أرسل اسم زر داخل القسم، وعند الانتهاء اضغط تم.\nالأزرار المضافة:\n{listed}"
        rows = [[(DONE, "success")]]
    elif step == "sname":
        text = "أرسل اسم المادة الجديدة:"
    elif step == "semoji":
        text = "أرسل إيموجي المادة:"
    elif step == "stype":
        text, rows = "اختر نوع المادة:", [[("📘 فصول", "success"), ("📗 وحدات", "success")]]
    elif step == "sfield":
        text, rows = "اختر ما تريد تعديله:", [[("✏️ الاسم", "success"), ("😀 الإيموجي", "success")]]
    elif step == "svalue":
        text = "أرسل القيمة الجديدة:"
    elif step == "ffield":
        text, rows = "اختر ما تريد تعديله:", [[("✏️ الاسم", "success"), ("👨‍🏫 الأستاذ", "success")]]
    elif step == "fvalue":
        text = "أرسل القيمة الجديدة:"
    elif step == "file":
        text = "اختر الملف، أو أرسل رقمه مثل #12:"
        rows = [[(f"#{r['id']} {r['title']}"[:60], "success")] for r in q("SELECT * FROM files ORDER BY id")]
    elif step == "confirm":
        text, rows = "هل تؤكد هذه العملية؟", [[(CONFIRM, "danger")]]
    elif step == "csec":
        text = "اختر القسم:"
        f["map"] = {}
        items = []
        for c in q("SELECT * FROM csections ORDER BY pos, id"):
            f["map"][custom_label(c)] = c["id"]
            items.append((custom_label(c), "success"))
        rows = pair(items)
    elif step == "bsec":
        text = "اختر المادة أو القسم:"
        f["map"], items = {}, []
        for s in q("SELECT * FROM subjects ORDER BY pos, id"):
            f["map"][subject_label(s)] = ("s", s["id"])
            items.append((subject_label(s), s["color"]))
        for c in q("SELECT * FROM csections ORDER BY pos, id"):
            f["map"][custom_label(c)] = ("c", c["id"])
            items.append((custom_label(c), "success"))
        rows = pair(items)
    elif step == "bsub":
        s = q1("SELECT * FROM subjects WHERE id=?", (f["sid"],))
        hidden = hidden_set(s["hidden"])
        state = [f"{lab}: {'مخفي' if key in hidden else 'ظاهر'}" for lab, key in BUTTON_KINDS.items()]
        text = "اختر الزر لإخفائه أو إظهاره:\n" + "\n".join(state)
        rows = [[("📘 الكتب", "success"), ("📙 الملازم", "success")], [("🧾 الملخصات", "success")]]
    elif step == "bcust":
        text = "اختر الزر داخل القسم:"
        f["map"] = {}
        items = []
        for b in q("SELECT * FROM cbuttons WHERE section_id=? ORDER BY pos, id", (f["cid"],)):
            f["map"][b["name"]] = b["id"]
            items.append((b["name"], "success"))
        rows = pair(items)
    elif step == "wait":
        text = "أرسل أي ملف أو صورة الآن لأستخرج الـ ID:"
    elif step == "text":
        text = f.get("prompt", "أرسل النص:")
    elif step == "ftext":
        text = f"الوصف الحالي:\n\n{setting('footer')}\n\nأرسل الوصف الجديد، أو اضغط حذف الوصف:"
        rows = [[("🗑 حذف الوصف", "danger")]]
    elif step == "amenu":
        text = "👥 إدارة المشرفين"
        rows = [[("➕ إضافة مشرف", "success"), ("🗑 حذف مشرف", "danger")], [("📋 قائمة المشرفين", "primary")]]
    elif step == "aid":
        text = "أرسل Telegram ID للمشرف الجديد:"
    elif step == "apick":
        text = "اختر المشرف للحذف:"
        f["map"] = {}
        items = []
        for a in q("SELECT user_id FROM admins"):
            items.append((f"#{a['user_id']}", "danger"))
        rows = pair(items)
    elif step == "pdf":
        text = "أرسل ملف PDF الآن كـ Document:"
    elif step == "range":
        text = "أرسل الصفحات، مثل: 4-8"
    elif step == "newname":
        text = "أرسل الاسم الجديد للملف:"
    elif step == "cutname":
        text = "أرسل اسم الملف الناتج:"

    await flow_send(chat, ctx, text, rows)


async def start_flow(chat, ctx, typ, extra):
    ctx.user_data["flow"] = {"type": typ, "step": FLOW_START[typ], **extra}
    if typ == "broadcast":
        ctx.user_data["flow"]["prompt"] = "أرسل نص الإعلان:"
    elif typ == "channel":
        ctx.user_data["flow"]["prompt"] = "أرسل معرف القناة مثل @Channel:"
    await flow_prompt(chat, ctx)


async def handle_flow(msg, ctx, uid):
    f = ctx.user_data.get("flow")
    if not f:
        return False
    chat = msg.chat_id
    text = (msg.text or "").strip()
    t, step = f["type"], f["step"]
    is_owner = uid == OWNER_ID

    async def again(hint):
        await msg.reply_text(hint)
        await flow_prompt(chat, ctx)

    async def finish(result):
        ctx.user_data.pop("flow", None)
        await msg.reply_text(result, reply_markup=owner_markup(is_owner))

    async def goto(new_step):
        f["step"] = new_step
        await flow_prompt(chat, ctx)

    # ---------- اختيار المادة أو القسم (إضافة ملف) ----------
    if step == "target":
        if text not in f["map"]:
            await again("اختر من الأزرار.")
            return True
        kind, tid = f["map"][text]
        if kind == "s":
            f["sid"] = tid
            await goto("kind")
        else:
            f["cid"] = tid
            await goto("cbtn")
        return True

    if step == "cbtn":
        if text not in f["map"]:
            await again("اختر الزر من الأزرار.")
            return True
        f["cbid"], f["kind"] = f["map"][text], "custom"
        await goto("payload")
        return True

    if step == "kind":
        k = FILE_KINDS.get(text)
        if not k:
            await again("اختر النوع من الأزرار.")
            return True
        f["kind"] = k
        await goto("payload")
        return True

    # ---------- استلام الملف أو الـ ID ----------
    if step == "payload":
        mode = f.get("mode", "any")
        fid, ftype = read_payload(msg, mode)
        if not fid:
            await again("أرسل الملف أو الـ File ID الصحيح.")
            return True

        if t == "replacefile":
            try:
                x("UPDATE files SET file_id=?, ftype=? WHERE id=?", (fid, ftype, f["rid"]))
            except sqlite3.IntegrityError:
                await finish("هذا الملف مستخدم في ملف آخر.")
                return True
            await finish("✅ تم استبدال الملف.")
            return True

        if t == "addquestion":
            s = q1("SELECT name FROM subjects WHERE id=?", (f["sid"],))
            title = f"أسئلة {Q_SECTIONS[f['sec']]}"
            if f.get("month"):
                title += f" - {Q_MONTHS[f['month']]}"
            title += f" - {s['name']}"
            ok, err = insert_file(f["sid"], None, "question", f["sec"], f.get("month"), title, None, fid, ftype)
            await finish("✅ تمت إضافة الأسئلة." if ok else err)
            return True

        if t == "addsummary":
            s = q1("SELECT name FROM subjects WHERE id=?", (f["sid"],))
            labels = CH_LABELS if q1("SELECT stype FROM subjects WHERE id=?", (f["sid"],))["stype"] == "ch" else UNIT_LABELS
            title = f"ملخص {s['name']} - {labels[f['sec']]}"
            ok, err = insert_file(f["sid"], None, "summary", f["sec"], None, title, None, fid, ftype)
            await finish("✅ تمت إضافة الملخص." if ok else err)
            return True

        # إضافة ملف عادي: نحفظ الـ ID ثم نطلب الاسم
        f["fid"], f["ftype"] = fid, ftype
        await goto("title")
        return True

    if step == "title":
        if not text:
            await again("أرسل الاسم كنص.")
            return True
        f["title"] = text
        if f.get("kind") == "note":
            await goto("teacher")
            return True
        ok, err = insert_file(f.get("sid"), f.get("cbid"), f["kind"], None, None,
                              f["title"], None, f["fid"], f["ftype"])
        await finish("✅ تمت إضافة الملف." if ok else err)
        return True

    if step == "teacher":
        if not text:
            await again("أرسل اسم الأستاذ، أو اضغط تخطي.")
            return True
        teacher = None if text == SKIP else text
        ok, err = insert_file(f.get("sid"), None, f["kind"], None, None,
                              f["title"], teacher, f["fid"], f["ftype"])
        await finish("✅ تمت إضافة الملزمة." if ok else err)
        return True

    # ---------- الأسئلة ----------
    if step == "qsec":
        key = next((kk for kk, v in Q_SECTIONS.items() if v == text), None)
        if not key:
            await again("اختر القسم من الأزرار.")
            return True
        f["sec"] = key
        f["month"] = None
        await goto("qmonth" if key in Q_NEEDS_MONTH else "subj")
        return True

    if step == "qmonth":
        mkey = next((kk for kk, v in Q_MONTHS.items() if v == text), None)
        if not mkey:
            await again("اختر الشهر من الأزرار.")
            return True
        f["month"] = mkey
        await goto("subj")
        return True

    # ---------- اختيار مادة (تستخدم في عدة تدفقات) ----------
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            await again("اختر المادة من الأزرار.")
            return True
        f["sid"] = s["id"]
        if t == "addquestion":
            await goto("payload")
        elif t == "addsummary":
            await goto("ssec")
        elif t == "editsubject":
            await goto("sfield")
        elif t == "deletesubject":
            f["do"] = ("delsub", s["id"])
            await goto("confirm")
        return True

    if step == "ssec":
        s = q1("SELECT * FROM subjects WHERE id=?", (f["sid"],))
        labels = CH_LABELS if s["stype"] == "ch" else UNIT_LABELS
        key = next((kk for kk, v in labels.items() if v == text), None)
        if not key:
            await again("اختر من الأزرار.")
            return True
        f["sec"] = key
        await goto("payload")
        return True

    # ---------- أقسام جديدة ----------
    if step == "cname":
        if not text:
            await again("أرسل اسم القسم.")
            return True
        f["cname"] = text
        await goto("cemoji")
        return True

    if step == "cemoji":
        if not text:
            await again("أرسل إيموجي القسم.")
            return True
        f["cemoji"] = text
        await goto("cmsg")
        return True

    if step == "cmsg":
        f["cmsg"] = "" if text == SKIP else text
        f["buttons"] = []
        await goto("cbtns")
        return True

    if step == "cbtns":
        if text == DONE:
            try:
                pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM csections")["p"]
                cur = DB.execute(
                    "INSERT INTO csections(name, emoji, pos, message) VALUES(?, ?, ?, ?)",
                    (f["cname"], f["cemoji"], pos, f.get("cmsg", "")),
                )
                for i, name in enumerate(f["buttons"], 1):
                    DB.execute(
                        "INSERT INTO cbuttons(section_id, name, pos) VALUES(?, ?, ?)",
                        (cur.lastrowid, name, i),
                    )
                DB.commit()
            except sqlite3.IntegrityError:
                DB.rollback()
                await finish("اسم القسم مستخدم من قبل.")
                return True
            await finish(f"✅ تم إنشاء القسم: {f['cemoji']} {f['cname']}")
            return True
        if not text:
            await again("أرسل اسم الزر.")
            return True
        if text in f["buttons"]:
            await again("هذا الزر موجود مسبقاً.")
            return True
        f["buttons"].append(text)
        await flow_prompt(chat, ctx)
        return True

    # ---------- مواد جديدة / تعديلها / حذفها ----------
    if step == "sname":
        if not text:
            await again("أرسل اسم المادة.")
            return True
        f["sname"] = text
        await goto("semoji")
        return True

    if step == "semoji":
        if not text:
            await again("أرسل إيموجي المادة.")
            return True
        f["semoji"] = text
        await goto("stype")
        return True

    if step == "stype":
        stype = {"📘 فصول": "ch", "📗 وحدات": "unit"}.get(text)
        if not stype:
            await again("اختر النوع من الأزرار.")
            return True
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM subjects")["p"]
        try:
            x("INSERT INTO subjects(name, emoji, color, stype, pos) VALUES(?, ?, 'success', ?, ?)",
              (f["sname"], f["semoji"], stype, pos))
            await finish("✅ تمت إضافة المادة.")
        except sqlite3.IntegrityError:
            await finish("هذه المادة موجودة مسبقاً.")
        return True

    if step == "sfield":
        field = {"✏️ الاسم": "name", "😀 الإيموجي": "emoji"}.get(text)
        if not field:
            await again("اختر من الأزرار.")
            return True
        f["col"] = field
        await goto("svalue")
        return True

    if step == "svalue":
        if not text:
            await again("أرسل القيمة.")
            return True
        try:
            x(f"UPDATE subjects SET {f['col']}=? WHERE id=?", (text, f["sid"]))
        except sqlite3.IntegrityError:
            await finish("هذا الاسم مستخدم من مادة أخرى.")
            return True
        await finish("✅ تم التعديل.")
        return True

    # ---------- حذف قسم جديد ----------
    if step == "csec":
        if text not in f["map"]:
            await again("اختر القسم من الأزرار.")
            return True
        f["do"] = ("delcs", f["map"][text])
        await goto("confirm")
        return True

    # ---------- تعديل الأزرار ----------
    if step == "bsec":
        if text not in f["map"]:
            await again("اختر من الأزرار.")
            return True
        kind, tid = f["map"][text]
        if kind == "s":
            f["sid"] = tid
            await goto("bsub")
        else:
            f["cid"] = tid
            await goto("bcust")
        return True

    if step == "bsub":
        bkind = BUTTON_KINDS.get(text)
        if not bkind:
            await again("اختر الزر من الأزرار.")
            return True
        f["do"] = ("tsub", f["sid"], bkind)
        await goto("confirm")
        return True

    if step == "bcust":
        if text not in f["map"]:
            await again("اختر الزر من الأزرار.")
            return True
        f["do"] = ("tcb", f["map"][text])
        await goto("confirm")
        return True

    if step == "confirm":
        if text != CONFIRM:
            await again("اضغط تأكيد أو إلغاء.")
            return True
        run_action(f["do"])
        await finish("✅ تم التنفيذ.")
        return True

    # ---------- الملفات ----------
    if step == "file":
        row = find_file_ref(text)
        if not row:
            await again("اختر الملف من الأزرار أو أرسل رقمه مثل #12.")
            return True
        if t == "togglefile":
            x("UPDATE files SET visible = 1 - visible WHERE id=?", (row["id"],))
            await finish("✅ تم. الحالة الآن: " + ("ظاهر" if not row["visible"] else "مخفي"))
            return True
        if t == "genlink":
            link = f"https://t.me/{ctx.bot.username}?start=f{row['id']}"
            await finish(f"🔗 رابط الملف:\n{link}")
            return True
        if t == "deletefile":
            f["do"] = ("delfile", row["id"])
            await goto("confirm")
            return True
        f["rid"] = row["id"]
        await goto("payload" if t == "replacefile" else "ffield")
        return True

    if step == "ffield":
        field = {"✏️ الاسم": "title", "👨‍🏫 الأستاذ": "teacher"}.get(text)
        if not field:
            await again("اختر من الأزرار.")
            return True
        f["col"] = field
        await goto("fvalue")
        return True

    if step == "fvalue":
        if not text:
            await again("أرسل القيمة.")
            return True
        x(f"UPDATE files SET {f['col']}=? WHERE id=?", (text, f["rid"]))
        await finish("✅ تم التعديل.")
        return True

    # ---------- التعرف على ID ----------
    if step == "wait":
        fid, _ = media_payload(msg)
        if not fid:
            await again("أرسل ملفاً أو صورة أو فيديو.")
            return True
        await msg.reply_text(
            f"📄 الاسم: {html.escape(media_name(msg))}\n🆔 الـ ID (اضغط عليه للنسخ):\n<code>{fid}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb([[(CANCEL, "danger")]]),
        )
        return True

    # ---------- إعلان / قناة ----------
    if step == "text":
        if not text:
            await again("أرسل النص.")
            return True
        if t == "channel":
            if not text.startswith("@") or len(text) < 2:
                await again("الصيغة الصحيحة: @Channel")
                return True
            set_setting("channel", text)
            SUB_CACHE.clear()
            await finish("✅ تم تغيير القناة.")
            return True
        ok, fail = await do_broadcast(ctx, text)
        await finish(f"✅ تم الإرسال.\nنجح: {ok}\nفشل: {fail}")
        return True

    # ---------- الوصف ----------
    if step == "ftext":
        if text == "🗑 حذف الوصف":
            f["do"] = ("footer", "")
            await goto("confirm")
            return True
        if not text:
            await again("أرسل الوصف الجديد.")
            return True
        set_setting("footer", text)
        await finish("✅ تم تحديث الوصف.")
        return True

    # ---------- المشرفون ----------
    if step == "amenu":
        if text == "➕ إضافة مشرف":
            await goto("aid")
        elif text == "🗑 حذف مشرف":
            await goto("apick")
        elif text == "📋 قائمة المشرفين":
            admins = q("SELECT user_id FROM admins")
            listed = "\n".join(f"#{a['user_id']}" for a in admins) or "لا يوجد مشرفون."
            await finish(f"👥 المشرفون:\n{listed}")
        else:
            await again("اختر من الأزرار.")
        return True

    if step == "aid":
        if not text.isdigit():
            await again("أرسل Telegram ID رقمياً.")
            return True
        x("INSERT OR IGNORE INTO admins(user_id, added) VALUES(?, ?)", (int(text), now()))
        await finish("✅ تمت إضافة المشرف.")
        return True

    if step == "apick":
        m = re.match(r"#(\d+)", text)
        if not m:
            await again("اختر المشرف من الأزرار.")
            return True
        f["do"] = ("deladmin", int(m.group(1)))
        await goto("confirm")
        return True

    # ---------- أدوات PDF ----------
    if step == "pdf":
        doc = msg.document
        if not doc or not (doc.file_name or "").lower().endswith(".pdf"):
            await again("أرسل ملف PDF كـ Document.")
            return True
        if PdfReader is None:
            await finish("أداة PDF غير مثبتة. ثبّت مكتبة pypdf على الاستضافة.")
            return True
        f["pdf_id"] = doc.file_id
        await goto("newname" if t == "pdfrename" else "range")
        return True

    if step == "newname":
        if not text:
            await again("أرسل الاسم الجديد.")
            return True
        name = text if text.lower().endswith(".pdf") else text + ".pdf"
        data = await download_bytes(ctx, f["pdf_id"])
        await ctx.bot.send_document(chat, document=InputFile(io.BytesIO(data), filename=name))
        await finish("✅ تم تغيير الاسم وإرسال الملف.")
        return True

    if step == "range":
        m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", text)
        if not m:
            await again("أرسل الصفحات بهذا الشكل: 4-8")
            return True
        data = await download_bytes(ctx, f["pdf_id"])
        total = len(PdfReader(io.BytesIO(data)).pages)
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if not (1 <= a <= b <= total):
            await again(f"الصفحات يجب أن تكون بين 1 و {total}.")
            return True
        f["range"] = (a, b)
        await goto("cutname")
        return True

    if step == "cutname":
        if not text:
            await again("أرسل اسم الملف الناتج.")
            return True
        a, b = f["range"]
        data = await download_bytes(ctx, f["pdf_id"])
        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()
        for i in range(a - 1, b):
            writer.add_page(reader.pages[i])
        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        name = text if text.lower().endswith(".pdf") else text + ".pdf"
        await ctx.bot.send_document(chat, document=InputFile(out, filename=name))
        await finish("✅ تم قص الملف وإرساله.")
        return True

    return True


# ============================================================
# أوامر وأحداث البوت
# ============================================================

async def owner_action(msg, ctx, uid, text):
    chat, is_owner = msg.chat_id, uid == OWNER_ID
    if text in OWNER_ONLY and not is_owner:
        return False

    if text == "🛠 لوحة المالك":
        ctx.user_data.pop("flow", None)
        await open_panel(chat, ctx, is_owner)
    elif text == "🏠 القائمة الرئيسية":
        ctx.user_data.pop("flow", None)
        await render(chat, ctx, ("home",), True)
    elif text == "🆔 جميع الـ IDs":
        await send_all_ids(chat, ctx)
    elif text == "📊 الإحصائيات":
        await send_stats(chat, ctx, is_owner)
    elif text == "⚙️ تشغيل/إيقاف الاشتراك":
        set_setting("sub_on", "0" if setting("sub_on") == "1" else "1")
        SUB_CACHE.clear()
        status = "مفعّل" if setting("sub_on") == "1" else "معطّل"
        await ctx.bot.send_message(chat, f"الاشتراك الإجباري الآن: {status}", reply_markup=owner_markup(is_owner))
    elif text in (PAUSE_ON, PAUSE_OFF):
        set_setting("bot_on", "0" if setting("bot_on") == "1" else "1")
        status = "يعمل" if setting("bot_on") == "1" else "تحت الصيانة"
        await ctx.bot.send_message(chat, f"البوت الآن: {status}", reply_markup=owner_markup(is_owner))
    elif text in OWNER_FLOWS:
        typ, extra = OWNER_FLOWS[text]
        await start_flow(chat, ctx, typ, extra)
    else:
        return False
    return True


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if not msg or not user:
        return
    uid = user.id
    upsert_user(uid)
    staff, is_owner = is_staff(uid), uid == OWNER_ID
    ctx.user_data.pop("flow", None)

    if not is_owner and setting("bot_on") == "0":
        await msg.reply_text(MAINT_TEXT)
        return

    pending = None
    if ctx.args and re.fullmatch(r"f\d+", ctx.args[0]):
        pending = int(ctx.args[0][1:])

    if not await is_member(ctx.bot, uid):
        await msg.reply_text(GATE_TEXT, reply_markup=gate_markup(pending))
        return

    if pending:
        await send_item(ctx, msg.chat_id, find_file_by_id(pending), staff)
    await render(msg.chat_id, ctx, ("home",), staff)


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_staff(user.id):
        ctx.user_data.pop("flow", None)
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
    staff, is_owner = is_staff(uid), uid == OWNER_ID
    text = msg.text.strip()

    if not is_owner and setting("bot_on") == "0":
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
        if await owner_action(msg, ctx, uid, text):
            return
        if await handle_flow(msg, ctx, uid):
            return

    await handle_student(msg, ctx, text, staff)


async def on_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg, user = update.effective_message, update.effective_user
    if msg and user and is_staff(user.id):
        await handle_flow(msg, ctx, user.id)


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    if not cb or not cb.data:
        return
    if not cb.data.startswith("chk:"):
        await cb.answer()
        return

    uid = cb.from_user.id
    upsert_user(uid)
    if uid != OWNER_ID and setting("bot_on") == "0":
        await cb.answer(MAINT_TEXT, show_alert=True)
        return

    staff = is_staff(uid)
    if not await is_member(ctx.bot, uid):
        await cb.answer("لم تشترك بعد", show_alert=True)
        return

    await cb.answer("تم التحقق ✅")
    pending = int(cb.data[4:] or 0)
    chat = cb.message.chat_id
    if pending:
        await send_item(ctx, chat, find_file_by_id(pending), staff)
    await render(chat, ctx, ("home",), staff)


async def on_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    iq = update.inline_query
    if not iq:
        return
    results = []
    query = iq.query.strip()
    if query.isdigit() and setting("bot_on") == "1":
        row = find_file_by_id(int(query))
        if row and row["visible"]:
            name = row["teacher"] if row["kind"] == "note" and row["teacher"] else row["title"]
            link = f"https://t.me/{ctx.bot.username}?start=f{row['id']}"
            results.append(InlineQueryResultArticle(
                id=str(row["id"]),
                title=name[:64],
                description="اضغط لإرسال رابط الملف",
                input_message_content=InputTextMessageContent(f"{name}\n{link}"),
            ))
    await iq.answer(results, cache_time=0, is_personal=True)


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
    app.add_handler(MessageHandler(
        (filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO
         | filters.VOICE | filters.ANIMATION | filters.Sticker.ALL) & ~filters.COMMAND,
        on_media,
    ))
    log.info("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
