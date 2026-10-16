#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت الرابع العلمي — إصدار نظيف
Python 3.11+ | python-telegram-bot 22.8

Required environment:
  BOT_TOKEN  = Telegram bot token from @BotFather
Optional:
  OWNER_ID   = 7683201905
  CHANNEL    = @Kii_8i
  SITE_URL   = deployed website URL
  DB_FILE    = fourth_scientific_bot.db
"""
import asyncio
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "7683201905"))
CHANNEL_DEFAULT = os.getenv("CHANNEL", "@Kii_8i").strip() or "@Kii_8i"
SITE_URL = os.getenv("SITE_URL", "").strip()
DB_FILE = os.getenv("DB_FILE", "fourth_scientific_bot.db")
SUB_CACHE_SECONDS = 180
RELEASE_YEAR_DEFAULT = 2026

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("fourth_scientific_bot")

DEFAULT_SUBJECTS = [
    ("رياضيات", "📐", "ch"),
    ("كيمياء", "🧪", "ch"),
    ("فيزياء", "⚡", "ch"),
    ("أحياء", "🧬", "ch"),
    ("English", "🇬🇧", "unit"),
    ("التربية الإسلامية", "📖", "unit"),
    ("الحاسوب", "💻", "ch"),
    ("الكردي", "📝", "unit"),
    ("اللغة العربية", "📚", "unit"),
    ("جرائم حزب البعث", "⚖️", "ch"),
]
KINDS = {
    "📘 كتاب": "book",
    "📙 ملزمة": "note",
    "🧾 ملخص": "summary",
    "❓ أسئلة": "question",
}
KIND_LABELS = {"book": "كتاب", "note": "ملزمة", "summary": "ملخص", "question": "أسئلة"}
CHAPTERS = {
    "ch1": "الفصل الأول",
    "ch2": "الفصل الثاني",
    "ch3": "الفصل الثالث",
    "ch4": "الفصل الرابع",
    "ch5": "الفصل الخامس",
    "ch6": "الفصل السادس",
}
UNITS = {"u1": "الوحدة الأولى", "u2": "الوحدة الثانية", "u3": "الوحدة الثالثة", "u4": "الوحدة الرابعة"}
QUESTION_SECTIONS = {"q_ch1": "الفصل الأول", "q_half": "نصف السنة", "q_ch2": "الفصل الثاني"}
MONTHS = {"m1": "الشهر الأول", "m2": "الشهر الثاني"}
MEDIA_TYPES = {
    "📄 مستند": "document",
    "🖼 صورة": "photo",
    "🎥 فيديو": "video",
    "🎵 صوت": "audio",
    "🎙 رسالة صوتية": "voice",
    "🎞 متحركة": "animation",
}

SUB_CACHE = {}
DB_LOCK = asyncio.Lock()
DB_PATH = Path(DB_FILE)
if str(DB_PATH.parent) not in ("", "."):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
DB.row_factory = sqlite3.Row
DB.execute("PRAGMA foreign_keys=ON")
DB.execute("PRAGMA busy_timeout=30000")
DB.execute("PRAGMA journal_mode=WAL")


def query(sql, params=()):
    return DB.execute(sql, params).fetchall()


def one(sql, params=()):
    return DB.execute(sql, params).fetchone()


def execute(sql, params=()):
    cur = DB.execute(sql, params)
    DB.commit()
    return cur


def columns(table):
    return {r["name"] for r in DB.execute(f"PRAGMA table_info({table})").fetchall()}


def add_missing_columns(table, definitions):
    existing = columns(table)
    for name, definition in definitions.items():
        if name not in existing:
            DB.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    DB.commit()


def init_db():
    DB.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        joined_at TEXT NOT NULL DEFAULT '',
        blocked INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        emoji TEXT NOT NULL DEFAULT '📚',
        color TEXT NOT NULL DEFAULT 'success',
        stype TEXT NOT NULL DEFAULT 'ch',
        pos INTEGER NOT NULL DEFAULT 0,
        visible INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER,
        kind TEXT NOT NULL DEFAULT 'book',
        section TEXT,
        month TEXT,
        title TEXT NOT NULL DEFAULT '',
        teacher TEXT,
        description TEXT NOT NULL DEFAULT '',
        release_year INTEGER NOT NULL DEFAULT 2026,
        file_id TEXT NOT NULL UNIQUE,
        media_type TEXT NOT NULL DEFAULT 'document',
        visible INTEGER NOT NULL DEFAULT 1,
        downloads INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT ''
    );
    """)
    # Idempotent migrations: old tables are upgraded in place, never dropped.
    add_missing_columns("users", {
        "joined_at": "TEXT NOT NULL DEFAULT ''",
        "blocked": "INTEGER NOT NULL DEFAULT 0",
    })
    add_missing_columns("subjects", {
        "emoji": "TEXT NOT NULL DEFAULT '📚'",
        "color": "TEXT NOT NULL DEFAULT 'success'",
        "stype": "TEXT NOT NULL DEFAULT 'ch'",
        "pos": "INTEGER NOT NULL DEFAULT 0",
        "visible": "INTEGER NOT NULL DEFAULT 1",
    })
    add_missing_columns("files", {
        "subject_id": "INTEGER",
        "kind": "TEXT NOT NULL DEFAULT 'book'",
        "section": "TEXT",
        "month": "TEXT",
        "title": "TEXT NOT NULL DEFAULT ''",
        "teacher": "TEXT",
        "description": "TEXT NOT NULL DEFAULT ''",
        "release_year": "INTEGER NOT NULL DEFAULT 2026",
        "file_id": "TEXT NOT NULL DEFAULT ''",
        "media_type": "TEXT NOT NULL DEFAULT 'document'",
        "visible": "INTEGER NOT NULL DEFAULT 1",
        "downloads": "INTEGER NOT NULL DEFAULT 0",
        "created_at": "TEXT NOT NULL DEFAULT ''",
    })
    execute("INSERT OR IGNORE INTO settings(key,value) VALUES('channel',?)", (CHANNEL_DEFAULT,))
    execute("INSERT OR IGNORE INTO settings(key,value) VALUES('subscription_enabled','1')")
    execute("INSERT OR IGNORE INTO settings(key,value) VALUES('site_url',?)", (SITE_URL,))
    execute("INSERT OR IGNORE INTO settings(key,value) VALUES('seeded','0')")
    if one("SELECT value FROM settings WHERE key='seeded'")["value"] != "1":
        for pos, (name, emoji, stype) in enumerate(DEFAULT_SUBJECTS, start=1):
            execute(
                "INSERT OR IGNORE INTO subjects(name,emoji,color,stype,pos,visible) VALUES(?,?,?,?,?,1)",
                (name, emoji, "success", stype, pos),
            )
        execute("UPDATE settings SET value='1' WHERE key='seeded'")
    # Backfill values for migrated records.
    execute("UPDATE files SET created_at=? WHERE created_at=''", (datetime.now().isoformat(timespec="seconds"),))


