import asyncio
import logging
import random
import sqlite3
import time
from contextlib import closing
from html import escape
from urllib.parse import urlparse

# Pyrogram Library
from pyrogram import Client as PyrogramClient

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import (
    TelegramError,
    Forbidden,
    RetryAfter,
    BadRequest,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = "8990092257:AAEjSow_PU3k3HEvDwjhD_Z8XcUyLZ9hcsc"

API_ID = 33511945
API_HASH = "d044392a17690c14ee5b4a23651a0700"

# আপনার জেনারেট করা String Session এখানে যুক্ত করা হলো
STRING_SESSION = "BQG2RvEAVVJuVtf1Rem5hsoaEIJoTmBtDZ0_l3exhFRpBNwr0erQWVTGT4izkeIy6EzPQlUg6bQwpJvOo-7PTEyiUgYsr7nJPjKUpE7s27umbfP0qAhy0cT42IbMOOt1FHx_4aVpB-lftHUXfs7yhU94Z63iNEzQFUhrUAZgKaieVj9kX643xv4HgHwOtHhGpg0PzHU3mcS_gh3WkSn1b7ahgDGJMHL3agj5uE4B0fZ04BNcXKNWoY_aex_UxZPwSg86andgQOyP7jGem_SNZy4s0w3VabJwl3SM-vSrKgRTfJnqd1nck0hi_TqoVal7ZcIiNVbrkbJyZ87QQsXXODjSXZ8QAAAAIL2oKZAA"

ADMIN_ID = 8788804249
BROADCAST_CHANNEL_ID = -1003785686277
WELCOME_MEDIA_CHANNEL_ID = -1003345168634  # আপনার টার্গেট প্রাইভেট চ্যানেল আইডি
PODCAST_SOURCE_CHANNEL_ID = -1003345168634
PODCAST_INVITE_LINK = "https://t.me/+J95hZDnKzcE0Njc0"

DATABASE = "media_bot.db"

DEFAULT_DELETE_AFTER = 30 * 60
WELCOME_DELETE_DELAY = 20 * 60  # Welcome message auto delete after 20 minutes
DELETE_CHECK_INTERVAL = 5
START_DELETE_DELAY = 2
ALBUM_COLLECT_DELAY = 2.0
MAX_RETRIES = 3

ADMIN_PANEL_IMAGE = (
    "https://carder.top/imagens/1791557140321-440701283.jpg"
)

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
    (
        3,
        "📲 ˢʰᵃʳᵉ ᴬⁿᴅ ᴬᴅᴅ ᴹ𝐞ᴍʙ𝐞𝐫ꜱ 🔰",
        "https://t.me/share/url?url=https%3A%2F%2Ft.me%2FXMedia90_Bot%3Fstart%3Dstart",
    ),
]

PODCAST_BUTTON = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔞ꜱʜᴀʀᴇ 𝐭𝐡𝐞 𝐯ɪᴅ𝐞𝖔ꜱ", url="https://t.me/share/url?url=https://t.me/XMedia90_Bot?start=start")]
])

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =========================================================
# DATABASE HELPERS / MIGRATION
# =========================================================

def db_connect():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def setup_database():
    with closing(db_connect()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_users (
                user_id INTEGER PRIMARY KEY
            )
        """)

        columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(broadcast_users)"
            ).fetchall()
        }
        if "status" not in columns:
            conn.execute(
                "ALTER TABLE broadcast_users "
                "ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        if "banned" not in columns:
            conn.execute(
                "ALTER TABLE broadcast_users "
                "ADD COLUMN banned INTEGER NOT NULL DEFAULT 0"
            )
        if "first_seen" not in columns:
            conn.execute(
                "ALTER TABLE broadcast_users "
                "ADD COLUMN first_seen REAL NOT NULL DEFAULT 0"
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_deletions (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                delete_at REAL NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS welcome_buttons (
                slot INTEGER PRIMARY KEY,
                label TEXT NOT NULL,
                url TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS welcome_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_type TEXT NOT NULL,
                file_id TEXT NOT NULL UNIQUE,
                source_message_id INTEGER,
                added_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_media_history (
                user_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                sent_at REAL NOT NULL,
                PRIMARY KEY (user_id, media_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS welcome_messages (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS podcast_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                added_at REAL NOT NULL,
                UNIQUE(chat_id, message_id)
            )
        """)

        conn.execute(
            "INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)",
            (ADMIN_ID,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
            ("welcome_text", DEFAULT_WELCOME),
        )
        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
            ("welcome_type", "text"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
            ("welcome_file_id", ""),
        )
        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
            ("delete_after", str(DEFAULT_DELETE_AFTER)),
        )

        for slot, label, url in DEFAULT_BUTTONS:
            conn.execute(
                "INSERT OR IGNORE INTO welcome_buttons (slot, label, url) "
                "VALUES (?, ?, ?)",
                (slot, label, url),
            )

        conn.commit()


