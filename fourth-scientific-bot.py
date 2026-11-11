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
    InputMediaDocument,
    InputMediaPhoto,
    InputTextMessageContent,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError
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
DB_FILE = "fourth_scientific_bot.db"
DEFAULT_CHANNEL = "@Kii_8i"
DEFAULT_FOOTER = (
    "#رابعيون : @Kii_8i\n"
    "رابط بوت ملازم الرابع العلمي : @Tiuezbot\n\n"
    "🕊️ شارك فربما تكون سبباً في تغيير مستقبل ."
)
DEFAULT_STORY = """❤️ أهلاً وسهلاً بك في شبكة رابعيون التعليمية

رابعيون مو مجرد بوت للملازم والملفات، بل مشروع انطلق حتى يكون سند إلك برحلتك الدراسية في الصف الرابع العلمي.

جمعنالك كل ما تحتاجه بمكان واحد، من كتب وملازم وملخصات وامتحانات، حتى نوفر وقتك وجهدك ونخلي وصولك للمعلومة أسهل وأسرع.

📚 هدفنا مو بس نوفرلك المصادر، وإنما نساعدك على:

- تطوير مستواك الدراسي.
- تجاوز الصعوبات وتحقيق التفوق.
- تنظيم رحلتك الدراسية والاستمرار بطموح.
- الإيمان بقدراتك وعدم الاستسلام.

نؤمن أن كل طالب عنده فرصة يصنع مستقبلاً يفتخر بيه، وأن النجاح يبدأ بخطوة وإصرار.

رابعيون مشروع بدأ بفكرة، وكبر بطموح، ومستقبله بيكم.

خلّي طموحك أكبر من الصعوبات، وابدأ رحلتك نحو التفوق ويا رابعيون.

رابعيون... رفيقك في رحلة الرابع العلمي."""

SUB_CACHE_SECONDS = 300
MEDIA_GROUP_MAX = 10
BROADCAST_BATCH = 25          # عدد الرسائل بالثانية الواحدة أثناء الإعلان
TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024

HOME_TEXT = "هلا بيك ببوت الرابع العلمي 🎓\nاختر من الأزرار بالأسفل:"
GATE_TEXT = "حتى تستخدم البوت، اشترك بالقنوات أولاً، ثم اضغط التحقق من الاشتراك."
MAINT_TEXT = "البوت تحت الصيانة، سيتم اضافة مميزات جديدة."
BACK = "🔙 رجوع"
CANCEL = "❌ إلغاء"
CONFIRM = "✅ تأكيد"
SKIP = "⏭ تخطي"
DONE = "✅ تم"
PAUSE_ON = "⏸ إيقاف البوت مؤقتاً"
PAUSE_OFF = "▶️ تشغيل البوت"
STORY_LABEL = "📖 حكاية رابعيون"
STORY_EDIT_LABEL = "📝 تعديل حكاية رابعيون"
SUB_LABEL = "🔒 الاشتراك الإجباري"
COLORS = {"🟢 أخضر": "success", "🔵 أزرق": "primary", "🔴 أحمر": "danger"}
COLOR_ROW = [("🟢 أخضر", "success"), ("🔵 أزرق", "primary"), ("🔴 أحمر", "danger")]
MEMBER_OK = ("member", "administrator", "creator")

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
Q_SECTIONS = {"ch1": "الفصل الأول", "half": "نصف السنة", "ch2": "الفصل الثاني", "end": "اسئلة نهاية السنه"}
Q_MONTHS = {"m1": "الشهر الأول", "m2": "الشهر الثاني"}
KIND_NAMES = {"book": "كتاب", "note": "ملزمة", "summary": "ملخص", "question": "أسئلة"}
KIND_FROM_AR = {"كتاب": "book", "ملزمة": "note", "ملخص": "summary"}
FILE_KINDS = {"📘 كتاب": "book", "📙 ملزمة": "note", "🧾 ملخص": "summary", "أسئلة": "question"}

# قائمة الملفات الرسمية: كل رقم يطابق الـ id في القاعدة.
# تُطبَّق مرة وحدة عند أول تشغيل (الإعداد files_snap_v4)، وتستبدل كل الملفات القديمة.
# ملفات الأسئلة (#48 و#49) مستثناة، ومحتوى أزرار الأسئلة يُفرَّغ.
FILES_SNAPSHOT = """
#2 | التربية الإسلامية | كتاب | كتاب الأسلامية [2026]
BQACAgQAAxkBAAIMDGrTcf86EWrsjrLCMOSoCuWyO9PBAAJNHQACI1sZUODQkEjwnva0PQQ
#3 | اللغة العربية | كتاب | عربي الجزء الاول
BQACAgQAAxkBAAIMDWrTcf-V58DTnf3FLrwV8Io2yc4dAAIoGwACDJ5oUKxZrmMPKeL0PQQ
#4 | English | كتاب | انكليزي كتاب الطالب [2026]
BQACAgQAAxkBAAIMD2rTcf9lMkJhjKxcOHghJNvLlOgIAAKqHgACLelYUCyIMVKYPttsPQQ
#5 | رياضيات | كتاب | كتاب الرياضيات [2027]
BQACAgQAAxkBAAIMEWrTcf-UfPStSBEcwu4O6-1UpbosAAKaIgACdIcZUjTphOSX_D_gPQQ
#6 | كيمياء | كتاب | كيمياء [2026]
BQACAgQAAxkBAAIMEmrTcf91NimvmNTMtVFNsLkV_ZxuAALcGwACLelQUBGFuxEWLZ8AAT0E
#7 | فيزياء | كتاب | فيزياء[2026]
BQACAgQAAxkBAAIME2rTcf-kFrO9ndiKQBbSlswlcZB_AALYGwACLelQUOryeBETtY9cPQQ
#8 | الحاسوب | كتاب | الحاسوب [2026]
BQACAgQAAxkBAAIMFGrTcf9SISexmrNm0npLMkITC5_kAALNGwACLelQUBvxgSA4uyxuPQQ
#9 | جرائم حزب البعث | كتاب | كتاب الجرائم [2026]
BQACAgQAAxkBAAIMFWrTcf-_zGchW7tUWpzexT82K_IIAAIOHAACLelQUFXdEILcCpwKPQQ
#10 | التربية الإسلامية | ملزمة | التربية الاسلامية
BQACAgQAAxkBAAIMt2rTdH0RfTYKY3wk8hRGR7d35CtxAAJJHAACDJ5wUKyuhgcaKePNPQQ
#11 | التربية الإسلامية | ملزمة | التربية الاسلامية
BQACAgQAAxkBAAIMuGrTdH0FJ7tsjGZyYi4XVazezONjAAKaIAACwWsxU4gqXUwm6wI1PQQ
#12 | اللغة العربية | ملزمة | أ. عمار السلامي الجزء الاول
BQACAgQAAxkBAAINA2rTdikjrRAAATgQDrNtk8eXFiJI6QACHB8AAnxQWVCOr3n_md_AlT0E
#14 | اللغة العربية | ملزمة | أ. عمار السلامي الجزء الثاني
BQACAgQAAxkBAAINBWrTdikLeFGsv6JIrqF-HWEx-CSoAAKbHAACKX3JUFPRr_fQdc4JPQQ
#15 | اللغة العربية | ملزمة | الست سمر علي الجزء الثاني
BQACAgQAAxkBAAINBmrTdil8lej0jOr-LWGeMxakiY8MAAJlHwACNPfJUa3ZFRKEEbIRPQQ
#16 | اللغة العربية | ملزمة | الست رفل الزبيدي الجزء الاول
BQACAgQAAxkBAAINVmrTd6wD3wweRUbpvC-VSbmuPbMTAAIYGwAC4MKRUzQ2SpWHZDRRPQQ
#17 | اللغة العربية | ملزمة | الست رفل الزبيدي الجزء الثاني
BQACAgQAAxkBAAINB2rTdiktwTFq1h1oz8vEIbWvDNoMAAJ7HAAC4MKJUw2Oku9xZQABiz0E
#20 | English | ملزمة | أ. طه حسين
BQACAgQAAxkBAAINp2rTeHZsqo-76x5nC8KD4_tD9UOxAAKWGgACdLfBUI50M_H1A3BHPQQ
#21 | أحياء | ملزمة | أ. احمد الجاف
BQACAgQAAxkBAAIN5mrTeUPp90D6LAZrYLFIDDWyeFetAAJHHgACc5_RUEnOH7sNOOugPQQ
#22 | أحياء | ملزمة | أ. قاسم منتصر
BQACAgQAAxkBAAIN52rTeUPQrHiyFB-r3U81Bc-dg5hLAAJFHgACc5_RULcQFdWU5YYaPQQ
#23 | كيمياء | ملزمة | أ. دانيار الجاف
BQACAgQAAxkBAAIOE2rTeeQEHH_XW70bWlGSZnmGLFWWAAJDHgACc5_RUBkWydg-5mtdPQQ
#24 | كيمياء | ملزمة | أ. مهند السوداني
BQACAgQAAxkBAAIOFGrTeeScWMz2_RJiIW1MrqbUaSDzAAJRJQAC4xPwUVOXebAX5QzKPQQ
#27 | فيزياء | ملزمة | أ. ابراهيم الخالدي
BQACAgIAAxkBAAIOaGrTe-RjhG9xIqnmZ2WLL_zKOCxEAALTrAACClrQS2j4-y5NFvb3PQQ
#28 | أحياء | ملزمة | أ. جاسم الموالي
BQACAgIAAxkBAAIOaWrTe-TsZzdSL8iwD72VGSfD7VV7AAJRowACxTBoSu6az6X2r7bgPQQ
#30 | فيزياء | ملزمة | أ. دانيار الجاف
BQACAgQAAxkBAAIOnWrTfcO3JeIoYotm6oCfX9a0vb4SAAJkGgACKX25UPkGW0tPJQkePQQ
#31 | فيزياء | ملزمة | أ. علي السوداني
BQACAgQAAxkBAAIOn2rTfcNrbHmwzCHgbyOyEzU0xrmhAAIWHwACfFBZUKz_UZO7N5ZwPQQ
#32 | الحاسوب | ملزمة | الست عواطف عبدالله
BQACAgQAAxkBAAIO1GrTfo7E8skAAYYNCN6IkA7cKguMVgACwB4AAp6IAVG9ny7t_-JyRj0E
#33 | فيزياء | ملخص | الفصل الأول | ملخص فيزياء - الفصل الأول
BQACAgIAAxkBAAIO8GrTfvWitC4uXu-YFeS2HXLCCsI4AAKGqAACYRkQStqQOPL06-8GPQQ
#34 | فيزياء | ملخص | الفصل الثاني | ملخص فيزياء - الفصل الثاني
BQACAgIAAxkBAAIO8WrTfvVdDCcpz88D85jSD23d5T4OAAK6pgACdnZoSihXFvx0p5jXPQQ
#35 | English | ملخص | الوحدة الأولى | ملخص English - الوحدة الأولى
BQACAgIAAxkBAAIPLWrTgkP69GkEIANwVq8rLvqNxog5AALfqQACIR6YShAbpWq12ikzPQQ
#36 | English | ملخص | الوحدة الثانية | ملخص English - الوحدة الثانية
BQACAgIAAxkBAAIPLmrTgkOL73qgCVQcJU4iz1ScTsidAALmqQACIR6YSs_4molH88vpPQQ
#37 | English | ملخص | الوحدة الثالثة | ملخص English - الوحدة الثالثة
BQACAgIAAxkBAAIPL2rTgkM-GVxFKnDVsfgTBpqZLMeWAALpqQACIR6YSgplyiu7Ecf9PQQ
#38 | فيزياء | ملخص | الفصل الثالث | ملخص فيزياء - الفصل الثالث
BQACAgIAAxkBAAIPb2rTiCXaBNpwzOKE2_5_If0CkaApAAJ7qwACDUCZSqhZ21Ktq9yuPQQ
#39 | التربية الإسلامية | ملخص | الوحدة الأولى | ملخص التربية الإسلامية - الوحدة الأولى
BQACAgIAAxkBAAIP32rTmJX09vS-G2W_RbsZnnGIk_1xAAI-qwACIR6YSgtzbzRKbP9HPQQ
#40 | التربية الإسلامية | ملخص | الوحدة الثانية | ملخص التربية الإسلامية - الوحدة الثانية
BQACAgIAAxkBAAIP4GrTmJUEnaM_WXnVB8eHcfbpnA67AAJAqwACIR6YSnuNU1_vcXuQPQQ
#41 | جرائم حزب البعث | ملخص | الفصل الأول | ملخص جرائم حزب البعث - الفصل الأول
BQACAgIAAxkBAAIQCGrTnUQAAUfBzeyT7QQSwunz5FsaTQACKKwAAg1AmUrCHBjDf_p_bT0E
#42 | جرائم حزب البعث | ملخص | الفصل الثاني | ملخص جرائم حزب البعث - الفصل الثاني
BQACAgIAAxkBAAIQCWrTnUSKwnnMiElZ8WQVuQABPVVnkAACO6wAAg1AmUo_ixVH5We0yz0E
#43 | جرائم حزب البعث | ملخص | الفصل الثالث | ملخص جرائم حزب البعث - الفصل الثالث
BQACAgIAAxkBAAIQCmrTnUSvIK6_i5Zqkli1JwfGMQ8uAAI_rAACDUCZSsNsVQWP8eSCPQQ
#44 | كيمياء | ملخص | الفصل الأول | ملخص كيمياء - الفصل الأول
BQACAgIAAxkBAAIQm2rTuULfkWDX5yGqlbbBRQ3WGKPiAAJorQACDUCZSoW8OcPRWm1oPQQ
#45 | كيمياء | ملخص | الفصل الثاني | ملخص كيمياء - الفصل الثاني
BQACAgIAAxkBAAIQnGrTuUIUyTSiWzG9bRS9NIHHgf-tAAJrrQACDUCZShDZUd_OdCexPQQ
#46 | كيمياء | ملخص | الفصل الثالث | ملخص كيمياء - الفصل الثالث
BQACAgIAAxkBAAIQnWrTuULRRfjFZqLYGFXKoEwCNxDiAAJwrQACDUCZSqKDWnWlR5nnPQQ
#50 | أحياء | كتاب | كتاب احياء 2026
BQACAgQAAxkBAAIja2rhBn6U_jlutinz21mhchFPUtOEAALUGwACLelQUOcd62MAAW6qsD0E
#100 | أحياء | ملزمة | أ. جاسم محمد الموالي
BQACAgIAAxkBAAIm7mriMuxRGDLi8svPDV30OCe5EK_XAAIzoQACL2PZS4qlVoTa2tadPQQ
#101 | فيزياء | ملزمة | أ. علي الذهبي «2027»
BQACAgIAAyEFAATsnMbMAAMKauRXF3tkN8L11js5ehqwxxZNiMYAAsGrAAJ1dRhLIAdwVEAq-BA9BA
#102 | اللغة العربية | ملزمة | الست سمر علي جزء الاول «2027»
BQACAgIAAxkBAAIukGrknlYRvcKleUBOco2wWDJ3bgujAAK_qwACdXUYS553Pbasf44KPQQ
#103 | English | ملزمة | أ. محمد النوفلي «2027»
BQACAgIAAxkBAAIuwGrkntN4PIAP0E9vr1u52B0wB1I-AAKsqwACqe8oS82PIQ2O2MdpPQQ
#104 | رياضيات | ملزمة | أ. حيدر وليد «2027»
BQACAgIAAxkBAAIuzmrknyfZQGMrbP0O5gIK9UQdEQIKAAKxqwACqe8oS1tJrNU7gtHwPQQ
#105 | كيمياء | ملزمة | أ. حسين حمزة «2027»
BQACAgIAAxkBAAIu22rkn2-rD9AS40jS1-lvD3a5y8mNAALDqwACdXUYS1o-cM4utShwPQQ
#106 | English | ملزمة | أ. علي الغرابي «2027»
BQACAgIAAxkBAAIvEWrkoM_OsEjLMrPq4MLIRzXnUrG3AAKtqwACqe8oSwvnZomdu65bPQQ
#107 | جرائم حزب البعث | ملزمة | أ. ابراهيم قاسم «2027»
BQACAgIAAxkBAAI6D2rnTPcb11NiijyjwQAB7Cj4ozpC8gAC5K0AAscCuEkPLdry7-XG7T0E
"""

