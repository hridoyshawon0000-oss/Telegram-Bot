import asyncio
import logging
import random
import sqlite3
import time
from contextlib import closing
from html import escape
from urllib.parse import urlparse

from pyrogram import Client as PyrogramClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError, Forbidden, RetryAfter, BadRequest
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters,
)

# =========================================================
# CONFIGURATION — fill these placeholders before running
# =========================================================
BOT_TOKEN = "8990092257:AAHio2Gi7JcrrWWweoKXofYRV4jd3nuLmJc"
API_ID = 33511945
API_HASH = "d044392a17690c14ee5b4a23651a0700"
STRING_SESSION = "BQG2RvEAMqEZvxYVQSiqGgYnAD2bpddJ_Lez9m0iqkT_2NuFZxGCUEMp5fWuGMJuKk9nMy7OAk55brZMGQElagVIt0P1jOmxnu8EymXtZgZzk8lHupdjcHNsJYIezihx6RGPry_aNDGl_dLP1KlRbZ_KEAZk7NUw6GsX_-RUXHWQPtaLmfS7qH987xKAiGiVo7pBjVGyL7F9kZVxHFBKMwq9nHbOT3T5SGxfljYWh3Ntq-6VAfdznvqVyztz6CvZS1UvjEQPfewL4qgKqqbx5lT8d0adu-8uuC6FtaboN6GEVgVIetDC1lU1i7cAKh-wXOgFTLHLlDhqF6PXPzyxnqlmwMTU9wAAAAIL2oKZAA"

ADMIN_ID = 8788804249
BROADCAST_CHANNEL_ID = -1003785686277
WELCOME_MEDIA_CHANNEL_ID = -1003345168634
PODCAST_SOURCE_CHANNEL_ID = -1003345168634
CONFIRMATION_GROUP_ID = -5558967317

DATABASE = "media_bot.db"
DEFAULT_DELETE_AFTER = 30 * 60
WELCOME_DELETE_DELAY = 20 * 60
DELETE_CHECK_INTERVAL = 5
START_DELETE_DELAY = 2
MAX_RETRIES = 3
PODCAST_BATCH_SIZE = 15
PODCAST_INTERVAL_SECONDS = 30 * 60
PODCAST_DELETE_SECONDS = 30 * 60

ADMIN_PANEL_IMAGE = "https://carder.top/imagens/1791557140321-440701283.jpg"

DEFAULT_WELCOME = """👋🏻 {mention} 👋🏻 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨 𝐭𝐡𝐞 𝐌𝐞𝐝𝐢𝐚 𝐁𝐨𝐭𝐬 🫦

Greetings, Agent! 🚀
Your VIP Access Pass has been generated.

📌 Get instant access to free premium resources,
top updates, and tools! 🎯

──────────────────
🔞 VIP DROPS │ 🎯 DAILY UPDATES │ ⛔ FREE CONTENT
──────────────────

👇 Unlock full access in 2 quick steps:

▸ Join all mandatory channels below 📌
▸ Hit the [ VERIFICATION ] button below 🔑

Enjoy your stay & welcome to the network! ❤️"""

DEFAULT_BUTTONS = [
    (1, "📢 ᴊ0𝐢𝐧𝐢𝐧𝐠 0𝐮𝐫 𝐜𝐡𝐚𝐧𝐧𝐞𝐥𝐬 🔞", "https://t.me/ALVEE_BD1"),
    (2, "🪧 𝐜0𝐧𝐭𝐚𝐜𝐭 𝐭0 𝐜𝐞0 0𝐰𝐧𝐞𝐫 📥", "https://t.me/ALVEE_BD"),
    (3, "📲 ˢʰᵃʳᵉ ᴬⁿᴅ ᴬᴅᴅ ᴹ𝐞ᴍʙ𝐞𝐫ꜱ 🔰",
     "https://t.me/share/url?url=https%3A%2F%2Ft.me%2FXMedia90_Bot%3Fstart%3Dstart"),
]
PODCAST_BUTTON = InlineKeyboardMarkup([[
    InlineKeyboardButton(
        "🔞ꜱʜᴀʀᴇ 𝐭𝐡𝐞 𝐯ɪᴅ𝐞𝖔ꜱ",
        url="https://t.me/share/url?url=https%3A%2F%2Ft.me%2FXMedia90_Bot%3Fstart%3Dstart",
    )
]])

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
SCAN_LOCK = asyncio.Lock()