def get_setting(key, default=""):
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def remember_user(user_id):
    execute(
        "INSERT OR IGNORE INTO users(user_id,joined_at,blocked) VALUES(?,?,0)",
        (user_id, datetime.now().isoformat(timespec="seconds")),
    )


def is_owner(user_id):
    return user_id == OWNER_ID


def subject_label(row):
    return f"{row['emoji']} {row['name']}"


def subject_by_name(text):
    for row in query("SELECT * FROM subjects ORDER BY pos,id"):
        if text.strip() in (row["name"], subject_label(row), str(row["id"])):
            return row
    return None


def media_from_message(message):
    if message.document:
        return message.document.file_id, "document"
    if message.photo:
        return message.photo[-1].file_id, "photo"
    if message.video:
        return message.video.file_id, "video"
    if message.audio:
        return message.audio.file_id, "audio"
    if message.voice:
        return message.voice.file_id, "voice"
    if message.animation:
        return message.animation.file_id, "animation"
    return None, None


def home_markup(owner):
    rows = []
    url = get_setting("site_url", SITE_URL).strip()
    if url and re.match(r"^https?://", url, re.I):
        rows.append([InlineKeyboardButton("🌐 الموقع", url=url)])
    else:
        rows.append([InlineKeyboardButton("🌐 الموقع", callback_data="site_missing")])
    if owner:
        rows.append([InlineKeyboardButton("🛠 لوحة المالك", callback_data="admin:menu")])
    return InlineKeyboardMarkup(rows)


def admin_markup():
    rows = [
        [InlineKeyboardButton("➕ إضافة ملف برفعه", callback_data="admin:addfile"),
         InlineKeyboardButton("🆔 إضافة ملف بـ ID", callback_data="admin:addid")],
        [InlineKeyboardButton("➕ إضافة ملخص", callback_data="admin:addsummary"),
         InlineKeyboardButton("➕ إضافة أسئلة", callback_data="admin:addquestion")],
        [InlineKeyboardButton("✏️ تعديل ملف", callback_data="admin:editfile"),
         InlineKeyboardButton("🔁 استبدال ملف", callback_data="admin:replacefile")],
        [InlineKeyboardButton("🗑 حذف ملف", callback_data="admin:deletefile"),
         InlineKeyboardButton("👁 إخفاء/إظهار", callback_data="admin:togglefile")],
        [InlineKeyboardButton("➕ إضافة مادة", callback_data="admin:addsubject"),
         InlineKeyboardButton("✏️ تعديل مادة", callback_data="admin:editsubject")],
        [InlineKeyboardButton("🗑 حذف مادة", callback_data="admin:deletesubject")],
        [InlineKeyboardButton("🔎 استخراج File ID", callback_data="admin:identify"),
         InlineKeyboardButton("🔗 إنشاء رابط", callback_data="admin:genlink")],
        [InlineKeyboardButton("🆔 جميع الـ IDs", callback_data="admin:allids"),
         InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats")],
        [InlineKeyboardButton("📢 إعلان للمستخدمين", callback_data="admin:broadcast")],
        [InlineKeyboardButton("⚙️ تشغيل/إيقاف الاشتراك", callback_data="admin:subscription"),
         InlineKeyboardButton("📣 تغيير القناة", callback_data="admin:channel")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="home")],
    ]
    return InlineKeyboardMarkup(rows)


