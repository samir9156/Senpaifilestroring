import asyncio
import html as _html
import json
import os
import re
import shutil
import subprocess
import time
import zipfile

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

from config import (API_ID, API_HASH, ADMIN_ID, SESSION_STRING, SOURCE_CHANNEL, OUTPUT_CHANNEL,
                    MAIN_LINK, LINK_TIMER_MIN, DEFAULT_TITLE)
from database import db
from helpers import admin_f, new_token, buttons_markup, safe
from plugins.rename_upload import _make_thumb

WORK = os.path.abspath("downloads/autoup")
JOIN_TEXT = "💫Join Main Channel💫"

DEFAULT_RENAME = "{title} Season {season} Episode {abs}({ep}) [{quality}] [@SenpaiAnimess]"
DEFAULT_CAPTION = (
    "🎬 <b>ANIME:</b> {title}\n"
    "━━━━━━━━━━━━━━\n"
    "⬡ Season: {season}\n"
    "⬡ Episode: {ep}\n"
    "⬡ Quality: {qualities}\n"
    "⬡ Audio: [Hindi] | #Official"
)
CAPTION_HELP = ("📝 Caption bhejo (HTML/bold/italic chalega).\n\nPlaceholders:\n"
                "{title} {season} {ep} {abs} {quality} {qualities}\n\n"
                "Default par wapas jaane ke liye: default\nCancel: /cancel")
RENAME_HELP = ("✏️ Rename format bhejo.\n\nPlaceholders:\n{title} {season} {ep} {abs} {quality}\n\n"
               "Example:\n{title} Season {season} Episode {abs}({ep}) [{quality}] [@SenpaiAnimess]\n\n"
               "Default par wapas jaane ke liye: default\nCancel: /cancel")


def U():
    u = db.data.setdefault("uploader", {})
    for k, v in (("on", True), ("caption", None), ("rename", None), ("eps", {}), ("alias", {}), ("seen", [])):
        u.setdefault(k, v)
    return u


# ───────────────── pure helpers ─────────────────
def parse_info(text):
    """Episode info nikalta hai: title, season, abs (Episode 380), ep (in-season, bracket wala (08))."""
    t = text or ""
    season = ep = paren = None
    m = re.search(r"season\s*[:\-]?\s*(\d+)", t, re.I) or re.search(r"\bs(\d{1,2})\s*e\d", t, re.I)
    if m:
        season = int(m.group(1))
    m = (re.search(r"episode\s*[:\-]?\s*(\d+)\s*(?:\(\s*(\d+)\s*\))?", t, re.I)
         or re.search(r"\bs\d{1,2}\s*e(\d{1,4})", t, re.I)
         or re.search(r"\bep?\.?\s*[:\-]?\s*(\d{1,4})", t, re.I))
    if m:
        ep = int(m.group(1))
        if m.re.groups >= 2 and m.group(2):
            paren = int(m.group(2))
    title = None
    t_clean = re.sub(r"^\s*(\[[^\]]*\]\s*)+", "", t)
    m = re.match(r"\s*(.+?)\s+(?:season|s\d{1,2}\s*e|episode|ep\b)", t_clean, re.I)
    if m:
        title = re.sub(r"[\[\]_]+", " ", m.group(1)).strip(" -")
    return {"title": title or DEFAULT_TITLE, "season": season, "abs": ep, "paren": paren}


def alias_keys(info):
    ks = []
    if info["season"] and info["paren"]:
        ks.append("s%de%d" % (info["season"], info["paren"]))
    return ks


def lookup_key(info):
    """Source ke post se hamare episode ka canonical key."""
    cfg = U()
    cands = []
    if info["season"] and info["abs"] is not None:
        cands.append("s%de%d" % (info["season"], info["abs"]))
    if info["abs"] is not None:
        cands.append(str(info["abs"]))
    for k in cands:
        if k in cfg["alias"]:
            return cfg["alias"][k]
        if k in cfg["eps"]:
            return k
    return str(info["abs"]) if info["abs"] is not None else None


def q_from_size(h, w=0):
    if h >= 1800 or w >= 3000:
        return "2160p"
    if h >= 900 or w >= 1800:
        return "1080p"
    if h >= 600 or w >= 1200:
        return "720p"
    if h >= 400 or w >= 800:
        return "480p"
    return "360p"


def render(tpl, vals):
    return re.sub(r"\{(\w+)\}", lambda m: str(vals.get(m.group(1).lower(), m.group(0))), tpl)