def db_get_setting(key, default=""):
    with closing(db_connect()) as conn:
        row = conn.execute(
            "SELECT value FROM bot_settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row[0] if row else default


def db_set_setting(key, value):
    with closing(db_connect()) as conn:
        conn.execute(
            "INSERT INTO bot_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        conn.commit()


def is_admin(user_id):
    with closing(db_connect()) as conn:
        row = conn.execute(
            "SELECT 1 FROM bot_admins WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row is not None


def get_admin_ids():
    with closing(db_connect()) as conn:
        return [
            row[0] for row in conn.execute(
                "SELECT user_id FROM bot_admins ORDER BY user_id"
            ).fetchall()
        ]


def register_user(user_id):
    with closing(db_connect()) as conn:
        conn.execute(
            """
            INSERT INTO broadcast_users
                (user_id, status, banned, first_seen)
            VALUES (?, 'active', 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET status = 'active'
            """,
            (user_id, time.time()),
        )
        conn.commit()


def get_registered_users(include_banned=False):
    query = "SELECT user_id FROM broadcast_users WHERE status = 'active'"
    if not include_banned:
        query += " AND banned = 0"
    with closing(db_connect()) as conn:
        return conn.execute(query).fetchall()


def mark_user_blocked(user_id):
    with closing(db_connect()) as conn:
        conn.execute(
            "UPDATE broadcast_users SET status = 'blocked' WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()


def set_user_banned(user_id, banned=True):
    with closing(db_connect()) as conn:
        conn.execute(
            """
            INSERT INTO broadcast_users
                (user_id, status, banned, first_seen)
            VALUES (?, 'active', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET banned = excluded.banned
            """,
            (user_id, 1 if banned else 0, time.time()),
        )
        conn.commit()


def get_member_stats():
    with closing(db_connect()) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM broadcast_users"
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM broadcast_users "
            "WHERE status = 'active' AND banned = 0"
        ).fetchone()[0]
        blocked = conn.execute(
            "SELECT COUNT(*) FROM broadcast_users WHERE status = 'blocked'"
        ).fetchone()[0]
        banned = conn.execute(
            "SELECT COUNT(*) FROM broadcast_users WHERE banned = 1"
        ).fetchone()[0]
    return total, active, blocked, banned


def get_welcome_buttons():
    with closing(db_connect()) as conn:
        return conn.execute(
            "SELECT slot, label, url FROM welcome_buttons ORDER BY slot"
        ).fetchall()


def update_welcome_button(slot, label, url):
    with closing(db_connect()) as conn:
        conn.execute(
            "UPDATE welcome_buttons SET label = ?, url = ? WHERE slot = ?",
            (label, url, slot),
        )
        conn.commit()


def get_delete_after():
    try:
        return max(60, int(db_get_setting(
            "delete_after", str(DEFAULT_DELETE_AFTER)
        )))
    except (ValueError, TypeError):
        return DEFAULT_DELETE_AFTER


def schedule_message_deletion(chat_id, message_id):
    delete_at = time.time() + get_delete_after()
    with closing(db_connect()) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scheduled_deletions
                (chat_id, message_id, delete_at)
            VALUES (?, ?, ?)
            """,
            (chat_id, message_id, delete_at),
        )
        conn.commit()


def remove_scheduled_deletion(chat_id, message_id):
    with closing(db_connect()) as conn:
        conn.execute(
            "DELETE FROM scheduled_deletions "
            "WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        )
        conn.commit()


# =========================================================
# WELCOME MEDIA POOL
# =========================================================

def save_welcome_media(media_type, file_id, source_message_id=None):
    if media_type not in ("photo", "video") or not file_id:
        return False
    with closing(db_connect()) as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO welcome_media "
            "(media_type, file_id, source_message_id, added_at) VALUES (?, ?, ?, ?)",
            (media_type, file_id, source_message_id, time.time()),
        )
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
            "SELECT id, media_type, file_id FROM welcome_media ORDER BY id"
        ).fetchall()
        if not all_media:
            return None

        unseen = conn.execute(
            "SELECT id, media_type, file_id FROM welcome_media "
            "WHERE id NOT IN (SELECT media_id FROM user_media_history WHERE user_id = ?)",
            (user_id,),
        ).fetchall()

        if not unseen:
            conn.execute(
                "DELETE FROM user_media_history WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            unseen = all_media

        chosen = random.choice(unseen)
        return chosen[0], chosen[1], chosen[2]


def mark_welcome_media_seen(user_id, media_id):
    with closing(db_connect()) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_media_history (user_id, media_id, sent_at) "
            "VALUES (?, ?, ?)",
            (user_id, media_id, time.time()),
        )
        conn.commit()


def get_previous_welcome(user_id):
    with closing(db_connect()) as conn:
        row = conn.execute(
            "SELECT chat_id, message_id FROM welcome_messages WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row


def save_previous_welcome(user_id, chat_id, message_id):
    with closing(db_connect()) as conn:
        conn.execute(
            "INSERT INTO welcome_messages (user_id, chat_id, message_id) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET chat_id=excluded.chat_id, message_id=excluded.message_id",
            (user_id, chat_id, message_id),
        )
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
        conn.execute("DELETE FROM welcome_messages WHERE user_id = ?", (user_id,))
        conn.commit()


# =========================================================
# WELCOME MESSAGE / BUTTONS
# =========================================================

def make_welcome_keyboard():
    rows = []
    for _slot, label, url in get_welcome_buttons():
        rows.append([InlineKeyboardButton(label, url=url)])
    return InlineKeyboardMarkup(rows)


def format_welcome_text(raw_text, user):
    safe_name = escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    marker = "___WELCOME_USER_MENTION___"
    safe_text = escape(raw_text or "").replace("{mention}", marker)
    return safe_text.replace(marker, mention)


async def send_welcome(bot, chat_id, user):
    welcome_text = db_get_setting("welcome_text", DEFAULT_WELCOME)
    formatted = format_welcome_text(welcome_text, user)
    keyboard = make_welcome_keyboard()

    chosen = choose_welcome_media(user.id)
    sent = None
    try:
        if chosen:
            media_id, media_type, file_id = chosen
            if media_type == "photo":
                sent = await bot.send_photo(
                    chat_id=chat_id, photo=file_id, caption=formatted[:1024],
                    parse_mode="HTML", reply_markup=keyboard,
                )
            else:
                sent = await bot.send_video(
                    chat_id=chat_id, video=file_id, caption=formatted[:1024],
                    parse_mode="HTML", reply_markup=keyboard,
                )
        else:
            sent = await bot.send_message(
                chat_id=chat_id, text=formatted[:4096], parse_mode="HTML",
                reply_markup=keyboard, disable_web_page_preview=True,
            )
        if chosen:
            mark_welcome_media_seen(user.id, media_id)
    except TelegramError:
        logger.exception("Could not send the welcome message to %s", chat_id)
        sent = await bot.send_message(
            chat_id=chat_id, text=formatted[:4096], parse_mode="HTML",
            reply_markup=keyboard, disable_web_page_preview=True,
        )

    if sent:
        save_previous_welcome(user.id, chat_id, sent.message_id)
        
        delete_at = time.time() + WELCOME_DELETE_DELAY
        with closing(db_connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scheduled_deletions
                    (chat_id, message_id, delete_at)
                VALUES (?, ?, ?)
                """,
                (chat_id, sent.message_id, delete_at),
            )
            conn.commit()

    return sent


# =========================================================
# /START
# =========================================================

async def delete_start_later(context, chat_id, message_id):
    await asyncio.sleep(START_DELETE_DELAY)
    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )
    except TelegramError as error:
        logger.debug("Could not delete /start message: %s", error)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message
    if not user or not chat or not message:
        return

    if chat.type == "private":
        with closing(db_connect()) as conn:
            row = conn.execute(
                "SELECT banned FROM broadcast_users WHERE user_id = ?",
                (user.id,),
            ).fetchone()

        if row and row[0]:
            await message.reply_text(
                "⛔ Your access to this bot has been restricted by an administrator."
            )
            return

        register_user(user.id)

    if chat.type == "private":
        await delete_previous_welcome(context.bot, user.id)

    context.application.create_task(
        delete_start_later(context, chat.id, message.message_id)
    )
    await send_welcome(context.bot, chat.id, user)


# =========================================================
# DIRECT USER MAILING HELPERS (PODCAST MAILING)
# =========================================================

async def copy_to_user(application, user_id, source_chat_id, message_id, reply_markup=None):
    for attempt in range(MAX_RETRIES):
        try:
            sent = await application.bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )
            schedule_message_deletion(user_id, sent.message_id)
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
# CHANNEL ALBUM HANDLING & OLD MEDIA SCANNER
# =========================================================