OWNER_ACTIONS = {
    "🛠 لوحة المالك": ("panel",),
    "🏠 القائمة الرئيسية": ("home",),
    "🆔 جميع الـ IDs": ("ids",),
    "🔗 جميع الروابط": ("links",),
    "📊 الإحصائيات": ("stats",),
    PAUSE_ON: ("pause",),
    PAUSE_OFF: ("pause",),
    SUB_LABEL: ("flow", "subs"),
    STORY_EDIT_LABEL: ("flow", "story"),
    "➕ إضافة ملف": ("flow", "addfile"),
    "🆔 إضافة ملف بـ ID": ("flow", "addfile"),
    "➕ إضافة زر للأسئلة": ("flow", "addqbtn"),
    "➕ إضافة زر للملخصات": ("flow", "addsumbtn"),
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
    "📢 إعلان": ("flow", "broadcast"),
    "👥 إدارة المشرفين": ("flow", "admins"),
}
OWNER_ONLY = {"📢 إعلان", "👥 إدارة المشرفين", PAUSE_ON, PAUSE_OFF}

FLOW_FIRST = {
    "addfile": "target", "addqbtn": "qsubj", "addsummary": "subj", "addsumbtn": "subj",
    "addsection": "cname", "addsubject": "sname", "editsubject": "subj", "delsubject": "subj",
    "delsection": "csec", "editfile": "file", "replacefile": "file", "deletefile": "file",
    "togglefile": "file", "identify": "wait", "genlink": "file", "footer": "ftext",
    "broadcast": "btext", "admins": "amenu", "edit": "root", "subs": "smenu", "story": "stext",
}

NAV_KEYS = ("step", "kind", "id", "bid", "ptype", "pid", "field")

# ============================================================
# قاعدة البيانات
# ============================================================

SCHEMA_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, joined TEXT, blocked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY, added TEXT);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '', added TEXT);
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
    emoji TEXT NOT NULL DEFAULT '', color TEXT NOT NULL DEFAULT 'success',
    stype TEXT NOT NULL DEFAULT 'ch', pos INTEGER NOT NULL DEFAULT 0,
    visible INTEGER NOT NULL DEFAULT 1, hidden TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS csections (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
    emoji TEXT NOT NULL DEFAULT '📁', color TEXT NOT NULL DEFAULT 'success',
    pos INTEGER NOT NULL DEFAULT 0, visible INTEGER NOT NULL DEFAULT 1,
    message TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS cbuttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, section_id INTEGER,
    ptype TEXT NOT NULL DEFAULT 'c', pid INTEGER, name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT 'success', pos INTEGER NOT NULL DEFAULT 0,
    visible INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cbutton_id INTEGER NOT NULL,
    ctype TEXT NOT NULL, body TEXT, file_id TEXT, pos INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sumsec (
    id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER NOT NULL,
    name TEXT NOT NULL, pos INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, cbutton_id INTEGER,
    kind TEXT NOT NULL DEFAULT 'book', section TEXT, month TEXT,
    title TEXT NOT NULL DEFAULT '', teacher TEXT, file_id TEXT UNIQUE,
    ftype TEXT NOT NULL DEFAULT 'document', visible INTEGER NOT NULL DEFAULT 1,
    created TEXT);
"""

# أعمدة تُضاف للقاعدة القديمة إن كانت ناقصة (لا تُحذف أي بيانات)
MIGRATIONS = {
    "users": {"joined": "TEXT", "blocked": "INTEGER NOT NULL DEFAULT 0"},
    "admins": {"added": "TEXT"},
    "subjects": {
        "emoji": "TEXT NOT NULL DEFAULT ''", "color": "TEXT NOT NULL DEFAULT 'success'",
        "stype": "TEXT NOT NULL DEFAULT 'ch'", "pos": "INTEGER NOT NULL DEFAULT 0",
        "visible": "INTEGER NOT NULL DEFAULT 1", "hidden": "TEXT NOT NULL DEFAULT ''",
    },
    "csections": {
        "color": "TEXT NOT NULL DEFAULT 'success'", "pos": "INTEGER NOT NULL DEFAULT 0",
        "visible": "INTEGER NOT NULL DEFAULT 1", "message": "TEXT NOT NULL DEFAULT ''",
        "emoji": "TEXT NOT NULL DEFAULT '📁'",
    },
    "cbuttons": {
        "section_id": "INTEGER", "ptype": "TEXT NOT NULL DEFAULT 'c'", "pid": "INTEGER",
        "color": "TEXT NOT NULL DEFAULT 'success'", "pos": "INTEGER NOT NULL DEFAULT 0",
        "visible": "INTEGER NOT NULL DEFAULT 1",
    },
    "files": {
        "subject_id": "INTEGER", "cbutton_id": "INTEGER", "kind": "TEXT NOT NULL DEFAULT 'book'",
        "section": "TEXT", "month": "TEXT", "teacher": "TEXT", "file_id": "TEXT",
        "title": "TEXT NOT NULL DEFAULT ''", "ftype": "TEXT NOT NULL DEFAULT 'document'",
        "visible": "INTEGER NOT NULL DEFAULT 1", "created": "TEXT",
    },
}

SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS ix_files_subject ON files(subject_id, kind, section, month);
CREATE INDEX IF NOT EXISTS ix_cbuttons_parent ON cbuttons(ptype, pid);
CREATE INDEX IF NOT EXISTS ix_content_button ON content(cbutton_id);
CREATE INDEX IF NOT EXISTS ix_sumsec_subject ON sumsec(subject_id, pos);
"""

DB = sqlite3.connect(DB_FILE, check_same_thread=False)
DB.row_factory = sqlite3.Row
for _pragma in (
    "PRAGMA foreign_keys=OFF",
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA cache_size=-32000",
    "PRAGMA mmap_size=268435456",
):
    DB.execute(_pragma)

SETTINGS = {}        # كاش للإعدادات
ADMIN_IDS = set()    # كاش للمشرفين
USERS_SEEN = set()   # كاش للمستخدمين
SUB_CACHE = {}       # كاش نتيجة الاشتراك لكل مستخدم
CHANNELS = []        # كاش قنوات الاشتراك الإجباري
LAST_WARN = {}       # آخر تحذير للمالك عن كل قناة
BCAST = {"running": False}
BG_TASKS = set()


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


def spawn(coro):
    """تشغيل مهمة بالخلفية بدون ما ينتظرها الطلب الحالي."""
    task = asyncio.create_task(coro)
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)
    return task


def migrate_summaries():
    """يحوّل الفصول القديمة للملخصات (ch1, u1 ...) إلى فصول قابلة للتعديل."""
    if setting("sum_mig_v1"):
        return
    rows = q(
        "SELECT DISTINCT subject_id, section FROM files WHERE kind='summary' "
        "AND subject_id IS NOT NULL AND section IS NOT NULL ORDER BY subject_id, section"
    )
    for r in rows:
        key = r["section"]
        if key.isdigit():
            continue
        name = CH_LABELS.get(key) or UNIT_LABELS.get(key) or key
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM sumsec WHERE subject_id=?", (r["subject_id"],))["p"]
        cur = x("INSERT INTO sumsec(subject_id, name, pos) VALUES(?, ?, ?)", (r["subject_id"], name, pos))
        x("UPDATE files SET section=? WHERE kind='summary' AND subject_id=? AND section=?",
          (str(cur.lastrowid), r["subject_id"], key))
    set_setting("sum_mig_v1", "1")


def get_or_create_sumsec(sid, name):
    r = q1("SELECT id FROM sumsec WHERE subject_id=? AND name=?", (sid, name))
    if r:
        return r["id"]
    pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM sumsec WHERE subject_id=?", (sid,))["p"]
    return DB.execute("INSERT INTO sumsec(subject_id, name, pos) VALUES(?, ?, ?)", (sid, name, pos)).lastrowid