# =========================================================
# DATABASE
# =========================================================
def db_connect():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def setup_database():
    with closing(db_connect()) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS broadcast_users (
            user_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'active',
            banned INTEGER NOT NULL DEFAULT 0,
            first_seen REAL NOT NULL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS scheduled_deletions (
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            delete_at REAL NOT NULL,
            PRIMARY KEY (chat_id, message_id)
        )""")
        conn.execute("CREATE TABLE IF NOT EXISTS bot_admins (user_id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("""CREATE TABLE IF NOT EXISTS welcome_buttons (
            slot INTEGER PRIMARY KEY, label TEXT NOT NULL, url TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS welcome_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            file_id TEXT NOT NULL UNIQUE,
            source_message_id INTEGER,
            added_at REAL NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS user_media_history (
            user_id INTEGER NOT NULL, media_id INTEGER NOT NULL, sent_at REAL NOT NULL,
            PRIMARY KEY (user_id, media_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS welcome_messages (
            user_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS podcast_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, added_at REAL NOT NULL,
            UNIQUE(chat_id, message_id)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS media_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, media_type TEXT NOT NULL, file_id TEXT NOT NULL,
            caption TEXT, source_chat_id INTEGER, source_message_id INTEGER, conf_message_id INTEGER
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS confirmed_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT NOT NULL,
            caption TEXT, added_at REAL NOT NULL
        )""")

        # Migrate older databases that may lack these columns.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(broadcast_users)").fetchall()}
        if "status" not in cols:
            conn.execute("ALTER TABLE broadcast_users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if "banned" not in cols:
            conn.execute("ALTER TABLE broadcast_users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0")
        if "first_seen" not in cols:
            conn.execute("ALTER TABLE broadcast_users ADD COLUMN first_seen REAL NOT NULL DEFAULT 0")

        conn.execute("INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)", (ADMIN_ID,))
        conn.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES (?,?)",
                     ("welcome_text", DEFAULT_WELCOME))
        conn.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES (?,?)",
                     ("welcome_type", "text"))
        conn.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES (?,?)",
                     ("welcome_file_id", ""))
        conn.execute("INSERT OR IGNORE INTO bot_settings (key,value) VALUES (?,?)",
                     ("delete_after", str(DEFAULT_DELETE_AFTER)))
        for slot, label, url in DEFAULT_BUTTONS:
            conn.execute("INSERT OR IGNORE INTO welcome_buttons (slot,label,url) VALUES (?,?,?)",
                         (slot, label, url))
        conn.commit()


def db_get_setting(key, default=""):
    with closing(db_connect()) as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def db_set_setting(key, value):
    with closing(db_connect()) as conn:
        conn.execute("""INSERT INTO bot_settings (key,value) VALUES (?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, str(value)))
        conn.commit()


def is_admin(user_id):
    with closing(db_connect()) as conn:
        return conn.execute("SELECT 1 FROM bot_admins WHERE user_id=?", (user_id,)).fetchone() is not None


def get_admin_ids():
    with closing(db_connect()) as conn:
        return [r[0] for r in conn.execute("SELECT user_id FROM bot_admins ORDER BY user_id").fetchall()]


def register_user(user_id):
    with closing(db_connect()) as conn:
        conn.execute("""INSERT INTO broadcast_users (user_id,status,banned,first_seen)
            VALUES (?,'active',0,?)
            ON CONFLICT(user_id) DO UPDATE SET status='active'""", (user_id, time.time()))
        conn.commit()


def get_registered_users(include_banned=False):
    sql = "SELECT user_id FROM broadcast_users WHERE status='active'"
    if not include_banned:
        sql += " AND banned=0"
    with closing(db_connect()) as conn:
        return conn.execute(sql).fetchall()


def mark_user_blocked(user_id):
    with closing(db_connect()) as conn:
        conn.execute("UPDATE broadcast_users SET status='blocked' WHERE user_id=?", (user_id,))
        conn.commit()


def set_user_banned(user_id, banned=True):
    with closing(db_connect()) as conn:
        conn.execute("""INSERT INTO broadcast_users (user_id,status,banned,first_seen)
            VALUES (?,'active',?,?)
            ON CONFLICT(user_id) DO UPDATE SET banned=excluded.banned""",
            (user_id, int(banned), time.time()))
        conn.commit()


def get_member_stats():
    with closing(db_connect()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM broadcast_users").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM broadcast_users WHERE status='active' AND banned=0").fetchone()[0]
        blocked = conn.execute("SELECT COUNT(*) FROM broadcast_users WHERE status='blocked'").fetchone()[0]
        banned = conn.execute("SELECT COUNT(*) FROM broadcast_users WHERE banned=1").fetchone()[0]
    return total, active, blocked, banned


def get_welcome_buttons():
    with closing(db_connect()) as conn:
        return conn.execute("SELECT slot,label,url FROM welcome_buttons ORDER BY slot").fetchall()


def update_welcome_button(slot, label, url):
    with closing(db_connect()) as conn:
        conn.execute("UPDATE welcome_buttons SET label=?,url=? WHERE slot=?", (label, url, slot))
        conn.commit()


def get_delete_after():
    try:
        return max(60, int(db_get_setting("delete_after", str(DEFAULT_DELETE_AFTER))))
    except (ValueError, TypeError):
        return DEFAULT_DELETE_AFTER


def schedule_message_deletion(chat_id, message_id, delay_seconds=None):
    if delay_seconds is None:
        delay_seconds = get_delete_after()
    with closing(db_connect()) as conn:
        conn.execute("""INSERT OR REPLACE INTO scheduled_deletions (chat_id,message_id,delete_at)
            VALUES (?,?,?)""", (chat_id, message_id, time.time() + delay_seconds))
        conn.commit()


def remove_scheduled_deletion(chat_id, message_id):
    with closing(db_connect()) as conn:
        conn.execute("DELETE FROM scheduled_deletions WHERE chat_id=? AND message_id=?",
                     (chat_id, message_id))
        conn.commit()


# =========================================================
# WELCOME MEDIA
# =========================================================
def save_welcome_media(media_type, file_id, source_message_id=None):
    if media_type not in ("photo", "video") or not file_id:
        return False
    with closing(db_connect()) as conn:
        cur = conn.execute("""INSERT OR IGNORE INTO welcome_media
            (media_type,file_id,source_message_id,added_at) VALUES (?,?,?,?)""",
            (media_type, file_id, source_message_id, time.time()))
        conn.commit()
        return cur.rowcount > 0


def get_channel_media(message):
    if message.video:
        return "video", message.video.file_id
    if message.photo:
        return "photo", message.photo[-1].file_id
    return None, None


def choose_welcome_media(user_id):
    with closing(db_connect()) as conn:
        all_media = conn.execute(
            "SELECT id,media_type,file_id,source_message_id FROM welcome_media ORDER BY id"
        ).fetchall()
        if not all_media:
            return None
        unseen = conn.execute("""SELECT id,media_type,file_id,source_message_id FROM welcome_media
            WHERE id NOT IN (SELECT media_id FROM user_media_history WHERE user_id=?)""",
            (user_id,)).fetchall()
        if not unseen:
            conn.execute("DELETE FROM user_media_history WHERE user_id=?", (user_id,))
            conn.commit()
            unseen = all_media
        return random.choice(unseen)


def mark_welcome_media_seen(user_id, media_id):
    with closing(db_connect()) as conn:
        conn.execute("INSERT OR IGNORE INTO user_media_history (user_id,media_id,sent_at) VALUES (?,?,?)",
                     (user_id, media_id, time.time()))
        conn.commit()


def get_previous_welcome(user_id):
    with closing(db_connect()) as conn:
        return conn.execute("SELECT chat_id,message_id FROM welcome_messages WHERE user_id=?",
                            (user_id,)).fetchone()


def save_previous_welcome(user_id, chat_id, message_id):
    with closing(db_connect()) as conn:
        conn.execute("""INSERT INTO welcome_messages (user_id,chat_id,message_id) VALUES (?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET chat_id=excluded.chat_id,message_id=excluded.message_id""",
            (user_id, chat_id, message_id))
        conn.commit()


async def delete_previous_welcome(bot, user_id):
    previous = get_previous_welcome(user_id)
    if not previous:
        return
    chat_id, message_id = previous
    remove_scheduled_deletion(chat_id, message_id)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError:
        pass
    with closing(db_connect()) as conn:
        conn.execute("DELETE FROM welcome_messages WHERE user_id=?", (user_id,))
        conn.commit()


def make_welcome_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, url=url)]
        for _slot, label, url in get_welcome_buttons()
    ])


