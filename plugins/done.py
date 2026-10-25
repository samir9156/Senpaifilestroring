from pyrogram import Client, filters
from helpers import admin_f, BATCH, CHANNELS
from plugins.links import batch_finish, batch_cancel
from plugins.forcesub import chan_finish, chan_cancel, chan_collect

# ONE handler for /done and /cancel (Pyrogram runs only one handler per group)
@Client.on_message(filters.command(["done", "cancel"]) & filters.private & admin_f)
async def done_cancel(c, m):
    cmd = m.command[0].lower()
    cid = m.chat.id
    if cid in CHANNELS:
        fn = chan_finish if cmd == "done" else chan_cancel
        return await fn(c, m, CHANNELS[cid])
    if cid in BATCH:
        fn = batch_finish if cmd == "done" else batch_cancel
        return await fn(c, m, BATCH[cid])
    await m.reply("Koi session active nahi hai. Pehle /batch1, /batch2, /addchannel ya /deletechannels do.")

# ONE collector for every admin message while a session is active
@Client.on_message(filters.private & admin_f, group=1)
async def collector(c, m):
    if m.text and m.text.startswith("/"):
        return
    cid = m.chat.id
    if cid in CHANNELS:
        return await chan_collect(c, m, CHANNELS[cid])
    sess = BATCH.get(cid)
    if sess:
        sess["msgs"].append(m)
