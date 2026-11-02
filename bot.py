import asyncio
import html
import logging
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import yt_dlp
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)

import admin
import db
from config import ADMIN_IDS, BOT_TOKEN, COOKIES_FILE, PROXY, TELEGRAM_API_URL

# Telegram'ning umumiy Bot API serveri 50 MB gacha fayl qabul qiladi,
# o'zimizning lokal Bot API serverimiz (TELEGRAM_API_URL) esa 2000 MB gacha.
MAX_FILE_SIZE = (2000 if TELEGRAM_API_URL else 50) * 1024 * 1024
MAX_FILE_MB = MAX_FILE_SIZE // (1024 * 1024)
UPLOAD_TIMEOUT = 3600 if TELEGRAM_API_URL else 600  # katta faylni yuborish uchun, soniya
MAX_PARALLEL = 3  # bir vaqtda nechta yuklash
YOUTUBE_QUALITIES = (360, 480, 720)  # 1080p keyinchalik pullik xizmat bo'ladi
MAX_PENDING = 1000  # tugmasi bosilmagan havolalar xotirada cheksiz to'planmasligi uchun


def find_ffmpeg() -> str | None:
    """Tizimdagi ffmpeg, bo'lmasa imageio-ffmpeg paketidagi tayyor binar."""
    if path := shutil.which("ffmpeg"):
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


FFMPEG_PATH = find_ffmpeg()
HAS_FFMPEG = FFMPEG_PATH is not None

URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/|music\.youtube\.com/watch\?v=|instagram\.com/(?:p|reel|reels|tv)/)"
    r"[^\s]+",
    re.IGNORECASE,
)
YOUTUBE_RE = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be|music\.youtube\.com)/", re.IGNORECASE)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("savebot")

dp = Dispatcher()
router = Router(name="user")
semaphore = asyncio.Semaphore(MAX_PARALLEL)
# callback_data 64 baytdan oshmasligi kerak, shuning uchun havolani qisqa kalit bilan saqlaymiz
pending_links: dict[str, str] = {}


class TooLargeError(Exception):
    pass


class TrackUsersMiddleware(BaseMiddleware):
    """Har bir xabar/tugma bosilganda foydalanuvchini bazaga yozadi, yangisi haqida adminlarga xabar beradi."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user and not user.is_bot:
            is_new = db.upsert_user(user.id, user.username, user.full_name, user.language_code)
            if is_new and ADMIN_IDS:
                await notify_admins(data["bot"], user)
        return await handler(event, data)


async def notify_admins(bot: Bot, user) -> None:
    uname = f" (@{user.username})" if user.username else ""
    text = (
        f"🆕 Yangi foydalanuvchi: <a href=\"tg://user?id={user.id}\">{html.escape(user.full_name)}</a>"
        f"{html.escape(uname)}\n🆔 <code>{user.id}</code> · 👥 Jami: {db.count_users()}"
    )
    for admin_id in ADMIN_IDS:
        if admin_id == user.id:
            continue
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:  # admin botni bloklagan yoki /start bosmagan bo'lishi mumkin
            log.warning("Adminga (%s) xabar yuborilmadi: %s", admin_id, e)


def quality_keyboard(key: str) -> InlineKeyboardMarkup:
    """YouTube uchun: sifatni tanlash yoki faqat audio."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🎬 {q}p", callback_data=f"v{q}:{key}") for q in YOUTUBE_QUALITIES],
            [InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data=f"a:{key}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"x:{key}")],
        ]
    )


def video_format(height: int | None) -> str:
    """Telegram'da yaxshi ochilishi uchun avval H.264 (avc1) + m4a, keyin istalgan mos format."""
    h = f"[height<={height}]" if height else ""
    if HAS_FFMPEG:
        return (
            f"bv*{h}[vcodec^=avc1]+ba[ext=m4a]/bv*{h}[ext=mp4]+ba[ext=m4a]/"
            f"bv*{h}+ba/b{h}/wv*+ba/w"
        )
    # ffmpeg bo'lmasa faqat tayyor (video+audio birga) formatlar
    return f"b{h}[ext=mp4]/b{h}/w"


def build_opts(mode: str, out_dir: str, height: int | None = None) -> dict:
    opts = {
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE,
        "noprogress": True,
        # YouTube imzolarini yechish uchun JS runtime (deno yoki node) bo'lsa ishlatiladi
        "js_runtimes": {"deno": {}, "node": {}},
    }
    if FFMPEG_PATH:
        opts["ffmpeg_location"] = FFMPEG_PATH
    if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE

    if mode == "video":
        opts["format"] = video_format(height)
        if HAS_FFMPEG:
            opts["merge_output_format"] = "mp4"
    else:
        if HAS_FFMPEG:
            opts["format"] = "ba/b"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        else:
            opts["format"] = "ba[ext=m4a]/ba/b"
    return opts


