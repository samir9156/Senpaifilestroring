import asyncio, os, sys
sys.stdout.reconfigure(line_buffering=True)   # Railway logs turant dikhein
sys.stderr.reconfigure(line_buffering=True)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import pyromod.listen  # noqa: F401  (patches Client.listen)
from pyrogram import Client, idle
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, STORAGE
from database import db
from autodetect import poll
from helpers import set_menu
from scheduler import delete_loop


async def load_storage(app):
    """Private channel ID par fresh session ka peer-cache khali hota hai.
    1) STORAGE_ACCESS_HASH variable ho to use pehle se seed kar deta hai.
    2) Nahi to bot band hone ke bajay ruk ke retry karta hai: storage channel me koi bhi
       message post karo, bot ko channel ka update milte hi peer cache ho jata hai."""
    h = os.environ.get("STORAGE_ACCESS_HASH", "").strip()
    if h.lstrip("-").isdigit() and isinstance(STORAGE, int):
        try:
            await app.storage.update_peers([(STORAGE, int(h), "channel", None, None)])
            print("[PEER] storage channel access hash seed ho gaya")
        except Exception as e:
            print("[PEER] seed failed:", repr(e))
    for attempt in range(40):          # ~10 minute tak try
        try:
            await db.load(app)
            return True
        except Exception as e:
            print("[DB] load failed (%d/40): %r" % (attempt + 1, e))
            if attempt == 0:
                print("[DB] Storage channel me koi bhi message post karo (bot admin hona chahiye), bot wait kar raha hai...")
            await asyncio.sleep(15)
    return False


async def main():
    if not (API_ID and API_HASH and BOT_TOKEN and ADMIN_ID and STORAGE):
        print("❌ Variables missing! Fill API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, STORAGE_CHANNEL_INPUT")
        return
    app = Client("filestore", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN,
                 plugins=dict(root="plugins"), in_memory=True)
    await app.start()
    print("✅ Bot started as @%s" % app.me.username)
    if not await load_storage(app):
        print("❌ Storage channel error: channel resolve nahi hua.")
        print("Check: bot us channel me ADMIN hai (post/pin/delete) aur STORAGE_CHANNEL_INPUT sahi ID hai.")
        await app.stop()
        return
    # channel private karne ke baad bhi restart par resolve ho, iske liye ID + access hash admin ko bhej do (ek baar)
    if not os.environ.get("STORAGE_ACCESS_HASH"):
        try:
            ah = getattr((await app.resolve_peer(db.sid)), "access_hash", None)
            if ah:
                await app.send_message(
                    ADMIN_ID,
                    "🔑 Channel ko private karna ho to Railway Variables me ye dono rakho:\n\n"
                    "<code>STORAGE_CHANNEL_INPUT=%s</code>\n<code>STORAGE_ACCESS_HASH=%s</code>" % (db.sid, ah))
        except Exception as e:
            print("[PEER] access hash nahi mila:", repr(e))
    asyncio.create_task(db.autosave(app))
    asyncio.create_task(poll(app))
    asyncio.create_task(delete_loop(app))
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
