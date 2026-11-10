import asyncio
import os
import re
import shutil
import time

from pyrogram import Client, filters
from pyrogram.types import Message

from helpers import is_admin, BATCH, CHANNELS

THUMB_DIR = os.path.abspath("thumbs")      # per-admin thumbnail: thumbs/<user_id>.jpg
DOWNLOAD_DIR = os.path.abspath("downloads")


def thumb_path(uid):
    return os.path.join(THUMB_DIR, "%s.jpg" % uid)


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.2f %s" % (n, unit))
        n /= 1024


def _fmt_time(sec):
    sec = int(sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return ("%dh %dm %ds" % (h, m, s)) if h else ("%dm %ds" % (m, s))


def _bar(pct):
    filled = int(pct // 10)
    return "█" * filled + "░" * (10 - filled)


async def progress_for_pyrogram(current, total, label, message, start, state):
    """Live progress bar. Edits the status message at most every ~4 sec."""
    now = time.time()
    if current != total and now - state.get("last", 0) < 4:
        return
    state["last"] = now
    diff = max(now - start, 0.001)
    speed = current / diff
    pct = current * 100 / total if total else 0
    eta = (total - current) / speed if speed > 0 else 0
    text = (
        "%s\n\n[%s] %.1f%%\n"
        "📦 %s / %s\n"
        "🚀 Speed: %s/s\n"
        "⏳ ETA: %s"
    ) % (label, _bar(pct), pct, _fmt_bytes(current), _fmt_bytes(total),
         _fmt_bytes(speed), _fmt_time(eta) if current != total else "0s")
    try:
        await message.edit_text(text)
    except Exception:
        pass


def _make_thumb(src, dst):
    """Telegram thumbs must be JPEG, max 320px side, under 200 KB."""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    im.thumbnail((320, 320))
    q = 90
    while True:
        im.save(dst, "JPEG", quality=q)
        if os.path.getsize(dst) <= 200 * 1024 or q <= 30:
            break
        q -= 10


def _busy(client, m):
    """True if admin is inside /batch, /addchannel or a listen() prompt."""
    cid = m.chat.id
    if cid in BATCH or cid in CHANNELS:
        return True
    return cid in (getattr(client, "listening", None) or {})


# 1. Image bhejo (bina command ke) -> thumbnail set
@Client.on_message(filters.photo & filters.private & ~filters.reply)
async def set_thumbnail(client: Client, message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if _busy(client, message):
        return
    status = await message.reply_text("⏳ Thumbnail set ho raha hai...")
    tmp = None
    try:
        os.makedirs(THUMB_DIR, exist_ok=True)
        tmp = os.path.join(THUMB_DIR, "raw_%s.jpg" % message.id)
        await client.download_media(message, file_name=tmp)
        await asyncio.to_thread(_make_thumb, tmp, thumb_path(message.from_user.id))
        await status.edit_text("✅ Thumbnail set ho gaya!\n\nAb koi bhi video bhejo, usko reply me naya naam do.")
    except Exception as e:
        await status.edit_text("❌ Error: %s" % e)
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


# 2. Video/file ke reply me naya naam -> download + upload (progress bar ke saath)
@Client.on_message(filters.text & filters.reply & filters.private & ~filters.regex(r"^/"))
async def rename_and_upload(client: Client, message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return
    if _busy(client, message):
        return
    src = message.reply_to_message
    media = src.video or src.document or src.audio
    if not media:
        return

    new_name = re.sub(r'[\\/:*?"<>|\n\r]+', " ", message.text).strip()
    if not new_name:
        return
    if "." not in new_name:
        old = getattr(media, "file_name", None)
        if old and "." in old:
            new_name += "." + old.rsplit(".", 1)[-1]
        else:
            new_name += ".mp3" if src.audio else ".mp4"

    work = os.path.join(DOWNLOAD_DIR, "%s_%s" % (message.chat.id, message.id))
    file_path = os.path.join(work, new_name)
    os.makedirs(work, exist_ok=True)
    status = await message.reply_text("⏳ Processing...")
    thumb = thumb_path(message.from_user.id)
    thumb = thumb if os.path.exists(thumb) else None

    try:
        start = time.time()
        await client.download_media(
            src, file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("⬇️ Downloading...\n`%s`" % new_name, status, start, {}),
        )

        start = time.time()
        up_args = ("⬆️ Uploading...\n`%s`" % new_name, status, start, {})
        caption = src.caption or ""
        if src.video:
            v = src.video
            await client.send_video(
                message.chat.id, file_path, caption=caption, file_name=new_name,
                thumb=thumb, duration=v.duration or 0, width=v.width or 0, height=v.height or 0,
                supports_streaming=True,
                progress=progress_for_pyrogram, progress_args=up_args,
            )
        elif src.audio:
            await client.send_audio(
                message.chat.id, file_path, caption=caption, file_name=new_name,
                thumb=thumb, duration=src.audio.duration or 0,
                performer=src.audio.performer, title=src.audio.title,
                progress=progress_for_pyrogram, progress_args=up_args,
            )
        else:
            await client.send_document(
                message.chat.id, file_path, caption=caption, file_name=new_name,
                thumb=thumb,
                progress=progress_for_pyrogram, progress_args=up_args,
            )

        await status.delete()
        for m in (src, message):
            try:
                await m.delete()
            except Exception:
                pass
    except Exception as e:
        await status.edit_text("❌ Error: %s" % e)
    finally:
        shutil.rmtree(work, ignore_errors=True)
