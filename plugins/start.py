from pyrogram import Client, filters
from config import ADMIN_ID
from database import db
from helpers import get_pending, fs_markup, send_content, send_setting, auto_delete

DEFAULT_WELCOME = "👋 Hello {name}!\n\nMain ek File Store Bot hu. Mere paas koi valid link se aao."
FS_MSG = {}

async def _del_old(c, uid):
    mid = FS_MSG.pop(uid, None)
    if mid:
        try:
            await c.delete_messages(uid, mid)
        except Exception:
            pass

async def gate_and_send(c, user, token):
    try:
        await _del_old(c, user.id)
        if user.id != ADMIN_ID:
            pending = await get_pending(c, user.id)
            if pending:
                m = await c.send_message(
                    user.id,
                    "<i>Hey %s\n\nPlease Join All My Update Channels To Use Me!</i>" % user.mention,
                    reply_markup=await fs_markup(c, pending, token),
                )
                FS_MSG[user.id] = m.id
                return
        await send_content(c, user.id, token)
    except Exception as e:
        print("[START] error:", repr(e))

@Client.on_message(filters.command("start") & filters.private)
async def start(c, m):
    db.add_user(m.from_user.id)
    if len(m.command) > 1:
        await gate_and_send(c, m.from_user, m.command[1])
        return
    if db.data["settings"].get("greeting"):
        await send_setting(c, m.from_user.id, "greeting")
    else:
        r = await m.reply(DEFAULT_WELCOME.format(name=m.from_user.first_name))
        auto_delete(r)

@Client.on_callback_query(filters.regex(r"^retry:"))
async def retry(c, q):
    try:
        token = q.data.split(":", 1)[1]
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        await gate_and_send(c, q.from_user, token)
    except Exception as e:
        print("[RETRY] error:", repr(e))