def get_album_buffer(application):
    return application.bot_data.setdefault("channel_album_buffer", {})


async def flush_channel_album(application, key):
    try:
        await asyncio.sleep(ALBUM_COLLECT_DELAY)
        buffer = get_album_buffer(application)
        album = buffer.get(key)
        if not album:
            return

        message_ids = sorted(set(album["message_ids"]))
        buffer.pop(key, None)

        if message_ids:
            users = get_registered_users()
            for (user_id,) in users:
                for msg_id in message_ids:
                    try:
                        await copy_to_user(
                            application=application,
                            user_id=user_id,
                            source_chat_id=key[0],
                            message_id=msg_id,
                        )
                        await asyncio.sleep(0.03)
                    except Exception:
                        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Album processing failed.")


async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if message is None:
        return

    application = context.application

    if message.chat_id == WELCOME_MEDIA_CHANNEL_ID:
        media_type, file_id = get_channel_media(message)
        if media_type and file_id:
            save_welcome_media(media_type, file_id, message.message_id)
            logger.info("Saved Welcome media from channel %s", message.chat_id)

    if message.chat_id == PODCAST_SOURCE_CHANNEL_ID:
        if message.video or (message.document and message.document.mime_type and "video" in message.document.mime_type):
            with closing(db_connect()) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO podcast_videos (chat_id, message_id, added_at) VALUES (?, ?, ?)",
                    (message.chat_id, message.message_id, time.time())
                )
                conn.commit()
            logger.info("Saved new podcast video from channel %s", message.chat_id)
        return

    if message.chat_id != BROADCAST_CHANNEL_ID:
        return

    if message.media_group_id:
        key = (message.chat_id, str(message.media_group_id))
        buffer = get_album_buffer(application)
        album = buffer.setdefault(key, {"message_ids": [], "task": None})

        if message.message_id not in album["message_ids"]:
            album["message_ids"].append(message.message_id)

        old_task = album.get("task")
        if old_task is not None and not old_task.done():
            old_task.cancel()

        album["task"] = application.create_task(
            flush_channel_album(application, key),
            name=f"flush_album_{message.media_group_id}",
        )
        return

    users = get_registered_users()
    for (user_id,) in users:
        try:
            await copy_to_user(
                application=application,
                user_id=user_id,
                source_chat_id=message.chat_id,
                message_id=message.message_id,
            )
            await asyncio.sleep(0.03)
        except Exception:
            pass


