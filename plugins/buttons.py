import asyncio, re
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait
from database import db
from helpers import admin_f, clean, channel_alive, parse_buttons, buttons_markup

BTN_HELP = ("🔘 Buttons bhejo (ek line = ek row).\n"
            "Ek hi row me 2 button chahiye to && lagao.\n\n"
            "Format:\n"
            "Watch Now - https://t.me/Kage_store_bot?start=abc\n"
            "Join - @SenpaiAnimess && Share - https://example.com\n\n"
            "Cancel: /cancel")

def _is_cancel(r):
    return bool(r.text) and r.text.strip().lower().startswith("/cancel")

def post_target(r):
    # (chat, message_id, title) if r is a forwarded channel post or a post link, else None
    fc = getattr(r, "forward_from_chat", None) or getattr(getattr(r, "forward_origin", None), "chat", None)
    mid = getattr(r, "forward_from_message_id", None) or getattr(getattr(r, "forward_origin", None), "message_id", None)
    if fc is not None and getattr(fc, "type", None) == ChatType.CHANNEL and mid:
        return fc.id, mid, fc.title
    t = (r.text or "").strip()
    mm = re.fullmatch(r"(?:https?://)?t\.me/c/(\d+)/(?:\d+/)?(\d+)", t)
    if mm:
        return int("-100" + mm.group(1)), int(mm.group(2)), None
    mm = re.fullmatch(r"(?:https?://)?t\.me/([A-Za-z0-9_]{4,})/(\d+)", t)
    if mm and mm.group(1) != "c":
        return "@" + mm.group(1), int(mm.group(2)), None
    return None

async def _listen(c, chat_id, timeout=300):
    try:
        return await c.listen(chat_id, timeout=timeout)
    except Exception:
        return None

async def _ask_buttons(c, chat_id, junk, extra=""):
    for _ in range(3):
        q = await c.send_message(chat_id, extra + BTN_HELP)
        junk.append(q.id)
        r = await _listen(c, chat_id)
        if r is None:
            return "timeout"
        junk.append(r.id)
        if _is_cancel(r):
            return "cancel"
        rows = parse_buttons(r.text)
        if rows:
            return rows
        e = await c.send_message(chat_id, "⚠️ Format galat hai. Har line: Text - link")
        junk.append(e.id)
    return "cancel"

# ───────── /button : add buttons to a post (edit channel post OR make a new post with buttons) ─────────
@Client.on_message(filters.command("button") & filters.private & admin_f)
async def button_cmd(c, m):
    chat = m.chat.id
    junk = [m.id]
    try:
        p = await m.reply(
            "🔘 <b>Button Bot</b>\n\n"
            "Post bhejo jis par button lagane hain:\n"
            "• Channel ka post yahan <b>forward</b> karo (ya uska link bhejo) → bot seedha us channel ke post me button laga dega "
            "(bot us channel me admin ho, 'Edit messages' right ke saath)\n"
            "• Ya koi naya post (text/photo/video) bhejo → bot button ke saath wapas bhej dega, use forward kar lena\n\n"
            "Cancel: /cancel")
        junk.append(p.id)
        r = await _listen(c, chat)
        if r is None:
            await clean(c, chat, junk)
            return await c.send_message(chat, "⏰ Time out ho gaya.")
        junk.append(r.id)
        if _is_cancel(r):
            await clean(c, chat, junk)
            return await c.send_message(chat, "❌ Cancel ho gaya.")
        target = post_target(r)
        rows = await _ask_buttons(c, chat, junk)
        if rows in ("timeout", "cancel"):
            await clean(c, chat, junk)
            return await c.send_message(chat, "⏰ Time out ho gaya." if rows == "timeout" else "❌ Cancel ho gaya.")
        markup = buttons_markup(rows)
        if target:
            cid, mid, title = target
            try:
                await c.edit_message_reply_markup(cid, mid, markup)
                await clean(c, chat, junk)
                return await c.send_message(chat, "✅ %s ke post me buttons lag gaye." % (title or "Channel"))
            except Exception as e:
                print("[BUTTON] edit failed:", repr(e))
                await clean(c, chat, junk)
                return await c.send_message(
                    chat, "❌ Button nahi lag paya: %s\n\nCheck karo: bot us channel me admin hai aur 'Edit messages of others' right on hai. "
                          "Post kisi aur bot ya 'via' se bheja gaya ho to edit nahi hota." % e)
        await c.copy_message(chat, chat, r.id, reply_markup=markup)
        await clean(c, chat, junk)
        await c.send_message(chat, "✅ Buttons ke saath post upar hai. Ise kisi bhi channel me forward kar sakte ho.")
    except Exception as e:
        print("[BUTTON] error:", repr(e))
        await c.send_message(chat, "❌ Error: %s" % e)