def build_rows(links):
    order = sorted(links, key=lambda q: int(q[:-1]))
    btns = [[q, links[q]] for q in order]
    rows = [btns[i:i + 3] for i in range(0, len(btns), 3)]
    join = [JOIN_TEXT, MAIN_LINK]
    if rows and len(rows[-1]) == 1:
        rows[-1].append(join)
    else:
        rows.append([join])
    return rows, order


def safe_name(s):
    return re.sub(r"[\\/:*?\"<>|\r\n]+", " ", s).strip()


def set_entry(info, tpl=None, thumb=None):
    cfg = U()
    key = str(info["abs"])
    e = cfg["eps"].setdefault(key, {"thumb": None, "tpl": None, "post": None, "links": {}})
    if thumb:
        e["thumb"] = thumb
    if tpl:
        e["tpl"] = tpl
    e["title"] = info["title"]
    e["season"] = info["season"]
    e["paren"] = info["paren"]
    for k in alias_keys(info):
        cfg["alias"][k] = key
    db.dirty = True
    return key


def fix_tpl(tpl):
    """Template me {Quality} hona zaroori hai."""
    if "{quality}" in tpl.lower():
        return tpl
    t2 = re.sub(r"\[\s*\d{3,4}p\s*\]", "[{Quality}]", tpl, flags=re.I)
    if t2 != tpl:
        return t2
    return tpl + " [{Quality}]"


# ───────────────── ffmpeg ─────────────────
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                       capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    dur = float(d.get("format", {}).get("duration") or v.get("duration") or 0)
    return {"w": int(v.get("width") or 0), "h": int(v.get("height") or 0), "dur": dur,
            "audio": any(s.get("codec_type") == "audio" for s in streams)}


def is_silent(path, dur):
    start = max(0, dur * 0.25)
    r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(start), "-t", "90", "-i", path,
                        "-vn", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+|-inf)\s*dB", r.stderr)
    if not m:
        return False
    return m.group(1) == "-inf" or float(m.group(1)) < -60


def grab_frame(path, out, dur):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(min(30, dur / 3 if dur else 5)), "-i", path,
                    "-frames:v", "1", out], capture_output=True)
    return os.path.exists(out)


# ───────────────── main flow ─────────────────
QUEUE = None


async def notify(bot, text):
    try:
        await bot.send_message(ADMIN_ID, text, disable_web_page_preview=True)
    except Exception as e:
        print("[UPLOADER] notify failed:", repr(e))