def format_welcome_text(raw_text, user):
    safe_name = escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    marker = "___WELCOME_USER_MENTION___"
    safe_text = escape(raw_text or "").replace("{mention}", marker)
    return safe_text.replace(marker, mention)


async def send_welcome(bot, chat_id, user):
    raw = db_get_setting("welcome_text", DEFAULT_WELCOME)
    formatted = format_welcome_text(raw, user)
    keyboard = make_welcome_keyboard()
    chosen = choose_welcome_media(user.id)
    sent = None

    try:
        if chosen:
            media_id, media_type, file_id, source_message_id = chosen
            # Bot API file_ids are bot-specific. Use file_id for media collected by the bot;
            # source_message_id is kept for reference and for scanner records.
            if file_id.startswith("source:") and source_message_id:
                # Old media found by the user session is copied from the source channel.
                copied = await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=WELCOME_MEDIA_CHANNEL_ID,
                    message_id=source_message_id,
                    caption=formatted[:1024],
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                sent = copied
            elif media_type == "photo":
                sent = await bot.send_photo(chat_id=chat_id, photo=file_id,
                    caption=formatted[:1024], parse_mode="HTML", reply_markup=keyboard)
            else:
                sent = await bot.send_video(chat_id=chat_id, video=file_id,
                    caption=formatted[:1024], parse_mode="HTML", reply_markup=keyboard)
            mark_welcome_media_seen(user.id, media_id)
        else:
            sent = await bot.send_message(chat_id=chat_id, text=formatted[:4096],
                parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
    except TelegramError:
        logger.exception("Welcome media failed for user %s", user.id)
        sent = await bot.send_message(chat_id=chat_id, text=formatted[:4096],
            parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)

    if sent:
        save_previous_welcome(user.id, chat_id, sent.message_id)
        schedule_message_deletion(chat_id, sent.message_id, WELCOME_DELETE_DELAY)
    return sent


# =========================================================
# START AND MESSAGE COPY HELPERS
# =========================================================
async def delete_start_later(context, chat_id, message_id):
    await asyncio.sleep(START_DELETE_DELAY)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, chat, message = update.effective_user, update.effective_chat, update.effective_message
    if not user or not chat or not message:
        return
    if chat.type == "private":
        with closing(db_connect()) as conn:
            row = conn.execute("SELECT banned FROM broadcast_users WHERE user_id=?", (user.id,)).fetchone()
        if row and row[0]:
            await message.reply_text("⛔ Your access to this bot has been restricted by an administrator.")
            return
        register_user(user.id)
        await delete_previous_welcome(context.bot, user.id)
    context.application.create_task(delete_start_later(context, chat.id, message.message_id))
    await send_welcome(context.bot, chat.id, user)


async def copy_to_user(application, user_id, source_chat_id, message_id,
                       reply_markup=None, deletion_seconds=None):
    for attempt in range(MAX_RETRIES):
        try:
            sent = await application.bot.copy_message(
                chat_id=user_id, from_chat_id=source_chat_id,
                message_id=message_id, reply_markup=reply_markup,
            )
            schedule_message_deletion(user_id, sent.message_id, deletion_seconds)
            return 1
        except RetryAfter as error:
            delay = error.retry_after
            if hasattr(delay, "total_seconds"):
                delay = delay.total_seconds()
            await asyncio.sleep(float(delay) + 1)
        except Forbidden:
            mark_user_blocked(user_id)
            raise
        except TelegramError:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(attempt + 1)
    return 0


# =========================================================
# MEDIA APPROVAL WORKFLOW
# =========================================================
async def incoming_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, chat = update.effective_message, update.effective_chat
    if not message or not chat or chat.id == CONFIRMATION_GROUP_ID:
        return
    if chat.type not in ("group", "supergroup", "channel"):
        return
    media_type, file_id = get_channel_media(message)
    if not media_type or not file_id:
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data=f"med_conf_{media_type}"),
        InlineKeyboardButton("❌ Delete", callback_data="med_del"),
    ]])
    try:
        source_info = f"📦 Source: {escape(chat.title or 'Unknown')} (<code>{chat.id}</code>)"
        full_caption = f"{source_info}\n\n{escape(message.caption or '')}"[:1024]
        if media_type == "video":
            sent = await context.bot.send_video(CONFIRMATION_GROUP_ID, video=file_id,
                caption=full_caption, parse_mode="HTML", reply_markup=keyboard)
        else:
            sent = await context.bot.send_photo(CONFIRMATION_GROUP_ID, photo=file_id,
                caption=full_caption, parse_mode="HTML", reply_markup=keyboard)
        with closing(db_connect()) as conn:
            conn.execute("""INSERT INTO media_approvals
                (media_type,file_id,caption,source_chat_id,source_message_id,conf_message_id)
                VALUES (?,?,?,?,?,?)""",
                (media_type, file_id, message.caption or "", chat.id, message.message_id, sent.message_id))
            conn.commit()
    except Exception:
        logger.exception("Could not forward media to confirmation group")


