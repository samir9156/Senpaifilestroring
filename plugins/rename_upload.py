import pyromod.listen
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatJoinRequest
import random, string, asyncio, os, time
import database
import config
import sys

AUTO_DELETE_TIME = 300 

def gen_token(): return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

async def auto_delete_msg(msg, delay=AUTO_DELETE_TIME):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except: pass

async def get_proper_invite_link(client, chat_id):
    try:
        chat = await client.get_chat(chat_id)
        if chat.username: return f"https://t.me/{chat.username}"
        link_obj = await client.create_chat_invite_link(chat_id)
        return link_obj.invite_link
    except Exception as e:
        print(f"❌ Link Error for {chat_id}: {e}")
        return None

# 🔥 Live Progress Bar Function
async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 3.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        
        def format_bytes(bytes):
            if bytes < 1024: return f"{bytes} B"
            elif bytes < 1024**2: return f"{bytes/1024:.1f} KB"
            elif bytes < 1024**3: return f"{bytes/1024**2:.1f} MB"
            else: return f"{bytes/1024**3:.2f} GB"
            
        def format_time(milliseconds):
            seconds = (milliseconds / 1000) % 60
            minutes = (milliseconds / (1000 * 60)) % 60
            return f"{int(minutes)}m {int(seconds)}s"

        tmp = f"{ud_type}\n"
        tmp += f"**[{format_bytes(current)} of {format_bytes(total)}]**\n"
        tmp += f"**Speed:** {format_bytes(speed)}/s\n"
        tmp += f"**Progress:** {percentage:.1f}%\n"
        tmp += f"**ETA:** {format_time(time_to_completion) if current != total else '0s'}"
        
        try: await message.edit_text(tmp)
        except: pass

# 🔥 UPDATED: Download -> Upload with Thumbnail & Progress
async def send_files(client, chat_id, file_data):
    first_msg_data = database.db_data.get("first_message", {})
    if first_msg_data:
        if "text" in first_msg_data:
            m = await client.send_message(chat_id, first_msg_data["text"])
            asyncio.create_task(auto_delete_msg(m))
        elif "chat_id" in first_msg_data:
            m = await client.copy_message(chat_id, first_msg_data["chat_id"], first_msg_data["message_id"])
            asyncio.create_task(auto_delete_msg(m))
        
    is_protected = not file_data.get("shareable", True)
    thumb = "thumbnail.jpg" if os.path.exists("thumbnail.jpg") else None
    status_msg = await client.send_message(chat_id, "⏳ **Preparing files...**")
    
    try:
        # Agar batch hai
        if file_data.get("is_batch"):
            for f in file_data["files"]:
                msg = await client.get_messages(f["chat_id"], f["message_id"])
                
                # Download phase
                start_time = time.time()
                path = await client.download_media(
                    msg, 
                    progress=progress_for_pyrogram, 
                    progress_args=("⬇️ **Downloading...**", status_msg, start_time)
                )
                
                # Upload phase
                start_time = time.time()
                if msg.video:
                    await client.send_video(chat_id, video=path, caption=msg.caption or "", thumb=thumb, protect_content=is_protected, progress=progress_for_pyrogram, progress_args=("⬆️ **Uploading...**", status_msg, start_time))
                else:
                    await client.send_document(chat_id, document=path, caption=msg.caption or "", thumb=thumb, protect_content=is_protected, progress=progress_for_pyrogram, progress_args=("⬆️ **Uploading...**", status_msg, start_time))
                
                if os.path.exists(path): os.remove(path)
                
        # Agar single file hai
        else:
            msg = await client.get_messages(file_data["chat_id"], file_data["message_id"])
            
            # Download phase
            start_time = time.time()
            path = await client.download_media(
                msg, 
                progress=progress_for_pyrogram, 
                progress_args=("⬇️ **Downloading...**", status_msg, start_time)
            )
            
            # Upload phase
            start_time = time.time()
            if msg.video:
                await client.send_video(chat_id, video=path, caption=msg.caption or "", thumb=thumb, protect_content=is_protected, progress=progress_for_pyrogram, progress_args=("⬆️ **Uploading...**", status_msg, start_time))
            else:
                await client.send_document(chat_id, document=path, caption=msg.caption or "", thumb=thumb, protect_content=is_protected, progress=progress_for_pyrogram, progress_args=("⬆️ **Uploading...**", status_msg, start_time))
            
            if os.path.exists(path): os.remove(path)
                
        await status_msg.delete()
    except Exception as e: 
        await status_msg.edit_text(f"❌ Error: {e}")
        
    last_msg_data = database.db_data.get("last_message", {})
    if last_msg_data:
        if "text" in last_msg_data:
            m = await client.send_message(chat_id, last_msg_data["text"])
            asyncio.create_task(auto_delete_msg(m))
        elif "chat_id" in last_msg_data:
            m = await client.copy_message(chat_id, last_msg_data["chat_id"], last_msg_data["message_id"])
            asyncio.create_task(auto_delete_msg(m))


