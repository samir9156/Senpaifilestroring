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
- /genlink1 /genlink2 (reply to a file) - shareable / secured link
- /batch1 /batch2 then send files, /done - batch link (order kept)
- /addchannel then forward one message from each channel, /done - add Force-Sub channels
- /deletechannels then forward one message from each channel, /done - remove channels
- /channels - list Force-Sub channels
- /setfirstmessage /setlastmessage /setgreeting /clearmessage first|last|greeting
- /addauthedit /delauth (main admin only, reply to user)

## Force-Sub rule
Every 24 hrs a user must send a join request to ANY 3 channels (joined channels are skipped).
Change REQUIRED_REQUESTS in config.py. Requests are never auto-approved.