async def media_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query, user = update.callback_query, update.effective_user
    if not query or not (query.data or "").startswith("med_"):
        return
    if not user or not is_admin(user.id):
        await query.answer("⛔ Admin access only.", show_alert=True)
        return
    await query.answer()
    conf_msg_id = query.message.message_id

    if query.data.startswith("med_conf_"):
        media_type = query.data.split("_")[2]
        with closing(db_connect()) as conn:
            row = conn.execute("SELECT file_id,caption FROM media_approvals WHERE conf_message_id=?",
                               (conf_msg_id,)).fetchone()
        if not row:
            await query.edit_message_caption(caption="❌ Media record not found or already processed.")
            return
        file_id, caption = row
        if media_type == "video":
            with closing(db_connect()) as conn:
                conn.execute("INSERT INTO confirmed_videos (file_id,caption,added_at) VALUES (?,?,?)",
                             (file_id, caption, time.time()))
                conn.commit()
            result = "✅ Confirmed and queued for broadcast."
        else:
            save_welcome_media("photo", file_id)
            result = "✅ Confirmed and added to welcome media pool."
        try:
            await query.edit_message_caption(
                caption=f"{(query.message.caption or '')[:700]}\n\n{result}",
                reply_markup=None,
            )
        except TelegramError:
            pass
        with closing(db_connect()) as conn:
            conn.execute("DELETE FROM media_approvals WHERE conf_message_id=?", (conf_msg_id,))
            conn.commit()

    elif query.data == "med_del":
        try:
            await query.message.delete()
        except TelegramError:
            pass
        with closing(db_connect()) as conn:
            conn.execute("DELETE FROM media_approvals WHERE conf_message_id=?", (conf_msg_id,))
            conn.commit()