# Pyrogram function using USER STRING SESSION to scan private channel media
async def scan_old_media_and_podcasts_pyrogram():
    try:
        async with PyrogramClient("user_scanner_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION) as pyro_app:
            logger.info("Starting scanning old media and podcasts using User Session...")
            
            # ক্যাশ পপ্যুলেট করার জন্য ডায়ালগ ফেচ করা হচ্ছে
            try:
                async for dialog in pyro_app.get_dialogs():
                    pass
            except Exception as e:
                logger.warning(f"Dialog fetch warning: {e}")

            target_chat = WELCOME_MEDIA_CHANNEL_ID
            
            # সঠিকভাবে চ্যাট রেজলভ করা
            try:
                chat_obj = await pyro_app.get_chat(WELCOME_MEDIA_CHANNEL_ID)
                target_chat = chat_obj.id
                logger.info(f"Resolved target chat ID successfully: {target_chat}")
            except Exception as e:
                logger.warning(f"Could not get chat directly via ID, trying invite link: {e}")
                try:
                    chat_obj = await pyro_app.join_chat(PODCAST_INVITE_LINK)
                    target_chat = chat_obj.id
                    logger.info(f"Joined chat via invite link successfully: {target_chat}")
                except Exception as inner_e:
                    logger.error(f"Failed to resolve or join chat: {inner_e}")
                    return

            welcome_count = 0
            podcast_count = 0

            async for message in pyro_app.get_chat_history(target_chat):
                # Welcome media scanning (photos and videos)
                m_type, f_id = None, None
                if message.photo:
                    m_type, f_id = "photo", message.photo.file_id
                elif message.video:
                    m_type, f_id = "video", message.video.file_id
                
                if m_type and f_id:
                    if save_welcome_media(m_type, f_id, message.id):
                        welcome_count += 1

                # Podcast video scanning
                if message.video or (message.document and message.document.mime_type and "video" in message.document.mime_type):
                    with closing(db_connect()) as conn:
                        cur = conn.execute(
                            "INSERT OR IGNORE INTO podcast_videos (chat_id, message_id, added_at) VALUES (?, ?, ?)",
                            (WELCOME_MEDIA_CHANNEL_ID, message.id, time.time())
                        )
                        conn.commit()
                        if cur.rowcount > 0:
                            podcast_count += 1

            logger.info(f"Pyrogram User Session scan completed! Added {welcome_count} welcome media & {podcast_count} podcast videos.")
    except Exception as e:
        logger.error(f"Pyrogram User Session scanning error: {e}", exc_info=True)


async def importpodcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_admin(user.id):
        if message:
            await message.reply_text("⛔ Admin access only.")
        return

    status_msg = await message.reply_text("⏳ Scanning and analyzing old media and videos from the target channel... Please wait.")
    
    try:
        await scan_old_media_and_podcasts_pyrogram()
        with closing(db_connect()) as conn:
            total_welcome = conn.execute("SELECT COUNT(*) FROM welcome_media").fetchone()[0]
            total_podcast = conn.execute("SELECT COUNT(*) FROM podcast_videos").fetchone()[0]
            
        await status_msg.edit_text(
            f"✅ Scan and analysis completed successfully!\n\n"
            f"🖼️ Total Welcome Media (Photos/Videos): <b>{total_welcome}</b>\n"
            f"🎬 Total Podcast Videos in database: <b>{total_podcast}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception("Import media/podcast error.")
        await status_msg.edit_text(f"❌ An error occurred during scanning: {e}")


async def podcast_poster_worker(application: Application):
    await asyncio.sleep(20)
    while True:
        try:
            with closing(db_connect()) as conn:
                videos = conn.execute("SELECT chat_id, message_id FROM podcast_videos").fetchall()
            
            users = get_registered_users()
            
            if videos and users:
                count = min(10, len(videos))
                selected = random.sample(videos, count)
                logger.info(f"Mailing {count} random podcast videos to {len(users)} users...")
                
                for chat_id, msg_id in selected:
                    for (user_id,) in users:
                        try:
                            await copy_to_user(
                                application=application,
                                user_id=user_id,
                                source_chat_id=chat_id,
                                message_id=msg_id,
                                reply_markup=PODCAST_BUTTON
                            )
                            await asyncio.sleep(0.03)
                        except Exception as e:
                            logger.warning(f"Failed to send podcast video ({msg_id}) to user {user_id}: {e}")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Podcast poster worker error.")
        
        await asyncio.sleep(30 * 60)


# =========================================================
# ADMIN PANEL UI
# =========================================================

def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Admin", callback_data="adm:add_admin")],
        [InlineKeyboardButton("👥 Total Members", callback_data="adm:members")],
        [InlineKeyboardButton("🔘 Welcome Message Buttons", callback_data="adm:welcome_buttons")],
        [InlineKeyboardButton("📊 Media Pool Stats", callback_data="adm:mediastats")],
        [InlineKeyboardButton("🚫 Ban Users", callback_data="adm:ban_menu")],
        [InlineKeyboardButton("⏱ Broadcast Deleting Time", callback_data="adm:delete_time")],
        [InlineKeyboardButton("🛡️ Admin List", callback_data="adm:admin_list")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="adm:home")]
    ])