async def process(bot, user, msg):
    cfg = U()
    media = msg.video or msg.document
    if media is None:
        return
    if msg.document and not (msg.document.mime_type or "").startswith("video/"):
        return
    if media.file_unique_id in cfg["seen"]:
        return
    src_text = " ".join(x for x in (msg.caption, getattr(media, "file_name", None)) if x)
    info = parse_info(src_text)
    if info["abs"] is None:
        return await notify(bot, "⚠️ Source post ka episode number samajh nahi aaya, skip kiya:\n%s" % (src_text[:200] or "(no caption)"))
    key = lookup_key(info)
    entry = cfg["eps"].get(key)
    if entry is None:
        key = set_entry(info)
        entry = cfg["eps"][key]
    # pehle se same quality hai? download se pehle hi skip (Telegram wali height se)
    if getattr(media, "height", 0):
        q0 = q_from_size(media.height, getattr(media, "width", 0) or 0)
        if q0 in entry["links"]:
            return

    work = os.path.join(WORK, str(msg.id))
    os.makedirs(work, exist_ok=True)
    try:
        await notify(bot, "⬇️ Download shuru: Episode %s (%s)" % (key, src_text[:60]))
        path = await user.download_media(msg, file_name=os.path.join(work, "src_" + (getattr(media, "file_name", None) or "video.mp4")))
        p = await asyncio.to_thread(probe, path)
        quality = q_from_size(p["h"], p["w"])
        if not p["audio"]:
            return await notify(bot, "🔇 Episode %s %s me audio hai hi nahi, skip kiya." % (key, quality))
        if await asyncio.to_thread(is_silent, path, p["dur"]):
            return await notify(bot, "🔇 Episode %s %s mute/silent hai, skip kiya. Source se fixed aayega to utha lunga." % (key, quality))
        if quality in entry["links"]:
            return await notify(bot, "ℹ️ Episode %s %s pehle se post me hai, skip kiya." % (key, quality))

        title = entry.get("title") or info["title"]
        season = entry.get("season") or info["season"] or ""
        paren = entry.get("paren") or info["paren"] or info["abs"]
        vals = {"title": title, "season": season, "abs": info["abs"], "ep": "%02d" % int(paren), "quality": quality}
        tpl = entry.get("tpl") or cfg.get("rename") or DEFAULT_RENAME
        ext = os.path.splitext(getattr(media, "file_name", None) or "")[1] or ".mp4"
        name = safe_name(render(tpl, vals)) + ext
        final = os.path.join(work, name)
        os.replace(path, final)

        # thumbnail
        thumb_jpg = os.path.join(work, "thumb.jpg")
        frame_used = False
        if entry.get("thumb"):
            raw = os.path.join(work, "thumb_raw.jpg")
            await bot.download_media(entry["thumb"], file_name=raw)
            await asyncio.to_thread(_make_thumb, raw, thumb_jpg)
        else:
            frame_used = await asyncio.to_thread(grab_frame, final, thumb_jpg, p["dur"])
            await notify(bot, "⚠️ Episode %s ka thumbnail set nahi hai, video ka frame laga raha hoon. "
                              "Thumbnail photo bhejke uske reply me naam likh do." % key)

        # storage me upload (isi se genlink banta hai)
        await notify(bot, "⬆️ Upload: %s" % name)
        cap_file = render(cfg.get("caption") or DEFAULT_CAPTION, {**vals, "qualities": quality})
        sent = await bot.send_video(db.sid, final, caption=cap_file, file_name=name,
                                    thumb=thumb_jpg if os.path.exists(thumb_jpg) else None,
                                    duration=int(p["dur"]), width=p["w"], height=p["h"], supports_streaming=True)
        token = new_token()
        db.data["links"][token] = {"ids": [sent.id], "secure": False, "timer": LINK_TIMER_MIN * 60, "time": int(time.time())}
        entry["links"][quality] = "https://t.me/%s?start=%s" % (bot.me.username, token)
        cfg["seen"] = (cfg["seen"] + [media.file_unique_id])[-500:]
        db.dirty = True

        # output channel post (naya ya purana edit)
        rows, order = build_rows(entry["links"])
        markup = buttons_markup(rows)
        caption = render(cfg.get("caption") or DEFAULT_CAPTION, {**vals, "quality": order[-1], "qualities": " | ".join(order)})
        if entry.get("post"):
            try:
                await bot.edit_message_caption(OUTPUT_CHANNEL, entry["post"], caption, reply_markup=markup)
            except Exception as e:
                if "MESSAGE_NOT_MODIFIED" not in str(e).upper():
                    raise
        else:
            photo = entry["thumb"] if entry.get("thumb") else thumb_jpg
            post = await bot.send_photo(OUTPUT_CHANNEL, photo, caption=caption, reply_markup=markup)
            entry["post"] = post.id
        await db.save(bot)
        await notify(bot, "✅ Episode %s %s post ho gaya." % (key, quality))
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def worker(bot, user):
    while True:
        msg = await QUEUE.get()
        try:
            await process(bot, user, msg)
        except Exception as e:
            print("[UPLOADER] error:", repr(e))
            await notify(bot, "❌ Auto upload error: %s" % e)
        finally:
            QUEUE.task_done()