async def confirmed_video_broadcaster_worker(application: Application):
    await asyncio.sleep(60)
    while True:
        try:
            with closing(db_connect()) as conn:
                videos = conn.execute("SELECT id,file_id,caption FROM confirmed_videos ORDER BY id LIMIT 15").fetchall()
            users = get_registered_users()
            if videos and users:
                for vid_id, file_id, caption in videos:
                    for (user_id,) in users:
                        try:
                            sent = await application.bot.send_video(
                                chat_id=user_id, video=file_id,
                                caption=(caption or "")[:1024],
                            )
                            schedule_message_deletion(user_id, sent.message_id, 30 * 60)
                        except Forbidden:
                            mark_user_blocked(user_id)
                        except TelegramError:
                            logger.warning("Confirmed video send failed for user %s", user_id)
                        await asyncio.sleep(0.05)
                ids = [row[0] for row in videos]
                with closing(db_connect()) as conn:
                    conn.executemany("DELETE FROM confirmed_videos WHERE id=?", [(x,) for x in ids])
                    conn.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Confirmed video worker error")
        await asyncio.sleep(30 * 60)


# =========================================================
# CHANNEL POSTS + OLD HISTORY SCANNER
# =========================================================
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message:
        return

    if message.chat_id == WELCOME_MEDIA_CHANNEL_ID:
        media_type, file_id = get_channel_media(message)
        if media_type and file_id:
            save_welcome_media(media_type, file_id, message.message_id)
            logger.info("Saved new welcome media message %s", message.message_id)

    if message.chat_id == PODCAST_SOURCE_CHANNEL_ID:
        is_video = bool(message.video) or bool(
            message.document and message.document.mime_type
            and message.document.mime_type.startswith("video/")
        )
        if is_video:
            with closing(db_connect()) as conn:
                conn.execute("""INSERT OR IGNORE INTO podcast_videos
                    (chat_id,message_id,added_at) VALUES (?,?,?)""",
                    (message.chat_id, message.message_id, time.time()))
                conn.commit()
            logger.info("Saved new source video %s", message.message_id)
        return

    if message.chat_id != BROADCAST_CHANNEL_ID:
        return

    users = get_registered_users()
    for (user_id,) in users:
        try:
            await copy_to_user(context.application, user_id, message.chat_id, message.message_id)
        except Exception:
            pass
        await asyncio.sleep(0.03)


async def scan_old_media_and_podcasts_pyrogram():
    if SCAN_LOCK.locked():
        logger.info("A scan is already running; skipping duplicate request.")
        return 0, 0

    async with SCAN_LOCK:
        welcome_count = 0
        podcast_count = 0
        async with PyrogramClient(
            "user_scanner_session",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=STRING_SESSION,
        ) as pyro_app:
            chat = await pyro_app.get_chat(PODCAST_SOURCE_CHANNEL_ID)
            source_chat_id = chat.id
            logger.info("Scanning old posts in source channel %s", source_chat_id)

            async for message in pyro_app.get_chat_history(source_chat_id):
                if message.photo:
                    source_ref = f"source:{source_chat_id}:{message.id}"
                    if save_welcome_media("photo", source_ref, message.id):
                        welcome_count += 1
                elif message.video:
                    source_ref = f"source:{source_chat_id}:{message.id}"
                    if save_welcome_media("video", source_ref, message.id):
                        welcome_count += 1

                is_video = bool(message.video) or bool(
                    message.document and message.document.mime_type
                    and message.document.mime_type.startswith("video/")
                )
                if is_video:
                    with closing(db_connect()) as conn:
                        cur = conn.execute("""INSERT OR IGNORE INTO podcast_videos
                            (chat_id,message_id,added_at) VALUES (?,?,?)""",
                            (source_chat_id, message.id, time.time()))
                        conn.commit()
                        if cur.rowcount > 0:
                            podcast_count += 1

        logger.info("Scan finished: %s welcome items; %s videos added",
                    welcome_count, podcast_count)
        return welcome_count, podcast_count