def download(url: str, mode: str, out_dir: str, height: int | None = None) -> tuple[Path, dict]:
    with yt_dlp.YoutubeDL(build_opts(mode, out_dir, height)) as ydl:
        info = ydl.extract_info(url, download=True)
    if info.get("entries"):  # Instagram karusel va h.k.
        info = next((e for e in info["entries"] if e), info)

    files = [p for p in Path(out_dir).iterdir() if p.is_file() and not p.name.endswith(".part")]
    if not files:
        # max_filesize oshganda yt-dlp faylni yuklamaydi
        raise TooLargeError
    file = max(files, key=lambda p: p.stat().st_size)
    if file.stat().st_size > MAX_FILE_SIZE:
        raise TooLargeError
    return file, info


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Salom! Menga <b>YouTube</b> yoki <b>Instagram</b> havolasini yuboring.\n\n"
        f"▶️ YouTube: sifatni tanlaysiz ({', '.join(f'{q}p' for q in YOUTUBE_QUALITIES)}) yoki faqat audio.\n"
        "📸 Instagram: video darhol yuklanadi."
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("light"))
async def cmd_light(message: Message) -> None:
    await message.answer(
        "💡 <b>L I G H T</b> 💡\n\n"
        "🇺🇿 Bu botni <b>Light</b> tayyorlagan.\n"
        "🇬🇧 This bot was made by <b>Light</b>.\n"
        "🇷🇺 Этот бот создал <b>Light</b>.\n\n"
        "<tg-spoiler>⚡ © Light — ✦ L·∞·T ✦</tg-spoiler>"
    )


@router.message(F.text.regexp(URL_RE))
async def on_link(message: Message, bot: Bot) -> None:
    url = URL_RE.search(message.text).group(0)
    if YOUTUBE_RE.match(url):
        key = uuid.uuid4().hex[:12]
        while len(pending_links) >= MAX_PENDING:
            pending_links.pop(next(iter(pending_links)))  # eng eskisini o'chiramiz
        pending_links[key] = url
        await message.reply("🎞 Qaysi sifatda yuklab beray?", reply_markup=quality_keyboard(key))
        return
    # Instagram va boshqalar: tanlovsiz, darhol eng yaxshi video
    status = await message.reply("⏳ Video yuklanmoqda, biroz kuting...")
    await process_download(bot, status, message.from_user.id, url, "video")


@router.message(F.text)
async def on_other_text(message: Message) -> None:
    await message.answer("⚠️ Iltimos, YouTube yoki Instagram havolasini yuboring.")


@router.callback_query(F.data.regexp(r"^(v\d{3,4}|a|x):[0-9a-f]{12}$"))
async def on_choice(call: CallbackQuery, bot: Bot) -> None:
    action, key = call.data.split(":", 1)
    url = pending_links.pop(key, None)

    if action == "x":
        await call.message.edit_text("❌ Bekor qilindi.")
        await call.answer()
        return
    if url is None:
        await call.answer("Havola eskirgan, qaytadan yuboring.", show_alert=True)
        return

    height = None
    if action.startswith("v"):
        height = int(action[1:])
        if height not in YOUTUBE_QUALITIES:  # qo'lda yasalgan callback_data dan himoya
            await call.answer("Bu sifat mavjud emas.", show_alert=True)
            return
    mode = "video" if height else "audio"
    await call.answer()
    label = f"Video ({height}p)" if height else "Audio"
    status = await call.message.edit_text(f"⏳ {label} yuklanmoqda, biroz kuting...")
    await process_download(bot, status, call.from_user.id, url, mode, height)