def migrate_channels():
    """ينقل القناة القديمة (تغيير القناة) إلى جدول القنوات مرة وحدة."""
    if setting("ch_mig_v1"):
        return
    if not q1("SELECT 1 FROM channels LIMIT 1"):
        old = setting("channel", DEFAULT_CHANNEL).strip()
        if old:
            ref = old if old.startswith("@") else "@" + old
            x("INSERT OR IGNORE INTO channels(ref, title, link, added) VALUES(?, ?, ?, ?)",
              (ref, ref, f"https://t.me/{ref.lstrip('@')}", now()))
    set_setting("ch_mig_v1", "1")


def load_channels():
    CHANNELS[:] = [dict(r) for r in q("SELECT id, ref, title, link FROM channels ORDER BY id")]


def parse_snapshot(text):
    rows, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") and "|" in line:
            parts = [p.strip() for p in line[1:].split("|")]
            cur = None
            kind = KIND_FROM_AR.get(parts[2]) if len(parts) > 3 else None
            if kind:
                if kind == "summary":
                    section = parts[3]
                    title = parts[4] if len(parts) > 4 else parts[3]
                else:
                    section, title = None, parts[3]
                cur = {"id": int(parts[0]), "subject": parts[1], "kind": kind,
                       "section": section, "title": title}
        elif cur is not None:
            cur["fid"] = line
            rows.append(cur)
            cur = None
    return rows


def apply_files_snapshot():
    if setting("files_snap_v4"):
        return
    subjects = {r["name"]: r["id"] for r in q("SELECT id, name FROM subjects")}
    try:
        DB.execute("DELETE FROM files")
        DB.execute("DELETE FROM content WHERE cbutton_id IN (SELECT id FROM cbuttons WHERE ptype='q')")
        for r in parse_snapshot(FILES_SNAPSHOT):
            sid = subjects.get(r["subject"])
            if sid is None:
                log.warning("Snapshot: subject not found: %s (#%s)", r["subject"], r["id"])
                continue
            section = str(get_or_create_sumsec(sid, r["section"])) if r["kind"] == "summary" else None
            DB.execute(
                "INSERT OR IGNORE INTO files(id, subject_id, kind, section, month, title, teacher, "
                "file_id, ftype, visible, created) VALUES(?, ?, ?, ?, NULL, ?, NULL, ?, ?, 1, ?)",
                (r["id"], sid, r["kind"], section, r["title"], r["fid"], ftype_from_id(r["fid"]), now()),
            )
        DB.commit()
    except Exception:
        DB.rollback()
        raise
    set_setting("files_snap_v4", "1")
    log.info("Files snapshot applied.")


def init_db():
    DB.executescript(SCHEMA_TABLES)
    for table, cols in MIGRATIONS.items():
        have = {r["name"] for r in q(f"PRAGMA table_info({table})")}
        for col, definition in cols.items():
            if col not in have:
                DB.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
    DB.commit()
    DB.executescript(SCHEMA_INDEXES)
    x("UPDATE cbuttons SET ptype='c', pid=section_id WHERE pid IS NULL AND section_id IS NOT NULL")
    for key, value in (("sub_on", "1"), ("bot_on", "1"), ("footer", DEFAULT_FOOTER), ("story", DEFAULT_STORY)):
        x("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (key, value))
    SETTINGS.update({r["key"]: r["value"] for r in q("SELECT key, value FROM settings")})
    if not setting("seed_v3"):
        for i, (name, emoji, color, stype) in enumerate(SUBJECTS, 1):
            x("INSERT OR IGNORE INTO subjects(name, emoji, color, stype, pos) VALUES(?, ?, ?, ?, ?)",
              (name, emoji, color, stype, i))
        set_setting("seed_v3", "1")
    migrate_summaries()
    migrate_channels()
    apply_files_snapshot()
    load_channels()
    ADMIN_IDS.update(r["user_id"] for r in q("SELECT user_id FROM admins"))
    log.info("Database ready.")


# ============================================================
# مساعدات عامة
# ============================================================

def is_staff(uid):
    return uid == OWNER_ID or uid in ADMIN_IDS


def upsert_user(uid):
    if uid in USERS_SEEN:
        return
    x("INSERT INTO users(user_id, joined, blocked) VALUES(?, ?, 0) "
      "ON CONFLICT(user_id) DO UPDATE SET blocked=0", (uid, now()))
    USERS_SEEN.add(uid)


def subject_label(s):
    return f"{s['emoji']} {s['name']}" if s["emoji"] else s["name"]


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


def style_for(label):
    return "danger" if any(w in label for w in ("حذف", "رجوع", "إلغاء")) else "primary"


def kb(rows):
    out = []
    for row in rows:
        line = []
        for item in row:
            text, style = item if isinstance(item, tuple) else (item, "success")
            line.append(KeyboardButton(text, style=style))
        out.append(line)
    return ReplyKeyboardMarkup(out, resize_keyboard=True, is_persistent=True)


def build_menu(ctx, items, back=True):
    """items: (النص، اللون، الإجراء[، True لزر بسطر لحاله]). تُحفظ الإجراءات لربط الضغط بها."""
    choices, rows, row, seen = {}, [], [], set()
    for it in items:
        label, style, action = it[0], it[1], it[2]
        solo = len(it) > 3 and bool(it[3])
        base = label[:60]
        text, n = base, 2
        while text in seen:
            text = f"{base[:55]} ({n})"
            n += 1
        seen.add(text)
        choices[text] = action
        if solo:
            if row:
                rows.append(row)
                row = []
            rows.append([(text, style)])
        else:
            row.append((text, style))
            if len(row) == 2:
                rows.append(row)
                row = []
    if row:
        rows.append(row)
    if back:
        rows.append([(BACK, "danger")])
    ctx.user_data["choices"] = choices
    return kb(rows)


def tg_len(s):
    """طول النص بوحدات تلغرام (UTF-16)."""
    return len(s.encode("utf-16-le")) // 2


def make_caption(head, footer):
    """يقص العنوان فقط ويحافظ على التذييل كاملاً."""
    if not footer:
        return head[:CAPTION_LIMIT]
    room = CAPTION_LIMIT - tg_len(footer) - 2
    if room < 1:
        return footer[:CAPTION_LIMIT]
    return f"{head[:room]}\n\n{footer}"


def footer_caption():
    footer = setting("footer", DEFAULT_FOOTER)
    return footer[:CAPTION_LIMIT] if footer else None


def gate_markup(token=""):
    rows = [[InlineKeyboardButton(f"📢 {c['title'] or c['ref']}"[:60], url=c["link"], style="primary")]
            for c in CHANNELS if c["link"]]
    rows.append([InlineKeyboardButton("✅ التحقق من الاشتراك", callback_data=f"chk:{token}", style="primary")])
    return InlineKeyboardMarkup(rows)


def story_text():
    return setting("story", DEFAULT_STORY)


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


def chat_arg(ref):
    return int(ref) if re.fullmatch(r"-?\d+", ref) else ref


def parse_ref(text):
    t = (text or "").strip()
    if "t.me/" in t:
        t = t.split("t.me/", 1)[1].split("?", 1)[0].strip("/")
        if not t or t.startswith("+"):
            return None
        t = "@" + t
    if re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,}", t):
        return t
    if re.fullmatch(r"-100\d+", t):
        return t
    return None


# ============================================================
# الأزرار والمحتوى والملخصات
# ============================================================

def children(ptype, pid, visible_only=True):
    sql = "SELECT * FROM cbuttons WHERE ptype=? AND pid=?"
    if visible_only:
        sql += " AND visible=1"
    return q(sql + " ORDER BY pos, id", (ptype, pid))


def insert_content(cbid, ctype, body, fid):
    x(
        "INSERT INTO content(cbutton_id, ctype, body, file_id, pos) VALUES(?, ?, ?, ?, "
        "(SELECT COALESCE(MAX(pos), 0) + 1 FROM content WHERE cbutton_id=?))",
        (cbid, ctype, body, fid, cbid),
    )


def content_step(cbid, text, media):
    if text == DONE:
        return "done"
    if text in (BACK, CANCEL):
        return "bad"
    if media[0]:
        insert_content(cbid, media[1], None, media[0])
        return "added"
    if text.startswith("ID:"):
        fid = text[3:].strip()
        if not looks_like_id(fid):
            return "bad"
        insert_content(cbid, ftype_from_id(fid), None, fid)
        return "added"
    if looks_like_id(text):
        insert_content(cbid, ftype_from_id(text), None, text)
        return "added"
    if text:
        insert_content(cbid, "text", text, None)
        return "added"
    return "bad"


def content_items(cbid):
    """المحتوى بالترتيب: أولاً محتوى الزر، ثم الملفات القديمة المرتبطة به."""
    items = [(r["ctype"], r["body"], r["file_id"])
             for r in q("SELECT * FROM content WHERE cbutton_id=? ORDER BY pos, id", (cbid,))]
    for r in q("SELECT * FROM files WHERE cbutton_id=? AND visible=1 ORDER BY id", (cbid,)):
        items.append(("photo" if r["ftype"] == "photo" else "document", None, r["file_id"]))
    return items


def purge_button(cid):
    """يحذف الزر وكل ما تحته، ولا يحذف الملفات (يفصلها فقط)."""
    for ch in q("SELECT id FROM cbuttons WHERE ptype='b' AND pid=?", (cid,)):
        purge_button(ch["id"])
    x("UPDATE files SET cbutton_id=NULL WHERE cbutton_id=?", (cid,))
    x("DELETE FROM content WHERE cbutton_id=?", (cid,))
    x("DELETE FROM cbuttons WHERE id=?", (cid,))


def button_path(cid):
    parts, cur = [], cid
    for _ in range(10):
        b = q1("SELECT * FROM cbuttons WHERE id=?", (cur,))
        if not b:
            break
        parts.append(b["name"])
        if b["ptype"] == "b":
            cur = b["pid"]
            continue
        if b["ptype"] == "s":
            s = q1("SELECT name FROM subjects WHERE id=?", (b["pid"],))
            parts.append(s["name"] if s else "")
        elif b["ptype"] == "c":
            c = q1("SELECT name FROM csections WHERE id=?", (b["pid"],))
            parts.append(c["name"] if c else "")
        elif b["ptype"] == "q":
            s = q1("SELECT name FROM subjects WHERE id=?", (b["pid"],))
            parts.append(f"أسئلة {s['name']}" if s else "أسئلة")
        break
    return " › ".join(p for p in reversed(parts) if p)


def button_parent_screen(cbid):
    b = q1("SELECT ptype, pid FROM cbuttons WHERE id=?", (cbid,))
    if not b:
        return ("home",)
    return {
        "b": ("btn", b["pid"]), "s": ("subject", b["pid"]),
        "c": ("csec", b["pid"]), "q": ("qsubj", b["pid"]),
    }.get(b["ptype"], ("home",))


def sum_list(sid):
    return q("SELECT * FROM sumsec WHERE subject_id=? ORDER BY pos, id", (sid,))


def sum_name(key):
    if not key or not str(key).isdigit():
        return str(key or "")
    r = q1("SELECT name FROM sumsec WHERE id=?", (int(key),))
    return r["name"] if r else ""


def create_subject(name, emoji, names):
    """ينشئ المادة وفصولها كعملية واحدة، فإذا فشلت شي ما يبقى ناقص."""
    try:
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM subjects")["p"]
        cur = DB.execute(
            "INSERT INTO subjects(name, emoji, color, stype, pos) VALUES(?, ?, 'success', 'ch', ?)",
            (name, emoji, pos))
        sid = cur.lastrowid
        for i, n in enumerate(names, 1):
            DB.execute("INSERT INTO sumsec(subject_id, name, pos) VALUES(?, ?, ?)", (sid, n, i))
        DB.commit()
        return sid
    except Exception:
        DB.rollback()
        raise


# ============================================================
# إرسال الملفات والمحتوى (الصور المتتالية تُرسل ألبوماً واحداً)
# ============================================================

def split_text(body, limit=3900):
    body = body or ""
    parts = [body[i:i + limit] for i in range(0, len(body), limit)]
    return [p for p in parts if p.strip()]