async def importpodcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, message = update.effective_user, update.effective_message
    if not user or not message or not is_admin(user.id):
        if message:
            await message.reply_text("⛔ Admin access only.")
        return
    status = await message.reply_text("⏳ Scanning old channel videos and welcome media...")
    try:
        welcome_added, videos_added = await scan_old_media_and_podcasts_pyrogram()
        with closing(db_connect()) as conn:
            total_welcome = conn.execute("SELECT COUNT(*) FROM welcome_media").fetchone()[0]
            total_videos = conn.execute("SELECT COUNT(*) FROM podcast_videos").fetchone()[0]
        await status.edit_text(
            "✅ Scan completed.\n\n"
            f"New welcome media: {welcome_added}\n"
            f"New videos: {videos_added}\n"
            f"Total welcome media: {total_welcome}\n"
            f"Total saved videos: {total_videos}"
        )
    except Exception as error:
        logger.exception("Import scan failed")
        await status.edit_text(f"❌ Scan failed: {str(error)[:700]}")


async def podcast_poster_worker(application: Application):
    # First run after startup, then repeat every 30 minutes.
    await asyncio.sleep(20)
    while True:
        try:
            with closing(db_connect()) as conn:
                videos = conn.execute(
                    "SELECT chat_id,message_id FROM podcast_videos ORDER BY RANDOM() LIMIT ?",
                    (PODCAST_BATCH_SIZE,),
                ).fetchall()
            users = get_registered_users()

            if videos and users:
                logger.info("Sending %s videos to %s users", len(videos), len(users))
                for chat_id, msg_id in videos:
                    for (user_id,) in users:
                        try:
                            await copy_to_user(
                                application, user_id, chat_id, msg_id,
                                reply_markup=PODCAST_BUTTON,
                                deletion_seconds=PODCAST_DELETE_SECONDS,
                            )
                        except Exception as error:
                            logger.warning("Video %s failed for %s: %s", msg_id, user_id, error)
                        await asyncio.sleep(0.05)
            else:
                logger.info("Podcast worker: no videos or registered users.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Podcast poster worker error")
        await asyncio.sleep(PODCAST_INTERVAL_SECONDS)


# =========================================================
# ADMIN PANEL
# =========================================================
def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Admin", callback_data="adm:add_admin")],
        [InlineKeyboardButton("👥 Total Members", callback_data="adm:members")],
        [InlineKeyboardButton("🔘 Welcome Buttons", callback_data="adm:welcome_buttons")],
        [InlineKeyboardButton("📊 Media Pool Stats", callback_data="adm:mediastats")],
        [InlineKeyboardButton("🚫 Ban Users", callback_data="adm:ban_menu")],
        [InlineKeyboardButton("⏱ Broadcast Delete Time", callback_data="adm:delete_time")],
        [InlineKeyboardButton("🛡️ Admin List", callback_data="adm:admin_list")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="adm:home")]])


async def edit_admin_page(query, text, keyboard=None):
    keyboard = keyboard or back_keyboard()
    try:
        if query.message and query.message.photo:
            await query.edit_message_caption(caption=text[:1024], parse_mode="HTML", reply_markup=keyboard)
        else:
            await query.edit_message_text(text=text[:4096], parse_mode="HTML",
                                          reply_markup=keyboard, disable_web_page_preview=True)
    except BadRequest as error:
        if "message is not modified" not in str(error).lower():
            logger.debug("Admin page edit failed: %s", error)


