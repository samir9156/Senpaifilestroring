from pyrogram import Client, filters
from pyrogram.types import Message
import database
from plugins.auth_admin import admin_filter

@Client.on_message(filters.command("setgreeting") & admin_filter)
async def set_greeting(client: Client, message: Message):
    if not message.reply_to_message: return await message.reply_text("❌ Kisi message pe reply karo.")
    database.db_data["greeting"] = {"chat_id": message.chat.id, "message_id": message.reply_to_message.id}
    await database.save_db(client)
    await message.reply_text("✅ Greeting Set!")

@Client.on_message(filters.command("setfirstmessage") & admin_filter)
async def set_first_msg(client: Client, message: Message):
    if not message.reply_to_message: return await message.reply_text("❌ Kisi message pe reply karo.")
    database.db_data["first_message"] = {"chat_id": message.chat.id, "message_id": message.reply_to_message.id}
    await database.save_db(client)
    await message.reply_text("✅ First Message Set!")

@Client.on_message(filters.command("setlastmessage") & admin_filter)
async def set_last_msg(client: Client, message: Message):
    if not message.reply_to_message: return await message.reply_text("❌ Kisi message pe reply karo.")
    database.db_data["last_message"] = {"chat_id": message.chat.id, "message_id": message.reply_to_message.id}
    await database.save_db(client)
    await message.reply_text("✅ Last Message Set!")