async def _send_single(ctx, chat, ctype, fid, caption=None):
    if ctype == "photo":
        await ctx.bot.send_photo(chat, fid, caption=caption)
    else:
        await ctx.bot.send_document(chat, fid, caption=caption)


async def send_group(ctx, chat, ctype, values, caption=None):
    if ctype == "text":
        for body in values:
            for part in split_text(body):
                try:
                    await ctx.bot.send_message(chat, part)
                except TelegramError as e:
                    log.error("Text send failed: %s", e)
        return
    if len(values) == 1:
        try:
            await _send_single(ctx, chat, ctype, values[0], caption)
        except TelegramError as e:
            log.error("Single send failed: %s", e)
        return
    cls = InputMediaPhoto if ctype == "photo" else InputMediaDocument
    media = [cls(v) for v in values]
    if caption:
        media[0] = cls(values[0], caption=caption)
    try:
        await ctx.bot.send_media_group(chat, media)
    except TelegramError as e:
        log.error("Media group failed, sending one by one: %s", e)
        for i, v in enumerate(values):
            try:
                await _send_single(ctx, chat, ctype, v, caption if i == 0 else None)
            except TelegramError as e2:
                log.error("Fallback send failed: %s", e2)


async def send_items(ctx, chat, items, caption=None):
    """items: قائمة (النوع، النص، الـ file_id) بالترتيب المطلوب."""
    groups = []
    for ctype, body, fid in items:
        if ctype == "text":
            groups.append(("text", [body]))
        elif groups and groups[-1][0] == ctype and len(groups[-1][1]) < MEDIA_GROUP_MAX:
            groups[-1][1].append(fid)
        else:
            groups.append((ctype, [fid]))
    cap_left = caption
    for ctype, values in groups:
        cap = None
        if ctype != "text" and cap_left:
            cap, cap_left = cap_left, None
        await send_group(ctx, chat, ctype, values, cap)


async def send_file(ctx, chat, row_id, uid):
    row = q1("SELECT * FROM files WHERE id=?", (row_id,))
    if not row or (not row["visible"] and not is_staff(uid)):
        await ctx.bot.send_message(chat, "الملف غير متاح حالياً.")
        return
    head = row["teacher"] if row["kind"] == "note" and row["teacher"] else row["title"]
    caption = make_caption(head, setting("footer", DEFAULT_FOOTER))
    try:
        if row["ftype"] == "photo":
            await ctx.bot.send_photo(chat, row["file_id"], caption=caption)
        else:
            await ctx.bot.send_document(chat, row["file_id"], caption=caption)
    except TelegramError as e:
        log.error("Send failed for file %s: %s", row["id"], e)
        await ctx.bot.send_message(chat, "تعذر إرسال الملف. أبلغ المالك.")


async def send_question_set(ctx, chat, sid, sec, month, uid):
    rows = q(
        "SELECT * FROM files WHERE kind='question' AND subject_id=? AND section IS ? AND month IS ? "
        "AND visible=1 ORDER BY id",
        (sid, sec, month),
    )
    if not rows:
        await ctx.bot.send_message(chat, "سيتم إضافة الأسئلة لاحقاً.")
        return
    items = [("photo" if r["ftype"] == "photo" else "document", None, r["file_id"]) for r in rows]
    await send_items(ctx, chat, items, caption=footer_caption())


async def deliver(ctx, chat, token, uid):
    """فتح الرابط العميق: f = ملف، c = زر."""
    if not re.fullmatch(r"[fc]\d+", token or ""):
        return
    n = int(token[1:])
    if token[0] == "f":
        await send_file(ctx, chat, n, uid)
        return
    row = q1("SELECT * FROM cbuttons WHERE id=?", (n,))
    if not row or (not row["visible"] and not is_staff(uid)):
        await ctx.bot.send_message(chat, "المحتوى غير متاح حالياً.")
        return
    items = content_items(n)
    if not items:
        await ctx.bot.send_message(chat, "لا يوجد محتوى حالياً.")
        return
    await send_items(ctx, chat, items, caption=footer_caption())


# ============================================================
# شاشات الطالب
# ============================================================

def build_home(ctx, staff):
    items = [(STORY_LABEL, "primary", ("story",), True)]
    for s in q("SELECT * FROM subjects WHERE visible=1 ORDER BY pos, id"):
        items.append((subject_label(s), s["color"], ("nav", ("subject", s["id"]))))
    for c in q("SELECT * FROM csections WHERE visible=1 ORDER BY pos, id"):
        items.append((csec_label(c), c["color"], ("nav", ("csec", c["id"]))))
    if staff:
        items.append(("🛠 لوحة المالك", "primary", ("panel",)))
    return HOME_TEXT, build_menu(ctx, items, back=False)


def build_subject(ctx, sid):
    s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
    if not s:
        return "المادة غير متاحة حالياً.", build_menu(ctx, [])
    hidden = hidden_set(s["hidden"])
    items = []
    if "book" not in hidden:
        items.append(("📘 الكتب", "success", ("nav", ("list", sid, "book"))))
    if "note" not in hidden:
        items.append(("📙 الملازم", "success", ("nav", ("list", sid, "note"))))
    if "summary" not in hidden:
        items.append(("🧾 الملخصات", "success", ("nav", ("summaries", sid))))
    if "questions" not in hidden:
        items.append(("الأسئلة", "primary", ("nav", ("qsubj", sid))))
    for b in children("s", sid):
        items.append((b["name"], b["color"], ("btn", b["id"])))
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
    items = [(r["name"], "success", ("sumsec", r["id"])) for r in sum_list(sid)]
    if not items:
        return f"🧾 الملخصات — {s['name']}\nسيتم إضافة الملخصات لاحقاً.", build_menu(ctx, [])
    return f"🧾 الملخصات — {s['name']}\nاختر:", build_menu(ctx, items)


def build_csec(ctx, cid):
    c = q1("SELECT * FROM csections WHERE id=?", (cid,))
    if not c:
        return "القسم غير متاح حالياً.", build_menu(ctx, [])
    items = [(b["name"], b["color"], ("btn", b["id"])) for b in children("c", cid)]
    if not items:
        return (c["message"] or "لا يوجد محتوى حالياً."), build_menu(ctx, [])
    return f"{csec_label(c)}\nاختر:", build_menu(ctx, items)


def build_qsubj(ctx, sid):
    s = q1("SELECT * FROM subjects WHERE id=?", (sid,))
    if not s:
        return "المادة غير متاحة حالياً.", build_menu(ctx, [])
    items = [(b["name"], b["color"], ("btn", b["id"])) for b in children("q", sid)]
    seen = set()
    for r in q("SELECT id, section, month, title FROM files WHERE kind='question' AND subject_id=? "
               "AND visible=1 ORDER BY id", (sid,)):
        key = (r["section"], r["month"])
        if key in seen:
            continue
        seen.add(key)
        items.append((r["title"], "primary", ("qset", sid, r["section"], r["month"])))
    if not items:
        return f"الأسئلة — {s['name']}\nسيتم إضافة الأسئلة لاحقاً.", build_menu(ctx, [])
    return f"الأسئلة — {s['name']}\nاختر:", build_menu(ctx, items)


async def render_button(chat, ctx, cbid, uid):
    row = q1("SELECT * FROM cbuttons WHERE id=?", (cbid,))
    if not row or (not row["visible"] and not is_staff(uid)):
        await ctx.bot.send_message(chat, "هذا القسم غير متاح حالياً.", reply_markup=build_menu(ctx, []))
        return
    ctx.user_data["screen"] = ("btn", cbid)
    items = content_items(cbid)
    if items:
        await send_items(ctx, chat, items, caption=footer_caption())
    kids = children("b", cbid)
    if kids:
        text = f"{row['name']}\nاختر:"
        markup = build_menu(ctx, [(k["name"], k["color"], ("btn", k["id"])) for k in kids])
    else:
        text = row["name"] if items else "لا يوجد محتوى حالياً."
        markup = build_menu(ctx, [])
    await ctx.bot.send_message(chat, text, reply_markup=markup)


async def render(chat, ctx, screen, uid):
    k = screen[0]
    if k == "btn":
        await render_button(chat, ctx, screen[1], uid)
        return
    if k == "subject":
        text, markup = build_subject(ctx, screen[1])
    elif k == "list":
        text, markup = build_list(ctx, screen[1], screen[2])
    elif k == "summaries":
        text, markup = build_summaries(ctx, screen[1])
    elif k == "csec":
        text, markup = build_csec(ctx, screen[1])
    elif k == "qsubj":
        text, markup = build_qsubj(ctx, screen[1])
    else:
        screen = ("home",)
        text, markup = build_home(ctx, is_staff(uid))
    ctx.user_data["screen"] = screen
    await ctx.bot.send_message(chat, text, reply_markup=markup)


def parent_of(screen):
    k = screen[0]
    if k == "btn":
        return button_parent_screen(screen[1])
    if k in ("list", "summaries", "qsubj"):
        return ("subject", screen[1])
    return ("home",)


async def do_action(chat, ctx, action, uid):
    k = action[0]
    if k == "nav":
        await render(chat, ctx, action[1], uid)
    elif k == "btn":
        await render(chat, ctx, ("btn", action[1]), uid)
    elif k == "file":
        await send_file(ctx, chat, action[1], uid)
    elif k == "story":
        await ctx.bot.send_message(chat, story_text())
    elif k == "sumsec":
        rows = q("SELECT id FROM files WHERE kind='summary' AND section=? AND visible=1 ORDER BY id",
                 (str(action[1]),))
        if not rows:
            await ctx.bot.send_message(chat, "سيتم إضافة الملخصات لاحقاً.")
            return
        for r in rows:
            await send_file(ctx, chat, r["id"], uid)
    elif k == "qset":
        await send_question_set(ctx, chat, action[1], action[2], action[3], uid)
    elif k == "panel":
        await open_panel(chat, ctx, uid == OWNER_ID)


# ============================================================
# الاشتراك الإجباري (قنوات متعددة، فحص متوازٍ مع كاش)
# ============================================================

async def warn_owner(bot, ref, err):
    log.warning("Subscription check failed for %s: %s", ref, err)
    t = time.time()
    if t - LAST_WARN.get(ref, 0) < 3600:
        return
    LAST_WARN[ref] = t
    try:
        await bot.send_message(
            OWNER_ID,
            f"⚠️ تعذر فحص الاشتراك في القناة {ref}، والبوت يتخطاها مؤقتاً.\n"
            f"تأكد أن البوت أدمن فيها.\nالسبب: {err}",
        )
    except TelegramError:
        pass


async def _check_one(bot, ref, uid):
    try:
        m = await bot.get_chat_member(chat_arg(ref), uid)
    except TelegramError as e:
        spawn(warn_owner(bot, ref, e))   # لا ينتظر الطالب التحذير
        return True                      # نتخطى القناة إذا فشل الفحص
    if m.status in MEMBER_OK or (m.status == "restricted" and getattr(m, "is_member", False)):
        return True
    return False


async def is_member(bot, uid):
    if is_staff(uid) or setting("sub_on") != "1" or not CHANNELS:
        return True
    if SUB_CACHE.get(uid, 0) > time.time():
        return True
    refs = [c["ref"] for c in CHANNELS]
    results = await asyncio.gather(*(_check_one(bot, r, uid) for r in refs))
    ok = all(results)
    if ok:
        if len(SUB_CACHE) > 50000:
            SUB_CACHE.clear()
        SUB_CACHE[uid] = time.time() + SUB_CACHE_SECONDS
    return ok


# ============================================================
# لوحة المالك
# ============================================================

