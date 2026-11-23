import pyromod.listen
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatJoinRequest
import random, string, asyncio, time, os
from database import db
import config

AUTO_DELETE_TIME = 300 

def gen_token(): return ''.join(random.choices(string.ascii_letters + string.digits, k=11))

async def get_invite_link(client, chat_id):
    try:
        ch_data = db.data.get("channels", {}).get(str(chat_id))
        if ch_data and ch_data.get("invite"):
            return ch_data["invite"]
        chat = await client.get_chat(chat_id)
        if chat.username: return f"https://t.me/{chat.username}"
        link_obj = await client.create_chat_invite_link(chat_id)
        return link_obj.invite_link
    except Exception as e:
        print(f"❌ Link Error for {chat_id}: {e}")
        return None

# 🔥 Sending Files (With Progress & Thumbnail)
async def send_files(client, chat_id, link_data):
    is_protected = link_data.get("secure", True)
    thumb = "thumbnail.jpg" if os.path.exists("thumbnail.jpg") else None
    status = await client.send_message(chat_id, "⏳ Preparing files...")
    
    try:
        for msg_id in link_data["ids"]:
            msg = await client.get_messages(config.STORAGE, msg_id)
            if not msg.empty:
                if thumb and (msg.video or msg.document):
                    path = await client.download_media(msg)
                    if msg.video:
                        await client.send_video(chat_id, video=path, caption=msg.caption or "", thumb=thumb, protect_content=is_protected)
                    else:
                        await client.send_document(chat_id, document=path, caption=msg.caption or "", thumb=thumb, protect_content=is_protected)
                    if os.path.exists(path): os.remove(path)
                else:
                    await client.copy_message(chat_id, config.STORAGE, msg_id, protect_content=is_protected)
        await status.delete()
    except Exception as e: 
        await status.edit_text(f"❌ Error: {e}")

# --- JOIN REQUEST TRACKER ---
@Client.on_chat_join_request()
async def join_request_handler(client, request: ChatJoinRequest):
    db.mark_request(request.chat.id, request.from_user.id)
    await db.save(client)

# --- START HANDLER ---
@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    token = message.command[1] if len(message.command) > 1 else None
    
    db.add_user(user_id, message.from_user.first_name, message.from_user.username)
    if db.dirty: await db.save(client)

    if user_id != config.ADMIN_ID:
        fs_channels = db.data.get("channels", {})
        missing = []
        
        if fs_channels:
            for ch_id_str, ch_data in fs_channels.items():
                ch_id = int(ch_id_str)
                reqs = db.data.get("requests", {}).get(ch_id_str, {})
                if str(user_id) in reqs:
                    continue # Request pending/approved
                    
                try:
                    member = await client.get_chat_member(ch_id, user_id)
                    if member.status in ["left", "kicked"]:
                        missing.append(ch_id)
                except Exception:
                    missing.append(ch_id)
                    
        if missing:
            text = f"Hey {message.from_user.first_name}\n\n<b>Please Join All My Update Channels To Use Me!</b>"
            buttons = []
            for i, ch_id in enumerate(missing, 1):
                link = await get_invite_link(client, ch_id)
                if link: buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=link)])
                else: buttons.append([InlineKeyboardButton(f"Channel {i} Error", callback_data="no_link")])
                    
            cb_data = f"verify_sub_{token}" if token else "verify_sub_"
            buttons.append([InlineKeyboardButton("♻️ Try Again", callback_data=cb_data)])
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            return
        
    if token:
        link_data = db.data["links"].get(token)
        if not link_data: return await message.reply_text("❌ Invalid or Expired Link!")
        await send_files(client, user_id, link_data)
        return

    greeting = db.data.get("settings", {}).get("greeting")
    if greeting:
        if "text" in greeting:
            m = await message.reply_text(greeting["text"])
            asyncio.create_task(auto_delete_msg(m, 60))
        elif "chat_id" in greeting:
            m = await client.copy_message(message.chat.id, greeting["chat_id"], greeting["message_id"])
            asyncio.create_task(auto_delete_msg(m, 60))
    else: 
        m = await message.reply_text(f"👋 **Welcome {message.from_user.first_name}!**")
        asyncio.create_task(auto_delete_msg(m, 60))

# --- VERIFY CALLBACK ---
@Client.on_callback_query(filters.regex("^verify_sub_"))
async def verify_callback(client, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer("Verifying...", show_alert=False)
    
    token = callback_query.data[11:] if len(callback_query.data) > 11 else ""
    fs_channels = db.data.get("channels", {})
    missing = []
    
    for ch_id_str, ch_data in fs_channels.items():
        ch_id = int(ch_id_str)
        reqs = db.data.get("requests", {}).get(ch_id_str, {})
        if str(user_id) in reqs:
            continue
            
        try:
            member = await client.get_chat_member(ch_id, user_id)
            if member.status in ["left", "kicked"]:
                missing.append(ch_id)
        except Exception:
            missing.append(ch_id)
            
    if missing:
        text = f"Hey {callback_query.from_user.first_name}\n\n<b>You still haven't joined all channels!</b>"
        buttons = []
        for i, ch_id in enumerate(missing, 1):
            link = await get_invite_link(client, ch_id)
            if link: buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=link)])
            else: buttons.append([InlineKeyboardButton(f"Channel {i} Error", callback_data="no_link")])
        
        buttons.append([InlineKeyboardButton("♻️ Try Again", callback_data=callback_query.data)])
        try: await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except: pass
    else:
        await callback_query.message.delete()
        if token:
            link_data = db.data["links"].get(token)
            if not link_data: return await client.send_message(user_id, "❌ Invalid or Expired Link!")
            await send_files(client, user_id, link_data)
        else:
            await client.send_message(user_id, "✅ <b>Verification complete!</b>\n\nAb apna link dobara click karein.")

async def auto_delete_msg(msg, delay):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except: pass