# (Baaki admin commands aur start_handler waisa hi rahega niche)
@Client.on_message(filters.command("addchannel") & filters.private)
async def add_channel_manual(client, message):
    # ... (same as before) ...
    pass

@Client.on_chat_member_updated()
async def track_bot_admin(client, update):
    # ... (same as before) ...
    pass

@Client.on_chat_join_request()
async def join_request_handler(client, request: ChatJoinRequest):
    # ... (same as before) ...
    pass

@Client.on_message(filters.command("clearfs") & filters.private)
async def clear_fs(client, message):
    # ... (same as before) ...
    pass

@Client.on_message(filters.command("ping") & filters.private)
async def ping_cmd(client, message):
    await message.reply_text("🏓 **Pong!**")

@Client.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    token = message.command[1] if len(message.command) > 1 else None
    
    if user_id != config.ADMIN_ID:
        fs_channels = database.db_data.get("fs_channels", [])
        missing = []
        
        if fs_channels:
            user_data = database.db_data["users"].get(str(user_id), {"verified": [], "requested": []})
            verified = user_data.get("verified", [])
            requested = user_data.get("requested", [])
            
            for ch_id in fs_channels:
                if ch_id in verified: continue
                if ch_id in requested:
                    if ch_id not in verified: verified.append(ch_id)
                    continue
                try:
                    member = await client.get_chat_member(ch_id, user_id)
                    if member.status in ["left", "kicked"]:
                        missing.append(ch_id)
                    else:
                        if ch_id not in verified: verified.append(ch_id)
                except Exception:
                    missing.append(ch_id) 
                    
            database.db_data["users"][str(user_id)] = {"verified": verified, "requested": requested}
            await database.save_db(client)
            
        if missing:
            text = f"Hey {message.from_user.first_name}\n\n<b>Please Join All My Update Channels To Use Me!</b>"
            buttons = []
            for i, ch_id in enumerate(missing, 1):
                link = await get_proper_invite_link(client, ch_id)
                if link: buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=link)])
                else: buttons.append([InlineKeyboardButton(f"Channel {i} Error", callback_data="no_link")])
                    
            cb_data = f"verify_sub_{token}" if token else "verify_sub_"
            buttons.append([InlineKeyboardButton("♻️ Try Again", callback_data=cb_data)])
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            return
        
    if token:
        file_data = database.db_data["files"].get(token)
        if not file_data: return await message.reply_text("❌ Invalid or Expired Link!")
        await send_files(client, user_id, file_data)
        return

    greeting = database.db_data.get("greeting", {})
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

@Client.on_callback_query(filters.regex("^verify_sub_"))
async def verify_callback(client, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer("Verifying...", show_alert=False)
    
    token = ""
    if len(callback_query.data) > 11: token = callback_query.data[11:]
    
    fs_channels = database.db_data.get("fs_channels", [])
    missing = []
    
    if fs_channels:
        user_data = database.db_data["users"].get(str(user_id), {"verified": [], "requested": []})
        verified = user_data.get("verified", [])
        requested = user_data.get("requested", [])
        
        for ch_id in fs_channels:
            if ch_id in verified: continue
            if ch_id in requested:
                if ch_id not in verified: verified.append(ch_id)
                continue
            try:
                member = await client.get_chat_member(ch_id, user_id)
                if member.status in ["left", "kicked"]:
                    missing.append(ch_id)
                else:
                    if ch_id not in verified: verified.append(ch_id)
            except Exception:
                missing.append(ch_id)
                
        database.db_data["users"][str(user_id)] = {"verified": verified, "requested": requested}
        await database.save_db(client)
        
    if missing:
        text = f"Hey {callback_query.from_user.first_name}\n\n<b>You still haven't joined all channels!</b>"
        buttons = []
        for i, ch_id in enumerate(missing, 1):
            link = await get_proper_invite_link(client, ch_id)
            if link: buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=link)])
            else: buttons.append([InlineKeyboardButton(f"Channel {i} Error", callback_data="no_link")])
        
        buttons.append([InlineKeyboardButton("♻️ Try Again", callback_data=callback_query.data)])
        
        try: await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except: pass
    else:
        await callback_query.message.delete()
        if token:
            file_data = database.db_data["files"].get(token)
            if not file_data: return await client.send_message(user_id, "❌ Invalid or Expired Link!")
            await send_files(client, user_id, file_data)
        else:
            await client.send_message(user_id, "✅ <b>Verification complete!</b>\n\nAb apna link dobara click karein ya `/start` bhejein.")