async def edit_admin_page(query, text, keyboard=None):
    keyboard = keyboard or back_keyboard()
    try:
        if query.message and query.message.photo:
            await query.edit_message_caption(
                caption=text[:1024],
                reply_markup=keyboard,
            )
        else:
            await query.edit_message_text(
                text=text[:4096],
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
    except BadRequest as error:
        if "message is not modified" not in str(error).lower():
            logger.debug("Could not edit admin panel message: %s", error)


async def show_admin_panel(update_or_query, context):
    keyboard = admin_main_keyboard()
    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        query = update_or_query.callback_query
        await query.answer()
        await edit_admin_page(query, "🛠️ <b>BOT ADMIN PANEL</b>\n\nChoose a section below:", keyboard)
        return

    message = update_or_query.effective_message
    try:
        await context.bot.send_photo(
            chat_id=message.chat_id,
            photo=ADMIN_PANEL_IMAGE,
            caption="🛠️ <b>BOT ADMIN PANEL</b>\n\nChoose a section below:",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except TelegramError:
        await message.reply_text(
            "🛠️ BOT ADMIN PANEL\n\nChoose a section below:",
            reply_markup=keyboard,
        )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.effective_message:
            await update.effective_message.reply_text("⛔ Admin access only.")
        return
    await show_admin_panel(update, context)


# =========================================================
# ADMIN CALLBACKS & INPUTS
# =========================================================

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not query:
        return
    await query.answer()

    if not user or not is_admin(user.id):
        await query.answer("⛔ Admin access only.", show_alert=True)
        return

    data = query.data or ""

    if data == "adm:home":
        await edit_admin_page(
            query,
            "🛠️ <b>BOT ADMIN PANEL</b>\n\nChoose a section below:",
            admin_main_keyboard(),
        )
        return

    if data == "adm:add_admin":
        context.user_data["admin_action"] = "add_admin"
        await edit_admin_page(
            query,
            "➕ <b>ADD ADMIN</b>\n\nSend the numeric Telegram user ID you want to add.\n\nSend /cancel to cancel.",
        )
        return

    if data == "adm:members":
        total, active, blocked, banned = get_member_stats()
        text = (
            "👥 <b>TOTAL MEMBERS</b>\n\n"
            f"📊 Registered users: <b>{total}</b>\n"
            f"🟢 Active / reachable: <b>{active}</b>\n"
            f"🚫 Known blocked users: <b>{blocked}</b>\n"
            f"⛔ Banned by admins: <b>{banned}</b>"
        )
        await edit_admin_page(query, text)
        return

    if data == "adm:mediastats":
        with closing(db_connect()) as conn:
            total_wm = conn.execute("SELECT COUNT(*) FROM welcome_media").fetchone()[0]
        await edit_admin_page(query, f"📊 <b>WELCOME MEDIA POOL STATS</b>\n\nTotal cached photos/videos for welcome message: <b>{total_wm}</b>")
        return

    if data == "adm:welcome_buttons":
        rows = []
        for slot, label, _url in get_welcome_buttons():
            rows.append([InlineKeyboardButton(
                f"✏️ Edit Button {slot}: {label[:30]}",
                callback_data=f"adm:edit_button:{slot}",
            )])
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="adm:home")])
        await edit_admin_page(
            query,
            "🔘 <b>WELCOME MESSAGE BUTTONS</b>\n\nChoose which button you want to edit:",
            InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("adm:edit_button:"):
        try:
            slot = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        if slot not in (1, 2, 3):
            return
        context.user_data["admin_action"] = "edit_button_label"
        context.user_data["button_slot"] = slot
        await edit_admin_page(
            query,
            f"✏️ <b>EDIT WELCOME BUTTON {slot}</b>\n\nSend the new button name first.\nThen the bot will ask you for the URL.\n\nSend /cancel to cancel.",
        )
        return

    if data == "adm:ban_menu":
        await edit_admin_page(
            query,
            "🚫 <b>USER ACCESS CONTROL</b>\n\nChoose an action:",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 Ban User", callback_data="adm:ban_user")],
                [InlineKeyboardButton("✅ Unban User", callback_data="adm:unban_user")],
                [InlineKeyboardButton("⬅️ Back", callback_data="adm:home")],
            ]),
        )
        return

    if data in ("adm:ban_user", "adm:unban_user"):
        context.user_data["admin_action"] = (
            "ban_user" if data == "adm:ban_user" else "unban_user"
        )
        action = "ban" if data == "adm:ban_user" else "unban"
        await edit_admin_page(
            query,
            f"Send the numeric Telegram user ID you want to <b>{action}</b>.\n\nSend /cancel to cancel.",
        )
        return

    if data == "adm:delete_time":
        current = get_delete_after()
        current_label = f"{current // 60}m"
        await edit_admin_page(
            query,
            f"⏱ <b>BROADCAST DELETING TIME</b>\n\nCurrent setting: <b>{current_label}</b>",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("15m", callback_data="adm:time:900"),
                    InlineKeyboardButton("30m", callback_data="adm:time:1800"),
                ],
                [InlineKeyboardButton("⬅️ Back", callback_data="adm:home")],
            ]),
        )
        return

    if data.startswith("adm:time:"):
        try:
            seconds = int(data.rsplit(":", 1)[1])
        except ValueError:
            return
        db_set_setting("delete_after", seconds)
        await edit_admin_page(
            query,
            f"✅ Broadcast deleting time set to <b>{seconds // 60} minutes</b>.",
        )
        return

    if data == "adm:admin_list":
        ids = get_admin_ids()
        listing = "\n".join(f"• <code>{admin_id}</code>" for admin_id in ids)
        await edit_admin_page(
            query,
            "🛡️ <b>ADMIN LIST</b>\n\n" + (listing or "No admins found."),
        )
        return


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and is_admin(update.effective_user.id):
        context.user_data.pop("admin_action", None)
        context.user_data.pop("button_slot", None)
        await update.effective_message.reply_text("❎ Cancelled.")
    else:
        await update.effective_message.reply_text("Nothing to cancel.")