def cancel_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel")]])


def options_markup(options, prefix):
    rows = []
    for key, label in options:
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}:{key}")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def subject_options(include_hidden=True):
    sql = "SELECT * FROM subjects"
    if not include_hidden:
        sql += " WHERE visible=1"
    sql += " ORDER BY pos,id"
    return [(str(s["id"]), f"{s['id']}. {subject_label(s)}") for s in query(sql)]


def file_options():
    rows = query("SELECT id,title,kind,visible FROM files ORDER BY id DESC LIMIT 80")
    return [(str(r["id"]), f"#{r['id']} · {KIND_LABELS.get(r['kind'],r['kind'])} · {r['title'][:40]}{' (مخفي)' if not r['visible'] else ''}") for r in rows]


def main_text():
    return "أهلاً بك في بوت الرابع العلمي.\nتصفّح المواد من الموقع، والبوت مخصّص لتسليم الملفات."


async def send_home(message, owner):
    await message.reply_text(main_text(), reply_markup=home_markup(owner))


async def send_admin(message):
    await message.reply_text("🛠 لوحة المالك\nاختر العملية المطلوبة:", reply_markup=admin_markup())


async def check_subscription(bot, user_id):
    if is_owner(user_id) or get_setting("subscription_enabled", "1") != "1":
        return True
    expiry = SUB_CACHE.get(user_id, 0)
    if expiry > time.time():
        return True
    channel = get_setting("channel", CHANNEL_DEFAULT)
    try:
        member = await bot.get_chat_member(channel, user_id)
        status = getattr(member, "status", "")
        is_member = getattr(member, "is_member", True)
        ok = status in ("member", "administrator", "creator") or (status == "restricted" and is_member)
        if ok:
            SUB_CACHE[user_id] = time.time() + SUB_CACHE_SECONDS
        else:
            SUB_CACHE.pop(user_id, None)
        return ok
    except TelegramError as exc:
        # Fail closed: don't deliver files if channel membership can't be verified.
        log.warning("Subscription check failed for %s: %s", channel, exc)
        return False


def gate_markup(pending_id=None):
    channel = get_setting("channel", CHANNEL_DEFAULT).strip()
    username = channel.lstrip("@")
    match = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", channel)
    if match:
        username = match.group(1)
    rows = []
    if username and re.fullmatch(r"[A-Za-z0-9_]{5,}", username):
        rows.append([InlineKeyboardButton("📢 اشترك بالقناة", url=f"https://t.me/{username}")])
    rows.append([InlineKeyboardButton("✅ تحقّق من الاشتراك", callback_data=f"checksub:{pending_id or 0}")])
    return InlineKeyboardMarkup(rows)


def file_link(bot_username, file_id):
    return f"https://t.me/{bot_username}?start=file_{file_id}"


async def deliver_file(ctx, chat_id, db_id, owner=False):
    row = one("SELECT * FROM files WHERE id=?", (db_id,))
    if not row or (not row["visible"] and not owner):
        await ctx.bot.send_message(chat_id, "هذا الملف غير متاح حالياً.")
        return
    caption_parts = [f"📙 {row['title']}"]
    if row["teacher"]:
        caption_parts.append(f"👨‍🏫 {row['teacher']}")
    caption_parts.append("🏷 للصف الرابع الإعدادي")
    caption_parts.append(f"📆 تاريخ الإصدار: {row['release_year'] or RELEASE_YEAR_DEFAULT}")
    if row["description"]:
        caption_parts.append(f"📝 {row['description']}")
    caption = "\n".join(caption_parts)[:1024]
    try:
        mt = row["media_type"] or "document"
        sender = {
            "document": ctx.bot.send_document,
            "photo": ctx.bot.send_photo,
            "video": ctx.bot.send_video,
            "audio": ctx.bot.send_audio,
            "voice": ctx.bot.send_voice,
            "animation": ctx.bot.send_animation,
        }.get(mt, ctx.bot.send_document)
        link = file_link(ctx.bot.username, db_id)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 مشاركة رابط الملف", url=link)]])
        await sender(chat_id=chat_id, **({"document": row["file_id"]} if mt == "document" else {
            {"photo": "photo", "video": "video", "audio": "audio", "voice": "voice", "animation": "animation"}[mt]: row["file_id"]
        }), caption=caption, reply_markup=markup)
        execute("UPDATE files SET downloads=downloads+1 WHERE id=?", (db_id,))
    except TelegramError as exc:
        log.exception("Failed to send file id=%s: %s", db_id, exc)
        await ctx.bot.send_message(chat_id, "تعذّر إرسال الملف. أبلغ المالك بهذا الخطأ.")


def parse_file_id(text):
    match = re.fullmatch(r"#?(\d+)", text.strip())
    return int(match.group(1)) if match else None


def begin_flow(ctx, action):
    ctx.user_data["flow"] = {"action": action, "step": "start"}


async def ask(message, ctx, text, markup=None):
    await message.reply_text(text, reply_markup=markup or cancel_markup())