async def show_admin_panel(update_or_query, context):
    keyboard = admin_main_keyboard()
    if getattr(update_or_query, "callback_query", None):
        query = update_or_query.callback_query
        await query.answer()
        await edit_admin_page(query, "🛠️ <b>BOT ADMIN PANEL</b>\n\nChoose a section below:", keyboard)
        return
    message = update_or_query.effective_message
    try:
        await context.bot.send_photo(
            chat_id=message.chat_id, photo=ADMIN_PANEL_IMAGE,
            caption="🛠️ <b>BOT ADMIN PANEL</b>\n\nChoose a section below:",
            parse_mode="HTML", reply_markup=keyboard,
        )
    except TelegramError:
        await message.reply_text("🛠️ BOT ADMIN PANEL\n\nChoose a section below:", reply_markup=keyboard)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Admin access only.")
        return
    await show_admin_panel(update, context)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query, user = update.callback_query, update.effective_user
    if not query:
        return
    if not user or not is_admin(user.id):
        await query.answer("⛔ Admin access only.", show_alert=True)
        return
    await query.answer()
    data = query.data or ""

    if data == "adm:home":
        await edit_admin_page(query, "🛠️ <b>BOT ADMIN PANEL</b>\n\nChoose a section below:", admin_main_keyboard())
    elif data == "adm:add_admin":
        context.user_data["admin_action"] = "add_admin"
        await edit_admin_page(query, "➕ <b>ADD ADMIN</b>\n\nSend numeric Telegram user ID.\n/cancel to cancel.")
    elif data == "adm:members":
        total, active, blocked, banned = get_member_stats()
        await edit_admin_page(query, f"👥 <b>MEMBERS</b>\n\nRegistered: <b>{total}</b>\nActive: <b>{active}</b>\nBlocked: <b>{blocked}</b>\nBanned: <b>{banned}</b>")
    elif data == "adm:mediastats":
        with closing(db_connect()) as conn:
            wm = conn.execute("SELECT COUNT(*) FROM welcome_media").fetchone()[0]
            vids = conn.execute("SELECT COUNT(*) FROM podcast_videos").fetchone()[0]
        await edit_admin_page(query, f"📊 <b>MEDIA STATS</b>\n\nWelcome photos/videos: <b>{wm}</b>\nSaved source videos: <b>{vids}</b>")
    elif data == "adm:welcome_buttons":
        rows = [[InlineKeyboardButton(f"✏️ Edit Button {slot}: {label[:30]}",
                                     callback_data=f"adm:edit_button:{slot}")]
                for slot, label, _url in get_welcome_buttons()]
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="adm:home")])
        await edit_admin_page(query, "🔘 <b>WELCOME BUTTONS</b>\n\nChoose a button to edit:",
                              InlineKeyboardMarkup(rows))
    elif data.startswith("adm:edit_button:"):
        try:
            slot = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        if slot not in (1, 2, 3):
            return
        context.user_data["admin_action"] = "edit_button_label"
        context.user_data["button_slot"] = slot
        await edit_admin_page(query, f"✏️ <b>EDIT BUTTON {slot}</b>\n\nSend the new button label, then URL.\n/cancel to cancel.")
    elif data == "adm:ban_menu":
        await edit_admin_page(query, "🚫 <b>USER ACCESS CONTROL</b>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Ban User", callback_data="adm:ban_user")],
                [InlineKeyboardButton("✅ Unban User", callback_data="adm:unban_user")],
                [InlineKeyboardButton("⬅️ Back", callback_data="adm:home")],
            ]))
    elif data in ("adm:ban_user", "adm:unban_user"):
        context.user_data["admin_action"] = "ban_user" if data.endswith("ban_user") and data == "adm:ban_user" else "unban_user"
        await edit_admin_page(query, "Send the numeric Telegram user ID.\n/cancel to cancel.")
    elif data == "adm:delete_time":
        current = get_delete_after()
        await edit_admin_page(query, f"⏱ <b>DELETE TIME</b>\n\nCurrent: <b>{current // 60} minutes</b>",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("15m", callback_data="adm:time:900"),
                 InlineKeyboardButton("30m", callback_data="adm:time:1800")],
                [InlineKeyboardButton("⬅️ Back", callback_data="adm:home")],
            ]))
    elif data.startswith("adm:time:"):
        try:
            seconds = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        db_set_setting("delete_after", seconds)
        await edit_admin_page(query, f"✅ Delete time set to <b>{seconds // 60} minutes</b>.")
    elif data == "adm:admin_list":
        ids = get_admin_ids()
        listing = "\n".join(f"• <code>{admin_id}</code>" for admin_id in ids)
        await edit_admin_page(query, "🛡️ <b>ADMIN LIST</b>\n\n" + (listing or "No admins found."))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and is_admin(update.effective_user.id):
        context.user_data.pop("admin_action", None)
        context.user_data.pop("button_slot", None)
        context.user_data.pop("pending_button_label", None)
        await update.effective_message.reply_text("❎ Cancelled.")
    elif update.effective_message:
        await update.effective_message.reply_text("Nothing to cancel.")


def valid_button_url(value):
    parsed = urlparse(value.strip())
    return parsed.scheme in ("https", "http", "tg") and bool(parsed.netloc or parsed.scheme == "tg")


