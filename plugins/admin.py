from pyrogram import Client, filters
from database import db
from helpers import owner_f, admin_f

def _target(m):
    if m.reply_to_message and m.reply_to_message.from_user:
        return m.reply_to_message.from_user.id
    if len(m.command) > 1 and m.command[1].lstrip("-").isdigit():
        return int(m.command[1])
    return None

@Client.on_message(filters.command("addauthedit") & filters.private & owner_f)
async def add_admin(c, m):
    uid = _target(m)
    if not uid:
        return await m.reply("User ke message ko reply karo ya /addauthedit <user_id>")
    if uid not in db.data["admins"]:
        db.data["admins"].append(uid)
        await db.save(c)
    await m.reply("✅ %s ab admin hai." % uid)

@Client.on_message(filters.command("delauth") & filters.private & owner_f)
async def del_admin(c, m):
    uid = _target(m)
    if not uid:
        return await m.reply("User ke message ko reply karo ya /delauth <user_id>")
    if uid in db.data["admins"]:
        db.data["admins"].remove(uid)
        await db.save(c)
        return await m.reply("🗑 %s admin se hata diya." % uid)
    await m.reply("Ye user admin nahi hai.")