def valid_button_url(value):
    value = value.strip()
    parsed = urlparse(value)
    return parsed.scheme in ("https", "http", "tg") and bool(parsed.netloc or parsed.scheme == "tg")


async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_admin(user.id):
        return

    action = context.user_data.get("admin_action")
    if not action:
        return

    if action == "add_admin":
        if not message.text or not message.text.strip().isdigit():
            await message.reply_text("❌ Please send a numeric Telegram user ID.")
            return
        new_admin_id = int(message.text.strip())
        with closing(db_connect()) as conn:
            conn.execute("INSERT OR IGNORE INTO bot_admins (user_id) VALUES (?)", (new_admin_id,))
            conn.commit()
        context.user_data.pop("admin_action", None)
        await message.reply_text(f"✅ Admin added: {new_admin_id}")
        return

    if action == "edit_button_label":
        if not message.text or not message.text.strip():
            await message.reply_text("❌ Please send a button name.")
            return
        context.user_data["pending_button_label"] = message.text.strip()[:64]
        context.user_data["admin_action"] = "edit_button_url"
        await message.reply_text("🔗 Now send the URL for this button.")
        return

    if action == "edit_button_url":
        if not message.text or not valid_button_url(message.text):
            await message.reply_text("❌ Invalid URL.")
            return
        slot = context.user_data.get("button_slot")
        label = context.user_data.get("pending_button_label")
        update_welcome_button(slot, label, message.text.strip())
        context.user_data.pop("admin_action", None)
        context.user_data.pop("button_slot", None)
        context.user_data.pop("pending_button_label", None)
        await message.reply_text(f"✅ Welcome button {slot} updated successfully.")
        return

    if action in ("ban_user", "unban_user"):
        if not message.text or not message.text.strip().isdigit():
            await message.reply_text("❌ Please send a numeric user ID.")
            return
        target_id = int(message.text.strip())
        if action == "ban_user":
            set_user_banned(target_id, True)
            result = f"🚫 User <code>{target_id}</code> banned."
        else:
            set_user_banned(target_id, False)
            result = f"✅ User <code>{target_id}</code> unbanned."
        context.user_data.pop("admin_action", None)
        await message.reply_text(result, parse_mode="HTML")
        return


