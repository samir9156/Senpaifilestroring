import json
import os
import asyncio
from pyrogram import Client

STORAGE_CHANNEL = int(os.environ.get("STORAGE_CHANNEL", -1001234567890))
DB_FILE = "bot_database.json"

db_data = {
    "users": {},
    "sublist": [],
    "rotation": {},
    "files": {},
    "greeting": {},
    "first_message": {},
    "last_message": {}
}

save_lock = asyncio.Lock()

async def load_db(client: Client):
    global db_data
    try:
        async for msg in client.search_messages(STORAGE_CHANNEL, query="#BotDatabase"):
            if msg.document:
                path = await msg.download()
                with open(path, "r", encoding="utf-8") as f:
                    db_data.update(json.load(f))
                os.remove(path)
                print("✅ Database loaded from GC!")
                return
    except Exception as e:
        print(f"⚠️ DB Load Error: {e}")

async def save_db(client: Client):
    if save_lock.locked(): return
    async with save_lock:
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db_data, f, indent=2)
            
            async for msg in client.search_messages(STORAGE_CHANNEL, query="#BotDatabase"):
                await msg.delete()
                
            await client.send_document(
                STORAGE_CHANNEL, DB_FILE, 
                caption="#BotDatabase\n⚠️ Do not delete this file.",
                file_name="database.json"
            )
            os.remove(DB_FILE)
        except Exception as e:
            print(f"❌ DB Save Error: {e}")

def is_auth_admin(user_id: int) -> bool:
    return db_data["users"].get(str(user_id), {}).get("is_auth", False)

def make_auth_admin(user_id: int, status: bool):
    uid = str(user_id)
    if uid not in db_data["users"]: db_data["users"][uid] = {"is_auth": False, "verified": []}
    db_data["users"][uid]["is_auth"] = status

def get_verified_channels(user_id: int) -> list:
    return db_data["users"].get(str(user_id), {}).get("verified", [])

def add_verified_channel(user_id: int, chat_id: int):
    uid = str(user_id)
    if uid not in db_data["users"]: db_data["users"][uid] = {"is_auth": False, "verified": []}
    if chat_id not in db_data["users"][uid]["verified"]:
        db_data["users"][uid]["verified"].append(chat_id)

def get_all_channels() -> list:
    return db_data["sublist"]

def add_channels_to_db(channels: list):
    for ch in channels:
        if not any(c["id"] == ch["id"] for c in db_data["sublist"]):
            db_data["sublist"].append(ch)

def clear_sublist():
    db_data["sublist"] = []
