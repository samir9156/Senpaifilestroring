import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import config

# Global variable to store thumbnail path
THUMB_PATH = "thumbnail.jpg"

# Helper function for progress bar
async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 5.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        
        # Formatting sizes
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
        
        try:
            await message.edit_text(tmp)
        except:
            pass # Ignore FloodWait or MessageNotModified errors

# 1. Set Thumbnail Feature (Triggered by sending a Photo without command)
@Client.on_message(filters.photo & filters.private)
async def set_thumbnail(client: Client, message: Message):
    if message.from_user.id != config.ADMIN_ID: return
    if message.reply_to_message: return # Ignore if it's a reply (handled by rename)
    
    status = await message.reply_text("⏳ **Downloading Thumbnail...**")
    try:
        path = await message.download(file_name=THUMB_PATH)
        await status.edit_text("✅ **Thumbnail Set Successfully!**\n\nAb kisi bhi video ko reply me naya naam bhej kar upload kar sakte ho.")
    except Exception as e:
        await status.edit_text(f"❌ Error setting thumbnail: {e}")

# 2. Rename & Upload Feature (Triggered by replying to a media with Text)
@Client.on_message(filters.text & filters.reply & filters.private & ~filters.regex(r"^/"))
async def rename_and_upload(client: Client, message: Message):
    if message.from_user.id != config.ADMIN_ID: return
    
    replied_msg = message.reply_to_message
    # Check if replied message is video or document
    if not (replied_msg.video or replied_msg.document or replied_msg.audio):
        return

    # Naya naam extract karo
    new_name = message.text.strip()
    
    # Agar user ne extension nahi diya (jaise .mkv, .mp4), toh original se le lo
    if "." not in new_name:
        if replied_msg.video:
            new_name += ".mp4"
        elif replied_msg.document:
            ext = replied_msg.document.file_name.split(".")[-1] if replied_msg.document.file_name else "mkv"
            new_name += f".{ext}"

    status_msg = await message.reply_text("⏳ **Processing...**")
    
    # File download path
    download_path = f"downloads/{new_name}"
    os.makedirs("downloads", exist_ok=True)

    try:
        # --- DOWNLOAD PHASE ---
        await status_msg.edit_text(f"⬇️ **Downloading...**\nTarget: `{new_name}`")
        start_time = time.time()
        
        # Pyrogram download with progress
        file_path = await client.download_media(
            replied_msg,
            file_name=download_path,
            progress=progress_for_pyrogram,
            progress_args=("⬇️ **Downloading...**", status_msg, start_time)
        )
        
        # --- UPLOAD PHASE ---
        await status_msg.edit_text(f"⬆️ **Uploading...**\nName: `{new_name}`")
        start_time = time.time()
        
        # Thumbnail path check
        thumb = THUMB_PATH if os.path.exists(THUMB_PATH) else None
        
        # Upload based on type
        if replied_msg.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=file_path,
                caption=replied_msg.caption or "",
                file_name=new_name,
                thumb=thumb,
                supports_streaming=True,
                progress=progress_for_pyrogram,
                progress_args=("⬆️ **Uploading...**", status_msg, start_time)
            )
        else:
            await client.send_document(
                chat_id=message.chat.id,
                document=file_path,
                caption=replied_msg.caption or "",
                file_name=new_name,
                thumb=thumb,
                progress=progress_for_pyrogram,
                progress_args=("⬆️ **Uploading...**", status_msg, start_time)
            )
            
        # --- CLEANUP ---
        await status_msg.delete()
        
        # Delete original message and reply to keep chat clean
        try: await replied_msg.delete()
        except: pass
        try: await message.delete()
        except: pass
        
        # Delete downloaded file to save disk space
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        await status_msg.edit_text(f"❌ **Error:** {str(e)}\n\n(Dhyan de: File 2GB se badi nahi honi chahiye)")