async def mediastats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_admin(user.id):
        return
    with closing(db_connect()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM welcome_media").fetchone()[0]
    await message.reply_text(f"📊 Total welcome media cached: {total}")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not is_admin(user.id):
        return

    source = message.reply_to_message
    if source is None:
        await message.reply_text("📢 Reply to a message and send /broadcast.")
        return

    status = await message.reply_text("⏳ Manual broadcast started...")
    users = get_registered_users()
    successful = 0
    failed = 0

    for (user_id,) in users:
        try:
            await copy_to_user(
                application=context.application,
                user_id=user_id,
                source_chat_id=source.chat_id,
                message_id=source.message_id,
            )
            successful += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.03)

    try:
        await status.edit_text(f"✅ Broadcast completed. Successful: {successful}, Failed: {failed}")
    except TelegramError:
        pass


# =========================================================
# AUTO-DELETION WORKER
# =========================================================

async def automatic_deletion(application: Application):
    now = time.time()
    with closing(db_connect()) as conn:
        due_messages = conn.execute(
            "SELECT chat_id, message_id FROM scheduled_deletions WHERE delete_at <= ?",
            (now,),
        ).fetchall()

    for chat_id, message_id in due_messages:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=message_id)
            remove_scheduled_deletion(chat_id, message_id)
        except Exception:
            remove_scheduled_deletion(chat_id, message_id)