# ───────── /autobutton : buttons on EVERY new post of a channel ─────────
@Client.on_message(filters.command("autobutton") & filters.private & admin_f)
async def autobutton_cmd(c, m):
    chat = m.chat.id
    junk = [m.id]
    try:
        cur = db.data["btn_channels"]
        lst = "\n".join("• %s %s" % (v.get("title"), "(ON)" if v.get("on", True) else "(OFF)") for v in cur.values()) or "Abhi koi channel set nahi hai."
        p = await m.reply("🤖 <b>Auto Button</b>\n\nJin channels me abhi auto button hai:\n%s\n\n"
                          "Jis channel ke har naye post pe button lagana hai (ya band karna hai), us channel ka ek post yahan forward karo.\n"
                          "Cancel: /cancel" % lst)
        junk.append(p.id)
        r = await _listen(c, chat)
        if r is None:
            await clean(c, chat, junk)
            return await c.send_message(chat, "⏰ Time out ho gaya.")
        junk.append(r.id)
        if _is_cancel(r):
            await clean(c, chat, junk)
            return await c.send_message(chat, "❌ Cancel ho gaya.")
        target = post_target(r)
        if not target:
            await clean(c, chat, junk)
            return await c.send_message(chat, "⚠️ Channel ka forwarded post (forward tag ke saath) ya post link bhejo. Dobara /autobutton do.")
        cid, _, title = target
        if not isinstance(cid, int):
            cid = (await c.get_chat(cid)).id
            title = title or (await c.get_chat(cid)).title
        key = str(cid)
        ok, why = await channel_alive(c, cid)
        if ok is False:
            await clean(c, chat, junk)
            return await c.send_message(chat, "❌ %s me bot admin nahi hai (%s). Pehle bot ko admin banao." % (title, why))
        q = await c.send_message(chat, "📌 %s\n\nButtons bhejo, ya auto button band karne ke liye: off\n\n%s" % (title, BTN_HELP))
        junk.append(q.id)
        r2 = await _listen(c, chat)
        if r2 is None:
            await clean(c, chat, junk)
            return await c.send_message(chat, "⏰ Time out ho gaya.")
        junk.append(r2.id)
        if _is_cancel(r2):
            await clean(c, chat, junk)
            return await c.send_message(chat, "❌ Cancel ho gaya.")
        if (r2.text or "").strip().lower() in ("off", "delete", "remove", "stop"):
            db.data["btn_channels"].pop(key, None)
            await db.save(c)
            await clean(c, chat, junk)
            return await c.send_message(chat, "🗑 %s ka auto button band kar diya." % title)
        rows = parse_buttons(r2.text)
        if not rows:
            await clean(c, chat, junk)
            return await c.send_message(chat, "⚠️ Format galat hai. Dobara /autobutton do.\n\n" + BTN_HELP)
        db.data["btn_channels"][key] = {"title": title, "rows": rows, "on": True}
        await db.save(c)
        await clean(c, chat, junk)
        await c.send_message(chat, "✅ %s: ab har naye post pe ye buttons apne aap lagenge.\n\n(Bot ko 'Edit messages of others' right chahiye.)" % title)
    except Exception as e:
        print("[AUTOBTN] error:", repr(e))
        await c.send_message(chat, "❌ Error: %s" % e)

# new post in a configured channel -> add buttons
@Client.on_message(filters.channel, group=3)
async def auto_buttons(c, m):
    cfg = db.data["btn_channels"].get(str(m.chat.id))
    if not cfg or not cfg.get("on", True) or m.service or m.reply_markup or m.media_group_id:
        return
    for _ in range(2):
        try:
            await c.edit_message_reply_markup(m.chat.id, m.id, buttons_markup(cfg["rows"]))
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            print("[AUTOBTN] failed", m.chat.id, m.id, repr(e))
            return
