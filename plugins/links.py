import asyncio, time
from pyrogram import Client, filters
from database import db
from helpers import admin_f, safe, new_token, clean, BATCH, CHANNELS

async def _store(c, msgs):
    ids = []
    for x in sorted(msgs, key=lambda x: x.id):   # keep exact admin sequence
        r = await safe(x.copy, db.sid)
        if r:
            ids.append(r.id)
    return sorted(ids)

async def _make_link(c, ids, secure):
    token = new_token()
    db.data["links"][token] = {"ids": ids, "secure": secure, "time": int(time.time())}
    await db.save(c)
    return "https://t.me/%s?start=%s" % (c.me.username, token)

@Client.on_message(filters.command(["genlink1", "genlink2"]) & filters.private & admin_f)
async def genlink(c, m):
    try:
        secure = m.command[0].lower() == "genlink2"
        r = m.reply_to_message
        if not r:
            return await m.reply("Kisi file/message ko reply karke command do.")
        ids = await _store(c, [r])
        if not ids:
            return await m.reply("❌ Storage channel me save nahi hua. Bot ke rights check karo.")
        link = await _make_link(c, ids, secure)
        await c.send_message(m.chat.id, "✅ %s Link:\n\n%s" % ("Secured (no forward/save)" if secure else "Shareable", link),
                             disable_web_page_preview=True)
        await clean(c, m.chat.id, [m.id, r.id])
    except Exception as e:
        print("[GENLINK] error:", repr(e))
        await m.reply("❌ Error: %s" % e)

@Client.on_message(filters.command(["batch1", "batch2"]) & filters.private & admin_f)
async def batch_start(c, m):
    CHANNELS.pop(m.chat.id, None)
    secure = m.command[0].lower() == "batch2"
    prompt = await m.reply("📦 Files bhejo (text/photo/video sab chalega).\nKhatam hone par /done likho, cancel ke liye /cancel.")
    BATCH[m.chat.id] = {"secure": secure, "msgs": [], "junk": [m.id, prompt.id]}

# plain functions (called from plugins/done.py)
async def batch_cancel(c, m, sess):
    BATCH.pop(m.chat.id, None)
    await clean(c, m.chat.id, sess["junk"] + [x.id for x in sess["msgs"]] + [m.id])
    await c.send_message(m.chat.id, "❌ Batch cancel ho gaya.")

async def batch_finish(c, m, sess):
    try:
        await asyncio.sleep(2)   # let last files finish arriving
        BATCH.pop(m.chat.id, None)
        msgs = sorted(sess["msgs"], key=lambda x: x.id)
        if not msgs:
            await clean(c, m.chat.id, sess["junk"] + [m.id])
            return await c.send_message(m.chat.id, "❌ Koi file nahi mili, batch empty.")
        status = await c.send_message(m.chat.id, "⏳ %d messages save ho rahe hain..." % len(msgs))
        ids = await _store(c, msgs)
        if not ids:
            return await status.edit("❌ Storage channel me save nahi hua. Bot ke rights check karo.")
        link = await _make_link(c, ids, sess["secure"])
        await c.send_message(m.chat.id, "✅ %s Batch Link (%d msgs):\n\n%s" % ("Secured" if sess["secure"] else "Shareable", len(ids), link),
                             disable_web_page_preview=True)
        await clean(c, m.chat.id, sess["junk"] + [x.id for x in msgs] + [m.id, status.id])
    except Exception as e:
        print("[BATCH] error:", repr(e))
        await m.reply("❌ Error: %s" % e)