async def deletion_worker(application: Application):
    while True:
        try:
            await automatic_deletion(application)
        except Exception:
            pass
        await asyncio.sleep(DELETE_CHECK_INTERVAL)


async def post_init(application: Application):
    setup_database()
    application.create_task(deletion_worker(application), name="deletion_worker")
    application.create_task(podcast_poster_worker(application), name="podcast_poster_worker")
    
    # ব্যাকগ্রাউন্ডে টার্গেট চ্যানেল থেকে পুরোনো ছবি/ভিডিও স্ক্যান করার টাস্ক শুরু হবে
    application.create_task(scan_old_media_and_podcasts_pyrogram(), name="scan_old_media_and_podcasts_pyrogram")
    logger.info("Database & workers initialized successfully.")


# =========================================================
# MAIN
# =========================================================

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("mediastats", mediastats_command))
    app.add_handler(CommandHandler("importpodcast", importpodcast_command))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^adm:"))

    app.add_handler(
        MessageHandler(
            filters.UpdateType.CHANNEL_POST,
            channel_post_handler,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & (filters.TEXT | filters.PHOTO | filters.VIDEO)
            & ~filters.COMMAND,
            admin_input_handler,
        )
    )

    logger.info("Telegram bot is starting...")
    app.run_polling(allowed_updates=["message", "channel_post", "callback_query"])


if __name__ == "__main__":
    main()
