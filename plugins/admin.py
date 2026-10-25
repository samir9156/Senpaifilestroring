from pyrogram import Client, filters
from database import db
from helpers import owner_f, clean, set_menu

async def _ask_target(c, m, action):
    # 1) reply  2) /cmd <id>  3) interactive: forward a message of the user OR send his numeric ID
    if m.reply_to_message and m.reply_to_message.from_user:
        return m.reply_to_message.from_user.id
    if len(m.command) > 1 and m.command[1].lstrip("-").isdigit():
        return int(m.command[1])
    p = await m.reply("👤 Jise %s banana hai, uska koi message forward karo ya uski numeric user ID bhejo.\nCancel: /cancel" % action)
    junk = [m.id, p.id]
    try:
        r = await c.listen(m.chat.id, timeout=300)
    except Exception:
        await clean(c, m.chat.id, junk)
        await c.send_message(m.chat.id, "⏰ Time out ho gaya.")
        return None
    junk.append(r.id)
    uid = None
    if r.text and r.text.strip().lower().startswith("/cancel"):
        await clean(c, m.chat.id, junk)
        await c.send_message(m.chat.id, "❌ Cancel ho gaya.")
        return None
    fu = getattr(r, "forward_from", None) or getattr(getattr(r, "forward_origin", None), "sender_user", None)
    if fu:
        uid = fu.id
    elif r.text and r.text.strip().lstrip("-").isdigit():
        uid = int(r.text.strip())
    await clean(c, m.chat.id, junk)
    if not uid:
        await c.send_message(m.chat.id, "⚠️ User pehchana nahi gaya (forward hidden ho sakta hai). Uski numeric ID bhejo: dobara command do.")
    return uid

@Client.on_message(filters.command("addauthedit") & filters.private & owner_f)
async def add_admin(c, m):
    uid = await _ask_target(c, m, "admin")
    if not uid:
        return
    if uid not in db.data["admins"]:
        db.data["admins"].append(uid)
        await db.save(c)
    await set_menu(c, uid, force=True)
    await c.send_message(m.chat.id, "✅ %s ab admin hai." % uid)

@Client.on_message(filters.command("delauth") & filters.private & owner_f)
async def del_admin(c, m):
    uid = await _ask_target(c, m, "admin se hatana")
    if not uid:
        return
    if uid in db.data["admins"]:
        db.data["admins"].remove(uid)
        await db.save(c)
        return await c.send_message(m.chat.id, "🗑 %s admin se hata diya." % uid)
    await c.send_message(m.chat.id, "Ye user admin nahi hai.")
