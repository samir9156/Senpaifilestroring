# Telegram File Store Bot

Pyrogram + pyromod file store bot. Database is a JSON file pinned inside your private Storage Channel (no MongoDB).

## Variables
API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, STORAGE_CHANNEL_INPUT (see .env.example)

## Run

    pip install -r requirements.txt
    export API_ID=... API_HASH=... BOT_TOKEN=... ADMIN_ID=... STORAGE_CHANNEL_INPUT=...
    python main.py

Bot must be ADMIN in the Storage Channel (post, pin, delete rights).

## Commands (admin)
- /genlink1 /genlink2 then send the file (no reply needed) - shareable / secured link
- /batch1 /batch2 then send files, /done - batch link (order kept)
- /addchannel then forward one message from each channel, /done - add Force-Sub channels
- /deletechannels then forward one message from each channel, /done - remove channels
- /channels - list Force-Sub channels
- /checkuser - see a user's status per channel (joined / requested / baaki) and what he will be shown
- /setfirstmessage /setlastmessage /setgreeting /clearmessage first|last|greeting
  (placeholders in text/caption: {first} {last} {name} {mention} {username} {id} {bot})
- /addauthedit /delauth then forward a message of the user or send his ID (main admin only)
- All commands appear in the bot's command menu automatically (admin only)

## Force-Sub rule
Per user, every rolling 24 hrs: send join requests to 3 NEW channels. Only the missing ones (max 3) are shown.
Channels he already requested (ever) or joined are never asked again. If nothing new is left, he gets files directly.
Change REQUIRED_REQUESTS in config.py. Requests are never auto-approved.
