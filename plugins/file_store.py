from pyrogram import Client, filters
from pyrogram.types import Message
import random, string
import database
from plugins.auth_admin import admin_filter

STORAGE_CHANNEL = database.STORAGE_CHANNEL

def generate_token(): return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

@Client.on_message(filters.command(["genlink1", "genlink2"]) & admin_filter)
async def gen_link(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.media:
        return await message.reply_text("❌ Kisi file pe reply karke command do.")
    target, token = message.reply_to_message, generate_token()
    status = await message.reply_text("⏳ Saving file to GC...")
    try:
        copied = await target.copy(STORAGE_CHANNEL)
        database.db_data["files"][token] = {
            "chat_id": copied.chat.id, "message_id": copied.id,
            "shareable": message.command[0] == "genlink1"
        }
        await database.save_db(client)
        await target.delete()
        await message.delete()
        link = f"https://t.me/{(await client.get_me()).username}?start={token}"
        await status.edit_text(f"✅ **Link Generated!**\n\n🔗 `{link}`\n*(DM Cleaned)*")
    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")

@Client.on_message(filters.command(["batch1", "batch2"]) & admin_filter)
async def batch_link(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.media:
        return await message.reply_text("❌ Batch ki pehli file pe reply karke command do.")
    first_msg = message.reply_to_message
    status = await message.reply_text("⏳ Send the LAST file of the batch now...")
    try:
        last_msg = await client.wait_for(chat_id=message.chat.id, filters=filters.media, timeout=60)
    except: return await status.edit_text("❌ Timeout.")
    await status.edit_text("⏳ Saving batch to GC...")
    token, saved_files = generate_token(), []
    try:
        msg_ids = list(range(first_msg.id, last_msg.id + 1))
        for mid in msg_ids:
            try:
                c = await client.copy_message(STORAGE_CHANNEL, message.chat.id, mid)
                if c.media: saved_files.append({"chat_id": STORAGE_CHANNEL, "message_id": c.id})
            except: pass
        if not saved_files: return await status.edit_text("❌ No media found in range.")
        database.db_data["files"][token] = {
            "files": saved_files, "shareable": message.command[0] == "batch1", "is_batch": True
        }
        await database.save_db(client)
        for mid in msg_ids:
            try: await client.delete_messages(message.chat.id, mid)
            except: pass
        await message.delete()
        link = f"https://t.me/{(await client.get_me()).username}?start={token}"
        await status.edit_text(f"✅ **Batch Link Generated!**\n\n🔗 `{link}`\n📦 Files: `{len(saved_files)}`\n*(DM Cleaned)*")
    except Exception as e:
        await status.edit_text(f"❌ Error: {e}")
