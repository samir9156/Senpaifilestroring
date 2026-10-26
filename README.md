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
- /button - button bot: forward a channel post (or send its link) + buttons -> bot adds buttons to that post; or send a new post -> bot returns it with buttons
- /autobutton - auto-add buttons to every new post of a channel (send 'off' to stop). Button format: one line = one row, `Text - link`, `&&` = same row
- Timer: after /genlink or /batch the bot asks an auto-delete timer for delivered files: minutes (1, 10, 30, 60...), 1d = 24h, 2d = 48h, skip
- /checkuser - see a user's status per channel (joined / requested / baaki) and what he will be shown
- /cleanchannels - remove dead channels (deleted / bot removed / bot not admin); dead channels are ignored for users anyway
- /refreshlinks - create fresh join-request invite links for all channels
- /stats - users, new/active, links, channels, requests
- /users - download users.txt
- /setfirstmessage /setlastmessage /setgreeting /clearmessage first|last|greeting
  (placeholders in text/caption: {first} {last} {name} {mention} {username} {id} {bot})
- /addauthedit /delauth then forward a message of the user or send his ID (main admin only)
- All commands appear in the bot's command menu automatically (admin only)

## Force-Sub rule
Per user, every rolling 24 hrs: send join requests to 3 NEW channels. Only the missing ones (max 3) are shown.
Channels he already requested (ever) or joined are never asked again. If nothing new is left, he gets files directly.
Change REQUIRED_REQUESTS in config.py. Requests are never auto-approved.