async def start_userbot(bot):
    global QUEUE
    if not SESSION_STRING:
        print("[UPLOADER] SESSION_STRING nahi hai -> auto uploader band.")
        return
    try:
        user = Client("uploader_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
        await user.start()
        async for _ in user.get_dialogs():   # peers cache me aa jayein
            pass
    except Exception as e:
        print("[UPLOADER] userbot start failed:", repr(e))
        await notify(bot, "❌ Userbot start nahi hua (SESSION_STRING check karo): %s" % e)
        return
    QUEUE = asyncio.Queue()

    async def on_src(_, m):
        if U()["on"]:
            QUEUE.put_nowait(m)

    src_f = filters.create(lambda _, __, m: bool(m.chat) and m.chat.id == SOURCE_CHANNEL) & (filters.video | filters.document)
    user.add_handler(MessageHandler(on_src, src_f))
    asyncio.create_task(worker(bot, user))
    print("[UPLOADER] userbot online, watching", SOURCE_CHANNEL)
    await notify(bot, "✅ Auto uploader chalu hai. Source: %s" % SOURCE_CHANNEL)


# ───────────────── admin commands ─────────────────
async def _ask_text(c, m, help_text):
    r = m.reply_to_message
    if r and r.text:
        return r
    await m.reply(help_text)
    try:
        r = await c.listen(m.chat.id, timeout=300)
    except Exception:
        await m.reply("⏰ Time out ho gaya.")
        return None
    if not r.text or r.text.strip().lower().startswith("/cancel"):
        await m.reply("❌ Cancel ho gaya.")
        return None
    return r


@Client.on_message(filters.command("setcaption") & filters.private & admin_f)
async def setcaption(c, m):
    r = await _ask_text(c, m, CAPTION_HELP)
    if not r:
        return
    U()["caption"] = None if r.text.strip().lower() == "default" else r.text.html
    db.dirty = True
    await m.reply("✅ Caption set ho gaya.")


@Client.on_message(filters.command("setrenameformat") & filters.private & admin_f)
async def setrename(c, m):
    r = await _ask_text(c, m, RENAME_HELP)
    if not r:
        return
    U()["rename"] = None if r.text.strip().lower() == "default" else r.text.strip()
    db.dirty = True
    await m.reply("✅ Rename format set ho gaya.")


@Client.on_message(filters.command("uploader") & filters.private & admin_f)
async def uploader_toggle(c, m):
    cfg = U()
    if len(m.command) > 1 and m.command[1].lower() in ("on", "off"):
        cfg["on"] = m.command[1].lower() == "on"
        db.dirty = True
    await m.reply("🤖 Auto uploader: %s\nEpisodes saved: %d\n\n/uploader on | /uploader off" %
                  ("ON ✅" if cfg["on"] else "OFF ⛔", len(cfg["eps"])))


@Client.on_message(filters.command("addbulkthumbs") & filters.private & admin_f)
async def bulk_thumbs(c, m):
    await m.reply("🗂 Thumbnails ki ZIP bhejo.\nZip ke andar har image ka naam episode ke naam jaisa ho, e.g.\n"
                  "Naruto Shippuden Season 18 Episode 380(08) [{Quality}] [@SenpaiAnimess].jpg\n\nCancel: /cancel")
    try:
        r = await c.listen(m.chat.id, timeout=300)
    except Exception:
        return await m.reply("⏰ Time out ho gaya.")
    if not r.document or not (r.document.file_name or "").lower().endswith(".zip"):
        return await m.reply("❌ ZIP file chahiye. Dobara /addbulkthumbs do.")
    work = os.path.join(WORK, "bulk_%s" % m.id)
    os.makedirs(work, exist_ok=True)
    st = await m.reply("⏳ Zip download ho rahi hai...")
    ok, bad = 0, []
    try:
        zpath = await c.download_media(r, file_name=os.path.join(work, "t.zip"))
        from PIL import Image
        with zipfile.ZipFile(zpath) as z:
            names = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n
                     and n.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
            for n in names:
                stem = os.path.splitext(os.path.basename(n))[0]
                info = parse_info(stem)
                if info["abs"] is None:
                    bad.append(stem)
                    continue
                try:
                    jpg = os.path.join(work, "i.jpg")
                    im = Image.open(z.open(n)).convert("RGB")
                    im.thumbnail((1280, 1280))
                    im.save(jpg, "JPEG", quality=90)
                    sent = await safe(c.send_photo, db.sid, jpg)
                    if not sent:
                        bad.append(stem)
                        continue
                    set_entry(info, tpl=fix_tpl(stem), thumb=sent.photo.file_id)
                    ok += 1
                except Exception as e:
                    print("[BULK] failed", n, repr(e))
                    bad.append(stem)
        await db.save(c)
        txt = "✅ %d thumbnails save ho gaye." % ok
        if bad:
            txt += "\n\n❌ Ye match nahi hue (naam me 'Episode <number>' hona chahiye):\n" + "\n".join(bad[:20])
        await st.edit_text(txt)
    except Exception as e:
        await st.edit_text("❌ Error: %s" % e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# single thumbnail: photo bhejo, phir uske reply me naam likho
@Client.on_message(filters.text & filters.reply & filters.private & admin_f & ~filters.regex(r"^/"), group=2)
async def thumb_name(c, m):
    r = m.reply_to_message
    if not r or not r.photo:
        return
    info = parse_info(m.text)
    if info["abs"] is None:
        return await m.reply("⚠️ Naam me 'Episode <number>' hona chahiye.\nExample: Naruto Shippuden Season 18 Episode 380(08) [{Quality}] [@SenpaiAnimess]")
    key = set_entry(info, tpl=fix_tpl(m.text.strip()), thumb=r.photo.file_id)
    await m.reply("✅ Episode %s ka thumbnail + naam save ho gaya." % key)