async def process_download(
    bot: Bot, status: Message, user_id: int, url: str, mode: str, height: int | None = None
) -> None:
    """Yuklab oladi, Telegramga yuboradi va status xabarini natijaga qarab yangilaydi."""
    chat_id = status.chat.id
    tmp_dir = tempfile.mkdtemp(prefix="savebot_")
    try:
        async with semaphore:
            file, info = await asyncio.to_thread(download, url, mode, tmp_dir, height)

        await status.edit_text("📤 Telegramga yuborilmoqda...")
        title = info.get("title") or "media"
        caption = f"<b>{html.escape(title[:900])}</b>\n\n🤖 @{(await bot.me()).username}"
        media = FSInputFile(file)
        duration = int(info["duration"]) if info.get("duration") else None

        if mode == "video":
            await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)
            await bot.send_video(
                chat_id,
                media,
                caption=caption,
                duration=duration,
                width=info.get("width"),
                height=info.get("height"),
                supports_streaming=True,
                request_timeout=UPLOAD_TIMEOUT,
            )
        else:
            await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VOICE)
            await bot.send_audio(
                chat_id,
                media,
                caption=caption,
                title=title[:64],
                performer=info.get("artist") or info.get("uploader"),
                duration=duration,
                request_timeout=UPLOAD_TIMEOUT,
            )
        await safe_edit(status, delete=True)
        db.log_download(user_id, url, mode, ok=True, title=title)
    except TooLargeError:
        db.log_download(user_id, url, mode, ok=False)
        hint = " Pastroq sifatni tanlab ko'ring." if height and height > YOUTUBE_QUALITIES[0] else ""
        await safe_edit(status, f"⚠️ Fayl {MAX_FILE_MB} MB dan katta, Telegram orqali yuborib bo'lmaydi.{hint}")
    except yt_dlp.utils.DownloadError as e:
        log.warning("Download error for %s: %s", url, e)
        db.log_download(user_id, url, mode, ok=False)
        msg = str(e).lower()
        if "login" in msg or "private" in msg or "cookies" in msg or "sign in" in msg:
            text = "🔒 Bu kontent yopiq yoki kirish talab qiladi."
        else:
            text = "❌ Yuklab bo'lmadi. Havola to'g'riligini tekshiring."
        await safe_edit(status, text)
    except Exception:
        log.exception("Unexpected error for %s", url)
        db.log_download(user_id, url, mode, ok=False)
        await safe_edit(status, "❌ Kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def safe_edit(status: Message, text: str = "", delete: bool = False) -> None:
    """Status xabarini o'zgartiradi/o'chiradi; foydalanuvchi uni o'chirib yuborgan bo'lsa ham yiqilmaydi."""
    try:
        if delete:
            await status.delete()
        else:
            await status.edit_text(text)
    except TelegramBadRequest as e:
        log.debug("Status xabarini yangilab bo'lmadi: %s", e)


async def set_commands(bot: Bot) -> None:
    user_cmds = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="id", description="Telegram ID ni bilish"),
    ]
    await bot.set_my_commands(user_cmds, scope=BotCommandScopeDefault())
    # Admin buyruqlari faqat adminlarning menyusida ko'rinadi
    admin_cmds = user_cmds + [
        BotCommand(command="admin", description="Admin panel"),
        BotCommand(command="users", description="Foydalanuvchilar ro'yxati"),
        BotCommand(command="user", description="Foydalanuvchi ma'lumotlari: /user ID"),
        BotCommand(command="stats", description="Statistika"),
        BotCommand(command="export", description="Ro'yxatni CSV faylda olish"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:  # admin hali botga /start bosmagan bo'lsa
            log.warning("Admin (%s) uchun menyu o'rnatilmadi: %s", admin_id, e)


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env fayliga BOT_TOKEN=... yozing.")
    if not HAS_FFMPEG:
        log.warning("ffmpeg topilmadi: audio m4a formatda, video esa past sifatda bo'lishi mumkin.")
    session_kwargs = {"proxy": PROXY} if PROXY else {}
    if TELEGRAM_API_URL:
        # Lokal Bot API server: 2000 MB gacha fayl yuborish mumkin
        session_kwargs["api"] = TelegramAPIServer.from_base(TELEGRAM_API_URL, is_local=True)
    session = AiohttpSession(**session_kwargs)
    bot = Bot(BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Ishga tushishda internet uzilib qolsa, yiqilmasdan qayta urinamiz
    delay = 3
    while True:
        try:
            me = await bot.get_me()
            break
        except TelegramNetworkError as e:
            log.warning("Telegramga ulanib bo'lmadi (%s). %s soniyadan keyin qayta urinaman...", e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    log.info("Bot ishga tushdi: @%s (fayl chegarasi: %s MB)", me.username, MAX_FILE_MB)
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS bo'sh: admin buyruqlari ishlamaydi. .env ga ADMIN_IDS=... yozing (ID ni /id orqali bilasiz).")

    db.init()
    dp.message.outer_middleware(TrackUsersMiddleware())
    dp.callback_query.outer_middleware(TrackUsersMiddleware())
    # admin router birinchi: aks holda "/users" kabi buyruqlarni oddiy matn handleri ushlab qoladi
    dp.include_routers(admin.router, router)
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