async def prompt_flow(message, ctx):
    f = ctx.user_data["flow"]
    a, step = f["action"], f["step"]
    if step == "subject":
        await ask(message, ctx, "اختر المادة بالضغط على الزر:", options_markup(subject_options(), "picksubject"))
    elif step == "kind":
        await ask(message, ctx, "اختر نوع الملف:", options_markup([(v, k) for k, v in KINDS.items() if v in ("book", "note")], "pickkind"))
    elif step == "title":
        await ask(message, ctx, "أرسل اسم الملف.")
    elif step == "teacher":
        await ask(message, ctx, "أرسل اسم الأستاذ، أو اكتب - إذا لا يوجد.")
    elif step == "description":
        await ask(message, ctx, "أرسل وصفاً مختصراً، أو اكتب - لتخطي الوصف.")
    elif step == "year":
        await ask(message, ctx, f"أرسل سنة الإصدار (الافتراضي {RELEASE_YEAR_DEFAULT})، أو اكتب -.")
    elif step == "media":
        await ask(message, ctx, "أرسل الملف أو الصورة أو الفيديو أو الصوت الآن.")
    elif step == "media_type":
        await ask(message, ctx, "اختر نوع الـ File ID:", options_markup([(v, k) for k, v in MEDIA_TYPES.items()], "pickmedia"))
    elif step == "fileid":
        await ask(message, ctx, "أرسل Telegram File ID كما هو.")
    elif step == "section":
        subject = one("SELECT * FROM subjects WHERE id=?", (f.get("subject_id"),)) if f.get("subject_id") else None
        opts = CHAPTERS if not subject or subject["stype"] == "ch" else UNITS
        await ask(message, ctx, "اختر الفصل أو الوحدة:", options_markup(list(opts.items()), "picksection"))
    elif step == "question_section":
        await ask(message, ctx, "اختر قسم الأسئلة:", options_markup(list(QUESTION_SECTIONS.items()), "pickqsection"))
    elif step == "month":
        await ask(message, ctx, "اختر الشهر:", options_markup(list(MONTHS.items()), "pickmonth"))
    elif step == "file":
        await ask(message, ctx, "اختر ملفاً من القائمة (آخر 80 ملفاً)، أو اكتب رقمه مثل #12:", options_markup(file_options(), "pickfile"))
    elif step == "edit_field":
        await ask(message, ctx, "ما الحقل الذي تريد تعديله؟", options_markup([
            ("title", "اسم الملف"), ("teacher", "الأستاذ"), ("description", "الوصف"),
            ("release_year", "سنة الإصدار"), ("visible", "إظهار/إخفاء"),
        ], "pickfield"))
    elif step == "new_value":
        await ask(message, ctx, "أرسل القيمة الجديدة.")
    elif step == "subject_name":
        await ask(message, ctx, "أرسل اسم المادة الجديدة.")
    elif step == "subject_emoji":
        await ask(message, ctx, "أرسل إيموجي المادة.")
    elif step == "subject_type":
        await ask(message, ctx, "اختر نوع تقسيم المادة:", options_markup([("ch", "فصول"), ("unit", "وحدات")], "pickstype"))
    elif step == "subject_field":
        await ask(message, ctx, "اختر ما تريد تعديله:", options_markup([("name", "الاسم"), ("emoji", "الإيموجي"), ("stype", "نوع التقسيم")], "picksubjectfield"))
    elif step == "subject_value":
        await ask(message, ctx, "أرسل القيمة الجديدة.")
    elif step == "confirm_delete_subject":
        await ask(message, ctx, "تأكيد حذف المادة وكل ملفاتها؟", options_markup([("yes", "نعم، احذف المادة وملفاتها")], "confirm"))
    elif step == "confirm_delete_file":
        await ask(message, ctx, "تأكيد حذف الملف نهائياً؟", options_markup([("yes", "نعم، احذف الملف")], "confirm"))
    elif step == "identify":
        await ask(message, ctx, "أرسل الملف أو الصورة أو الفيديو أو الصوت لاستخراج File ID.")
    elif step == "broadcast":
        await ask(message, ctx, "أرسل نص الإعلان الذي تريد إرساله للمستخدمين.")
    elif step == "channel":
        await ask(message, ctx, "أرسل القناة بصيغة @ChannelUsername.")
    elif step == "link":
        await ask(message, ctx, "أرسل رقم الملف داخل قاعدة البيانات، مثل 12.")


async def complete_add(ctx, message):
    f = ctx.user_data["flow"]
    kind = f["kind"]
    title = f["title"]
    teacher = f.get("teacher") if kind == "note" else None
    section = f.get("section")
    month = f.get("month")
    try:
        execute(
            """INSERT INTO files
            (subject_id,kind,section,month,title,teacher,description,release_year,file_id,media_type,visible,downloads,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,1,0,?)""",
            (f.get("subject_id"), kind, section, month, title, teacher,
             f.get("description", ""), f.get("release_year", RELEASE_YEAR_DEFAULT),
             f["file_id"], f.get("media_type", "document"), datetime.now().isoformat(timespec="seconds")),
        )
        new_id = one("SELECT last_insert_rowid() AS id")["id"]
        await message.reply_text(f"✅ تمت إضافة الملف.\nرقم الملف: #{new_id}\nالرابط: {file_link(ctx.bot.username, new_id)}",
                                 reply_markup=admin_markup())
    except sqlite3.IntegrityError:
        await message.reply_text("هذا الـ File ID موجود مسبقاً. لم تتم إضافة نسخة مكررة.", reply_markup=admin_markup())
    finally:
        ctx.user_data.pop("flow", None)