def owner_markup(is_owner):
    pause = PAUSE_OFF if setting("bot_on") == "0" else PAUSE_ON
    rows = [
        [("➕ إضافة ملف", "success"), ("🆔 إضافة ملف بـ ID", "success")],
        [("➕ إضافة زر للأسئلة", "success"), ("➕ إضافة زر للملخصات", "success")],
        [("➕ إضافة ملخصات", "success"), ("➕ إضافة قسم جديد", "success")],
        [("🧩 تعديل الأزرار", "success"), ("✏️ تعديل ملف", "success")],
        [("🔁 استبدال ملف", "success"), ("🗑 حذف ملف", "danger")],
        [("👁 إخفاء/إظهار ملف", "primary"), ("➕ إضافة مادة", "success")],
        [("✏️ تعديل مادة", "success"), ("🗑 حذف مادة", "danger")],
        [("🗑 حذف قسم", "danger"), ("🆔 جميع الـ IDs", "primary")],
        [("🔗 جميع الروابط", "primary"), ("🔎 التعرف على ID", "primary")],
        [("🔗 إنشاء رابط", "success"), ("📊 الإحصائيات", "primary")],
        [("📝 تعديل الوصف", "primary"), (SUB_LABEL, "primary")],
        [(STORY_EDIT_LABEL, "primary")],
    ]
    if is_owner:
        rows.append([("📢 إعلان", "primary"), (pause, "primary")])
        rows.append([("👥 إدارة المشرفين", "primary")])
    rows.append([("🏠 القائمة الرئيسية", "danger")])
    return kb(rows)


async def open_panel(chat, ctx, is_owner):
    ctx.user_data.pop("flow", None)
    await ctx.bot.send_message(chat, "🛠 لوحة المالك", reply_markup=owner_markup(is_owner))


def section_text(r):
    """نص القسم أو الفصل لأي ملف، يُقرأ من القاعدة الحالية."""
    if r["kind"] == "summary" and r["section"]:
        return sum_name(r["section"])
    text = ""
    if r["section"]:
        text = CH_LABELS.get(r["section"]) or UNIT_LABELS.get(r["section"]) or Q_SECTIONS.get(r["section"], "")
    if r["month"]:
        text = (text + " " if text else "") + Q_MONTHS.get(r["month"], "")
    return text


def all_ids_lines():
    lines = []
    for r in q("SELECT f.*, s.name AS sn FROM files f LEFT JOIN subjects s ON s.id=f.subject_id ORDER BY f.id"):
        parts = [r["sn"] or "-", KIND_NAMES.get(r["kind"], r["kind"]), section_text(r)]
        name = r["teacher"] if r["kind"] == "note" and r["teacher"] else r["title"]
        lines.append(f"#{r['id']} | " + " | ".join(html.escape(p) for p in parts if p)
                     + f" | {html.escape(name)}\n<code>{r['file_id']}</code>")
    for it in q(
        "SELECT ct.id, ct.file_id, cb.name AS bn FROM content ct JOIN cbuttons cb ON cb.id=ct.cbutton_id "
        "WHERE ct.ctype<>'text' ORDER BY ct.id"
    ):
        lines.append(f"C#{it['id']} | محتوى زر | {html.escape(it['bn'])}\n<code>{it['file_id']}</code>")
    return lines


async def send_lines(chat, ctx, lines, parse_mode=None, markup=None):
    chunk = ""
    for line in lines:
        block = line + "\n\n"
        if len(chunk) + len(block) > 3500:
            await ctx.bot.send_message(chat, chunk, parse_mode=parse_mode)
            chunk = ""
        chunk += block
    if chunk.strip():
        await ctx.bot.send_message(chat, chunk, parse_mode=parse_mode, reply_markup=markup)


async def send_all_ids(chat, ctx, is_owner):
    lines = all_ids_lines()
    if not lines:
        await ctx.bot.send_message(chat, "لا توجد ملفات.", reply_markup=owner_markup(is_owner))
        return
    await send_lines(chat, ctx, lines, parse_mode=ParseMode.HTML, markup=owner_markup(is_owner))


async def send_all_links(chat, ctx, is_owner):
    username = ctx.bot.username
    lines, seen = [], set()
    for r in q("SELECT f.*, s.name AS sn FROM files f LEFT JOIN subjects s ON s.id=f.subject_id "
               "WHERE f.visible=1 ORDER BY f.id"):
        name = r["teacher"] if r["kind"] == "note" and r["teacher"] else r["title"]
        parts = [r["sn"] or "بدون مادة", KIND_NAMES.get(r["kind"], r["kind"]), section_text(r)]
        link = f"https://t.me/{username}?start=f{r['id']}"
        if link in seen:
            continue
        seen.add(link)
        lines.append(f"{name}\n{' | '.join(p for p in parts if p)}\n{link}")
    for cb in q("SELECT * FROM cbuttons WHERE visible=1 ORDER BY id"):
        has_content = q1("SELECT 1 FROM content WHERE cbutton_id=? LIMIT 1", (cb["id"],)) or \
            q1("SELECT 1 FROM files WHERE cbutton_id=? AND visible=1 LIMIT 1", (cb["id"],))
        if not has_content:
            continue
        link = f"https://t.me/{username}?start=c{cb['id']}"
        if link in seen:
            continue
        seen.add(link)
        lines.append(f"📦 {cb['name']}\n{button_path(cb['id'])}\n{link}")
    if not lines:
        await ctx.bot.send_message(chat, "لا توجد روابط.", reply_markup=owner_markup(is_owner))
        return
    await ctx.bot.send_message(chat, f"🔗 جميع الروابط ({len(lines)})")
    await send_lines(chat, ctx, lines, markup=owner_markup(is_owner))


async def send_stats(chat, ctx, is_owner):
    def count(sql, p=()):
        return q1(sql, p)[0]

    text = (
        "📊 الإحصائيات\n\n"
        f"المستخدمون: {count('SELECT COUNT(*) FROM users')}\n"
        f"المحظورون: {count('SELECT COUNT(*) FROM users WHERE blocked=1')}\n"
        f"المشرفون: {count('SELECT COUNT(*) FROM admins')}\n"
        f"المواد الظاهرة: {count('SELECT COUNT(*) FROM subjects WHERE visible=1')}\n"
        f"الأقسام: {count('SELECT COUNT(*) FROM csections')}\n"
        f"الكتب: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('book',))}\n"
        f"الملازم: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('note',))}\n"
        f"الملخصات: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('summary',))}\n"
        f"الأسئلة: {count('SELECT COUNT(*) FROM files WHERE kind=?', ('question',))}\n"
        f"الملفات المخفية: {count('SELECT COUNT(*) FROM files WHERE visible=0')}\n"
        f"القنوات الإجبارية: {len(CHANNELS)}\n"
        f"الاشتراك: {'مفعّل' if setting('sub_on') == '1' else 'معطّل'}"
    )
    await ctx.bot.send_message(chat, text, reply_markup=owner_markup(is_owner))


async def _send_bcast(bot, uid, text):
    for _ in range(2):
        try:
            await bot.send_message(uid, text)
            return True
        except RetryAfter as e:
            await asyncio.sleep(min(e.retry_after, 30))
        except Forbidden:
            x("UPDATE users SET blocked=1 WHERE user_id=?", (uid,))
            USERS_SEEN.discard(uid)
            return False
        except TelegramError:
            return False
    return False


async def run_broadcast(bot, text, report_chat):
    BCAST["running"] = True
    ok = bad = 0
    try:
        uids = [r["user_id"] for r in q("SELECT user_id FROM users WHERE blocked=0")]
        for i in range(0, len(uids), BROADCAST_BATCH):
            res = await asyncio.gather(*(_send_bcast(bot, u, text) for u in uids[i:i + BROADCAST_BATCH]))
            ok += sum(1 for r in res if r)
            bad += sum(1 for r in res if not r)
            await asyncio.sleep(1)
        await bot.send_message(report_chat, f"✅ انتهى الإعلان.\nنجح: {ok}\nفشل: {bad}")
    except Exception:
        log.exception("Broadcast failed")
    finally:
        BCAST["running"] = False


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
    elif k == "links":
        await send_all_links(chat, ctx, is_owner)
    elif k == "stats":
        await send_stats(chat, ctx, is_owner)
    elif k == "pause":
        set_setting("bot_on", "0" if setting("bot_on") == "1" else "1")
        status = "يعمل" if setting("bot_on") == "1" else "تحت الصيانة"
        await msg.reply_text(f"البوت الآن: {status}", reply_markup=owner_markup(is_owner))
    elif k == "flow":
        if spec[1] == "story":
            await ctx.bot.send_message(chat, "📖 النص الحالي:")
            await ctx.bot.send_message(chat, story_text())
        await start_flow(chat, ctx, spec[1])


# ============================================================
# محرك التدفقات
# ============================================================

async def flow_prompt(chat, ctx):
    f = ctx.user_data["flow"]
    text, rows = flow_build(f)
    await ctx.bot.send_message(chat, text, reply_markup=kb(list(rows) + [[(CANCEL, "danger")]]))


async def goto(chat, ctx, f, step):
    f["step"] = step
    await flow_prompt(chat, ctx)


def snapshot(f):
    return {k: f[k] for k in NAV_KEYS if k in f}


async def enter(chat, ctx, f, step, **state):
    """ينتقل لشاشة جديدة ويحفظ حالة الشاشة الحالية للرجوع إليها (بدون ما يفقد الأرقام)."""
    f.setdefault("hist", []).append(snapshot(f))
    f.update(state)
    f["step"] = step
    await flow_prompt(chat, ctx)


async def go_back(chat, ctx, f):
    prev = f["hist"].pop() if f.get("hist") else {"step": "root"}
    for k in NAV_KEYS:
        if k not in prev:
            f.pop(k, None)
    f.update(prev)
    await flow_prompt(chat, ctx)


async def start_flow(chat, ctx, typ, **extra):
    ctx.user_data["flow"] = {"type": typ, "step": FLOW_FIRST[typ], "hist": [], **extra}
    await flow_prompt(chat, ctx)


async def fail(msg, ctx, hint):
    await msg.reply_text(hint)
    await flow_prompt(msg.chat_id, ctx)