@Client.on_message(filters.command("setgreeting") & filters.private)
async def set_greeting(client, message):
    if message.from_user.id != config.ADMIN_ID: return
    if not message.reply_to_message: return await message.reply_text("❌ Message pe reply karo.")
    database.db_data["greeting"] = {"chat_id": message.chat.id, "message_id": message.reply_to_message.id}
    await database.save_db(client)
    await message.reply_text("✅ Greeting Set!")

@Client.on_message(filters.command("setfirstmessage") & filters.private)
async def set_first(client, message):
    if message.from_user.id != config.ADMIN_ID: return
    if not message.reply_to_message: return await message.reply_text("❌ Message pe reply karo.")
    database.db_data["first_message"] = {"chat_id": message.chat.id, "message_id": message.reply_to_message.id}
    await database.save_db(client)
    await message.reply_text("✅ First Message Set!")

@Client.on_message(filters.command("setlastmessage") & filters.private)
async def set_last(client, message):
    if message.from_user.id != config.ADMIN_ID: return
    if not message.reply_to_message: return await message.reply_text("❌ Message pe reply karo.")
    database.db_data["last_message"] = {"chat_id": message.chat.id, "message_id": message.reply_to_message.id}
    await database.save_db(client)
    await message.reply_text("✅ Last Message Set!")

@Client.on_message(filters.command(["genlink1", "genlink2"]) & filters.private)
async def genlink(client, message):
    if message.from_user.id != config.ADMIN_ID: return
    is_shareable = message.command[0] == "genlink1"
    status = await message.reply_text("⏳ **File bhejein...**")
    try:
        file_msg = await client.listen(chat_id=message.chat.id, filters=filters.user(config.ADMIN_ID) & filters.media, timeout=60)
    except asyncio.TimeoutError: return await status.edit_text("❌ Timeout!")
        
    await status.edit_text("⏳ Saving...")
    token = gen_token()
    copied = await file_msg.copy(config.STORAGE_CHANNEL)
    database.db_data["files"][token] = {"chat_id": copied.chat.id, "message_id": copied.id, "shareable": is_shareable}
    await database.save_db(client)
    await file_msg.delete(); await message.delete()
    link = f"https://t.me/{(await client.get_me()).username}?start={token}"
    await status.edit_text(f"✅ **Link:** `{link}`\n*(Chat cleaned)*")

@Client.on_message(filters.command(["batch1", "batch2"]) & filters.private)
async def batch(client, message):
    if message.from_user.id != config.ADMIN_ID: return
    is_shareable = message.command[0] == "batch1"
    prompt = await message.reply_text("📦 **Batch Mode**\n\nSaare files/messages bhejein. Khatam hone par **/done** likhein.")
    try:
        done = await client.listen(chat_id=message.chat.id, filters=filters.user(config.ADMIN_ID) & filters.command("done"), timeout=600)
    except asyncio.TimeoutError: return await prompt.edit_text("❌ Timeout!")
        
    await prompt.edit_text("⏳ Processing messages...")
    msg_ids = list(range(prompt.id + 1, done.id))
    if not msg_ids:
        await done.delete(); await message.delete()
        return await prompt.edit_text("❌ Koi message nahi mila.")
        
    msgs = []
    for i in range(0, len(msg_ids), 200):
        chunk = msg_ids[i:i+200]
        res = await client.get_messages(chat_id=message.chat.id, message_ids=chunk)
        if isinstance(res, list): msgs.extend(res)
        else: msgs.append(res)
        
    msgs = [m for m in msgs if not m.empty]
    msgs.sort(key=lambda x: x.id)
    
    if not msgs:
        await done.delete(); await message.delete()
        return await prompt.edit_text("❌ Koi valid message nahi mila.")
        
    token = gen_token()
    saved = []
    for m in msgs:
        try:
            c = await m.copy(config.STORAGE_CHANNEL)
            saved.append({"chat_id": config.STORAGE_CHANNEL, "message_id": c.id})
            await m.delete()
        except: pass
        
    database.db_data["files"][token] = {"files": saved, "shareable": is_shareable, "is_batch": True}
    await database.save_db(client)
    await done.delete(); await message.delete()
    link = f"https://t.me/{(await client.get_me()).username}?start={token}"
    await prompt.edit_text(f"✅ **Batch Link:** `{link}`\n📦 Total: {len(saved)}\n*(Chat cleaned)*")
