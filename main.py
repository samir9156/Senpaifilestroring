from pyrogram import Client, idle
import os
import database

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

plugins = dict(root="plugins")

app = Client(
    "FileStoreBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=plugins
)

async def main():
    print("🤖 Bot Starting...")
    await app.start()
    await database.load_db(app)
    print("✅ Bot Started & DB Loaded!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
