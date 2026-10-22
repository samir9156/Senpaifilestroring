from pyrogram import Client, filters
from pyrogram.types import Message
import os
import database

OWNER_ID = int(os.environ.get("ADMIN_ID", 123456789))

async def is_admin_filter(_, __, message: Message):
    if not message.from_user: return False
    if message.from_user.id == OWNER_ID: return True
    return database.is_auth_admin(message.from_user.id)

admin_filter = filters.create(is_admin_filter)

@Client.on_message(filters.command(["addauthedit", "addauth"]) & filters.user(OWNER_ID))
async def add_auth_admin(client: Client, message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else (await client.get_users(int(message.command[1])) if len(message.command) > 1 else None)
    if not target: return await message.reply_text("❌ User not found.")
    if target.id == OWNER_ID: return await message.reply_text("👑 Main Owner!")
    database.make_auth_admin(target.id, True)
    await database.save_db(client)
    await message.reply_text(f"✅ **Auth Admin Added!**\n👤 {target.mention}")

@Client.on_message(filters.command(["delauth", "removeauth"]) & filters.user(OWNER_ID))
async def del_auth_admin(client: Client, message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else (await client.get_users(int(message.command[1])) if len(message.command) > 1 else None)
    if not target: return await message.reply_text("❌ User not found.")
    database.make_auth_admin(target.id, False)
    await database.save_db(client)
    await message.reply_text(f"❌ **Auth Admin Removed!**\n👤 {target.mention}")
