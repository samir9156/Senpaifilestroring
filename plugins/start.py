from pyrogram import Client, filters
from pyrogram.types import Message
import database

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    if len(message.command) > 1:
        token = message.command[1]
        file_data = database.db_data["files"].get(token)
        if not file_data: return await message.reply_text("❌ Invalid Link!")
            
        if database.db_data.get("first_message"):
            f = database.db_data["first_message"]
            await client.copy_message(message.chat.id, f["chat_id"], f["message_id"])
        
        is_protected = not file_data.get("shareable", True)
        status = await message.reply_text("⏳ Sending file(s)...")
        
        try:
            if file_data.get("is_batch"):
                for f in file_data["files"]:
                    await client.copy_message(message.chat.id, f["chat_id"], f["message_id"], protect_content=is_protected)
            else:
                await client.copy_message(message.chat.id, file_data["chat_id"], file_data["message_id"], protect_content=is_protected)
            await status.delete()
        except Exception as e:
            await status.edit_text(f"❌ Error fetching file: {e}")
            
        if database.db_data.get("last_message"):
            l = database.db_data["last_message"]
            await client.copy_message(message.chat.id, l["chat_id"], l["message_id"])
        return 
        
    greeting = database.db_data.get("greeting")
    if greeting:
        try: await client.copy_message(message.chat.id, greeting["chat_id"], greeting["message_id"])
        except: await message.reply_text("👋 Welcome!")
    else:
        await message.reply_text(f"👋 **Welcome {message.from_user.first_name}!**\n\nMain ek File Store Bot hoon.")
