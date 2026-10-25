from pyrogram import Client, filters
from config import ADMIN_ID
from database import db
from helpers import get_pending, fs_markup, send_content, send_setting, auto_delete, is_admin, set_menu

DEFAULT_WELCOME = "👋 Hello {mention}!\n\nWelcome to <b>{bot}</b>.\nOpen a valid link to get your files."
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
        await send_content(c, user.id, token, user)
    except Exception as e:
        print("[START] error:", repr(e))

@Client.on_message(filters.command("start") & filters.private)
async def start(c, m):
    db.add_user(m.from_user.id, m.from_user.first_name, m.from_user.username)
    if is_admin(m.from_user.id):
        await set_menu(c, m.from_user.id)
    if len(m.command) > 1:
        await gate_and_send(c, m.from_user, m.command[1])
        return
    if db.data["settings"].get("greeting"):
        await send_setting(c, m.from_user.id, "greeting", m.from_user)
    else:
        r = await m.reply(DEFAULT_WELCOME.format(mention=m.from_user.mention, bot=c.me.first_name))
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