async def finish(msg, ctx, text, uid):
    ctx.user_data.pop("flow", None)
    await msg.reply_text(text, reply_markup=owner_markup(uid == OWNER_ID))


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
        if not items:
            return "لا توجد أزرار داخل هذا القسم. أضف زراً من 🧩 تعديل الأزرار أولاً.", []
        return "اختر الزر داخل القسم:", pair(items)

    if step == "kind":
        return "اختر نوع المحتوى:", [
            [("📘 كتاب", "success"), ("📙 ملزمة", "success")],
            [("🧾 ملخص", "success"), ("أسئلة", "primary")],
        ]

    if step == "sumpick":
        f["map"], items = {}, []
        for r in sum_list(f["sid"]):
            f["map"][r["name"]] = r["id"]
            items.append((r["name"], "success"))
        return "اختر الفصل أو الوحدة للملخص:", pair(items)

    if step == "qpick":
        f["map"], items = {}, []
        for b in q("SELECT * FROM cbuttons WHERE ptype='q' AND pid=? ORDER BY pos, id", (f["sid"],)):
            f["map"][b["name"]] = b["id"]
            items.append((b["name"], b["color"]))
        return "اختر قسم الأسئلة:", pair(items)

    if step == "payload":
        if "bid" in f:
            return "أرسل الصور أو الملفات أو النص، أو ID: ثم الـ ID. عند الانتهاء اضغط تم.", [[(DONE, "success")]]
        rows = [[(DONE, "success")]] if f.get("loop") else []
        return "أرسل الملف أو الصورة، أو أرسل الـ ID كنص.", rows

    if step == "title":
        return "أرسل اسم الملف:", []

    if step == "teacher":
        return "أرسل اسم الأستاذ، أو اضغط تخطي:", [[(SKIP, "primary")]]

    if step in ("subj", "qsubj"):
        return "اختر المادة:", pair([(subject_label(s), s["color"])
                                      for s in q("SELECT * FROM subjects ORDER BY pos, id")])

    if step == "qbname":
        return "أرسل اسم الزر، مثل: أسئلة الشهر الأول:", []

    if step == "qbcolor":
        return "اختر لون الزر:", [COLOR_ROW]

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
        return "أرسل إيموجي المادة، أو اضغط تخطي إذا لا تريد إيموجي:", [[(SKIP, "primary")]]

    if step == "sumnames":
        listed = "\n".join(f"- {n}" for n in f.get("sumnames", [])) or "لا يوجد بعد"
        return (
            "أرسل اسم فصل أو وحدة للملخصات واحداً تلو الآخر.\n"
            "عند الانتهاء اضغط تم، أو تخطَّ إذا لا تريد ملخصات.\n"
            f"المضاف:\n{listed}"
        ), [[(SKIP, "primary"), (DONE, "success")]]

    if step == "sfield":
        return "اختر ما تريد تعديله:", [[("✏️ الاسم", "success"), ("😀 الإيموجي", "success")]]

    if step == "svalue":
        rows = [[(SKIP, "primary")]] if f.get("col") == "emoji" else []
        return "أرسل القيمة الجديدة:", rows

    if step == "sact":
        return "اختر ما تريد فعله بفصول الملخصات:", [
            [("➕ فصل جديد", "success")],
            [("✏️ تعديل اسم فصل", "primary"), ("🗑 حذف فصل", "danger")],
        ]

    if step == "sadd":
        return "أرسل اسم الفصل أو الوحدة الجديد:", []

    if step in ("srpick", "sdpick"):
        f["map"], items = {}, []
        for r in sum_list(f["sid"]):
            f["map"][r["name"]] = r["id"]
            items.append((r["name"], "success" if step == "srpick" else "danger"))
        text = "اختر الفصل لتعديل اسمه:" if step == "srpick" else "اختر الفصل لحذفه:"
        if not items:
            text = "لا توجد فصول لهذه المادة بعد."
        return text, pair(items)

    if step == "srename":
        return "أرسل الاسم الجديد للفصل:", []

    if step == "file":
        f["map"] = {}
        rows = []
        for r in q("SELECT id, title FROM files ORDER BY id"):
            label = f"#{r['id']} {r['title']}"[:60]
            f["map"][label] = r["id"]
            rows.append([(label, "success")])
        return "اختر الملف، أو أرسل رقمه مثل #12:", rows

    if step == "ffield":
        return "اختر ما تريد تعديله:", [[("✏️ الاسم", "success"), ("👨‍🏫 الأستاذ", "success")]]

    if step == "fvalue":
        rows = [[(SKIP, "primary")]] if f.get("col") == "teacher" else []
        return "أرسل القيمة الجديدة:", rows

    if step == "confirm":
        if f["do"][0] == "delsumsec":
            return "⚠️ سيتم حذف الفصل وكل ملخصاته. هل تؤكد؟", [[(CONFIRM, "danger")]]
        if f["do"][0] == "delch":
            return "⚠️ سيتم حذف القناة من الاشتراك الإجباري. هل تؤكد؟", [[(CONFIRM, "danger")]]
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

    # ----- الاشتراك الإجباري -----
    if step == "smenu":
        status = "مفعّل" if setting("sub_on") == "1" else "معطّل"
        note = "\n⚠️ ما فيه قنوات، فالاشتراك ما يفرض شي." if not CHANNELS else ""
        return (f"🔒 الاشتراك الإجباري\nالحالة: {status}\nعدد القنوات: {len(CHANNELS)}{note}\nاختر:"), [
            [("➕ إضافة قناة", "success"), ("📋 القنوات والحذف", "primary")],
            [("⚙️ تشغيل/إيقاف الاشتراك", "primary")],
            [(BACK, "danger")],
        ]

    if step == "chref":
        return ("أرسل معرف القناة:\n- عامة: @username\n- خاصة: رقمها مثل -1001234567890\n"
                "البوت لازم يكون أدمن فيها."), [[(BACK, "danger")]]

    if step == "chlink":
        return ("القناة الخاصة ما قدرت أطلع لها رابط دعوة. "
                "أرسل رابط الدعوة (يبدأ بـ https://t.me/):"), [[(BACK, "danger")]]

    if step == "chlist":
        f["map"], items = {}, []
        for c in CHANNELS:
            label = f"🗑 {c['ref']}"[:60]
            f["map"][label] = c["id"]
            items.append((label, "danger"))
        text = "اختر القناة لحذفها:" if items else "لا توجد قنوات مضافة."
        return text, pair(items) + [[(BACK, "danger")]]

    # ----- حكاية رابعيون -----
    if step == "stext":
        return f"أرسل النص الجديد لحكاية رابعيون (حد أقصى {TEXT_LIMIT} حرف):", [[(BACK, "danger")]]

    # ----- المحرر: مادة/قسم ← أزرار ← زر داخل زر ... -----
    if step == "root":
        f["map"], items = {}, []
        for s in q("SELECT * FROM subjects ORDER BY pos, id"):
            f["map"][subject_label(s)] = ("s", s["id"])
            items.append((subject_label(s), s["color"]))
        for c in q("SELECT * FROM csections ORDER BY pos, id"):
            f["map"][csec_label(c)] = ("c", c["id"])
            items.append((csec_label(c), c["color"]))
        return "🧩 اختر المادة أو القسم:", pair(items) + [[(BACK, "danger")]]

    if step == "node":
        f["opts"] = {}
        if f["kind"] == "s":
            s = q1("SELECT * FROM subjects WHERE id=?", (f["id"],))
            hidden = hidden_set(s["hidden"])
            title = subject_label(s)
            for key, name in (("book", "📘 الكتب"), ("note", "📙 الملازم"),
                              ("summary", "🧾 الملخصات"), ("questions", "الأسئلة")):
                f["opts"][f"{name}: {'مخفي' if key in hidden else 'ظاهر'}"] = ("tog", key)
            f["opts"]["➕ زر جديد داخل المادة"] = ("newbtn", "s", f["id"])
            f["opts"]["🗂 الأزرار الإضافية"] = ("blist", "s", f["id"])
            f["opts"]["أزرار الأسئلة"] = ("blist", "q", f["id"])
        else:
            c = q1("SELECT * FROM csections WHERE id=?", (f["id"],))
            title = csec_label(c)
            f["opts"] = {
                "✏️ اسم القسم": ("field", "name"),
                "😀 إيموجي القسم": ("field", "emoji"),
                "📝 رسالة القسم": ("field", "message"),
                "👁 إظهار/إخفاء القسم": ("tvis",),
                "➕ زر جديد داخل القسم": ("newbtn", "c", f["id"]),
                "🗂 الأزرار الداخلية": ("blist", "c", f["id"]),
                "🗑 حذف القسم": ("delcs",),
            }
        rows = pair([(k, style_for(k)) for k in f["opts"]]) + [[(BACK, "danger")]]
        return f"⚙️ {title}\nاختر:", rows

    if step == "blist":
        f["map"], items = {}, []
        for b in q("SELECT * FROM cbuttons WHERE ptype=? AND pid=? ORDER BY pos, id", (f["kind"], f["id"])):
            label = b["name"] if b["visible"] else f"🙈 {b['name']}"
            f["map"][label] = b["id"]
            items.append((label, b["color"]))
        f["opts"] = {"➕ زر جديد هنا": ("newbtn", f["kind"], f["id"])}
        rows = pair(items) + [[("➕ زر جديد هنا", "success")], [(BACK, "danger")]]
        return ("🗂 الأزرار:" if items else "🗂 لا توجد أزرار بعد."), rows

    if step == "bnode":
        b = q1("SELECT * FROM cbuttons WHERE id=?", (f["bid"],))
        if not b:
            return "الزر غير موجود.", [[(BACK, "danger")]]
        f["opts"] = {
            "✏️ اسم الزر": ("bname",),
            "🎨 لون الزر": ("color",),
            "👁 إظهار/إخفاء الزر": ("tbtn",),
            "📥 إضافة محتوى": ("content",),
            "🧹 حذف المحتوى": ("clear",),
            "➕ زر داخل هذا الزر": ("newbtn", "b", f["bid"]),
            "🗂 الأزرار الداخلية": ("blist", "b", f["bid"]),
            "🗑 حذف الزر": ("delb",),
        }
        rows = pair([(k, style_for(k)) for k in f["opts"]]) + [[(BACK, "danger")]]
        return f"🔘 {b['name']}\nاختر:", rows

    if step == "bnew":
        return "أرسل اسم الزر الجديد:", []

    if step == "bcolor":
        return "اختر لون الزر الجديد:", [COLOR_ROW]

    if step == "bname":
        return "أرسل الاسم الجديد للزر:", []

    if step == "color":
        return "اختر اللون الجديد:", [COLOR_ROW]

    if step == "content":
        return "📥 أرسل المحتوى: نص أو صورة أو ملف، أو ID: ثم الـ ID.\nعند الانتهاء اضغط تم.", [[(DONE, "success")]]

    if step == "input":
        return "أرسل القيمة الجديدة:", []

    return "اختر من الأزرار:", []


def run_do(do):
    k = do[0]
    if k == "delsub":
        for b in q("SELECT id FROM cbuttons WHERE ptype IN ('s','q') AND pid=?", (do[1],)):
            purge_button(b["id"])
        x("DELETE FROM files WHERE subject_id=?", (do[1],))
        x("DELETE FROM sumsec WHERE subject_id=?", (do[1],))
        x("DELETE FROM subjects WHERE id=?", (do[1],))
    elif k == "delcs":
        for b in q("SELECT id FROM cbuttons WHERE ptype='c' AND pid=?", (do[1],)):
            purge_button(b["id"])
        x("DELETE FROM csections WHERE id=?", (do[1],))
    elif k == "delfile":
        x("DELETE FROM files WHERE id=?", (do[1],))
    elif k == "deladmin":
        x("DELETE FROM admins WHERE user_id=?", (do[1],))
        ADMIN_IDS.discard(do[1])
    elif k == "footer":
        set_setting("footer", do[1])
    elif k == "delbtn":
        purge_button(do[1])
    elif k == "clearc":
        x("UPDATE files SET cbutton_id=NULL WHERE cbutton_id=?", (do[1],))
        x("DELETE FROM content WHERE cbutton_id=?", (do[1],))
    elif k == "delsumsec":
        x("DELETE FROM files WHERE kind='summary' AND section=?", (str(do[1]),))
        x("DELETE FROM sumsec WHERE id=?", (do[1],))
    elif k == "delch":
        x("DELETE FROM channels WHERE id=?", (do[1],))
        load_channels()
        SUB_CACHE.clear()


async def h_confirm(msg, ctx, uid, f, text):
    if text != CONFIRM:
        return await fail(msg, ctx, "اضغط ✅ تأكيد أو ❌ إلغاء.")
    run_do(f["do"])
    if f["type"] in ("edit", "subs"):
        await msg.reply_text("✅ تم التنفيذ.")
        return await go_back(msg.chat_id, ctx, f)
    await finish(msg, ctx, "✅ تم التنفيذ.", uid)


async def save_subject_file(msg, ctx, uid, f, teacher):
    if f["kind"] == "summary":
        ok, err = insert_file(f["sid"], "summary", str(f["secid"]), None, f["title"], None, f["fid"], f["ftype"])
    else:
        ok, err = insert_file(f["sid"], f["kind"], None, None, f["title"], teacher, f["fid"], f["ftype"])
    return await finish(msg, ctx, "✅ تمت إضافة الملف." if ok else err, uid)


