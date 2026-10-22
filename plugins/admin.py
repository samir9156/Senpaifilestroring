from pyrogram import Client, filters
from pyrogram.types import Message
from plugins.auth_admin import admin_filter
import database
import re

async def verify_bot_admin(client: Client, channel_username: str):
    try:
        chat = await client.get_chat(channel_username)
        member = await client.get_chat_member(chat.id, "me")
        if member.status in ["administrator", "creator"] and member.privileges and member.privileges.can_invite_users:
            return True, chat.title, chat.id
        return False, "Bot Admin nahi hai ya Invite permission nahi hai.", None
    except Exception as e:
        return False, f"Error: {str(e)}", None

@Client.on_message(filters.command("updatesublist") & admin_filter)
async def update_sublist(client: Client, message: Message):
    text = message.text if not message.reply_to_message else message.reply_to_message.text
    raw_channels = re.findall(r'(?:@|t\.me/)([\w\d_]+)', text or "")
    if not raw_channels: return await message.reply_text("❌ Koi valid channel nahi mila.")
    msg = await message.reply_text("🔄 Verifying channels...")
    valid, errors = [], []
    for ch in set(raw_channels):
        success, info, ch_id = await verify_bot_admin(client, f"@{ch}")
        if success: valid.append({"username": f"@{ch}", "title": info, "id": ch_id})
        else: errors.append(f"❌ {ch}: {info}")
    if valid:
        database.add_channels_to_db(valid)
        await database.save_db(client)
    res = f"✅ **{len(valid)} Channels Added!**\n"
    if errors: res += "\n**Errors:**\n" + "\n".join(errors)
    await msg.edit_text(res)

@Client.on_message(filters.command("editsublist") & admin_filter)
async def edit_sublist(client: Client, message: Message):
    text = message.text if not message.reply_to_message else message.reply_to_message.text
    raw_channels = re.findall(r'(?:@|t\.me/)([\w\d_]+)', text or "")
    msg = await message.reply_text("🔄 Replacing list...")
    valid = []
    for ch in set(raw_channels):
        success, info, ch_id = await verify_bot_admin(client, f"@{ch}")
        if success: valid.append({"username": f"@{ch}", "title": info, "id": ch_id})
    if valid:
        database.clear_sublist()
        database.add_channels_to_db(valid)
        await database.save_db(client)
        await msg.edit_text(f"✅ **List Replaced!**\nNaye channels: `{len(valid)}`")
    else:
        await msg.edit_text("❌ Koi valid channel nahi mila.")