async def do_broadcast(ctx, text):
    success = failed = 0
    user_rows = query("SELECT user_id FROM users WHERE blocked=0")
    for row in user_rows:
        try:
            await ctx.bot.send_message(chat_id=row["user_id"], text=text)
            success += 1
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
            try:
                await ctx.bot.send_message(chat_id=row["user_id"], text=text)
                success += 1
            except TelegramError:
                failed += 1
        except Forbidden:
            execute("UPDATE users SET blocked=1 WHERE user_id=?", (row["user_id"],))
            failed += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.06)
    return success, failed


async def show_all_ids(message):
    rows = query("""SELECT f.*,s.name AS subject_name FROM files f
                    LEFT JOIN subjects s ON s.id=f.subject_id ORDER BY f.id""")
    if not rows:
        await message.reply_text("لا توجد ملفات مسجلة.", reply_markup=admin_markup())
        return
    chunks, current = [], ""
    for row in rows:
        info = (
            f"#{row['id']} | {KIND_LABELS.get(row['kind'], row['kind'])} | "
            f"{row['subject_name'] or 'الأسئلة'} | {row['title']}\n"
            f"File ID: {row['file_id']}\n"
        )
        if len(current) + len(info) > 3500:
            chunks.append(current)
            current = ""
        current += info + "\n"
    if current:
        chunks.append(current)
    for chunk in chunks:
        await message.reply_text(chunk)
    await message.reply_text("انتهت القائمة.", reply_markup=admin_markup())


async def show_stats(message):
    users = one("SELECT COUNT(*) n FROM users")["n"]
    blocked = one("SELECT COUNT(*) n FROM users WHERE blocked=1")["n"]
    subjects = one("SELECT COUNT(*) n FROM subjects WHERE visible=1")["n"]
    hidden_subjects = one("SELECT COUNT(*) n FROM subjects WHERE visible=0")["n"]
    file_counts = {kind: one("SELECT COUNT(*) n FROM files WHERE kind=?", (kind,))["n"] for kind in KIND_LABELS}
    downloads = one("SELECT COALESCE(SUM(downloads),0) n FROM files")["n"]
    most = query("SELECT title,downloads FROM files ORDER BY downloads DESC,id DESC LIMIT 5")
    most_text = "\n".join(f"• {r['title']} — {r['downloads']} تنزيل" for r in most) or "لا توجد ملفات."
    await message.reply_text(
        "📊 إحصائيات البوت\n\n"
        f"المستخدمون: {users}\nالمحظورون: {blocked}\n"
        f"المواد الظاهرة: {subjects}\nالمواد المخفية: {hidden_subjects}\n"
        f"الكتب: {file_counts['book']}\nالملازم: {file_counts['note']}\n"
        f"الملخصات: {file_counts['summary']}\nالأسئلة: {file_counts['question']}\n"
        f"إجمالي التنزيلات: {downloads}\n\nالأكثر تنزيلاً:\n{most_text}",
        reply_markup=admin_markup(),
    )


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    remember_user(user.id)
    ctx.user_data.pop("flow", None)
    pending_id = None
    if ctx.args:
        arg = ctx.args[0]
        match = re.fullmatch(r"(?:file_|f)(\d+)", arg)
        if match:
            pending_id = int(match.group(1))
    if not is_owner(user.id) and not await check_subscription(ctx.bot, user.id):
        await message.reply_text(
            "لاستخدام البوت وتنزيل الملفات، اشترك بقناة رابعيون أولاً ثم اضغط التحقق.",
            reply_markup=gate_markup(pending_id),
        )
        return
    if pending_id:
        await deliver_file(ctx, message.chat_id, pending_id, is_owner(user.id))
    await send_home(message, is_owner(user.id))


async def admin_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and is_owner(user.id):
        await send_admin(update.effective_message)
    else:
        await update.effective_message.reply_text("هذا الأمر مخصص للمالك.")


