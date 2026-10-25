import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import pyromod.listen  # noqa: F401  (patches Client.listen)
from pyrogram import Client, idle
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, STORAGE
from database import db
from autodetect import poll
from helpers import set_menu

async def main():
    if not (API_ID and API_HASH and BOT_TOKEN and ADMIN_ID and STORAGE):
        print("❌ Variables missing! Fill API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, STORAGE_CHANNEL_INPUT")
        return
    app = Client("filestore", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN,
                 plugins=dict(root="plugins"), in_memory=True)
    await app.start()
    print("✅ Bot started as @%s" % app.me.username)
    try:
        await db.load(app)
    except Exception as e:
        print("❌ Storage channel error:", repr(e))
        print("Bot ko storage channel me ADMIN banao (post/pin/delete rights) aur ID/username sahi do.")
        await app.stop()
        return
    asyncio.create_task(db.autosave(app))
    asyncio.create_task(poll(app))
    await set_menu(app)
    try:
        await app.send_message(ADMIN_ID, "✅ Bot online! DB loaded. Channels: %d" % len(db.data["channels"]))
    except Exception as e:
        print("[WARN] Admin ko message nahi gaya (pehle bot ko /start karo):", repr(e))
    await idle()
    await db.save(app)
    await app.stop()

try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    pass