async def h_addfile(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "target":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر من الأزرار.")
        kind, tid = f["map"][text]
        if kind == "s":
            f["sid"] = tid
            return await goto(chat, ctx, f, "kind")
        f["cid"] = tid
        return await goto(chat, ctx, f, "cbtn")

    if step == "cbtn":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الزر من الأزرار.")
        bid = f["map"][text]
        if f.get("fid"):
            insert_content(bid, f["ftype"], None, f["fid"])
            return await finish(msg, ctx, "✅ تمت الإضافة.", uid)
        f["bid"] = bid
        return await goto(chat, ctx, f, "payload")

    if step == "kind":
        k = FILE_KINDS.get(text)
        if not k:
            return await fail(msg, ctx, "اختر النوع من الأزرار.")
        f["kind"] = k
        if k == "summary":
            if not sum_list(f["sid"]):
                return await finish(msg, ctx, "لا توجد فصول للملخصات لهذه المادة. أضفها من ➕ إضافة زر للملخصات أولاً.", uid)
            return await goto(chat, ctx, f, "sumpick")
        if k == "question":
            if not q1("SELECT 1 FROM cbuttons WHERE ptype='q' AND pid=?", (f["sid"],)):
                return await finish(msg, ctx, "لا توجد أزرار للأسئلة لهذه المادة. أضفها من ➕ إضافة زر للأسئلة أولاً.", uid)
            return await goto(chat, ctx, f, "qpick")
        return await goto(chat, ctx, f, "title" if f.get("fid") else "payload")

    if step == "sumpick":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الفصل من الأزرار.")
        f["secid"] = f["map"][text]
        return await goto(chat, ctx, f, "title" if f.get("fid") else "payload")

    if step == "qpick":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر القسم من الأزرار.")
        bid = f["map"][text]
        if f.get("fid"):
            insert_content(bid, f["ftype"], None, f["fid"])
            return await finish(msg, ctx, "✅ تمت الإضافة إلى الأسئلة.", uid)
        f["bid"], f["loop"] = bid, True
        return await goto(chat, ctx, f, "payload")

    if step == "payload":
        if "bid" in f:
            if text == DONE:
                return await finish(msg, ctx, "✅ انتهت الإضافة.", uid)
            res = content_step(f["bid"], text, media)
            if res == "added":
                await msg.reply_text("✅ تمت الإضافة، أرسل التالي أو اضغط تم.")
                return await flow_prompt(chat, ctx)
            return await fail(msg, ctx, "أرسل نصاً أو صورة أو ملفاً، أو ID: ثم الـ ID.")
        fid, ftype = read_file_payload(text, media)
        if not fid:
            return await fail(msg, ctx, "أرسل الملف أو الـ ID.")
        f["fid"], f["ftype"] = fid, ftype
        return await goto(chat, ctx, f, "title")

    if step == "title":
        if not text:
            return await fail(msg, ctx, "أرسل الاسم كنص.")
        f["title"] = text
        if f["kind"] == "note":
            return await goto(chat, ctx, f, "teacher")
        return await save_subject_file(msg, ctx, uid, f, None)

    if step == "teacher":
        return await save_subject_file(msg, ctx, uid, f, None if text == SKIP else text)


async def h_addqbtn(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "qsubj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"] = s["id"]
        return await goto(chat, ctx, f, "qbname")
    if step == "qbname":
        if not text:
            return await fail(msg, ctx, "أرسل اسم الزر.")
        f["qname"] = text
        return await goto(chat, ctx, f, "qbcolor")
    if step == "qbcolor":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM cbuttons WHERE ptype='q' AND pid=?", (f["sid"],))["p"]
        cur = x("INSERT INTO cbuttons(section_id, ptype, pid, name, color, pos) VALUES(NULL, 'q', ?, ?, ?, ?)",
                (f["sid"], f["qname"], COLORS[text], pos))
        f["bid"] = cur.lastrowid
        await msg.reply_text("✅ تم إنشاء الزر. أرسل صوره أو ملفاته أو نصه الآن، وعند الانتهاء اضغط تم.")
        return await goto(chat, ctx, f, "content")
    if step == "content":
        res = content_step(f["bid"], text, media)
        if res == "done":
            return await finish(msg, ctx, "✅ انتهت الإضافة.", uid)
        if res == "added":
            await msg.reply_text("✅ تمت الإضافة، أرسل التالي أو اضغط تم.")
            return await flow_prompt(chat, ctx)
        return await fail(msg, ctx, "أرسل نصاً أو صورة أو ملفاً، أو ID: ثم الـ ID.")


async def h_addsummary(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"] = s["id"]
        if not sum_list(s["id"]):
            return await finish(msg, ctx, "لا توجد فصول للملخصات لهذه المادة. أضفها من ➕ إضافة زر للملخصات أولاً.", uid)
        return await goto(chat, ctx, f, "sumpick")
    if step == "sumpick":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الفصل من الأزرار.")
        f["secid"], f["loop"] = f["map"][text], True
        return await goto(chat, ctx, f, "payload")
    if step == "payload":
        if text == DONE:
            return await finish(msg, ctx, "✅ انتهت الإضافة.", uid)
        fid, ftype = read_file_payload(text, media)
        if not fid:
            return await fail(msg, ctx, "أرسل الملف أو الـ ID، أو اضغط تم.")
        s = q1("SELECT name FROM subjects WHERE id=?", (f["sid"],))
        title = f"ملخص {s['name']} - {sum_name(str(f['secid']))}"
        ok, err = insert_file(f["sid"], "summary", str(f["secid"]), None, title, None, fid, ftype)
        await msg.reply_text("✅ تمت الإضافة، أرسل التالي أو اضغط تم." if ok else err)
        return await flow_prompt(chat, ctx)


async def h_addsumbtn(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"] = s["id"]
        return await goto(chat, ctx, f, "sact")
    if step == "sact":
        if text == "➕ فصل جديد":
            return await goto(chat, ctx, f, "sadd")
        if text == "✏️ تعديل اسم فصل":
            return await goto(chat, ctx, f, "srpick")
        if text == "🗑 حذف فصل":
            return await goto(chat, ctx, f, "sdpick")
        return await fail(msg, ctx, "اختر من الأزرار.")
    if step == "sadd":
        if not text:
            return await fail(msg, ctx, "أرسل اسم الفصل.")
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM sumsec WHERE subject_id=?", (f["sid"],))["p"]
        x("INSERT INTO sumsec(subject_id, name, pos) VALUES(?, ?, ?)", (f["sid"], text, pos))
        await msg.reply_text("✅ تمت إضافة الفصل.")
        return await goto(chat, ctx, f, "sact")
    if step == "srpick":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الفصل من الأزرار.")
        f["secid"] = f["map"][text]
        return await goto(chat, ctx, f, "srename")
    if step == "srename":
        if not text:
            return await fail(msg, ctx, "أرسل الاسم الجديد.")
        x("UPDATE sumsec SET name=? WHERE id=?", (text, f["secid"]))
        return await finish(msg, ctx, "✅ تم تعديل اسم الفصل.", uid)
    if step == "sdpick":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر الفصل من الأزرار.")
        f["do"] = ("delsumsec", f["map"][text])
        return await goto(chat, ctx, f, "confirm")


async def h_addsection(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "cname":
        if not text:
            return await fail(msg, ctx, "أرسل اسم القسم.")
        f["cname"] = text
        return await goto(chat, ctx, f, "cemoji")
    if step == "cemoji":
        if not text:
            return await fail(msg, ctx, "أرسل إيموجي القسم.")
        f["cemoji"] = text
        return await goto(chat, ctx, f, "cmsg")
    if step == "cmsg":
        f["cmsg"] = "" if text == SKIP else text
        return await goto(chat, ctx, f, "ccolor")
    if step == "ccolor":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        f["ccolor"], f["buttons"] = COLORS[text], []
        return await goto(chat, ctx, f, "cbtns")
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
                        "INSERT INTO cbuttons(section_id, ptype, pid, name, color, pos) VALUES(?, 'c', ?, ?, ?, ?)",
                        (cur.lastrowid, cur.lastrowid, name, f["ccolor"], i),
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
        return await goto(chat, ctx, f, "semoji")
    if step == "semoji":
        f["semoji"] = "" if text == SKIP else text
        return await goto(chat, ctx, f, "sumnames")
    if step == "sumnames":
        if text == SKIP:
            names = []
        elif text == DONE:
            names = f.get("sumnames", [])
        else:
            if not text:
                return await fail(msg, ctx, "أرسل اسم الفصل أو اضغط تم أو تخطي.")
            f.setdefault("sumnames", []).append(text)
            return await flow_prompt(chat, ctx)
        try:
            create_subject(f["sname"], f["semoji"], names)
        except sqlite3.IntegrityError:
            return await finish(msg, ctx, "هذه المادة موجودة مسبقاً.", uid)
        return await finish(msg, ctx, "✅ تمت إضافة المادة.", uid)


async def h_editsubject(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "subj":
        s = label_of_subject(text)
        if not s:
            return await fail(msg, ctx, "اختر المادة من الأزرار.")
        f["sid"] = s["id"]
        return await goto(chat, ctx, f, "sfield")
    if step == "sfield":
        col = {"✏️ الاسم": "name", "😀 الإيموجي": "emoji"}.get(text)
        if not col:
            return await fail(msg, ctx, "اختر من الأزرار.")
        f["col"] = col
        return await goto(chat, ctx, f, "svalue")
    if step == "svalue":
        if f["col"] == "emoji" and text == SKIP:
            value = ""
        elif not text:
            return await fail(msg, ctx, "أرسل القيمة.")
        else:
            value = text
        try:
            x(f"UPDATE subjects SET {f['col']}=? WHERE id=?", (value, f["sid"]))
        except sqlite3.IntegrityError:
            return await finish(msg, ctx, "هذا الاسم مستخدم من مادة أخرى.", uid)
        return await finish(msg, ctx, "✅ تم التعديل.", uid)


async def h_delsubject(msg, ctx, uid, f, text, media):
    s = label_of_subject(text)
    if not s:
        return await fail(msg, ctx, "اختر المادة من الأزرار.")
    f["do"] = ("delsub", s["id"])
    return await goto(msg.chat_id, ctx, f, "confirm")


async def h_delsection(msg, ctx, uid, f, text, media):
    if text not in f.get("map", {}):
        return await fail(msg, ctx, "اختر القسم من الأزرار.")
    f["do"] = ("delcs", f["map"][text])
    return await goto(msg.chat_id, ctx, f, "confirm")


async def h_editfile(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "file":
        rid = resolve_file(f, text)
        if rid is None:
            return await fail(msg, ctx, "اختر الملف من الأزرار أو أرسل رقمه مثل #12.")
        f["rid"] = rid
        return await goto(chat, ctx, f, "ffield")
    if step == "ffield":
        col = {"✏️ الاسم": "title", "👨‍🏫 الأستاذ": "teacher"}.get(text)
        if not col:
            return await fail(msg, ctx, "اختر من الأزرار.")
        f["col"] = col
        return await goto(chat, ctx, f, "fvalue")
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
        return await goto(chat, ctx, f, "payload")
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
    return await goto(msg.chat_id, ctx, f, "confirm")


async def h_togglefile(msg, ctx, uid, f, text, media):
    rid = resolve_file(f, text)
    if rid is None:
        return await fail(msg, ctx, "اختر الملف من الأزرار.")
    x("UPDATE files SET visible = 1 - visible WHERE id=?", (rid,))
    row = q1("SELECT visible FROM files WHERE id=?", (rid,))
    return await finish(msg, ctx, "✅ تم. الحالة الآن: " + ("ظاهر" if row["visible"] else "مخفي"), uid)


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
    link = f"https://t.me/{ctx.bot.username}?start=f{rid}"
    return await finish(msg, ctx, f"🔗 رابط الملف:\n{link}", uid)


async def h_footer(msg, ctx, uid, f, text, media):
    if text == "🗑 حذف الوصف":
        f["do"] = ("footer", "")
        return await goto(msg.chat_id, ctx, f, "confirm")
    if not text:
        return await fail(msg, ctx, "أرسل الوصف الجديد كنص.")
    set_setting("footer", text)
    return await finish(msg, ctx, "✅ تم تحديث الوصف.", uid)


async def h_broadcast(msg, ctx, uid, f, text, media):
    if not text:
        return await fail(msg, ctx, "أرسل نص الإعلان.")
    if tg_len(text) > TEXT_LIMIT:
        return await fail(msg, ctx, f"نص الإعلان أطول من الحد ({TEXT_LIMIT} حرف).")
    if BCAST["running"]:
        return await finish(msg, ctx, "يوجد إعلان قيد الإرسال، انتظر حتى ينتهي.", uid)
    spawn(run_broadcast(ctx.bot, text, msg.chat_id))
    return await finish(msg, ctx, "⏳ بدأ الإرسال، وبيوصلك التقرير لما ينتهي.", uid)


async def h_admins(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if step == "amenu":
        if text == "➕ إضافة مشرف":
            return await goto(chat, ctx, f, "aid")
        if text == "🗑 حذف مشرف":
            return await goto(chat, ctx, f, "apick")
        if text == "📋 قائمة المشرفين":
            listed = "\n".join(f"#{a['user_id']}" for a in q("SELECT user_id FROM admins")) or "لا يوجد مشرفون."
            return await finish(msg, ctx, f"👥 المشرفون:\n{listed}", uid)
        return await fail(msg, ctx, "اختر من الأزرار.")
    if step == "aid":
        if not text.isdigit():
            return await fail(msg, ctx, "أرسل Telegram ID رقمياً.")
        x("INSERT OR IGNORE INTO admins(user_id, added) VALUES(?, ?)", (int(text), now()))
        ADMIN_IDS.add(int(text))
        return await finish(msg, ctx, "✅ تمت إضافة المشرف.", uid)
    if step == "apick":
        m = re.match(r"#(\d+)", text)
        if not m:
            return await fail(msg, ctx, "اختر المشرف من الأزرار.")
        f["do"] = ("deladmin", int(m.group(1)))
        return await goto(chat, ctx, f, "confirm")


async def save_channel(msg, ctx, f, ref, title, link):
    x("INSERT OR IGNORE INTO channels(ref, title, link, added) VALUES(?, ?, ?, ?)", (ref, title, link, now()))
    load_channels()
    SUB_CACHE.clear()
    await msg.reply_text(f"✅ تمت إضافة القناة: {title}")
    return await go_back(msg.chat_id, ctx, f)


async def h_subs(msg, ctx, uid, f, text, media):
    chat, step, bot = msg.chat_id, f["step"], ctx.bot

    if step == "smenu":
        if text == "➕ إضافة قناة":
            return await enter(chat, ctx, f, "chref")
        if text == "📋 القنوات والحذف":
            return await enter(chat, ctx, f, "chlist")
        if text == "⚙️ تشغيل/إيقاف الاشتراك":
            set_setting("sub_on", "0" if setting("sub_on") == "1" else "1")
            SUB_CACHE.clear()
            return await flow_prompt(chat, ctx)
        return await fail(msg, ctx, "اختر من الأزرار.")

    if step == "chref":
        ref = parse_ref(text)
        if not ref:
            return await fail(msg, ctx, "أرسل معرف القناة مثل @channel، أو رقمها مثل -1001234567890.")
        if any(c["ref"] == ref for c in CHANNELS):
            return await fail(msg, ctx, "هذه القناة مضافة مسبقاً.")
        try:
            info = await bot.get_chat(chat_arg(ref))
            me = await bot.get_chat_member(chat_arg(ref), bot.id)
        except TelegramError:
            return await fail(msg, ctx, "ما قدرت أوصل للقناة. تأكد من المعرف، وأن البوت موجود فيها.")
        if me.status not in ("administrator", "creator"):
            return await fail(msg, ctx, "البوت مو أدمن في القناة. ارفعه أدمن ثم أرسل المعرف من جديد.")
        title = info.title or ref
        if info.username:
            ref = "@" + info.username
            if any(c["ref"] == ref for c in CHANNELS):
                return await fail(msg, ctx, "هذه القناة مضافة مسبقاً.")
            return await save_channel(msg, ctx, f, ref, title, f"https://t.me/{info.username}")
        # قناة خاصة: ننشئ رابط دعوة جديد بدون ما نلغي الروابط القديمة
        try:
            invite = await bot.create_chat_invite_link(chat_arg(ref))
            link = invite.invite_link
        except TelegramError:
            link = ""
        if link:
            return await save_channel(msg, ctx, f, ref, title, link)
        f["chref"], f["chtitle"] = ref, title
        return await goto(chat, ctx, f, "chlink")

    if step == "chlink":
        link = (text or "").strip()
        if not (link.startswith("https://t.me/") or link.startswith("https://telegram.me/")):
            return await fail(msg, ctx, "أرسل رابط دعوة صحيح يبدأ بـ https://t.me/")
        return await save_channel(msg, ctx, f, f["chref"], f["chtitle"], link)

    if step == "chlist":
        cid = f.get("map", {}).get(text)
        if cid is None:
            return await fail(msg, ctx, "اختر القناة من الأزرار.")
        f["do"] = ("delch", cid)
        return await enter(chat, ctx, f, "confirm")

    return await fail(msg, ctx, "اختر من الأزرار.")


async def h_story(msg, ctx, uid, f, text, media):
    if not text:
        return await fail(msg, ctx, "أرسل النص كرسالة نصية.")
    if tg_len(text) > TEXT_LIMIT:
        return await fail(msg, ctx, f"النص أطول من الحد ({tg_len(text)}/{TEXT_LIMIT}). اختصره وأرسله مرة ثانية.")
    set_setting("story", text)
    return await finish(msg, ctx, "✅ تم تحديث حكاية رابعيون.", uid)


async def h_edit(msg, ctx, uid, f, text, media):
    chat, step = msg.chat_id, f["step"]
    if text == BACK:
        if f.get("hist"):
            return await go_back(chat, ctx, f)
        return await finish(msg, ctx, "تم الخروج من تعديل الأزرار.", uid)

    if step == "root":
        if text not in f.get("map", {}):
            return await fail(msg, ctx, "اختر من الأزرار.")
        kind, eid = f["map"][text]
        return await enter(chat, ctx, f, "node", kind=kind, id=eid)

    if step == "node":
        act = f.get("opts", {}).get(text)
        if not act:
            return await fail(msg, ctx, "اختر من الأزرار.")
        k = act[0]
        if k == "tog":
            s = q1("SELECT hidden FROM subjects WHERE id=?", (f["id"],))
            hidden = hidden_set(s["hidden"]) ^ {act[1]}
            x("UPDATE subjects SET hidden=? WHERE id=?", (",".join(sorted(hidden)), f["id"]))
            return await flow_prompt(chat, ctx)
        if k == "tvis":
            x("UPDATE csections SET visible = 1 - visible WHERE id=?", (f["id"],))
            return await flow_prompt(chat, ctx)
        if k == "field":
            return await enter(chat, ctx, f, "input", field=act[1])
        if k == "newbtn":
            return await enter(chat, ctx, f, "bnew", ptype=act[1], pid=act[2])
        if k == "blist":
            return await enter(chat, ctx, f, "blist", kind=act[1], id=act[2])
        if k == "delcs":
            f["do"] = ("delcs", f["id"])
            f["step"] = "confirm"
            return await flow_prompt(chat, ctx)
        return await fail(msg, ctx, "اختر من الأزرار.")

    if step == "blist":
        act = f.get("opts", {}).get(text)
        if act and act[0] == "newbtn":
            return await enter(chat, ctx, f, "bnew", ptype=act[1], pid=act[2])
        cbid = f.get("map", {}).get(text)
        if cbid is None:
            return await fail(msg, ctx, "اختر الزر من الأزرار.")
        return await enter(chat, ctx, f, "bnode", bid=cbid)

    if step == "bnode":
        act = f.get("opts", {}).get(text)
        if not act:
            return await fail(msg, ctx, "اختر من الأزرار.")
        k = act[0]
        if k == "bname":
            return await enter(chat, ctx, f, "bname")
        if k == "color":
            return await enter(chat, ctx, f, "color")
        if k == "tbtn":
            x("UPDATE cbuttons SET visible = 1 - visible WHERE id=?", (f["bid"],))
            return await flow_prompt(chat, ctx)
        if k == "content":
            return await enter(chat, ctx, f, "content")
        if k == "clear":
            f["do"] = ("clearc", f["bid"])
            return await enter(chat, ctx, f, "confirm")
        if k == "newbtn":
            return await enter(chat, ctx, f, "bnew", ptype=act[1], pid=act[2])
        if k == "blist":
            return await enter(chat, ctx, f, "blist", kind=act[1], id=act[2])
        if k == "delb":
            f["do"] = ("delbtn", f["bid"])
            f["step"] = "confirm"
            return await flow_prompt(chat, ctx)
        return await fail(msg, ctx, "اختر من الأزرار.")

    if step == "bnew":
        if not text:
            return await fail(msg, ctx, "أرسل اسم الزر.")
        f["bname"] = text
        return await goto(chat, ctx, f, "bcolor")

    if step == "bcolor":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        pos = q1("SELECT COALESCE(MAX(pos), 0) + 1 AS p FROM cbuttons WHERE ptype=? AND pid=?",
                 (f["ptype"], f["pid"]))["p"]
        sec_id = f["pid"] if f["ptype"] == "c" else None
        x("INSERT INTO cbuttons(section_id, ptype, pid, name, color, pos) VALUES(?, ?, ?, ?, ?, ?)",
          (sec_id, f["ptype"], f["pid"], f["bname"], COLORS[text], pos))
        await msg.reply_text("✅ تمت إضافة الزر.")
        return await go_back(chat, ctx, f)

    if step == "bname":
        if not text:
            return await fail(msg, ctx, "أرسل الاسم.")
        x("UPDATE cbuttons SET name=? WHERE id=?", (text, f["bid"]))
        return await go_back(chat, ctx, f)

    if step == "color":
        if text not in COLORS:
            return await fail(msg, ctx, "اختر اللون من الأزرار.")
        x("UPDATE cbuttons SET color=? WHERE id=?", (COLORS[text], f["bid"]))
        return await go_back(chat, ctx, f)

    if step == "content":
        res = content_step(f["bid"], text, media)
        if res == "done":
            return await go_back(chat, ctx, f)
        if res == "added":
            await msg.reply_text("✅ تمت الإضافة.")
            return await flow_prompt(chat, ctx)
        return await fail(msg, ctx, "أرسل نصاً أو صورة أو ملفاً، أو ID: ثم الـ ID.")

    if step == "input":
        if not text:
            return await fail(msg, ctx, "أرسل القيمة.")
        col = f.get("field")
        if col not in ("name", "emoji", "message"):
            return await fail(msg, ctx, "اختر من الأزرار.")
        try:
            x(f"UPDATE csections SET {col}=? WHERE id=?", (text, f["id"]))
        except sqlite3.IntegrityError:
            return await fail(msg, ctx, "هذا الاسم مستخدم من قسم آخر.")
        return await go_back(chat, ctx, f)

    return await fail(msg, ctx, "اختر من الأزرار.")


FLOW_HANDLERS = {
    "addfile": h_addfile,
    "addqbtn": h_addqbtn,
    "addsummary": h_addsummary,
    "addsumbtn": h_addsumbtn,
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
    "broadcast": h_broadcast,
    "admins": h_admins,
    "subs": h_subs,
    "story": h_story,
    "edit": h_edit,
}


async def handle_flow(msg, ctx, uid):
    f = ctx.user_data.get("flow")
    if not f:
        return False
    text = (msg.text or "").strip()
    media = media_payload(msg)

    if text == BACK and f["step"] != "confirm":
        if f["type"] in ("subs", "story", "edit"):
            if f.get("hist"):
                await go_back(msg.chat_id, ctx, f)
            else:
                ctx.user_data.pop("flow", None)
                await msg.reply_text("تم الخروج.", reply_markup=owner_markup(uid == OWNER_ID))
            return True
        ctx.user_data.pop("flow", None)
        await msg.reply_text("تم الإلغاء.", reply_markup=owner_markup(uid == OWNER_ID))
        return True

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
    token = token if re.fullmatch(r"[fc]\d+", token) else ""
    if not is_staff(uid) and setting("bot_on") == "0":
        await msg.reply_text(MAINT_TEXT)
        return
    if not await is_member(ctx.bot, uid):
        await msg.reply_text(GATE_TEXT, reply_markup=gate_markup(token))
        return
    if token:
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
    chat = cb.message.chat_id if cb.message else uid
    upsert_user(uid)

    if cb.data.startswith("chk:"):
        token = cb.data[4:]
        token = token if re.fullmatch(r"[fc]\d+", token) else ""
        if not is_staff(uid) and setting("bot_on") == "0":
            await cb.answer(MAINT_TEXT, show_alert=True)
            return
        if not await is_member(ctx.bot, uid):
            await cb.answer("لم تشترك بعد", show_alert=True)
            return
        await cb.answer("تم التحقق ✅")
        if token:
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
            cb = q1("SELECT * FROM cbuttons WHERE id=? AND visible=1", (int(token[1:]),))
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
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )
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