async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, message = update.effective_user, update.effective_message
    if not user or not message or not is_admin(user.id):
        return
    action = context.user_data.get("admin_action")
    if not action:
        return

    text = (message.text or "").strip()
    if action in ("add_admin", "ban_user", "unban_user"):
        if not text.isdigit():
            await message.reply_text("❌ Please send a numeric Telegram user ID.")
            return
        target = int(text)
        if action == "add_admin":
            with closing(db_connect()) as conn:
                conn.execute("INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)", (target,))
                conn.commit()
            result = f"✅ Admin added: {target}"
        else:
            set_user_banned(target, action == "ban_user")
            result = f"✅ User {target} " + ("banned." if action == "ban_user" else "unbanned.")
        context.user_data.pop("admin_action", None)
        await message.reply_text(result)
    elif action == "edit_button_label":
        if not text:
            await message.reply_text("❌ Please send a button name.")
            return
        context.user_data["pending_button_label"] = text[:64]
        context.user_data["admin_action"] = "edit_button_url"
        await message.reply_text("🔗 Now send the button URL.")
    elif action == "edit_button_url":
        if not valid_button_url(text):
            await message.reply_text("❌ Invalid URL.")
            return
        slot = context.user_data.get("button_slot")
        label = context.user_data.get("pending_button_label", "Button")
        update_welcome_button(slot, label, text)
        context.user_data.pop("admin_action", None)
        context.user_data.pop("button_slot", None)
        context.user_data.pop("pending_button_label", None)
        await message.reply_text(f"✅ Welcome button {slot} updated.")


async def mediastats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, message = update.effective_user, update.effective_message
    if not user or not message or not is_admin(user.id):
        return
    with closing(db_connect()) as conn:
        welcome = conn.execute("SELECT COUNT(*) FROM welcome_media").fetchone()[0]
        videos = conn.execute("SELECT COUNT(*) FROM podcast_videos").fetchone()[0]
    await message.reply_text(f"📊 Welcome media: {welcome}\n🎬 Source videos: {videos}")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message, user = update.effective_message, update.effective_user
    if not message or not user or not is_admin(user.id):
        return
    source = message.reply_to_message
    if not source:
        await message.reply_text("📢 Reply to a message and send /broadcast.")
        return
    status = await message.reply_text("⏳ Manual broadcast started...")
    users = get_registered_users()
    successful = failed = 0
    for (user_id,) in users:
        try:
            await copy_to_user(context.application, user_id, source.chat_id, source.message_id)
            successful += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.03)
    try:
        await status.edit_text(f"✅ Broadcast completed. Successful: {successful}, Failed: {failed}")
    except TelegramError:
        pass


# =========================================================
# AUTO DELETE AND STARTUP
# =========================================================
async def automatic_deletion(application: Application):
    now = time.time()
    with closing(db_connect()) as conn:
        due = conn.execute("SELECT chat_id,message_id FROM scheduled_deletions WHERE delete_at<=?",
                           (now,)).fetchall()
    for chat_id, message_id in due:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramError as error:
            logger.warning("Could not delete message %s in %s: %s", message_id, chat_id, error)
        finally:
            remove_scheduled_deletion(chat_id, message_id)


async def deletion_worker(application: Application):
    while True:
        try:
            await automatic_deletion(application)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Deletion worker error")
        await asyncio.sleep(DELETE_CHECK_INTERVAL)


async def post_init(application: Application):
    setup_database()
    application.create_task(deletion_worker(application), name="deletion_worker")
    application.create_task(podcast_poster_worker(application), name="podcast_poster_worker")
    application.create_task(confirmed_video_broadcaster_worker(application), name="confirmed_video_broadcaster_worker")
    application.create_task(scan_old_media_and_podcasts_pyrogram(), name="initial_media_scan")
    logger.info("Database and workers initialized.")


# =========================================================
# MAIN
# =========================================================
def main():
    if BOT_TOKEN == "PASTE_NEW_BOT_TOKEN_HERE":
        raise RuntimeError("Set BOT_TOKEN at the top of this file before starting.")
    if API_HASH == "PASTE_API_HASH_HERE" or STRING_SESSION == "PASTE_NEW_STRING_SESSION_HERE":
        raise RuntimeError("Set API_HASH and STRING_SESSION at the top of this file before starting.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("mediastats", mediastats_command))
    app.add_handler(CommandHandler("importpodcast", importpodcast_command))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^adm:"))
    app.add_handler(CallbackQueryHandler(media_approval_callback, pattern=r"^med_"))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
    app.add_handler(MessageHandler((filters.PHOTO | filters.VIDEO) & ~filters.ChatType.PRIVATE,
                                   incoming_media_handler))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.VIDEO)
                                   & ~filters.COMMAND, admin_input_handler))
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=["message", "channel_post", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    main()