async def cancel_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("flow", None)
    await update.effective_message.reply_text("تم إلغاء العملية.", reply_markup=home_markup(is_owner(update.effective_user.id)))


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cb = update.callback_query
    if not cb:
        return
    data = cb.data or ""
    await cb.answer()
    uid = cb.from_user.id
    if data == "site_missing":
        await cb.message.reply_text("رابط الموقع غير مضبوط. أضف متغير البيئة SITE_URL في FadeHost ثم أعد النشر.")
        return
    if data == "home":
        ctx.user_data.pop("flow", None)
        await send_home(cb.message, is_owner(uid))
        return
    if data == "cancel":
        ctx.user_data.pop("flow", None)
        await cb.message.reply_text("تم إلغاء العملية.", reply_markup=admin_markup() if is_owner(uid) else home_markup(False))
        return
    if data.startswith("checksub:"):
        if not is_owner(uid):
            SUB_CACHE.pop(uid, None)
        if not await check_subscription(ctx.bot, uid):
            await cb.message.reply_text(
                "لم يتم تأكيد الاشتراك. اشترك بالقناة ثم اضغط التحقق مرة أخرى. "
                "إذا كنت مشتركاً بالفعل، فقد يحتاج البوت إلى صلاحية التحقق من أعضاء القناة."
            )
            return
        try:
            pending = int(data.split(":", 1)[1])
        except ValueError:
            pending = 0
        await cb.message.reply_text("تم التحقق من الاشتراك.")
        if pending:
            await deliver_file(ctx, cb.message.chat_id, pending, is_owner(uid))
        await send_home(cb.message, is_owner(uid))
        return
    if not data.startswith("admin:"):
        # Selection callbacks for an active owner flow.
        if not is_owner(uid):
            return
        if data.startswith("picksubject:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["subject_id"] = int(data.split(":", 1)[1])
            if f["action"] in ("addfile", "addid"):
                f["step"] = "kind"
            elif f["action"] == "addsummary":
                f["kind"] = "summary"
                f["step"] = "section"
            elif f["action"] == "addquestion":
                f["kind"] = "question"
                f["subject_id"] = None
                f["step"] = "question_section"
            elif f["action"] == "editsubject":
                f["step"] = "subject_field"
            elif f["action"] == "deletesubject":
                f["step"] = "confirm_delete_subject"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickkind:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["kind"] = data.split(":", 1)[1]
            f["step"] = "title"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickmedia:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["media_type"] = data.split(":", 1)[1]
            f["step"] = "fileid"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("picksection:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["section"] = data.split(":", 1)[1]
            f["step"] = "title"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickqsection:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["section"] = data.split(":", 1)[1]
            f["step"] = "month" if f["section"] != "q_half" else "title"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickmonth:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["month"] = data.split(":", 1)[1]
            f["step"] = "title"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickfile:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["file_db_id"] = int(data.split(":", 1)[1])
            if f["action"] == "deletefile":
                f["step"] = "confirm_delete_file"
                await prompt_flow(cb.message, ctx)
            elif f["action"] == "togglefile":
                row = one("SELECT visible FROM files WHERE id=?", (f["file_db_id"],))
                execute("UPDATE files SET visible=? WHERE id=?", (0 if row["visible"] else 1, f["file_db_id"]))
                ctx.user_data.pop("flow", None)
                await cb.message.reply_text("تم تحديث حالة ظهور الملف.", reply_markup=admin_markup())
            elif f["action"] == "editfile":
                f["step"] = "edit_field"
                await prompt_flow(cb.message, ctx)
            elif f["action"] == "replacefile":
                f["step"] = "media"
                await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickfield:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["field"] = data.split(":", 1)[1]
            if f["field"] == "visible":
                row = one("SELECT visible FROM files WHERE id=?", (f["file_db_id"],))
                execute("UPDATE files SET visible=? WHERE id=?", (0 if row["visible"] else 1, f["file_db_id"]))
                ctx.user_data.pop("flow", None)
                await cb.message.reply_text("تم تحديث حالة ظهور الملف.", reply_markup=admin_markup())
            else:
                f["step"] = "new_value"
                await prompt_flow(cb.message, ctx)
            return
        if data.startswith("picksubjectfield:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            f["field"] = data.split(":", 1)[1]
            if f["field"] == "stype":
                f["step"] = "subject_type"
            else:
                f["step"] = "subject_value"
            await prompt_flow(cb.message, ctx)
            return
        if data.startswith("pickstype:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            stype = data.split(":", 1)[1]
            if f["action"] == "addsubject":
                pos = one("SELECT COALESCE(MAX(pos),0)+1 AS n FROM subjects")["n"]
                try:
                    execute(
                        "INSERT INTO subjects(name,emoji,color,stype,pos,visible) VALUES(?,?, 'success', ?, ?, 1)",
                        (f["subject_name"], f.get("emoji", "📚"), stype, pos),
                    )
                    answer = "تمت إضافة المادة بنجاح."
                except sqlite3.IntegrityError:
                    answer = "هذه المادة موجودة بالفعل."
            else:
                execute("UPDATE subjects SET stype=? WHERE id=?", (stype, f["subject_id"]))
                answer = "تم تحديث نوع تقسيم المادة."
            ctx.user_data.pop("flow", None)
            await cb.message.reply_text(answer, reply_markup=admin_markup())
            return
        if data.startswith("confirm:"):
            f = ctx.user_data.get("flow")
            if not f:
                return
            if data.split(":", 1)[1] != "yes":
                return
            if f["action"] == "deletefile":
                execute("DELETE FROM files WHERE id=?", (f["file_db_id"],))
                answer = "تم حذف الملف."
            else:
                execute("DELETE FROM subjects WHERE id=?", (f["subject_id"],))
                answer = "تم حذف المادة وملفاتها المرتبطة."
            ctx.user_data.pop("flow", None)
            await cb.message.reply_text(answer, reply_markup=admin_markup())
            return
        return

    if not is_owner(uid):
        await cb.answer("غير مسموح.", show_alert=True)
        return
    action = data.split(":", 1)[1]
    if action == "menu":
        await send_admin(cb.message)
        return
    if action in ("allids", "stats"):
        if action == "allids":
            await show_all_ids(cb.message)
        else:
            await show_stats(cb.message)
        return
    if action == "subscription":
        current = get_setting("subscription_enabled", "1")
        set_setting("subscription_enabled", "0" if current == "1" else "1")
        SUB_CACHE.clear()
        status = "مفعّل" if get_setting("subscription_enabled") == "1" else "معطّل"
        await cb.message.reply_text(f"الاشتراك الإجباري الآن: {status}", reply_markup=admin_markup())
        return
    if action in ("addfile", "addid", "addsummary", "addquestion", "editfile",
                  "replacefile", "deletefile", "togglefile", "addsubject",
                  "editsubject", "deletesubject", "identify", "genlink", "broadcast", "channel"):
        begin_flow(ctx, action)
        f = ctx.user_data["flow"]
        if action in ("addfile", "addid", "addsummary", "editsubject", "deletesubject"):
            f["step"] = "subject"
        elif action in ("editfile", "replacefile", "deletefile", "togglefile"):
            f["step"] = "file"
        elif action == "addquestion":
            f["kind"] = "question"
            f["step"] = "question_section"
        elif action == "addsubject":
            f["step"] = "subject_name"
        elif action == "identify":
            f["step"] = "identify"
        elif action == "genlink":
            f["step"] = "link"
        elif action == "broadcast":
            f["step"] = "broadcast"
        elif action == "channel":
            f["step"] = "channel"
        await prompt_flow(cb.message, ctx)
        return


async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or not msg.text:
        return
    remember_user(user.id)
    text = msg.text.strip()
    owner = is_owner(user.id)

    if text.startswith("/"):
        return
    if not owner:
        if not await check_subscription(ctx.bot, user.id):
            await msg.reply_text("اشترك بقناة رابعيون أولاً لاستخدام البوت.", reply_markup=gate_markup())
            return
        await msg.reply_text("استخدم الموقع لتصفح المواد. إذا عندك رابط ملف من الموقع، افتحه عبر تيليجرام.")
        return

    f = ctx.user_data.get("flow")
    if not f:
        if text in ("الموقع", "🌐 الموقع"):
            await send_home(msg, True)
        elif text in ("لوحة المالك", "🛠 لوحة المالك", "/admin"):
            await send_admin(msg)
        return

    step, action = f["step"], f["action"]
    if step == "title":
        if not text:
            await prompt_flow(msg, ctx); return
        f["title"] = text
        if action in ("addfile", "addid"):
            if f["kind"] == "note":
                f["step"] = "teacher"
            else:
                f["teacher"] = None
                f["step"] = "description"
        else:
            f["step"] = "description"
        await prompt_flow(msg, ctx); return
    if step == "teacher":
        f["teacher"] = "" if text == "-" else text
        f["step"] = "description"
        await prompt_flow(msg, ctx); return
    if step == "description":
        f["description"] = "" if text == "-" else text
        f["step"] = "year"
        await prompt_flow(msg, ctx); return
    if step == "year":
        try:
            year = RELEASE_YEAR_DEFAULT if text == "-" else int(text)
            if year < 2000 or year > 2100:
                raise ValueError
        except ValueError:
            await ask(msg, ctx, f"أدخل سنة صحيحة بين 2000 و2100 أو اكتب - للعام {RELEASE_YEAR_DEFAULT}.")
            return
        f["release_year"] = year
        f["step"] = "media" if action == "addfile" else "media_type"
        await prompt_flow(msg, ctx); return
    if step == "fileid":
        if not text or any(ch.isspace() for ch in text):
            await ask(msg, ctx, "أرسل File ID صحيحاً دون مسافات."); return
        f["file_id"] = text
        if action in ("addid", "addsummary", "addquestion"):
            await complete_add(ctx, msg); return
        return
    if step == "subject_name":
        if one("SELECT 1 FROM subjects WHERE name=?", (text,)):
            await ask(msg, ctx, "هذه المادة موجودة بالفعل. أرسل اسماً مختلفاً."); return
        f["subject_name"] = text
        f["step"] = "subject_emoji"
        await prompt_flow(msg, ctx); return
    if step == "subject_emoji":
        f["emoji"] = text[:12]
        f["step"] = "subject_type"
        await prompt_flow(msg, ctx); return
    if step == "subject_value":
        field = f["field"]
        if field == "name" and one("SELECT 1 FROM subjects WHERE name=? AND id<>?", (text, f["subject_id"])):
            await ask(msg, ctx, "اسم المادة مستخدم بالفعل. أرسل اسماً آخر."); return
        execute(f"UPDATE subjects SET {field}=? WHERE id=?", (text, f["subject_id"]))
        ctx.user_data.pop("flow", None)
        await msg.reply_text("تم تعديل المادة.", reply_markup=admin_markup()); return
    if step == "new_value":
        field = f["field"]
        try:
            if field == "release_year":
                val = int(text)
                if val < 2000 or val > 2100:
                    raise ValueError
            else:
                val = text
            execute(f"UPDATE files SET {field}=? WHERE id=?", (val, f["file_db_id"]))
        except ValueError:
            await ask(msg, ctx, "أدخل سنة صحيحة بين 2000 و2100."); return
        ctx.user_data.pop("flow", None)
        await msg.reply_text("تم تعديل الملف.", reply_markup=admin_markup()); return
    if step == "broadcast":
        ctx.user_data.pop("flow", None)
        success, failed = await do_broadcast(ctx, text)
        await msg.reply_text(f"انتهى الإعلان.\nنجح: {success}\nفشل: {failed}", reply_markup=admin_markup()); return
    if step == "channel":
        channel = text.strip()
        if not (channel.startswith("@") and re.fullmatch(r"@[A-Za-z0-9_]{5,}", channel)):
            await ask(msg, ctx, "الصيغة المطلوبة: @ChannelUsername"); return
        set_setting("channel", channel)
        SUB_CACHE.clear()
        ctx.user_data.pop("flow", None)
        await msg.reply_text("تم تغيير قناة الاشتراك.", reply_markup=admin_markup()); return
    if step == "link":
        db_id = parse_file_id(text)
        row = one("SELECT id FROM files WHERE id=?", (db_id,)) if db_id else None
        ctx.user_data.pop("flow", None)
        if not row:
            await msg.reply_text("لم أجد ملفاً بهذا الرقم.", reply_markup=admin_markup()); return
        await msg.reply_text(f"رابط الملف:\n{file_link(ctx.bot.username, row['id'])}", reply_markup=admin_markup()); return
    if step == "file":
        db_id = parse_file_id(text)
        row = one("SELECT id FROM files WHERE id=?", (db_id,)) if db_id else None
        if not row:
            await ask(msg, ctx, "أرسل رقم ملف صحيحاً مثل #12 أو اختره من الأزرار."); return
        f["file_db_id"] = db_id
        if action == "deletefile":
            f["step"] = "confirm_delete_file"
        elif action == "togglefile":
            old = one("SELECT visible FROM files WHERE id=?", (db_id,))["visible"]
            execute("UPDATE files SET visible=? WHERE id=?", (0 if old else 1, db_id))
            ctx.user_data.pop("flow", None)
            await msg.reply_text("تم تغيير حالة ظهور الملف.", reply_markup=admin_markup()); return
        elif action == "replacefile":
            f["step"] = "media"
        elif action == "editfile":
            f["step"] = "edit_field"
        await prompt_flow(msg, ctx); return
    if step == "identify":
        await ask(msg, ctx, "أرسل الملف كملف/صورة/فيديو/صوت، وليس كنص.")
        return
    if step in ("subject", "kind", "section", "question_section", "month", "media_type", "subject_field", "subject_type", "edit_field", "confirm_delete_file", "confirm_delete_subject"):
        await ask(msg, ctx, "استخدم أزرار الاختيار الظاهرة في الرسالة.")
        return


async def media_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return
    remember_user(user.id)
    if not is_owner(user.id):
        if not await check_subscription(ctx.bot, user.id):
            await msg.reply_text("اشترك بقناة رابعيون أولاً لاستخدام البوت.", reply_markup=gate_markup())
        return
    f = ctx.user_data.get("flow")
    if not f:
        return
    file_id, media_type = media_from_message(msg)
    if not file_id:
        await ask(msg, ctx, "لم أتعرف على نوع الملف. أرسل مستنداً أو صورة أو فيديو أو صوتاً.")
        return
    action, step = f["action"], f["step"]
    if step == "identify":
        await msg.reply_text(f"🆔 File ID:\n{file_id}\n\nنوع الملف: {media_type}", reply_markup=cancel_markup())
        return
    if step == "media" and action == "addfile":
        f["file_id"], f["media_type"] = file_id, media_type
        await complete_add(ctx, msg)
        return
    if step == "media" and action == "replacefile":
        try:
            execute("UPDATE files SET file_id=?,media_type=? WHERE id=?", (file_id, media_type, f["file_db_id"]))
            ctx.user_data.pop("flow", None)
            await msg.reply_text("تم استبدال الملف بنجاح.", reply_markup=admin_markup())
        except sqlite3.IntegrityError:
            await msg.reply_text("هذا File ID مستخدم في ملف آخر. لم يتم التغيير.", reply_markup=admin_markup())
        return
    await ask(msg, ctx, "الخطوة الحالية تحتاج نصاً أو اختياراً من الأزرار.")


async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err = ctx.error
    log.error("Unhandled error: %r", err, exc_info=(type(err), err, err.__traceback__) if err else None)


def main():
    if not BOT_TOKEN or BOT_TOKEN == "BOT_TOKEN" or len(BOT_TOKEN) < 20:
        raise RuntimeError("متغير البيئة BOT_TOKEN غير مضبوط. ضع توكن Telegram الحقيقي من @BotFather في إعدادات الاستضافة.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    media_filters = (
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO |
        filters.VOICE | filters.ANIMATION
    )
    app.add_handler(MessageHandler(media_filters & ~filters.COMMAND, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    log.info("Starting bot; database=%s", DB_PATH.resolve())
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
