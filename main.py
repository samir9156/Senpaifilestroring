import asyncio, os
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
