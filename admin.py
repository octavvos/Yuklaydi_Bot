"""Faqat adminlar uchun buyruqlar: foydalanuvchilar ro'yxati, ma'lumotlari, statistika."""

import csv
import html
import io
import math
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import db
from config import ADMIN_IDS

PAGE_SIZE = 10

router = Router(name="admin")
# Routerdagi barcha handlerlar faqat adminlar uchun ishlaydi
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


def user_link(row) -> str:
    name = html.escape(row["full_name"] or "Nomsiz")
    return f'<a href="tg://user?id={row["id"]}">{name}</a>'


def panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm:users:0")],
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
                InlineKeyboardButton(text="📄 CSV eksport", callback_data="adm:export"),
            ],
        ]
    )


def users_page(page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    total = db.count_users()
    if total == 0:
        return "Hali hech kim botdan foydalanmagan.", None

    pages = math.ceil(total / PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    rows = db.list_users(page * PAGE_SIZE, PAGE_SIZE)

    lines = [f"👥 <b>Foydalanuvchilar: {total} ta</b> (sahifa {page + 1}/{pages})\n"]
    for i, r in enumerate(rows, start=page * PAGE_SIZE + 1):
        uname = f" @{html.escape(r['username'])}" if r["username"] else ""
        lines.append(
            f"{i}. {user_link(r)}{uname}\n"
            f"    🆔 <code>{r['id']}</code> · 📥 {r['dl_count']} · 🕒 {r['last_seen'][:16]}\n"
            f"    👉 /u_{r['id']}"
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"adm:users:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"adm:users:{page + 1}"))
    kb = InlineKeyboardMarkup(inline_keyboard=[nav]) if nav else None
    return "\n".join(lines), kb


def user_card(user_id: int) -> str | None:
    u = db.get_user(user_id)
    if u is None:
        return None
    s = db.user_download_stats(user_id)
    lines = [
        "👤 <b>Foydalanuvchi ma'lumotlari</b>\n",
        f"Ism: {user_link(u)}",
        f"Username: {'@' + html.escape(u['username']) if u['username'] else '—'}",
        f"ID: <code>{u['id']}</code>",
        f"Til: {u['language'] or '—'}",
        f"Birinchi kirgan: {u['first_seen']}",
        f"Oxirgi faollik: {u['last_seen']}",
        "",
        f"📥 Yuklashlar: 🎬 {s['video']} video · 🎵 {s['audio']} audio · ❌ {s['failed']} xato",
    ]
    history = db.user_downloads(user_id)
    if history:
        lines.append("\n<b>Oxirgi yuklashlar:</b>")
        for d in history:
            icon = ("🎬" if d["mode"] == "video" else "🎵") if d["ok"] else "❌"
            title = html.escape((d["title"] or d["url"])[:50])
            lines.append(f'{icon} {d["created_at"][5:16]} — <a href="{html.escape(d["url"])}">{title}</a>')
    return "\n".join(lines)


def stats_text() -> str:
    s = db.stats()
    return (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🆕 Bugun qo'shilgan: <b>{s['new_today']}</b>\n"
        f"🟢 Bugun faol: <b>{s['active_today']}</b>\n"
        f"📅 7 kunda faol: <b>{s['active_week']}</b>\n\n"
        f"📥 Jami yuklashlar: <b>{s['downloads']}</b> (bugun {s['downloads_today']})\n"
        f"🎬 Video: <b>{s['video']}</b> · 🎵 Audio: <b>{s['audio']}</b>\n"
        f"❌ Xatolar: <b>{s['failed']}</b>"
    )


def export_file() -> BufferedInputFile:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "username", "full_name", "language", "first_seen", "last_seen", "downloads"])
    for r in db.all_users():
        w.writerow([r["id"], r["username"] or "", r["full_name"], r["language"] or "",
                    r["first_seen"], r["last_seen"], r["dl_count"]])
    # utf-8-sig — Excel o'zbek/kirill harflarini to'g'ri ochishi uchun
    data = buf.getvalue().encode("utf-8-sig")
    return BufferedInputFile(data, filename=f"users_{datetime.now():%Y%m%d_%H%M}.csv")


# ---------- Buyruqlar ----------

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(
        "🛠 <b>Admin panel</b>\n\n"
        "/users — foydalanuvchilar ro'yxati\n"
        "/user <code>ID</code> yoki <code>@username</code> — foydalanuvchi ma'lumotlari\n"
        "/stats — statistika\n"
        "/export — ro'yxatni CSV faylda olish",
        reply_markup=panel_keyboard(),
    )


@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    text, kb = users_page(0)
    await message.answer(text, reply_markup=kb, disable_web_page_preview=True)


@router.message(F.text.regexp(r"^/u_(\d+)(@\w+)?$"))
async def cmd_u_shortcut(message: Message) -> None:
    user_id = int(message.text.split("_", 1)[1].split("@")[0])
    await message.answer(user_card(user_id) or "Foydalanuvchi topilmadi.", disable_web_page_preview=True)


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject) -> None:
    query = (command.args or "").strip()
    if not query:
        await message.answer("Foydalanish: /user <code>ID</code> yoki /user <code>@username</code>")
        return
    if query.isdigit():
        await message.answer(user_card(int(query)) or "Foydalanuvchi topilmadi.", disable_web_page_preview=True)
        return

    found = db.find_users(query)
    if not found:
        await message.answer("Hech kim topilmadi.")
    elif len(found) == 1:
        await message.answer(user_card(found[0]["id"]), disable_web_page_preview=True)
    else:
        lines = [f"🔎 {len(found)} ta topildi:\n"]
        lines += [f"• {user_link(r)} — /u_{r['id']}" for r in found]
        await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    await message.answer(stats_text())


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    await message.answer_document(export_file(), caption=f"👥 {db.count_users()} ta foydalanuvchi")


# ---------- Tugmalar ----------

@router.callback_query(F.data.startswith("adm:users:"))
async def cb_users(call: CallbackQuery) -> None:
    text, kb = users_page(int(call.data.rsplit(":", 1)[1]))
    await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery) -> None:
    await call.message.answer(stats_text())
    await call.answer()


@router.callback_query(F.data == "adm:export")
async def cb_export(call: CallbackQuery) -> None:
    await call.message.answer_document(export_file(), caption=f"👥 {db.count_users()} ta foydalanuvchi")
    await call.answer()
