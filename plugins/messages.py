from pyrogram import Client, filters
from database import db
from helpers import admin_f

async def _setter(c, m, key, label):
    try:
        p = await m.reply("📝 %s message bhejo (text/photo/video...). Cancel: /cancel" % label)
        r = await c.listen(m.chat.id, timeout=300)
        if r.text and r.text.strip().lower().startswith("/cancel"):
            return await m.reply("Cancelled.")
        saved = await r.copy(db.sid)
        db.data["settings"][key] = saved.id
        await db.save(c)
        await m.reply("✅ %s message set ho gaya (5 min baad auto-delete hoga)." % label)
    except Exception as e:
        print("[SETMSG] error:", repr(e))
        await m.reply("❌ Error / timeout: %s" % e)

@Client.on_message(filters.command("setfirstmessage") & filters.private & admin_f)
async def setfirst(c, m):
    await _setter(c, m, "first", "First")

@Client.on_message(filters.command("setlastmessage") & filters.private & admin_f)
async def setlast(c, m):
    await _setter(c, m, "last", "Last")

@Client.on_message(filters.command("setgreeting") & filters.private & admin_f)
async def setgreet(c, m):
    await _setter(c, m, "greeting", "Greeting")

@Client.on_message(filters.command("clearmessage") & filters.private & admin_f)
async def clearmsg(c, m):
    key = m.command[1].lower() if len(m.command) > 1 else ""
    if key not in ("first", "last", "greeting"):
        return await m.reply("Usage: /clearmessage first|last|greeting")
    db.data["settings"][key] = None
    await db.save(c)
    await m.reply("🗑 %s message hata diya." % key)
