from pyrogram import Client, idle
import os
import database
from threading import Thread
from flask import Flask

# --- Render ke liye Dummy Web Server ---
app_web = Flask(__name__)

@app_web.route('/')
def health_check():
    return "Bot is alive!", 200

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

# --- Pyrogram Bot ---
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
    
    # Web server ko background thread me start karo
    Thread(target=run_web_server, daemon=True).start()
    print("🌐 Web server started on PORT")

    await app.start()
    await database.load_db(app)
    print("✅ Bot Started & DB Loaded!")
    
    from pyrogram import idle
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
