import asyncio, re
from pyrogram import Client, filters, raw
from pyrogram.enums import ChatType
from config import ADMIN_ID
from database import db
from helpers import add_channel, admin_f, clean, channel_alive, BATCH, CHANNELS
from autodetect import register_channel, unregister_channel, _call

# ───────── raw updates (own group, never blocks other handlers) ─────────
@Client.on_raw_update(group=-10)
async def raw_updates(c, update, users, chats):
    try:
        if isinstance(update, raw.types.UpdateChannelParticipant):
            if update.user_id != c.me.id:
                return
            ch = chats.get(update.channel_id) if chats else None
            if ch is not None and not getattr(ch, "broadcast", False):
                return
            cid = int("-100" + str(update.channel_id))
            np = update.new_participant
            print("[RAW] bot status change in", cid, "->", type(np).__name__ if np else None)
            if isinstance(np, (raw.types.ChannelParticipantAdmin, raw.types.ChannelParticipantCreator)):
                await register_channel(c, cid)
            else:
                await unregister_channel(c, cid)
        elif isinstance(update, raw.types.UpdateBotChatInviteRequester):
            if isinstance(update.peer, raw.types.PeerChannel):
                cid = int("-100" + str(update.peer.channel_id))
                if str(cid) in db.data["channels"]:
                    db.mark_request(cid, update.user_id)
                    print("[FS] request saved (raw)", cid, update.user_id)
    except Exception as e:
        print("[RAW] error:", repr(e))

@Client.on_chat_join_request()
async def on_join_request(c, r):
    try:
        if str(r.chat.id) in db.data["channels"]:
            db.mark_request(r.chat.id, r.from_user.id)
            print("[FS] request saved", r.chat.id, r.from_user.id)
    except Exception as e:
        print("[FS] join request error:", repr(e))

# ───────── /addchannel & /deletechannels (message-based sessions) ─────────
def _status_text(s):
    head = "➕ Add" if s["mode"] == "add" else "🗑 Delete"
    if not s["found"]:
        return head + " mode\nChannels mile: 0"
    rows = "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(s["found"].values()))
    return "%s mode\nChannels mile (%d):\n%s" % (head, len(s["found"]), rows)

async def _refresh(s):
    try:
        await s["status"].edit(_status_text(s))
    except Exception:
        pass

async def _start_session(c, m, mode):
    BATCH.pop(m.chat.id, None)
    if mode == "add":
        txt = ("📢 Pehle bot ko un sab channels me ADMIN bana do.\n\n"
               "Phir har channel ka ek message mujhe forward karo (ya us channel me koi post daal do).\n"
               "Ek ek karke sabhi channels ke message bhejo, aur end me /done likho.\n"
               "Cancel: /cancel")
    else:
        txt = ("🗑 Jin channels ko Force-Sub se hatana hai, unka ek ek message mujhe forward karo "
               "(ya us channel me koi post daal do).\nPhir /done likho. Cancel: /cancel")
    prompt = await m.reply(txt)
    status = await m.reply(_status_text({"mode": mode, "found": {}}))
    CHANNELS[m.chat.id] = {"mode": mode, "found": {}, "junk": [m.id, prompt.id, status.id], "msgs": [], "status": status}

@Client.on_message(filters.command("addchannel") & filters.private & admin_f)
async def addchannel(c, m):
    if len(m.command) == 1:
        return await _start_session(c, m, "add")
    # old manual format: /addchannel -100xxx @username https://t.me/+xxx
    entries = []
    for a in m.command[1:]:
        if re.fullmatch(r"-100\d+", a):
            entries.append({"id": int(a)})
        elif not entries:
            continue
        elif a.startswith("@"):
            entries[-1]["username"] = a.lstrip("@")
        elif "t.me/" in a:
            entries[-1]["link"] = a
    if not entries:
        return await m.reply("Sirf /addchannel bhejo aur phir channel ke messages forward karo.")
    out = []
    for e in entries:
        try:
            t = await add_channel(c, e["id"], manual=e.get("link"), username=e.get("username"))
            out.append("✅ %s (%s)" % (t, e["id"]))
        except Exception as ex:
            out.append("❌ %s -> %s" % (e["id"], ex))
    await db.save(c)
    await m.reply("\n".join(out))

@Client.on_message(filters.command("deletechannels") & filters.private & admin_f)
async def deletechannels(c, m):
    await _start_session(c, m, "del")

@Client.on_message(filters.command("channels") & filters.private & admin_f)
async def channels(c, m):
    ch = db.data["channels"]
    if not ch:
        return await m.reply("Koi Force-Sub channel nahi hai.")
    res = await asyncio.gather(*[channel_alive(c, cid) for cid in ch])
    rows, dead = [], 0
    for i, ((cid, v), (ok, why)) in enumerate(zip(ch.items(), res), 1):
        if ok:
            tag = "✅"
        elif ok is None:
            tag = "⚠️ check nahi hua"
        else:
            tag = "❌ " + why
            dead += 1
        rows.append("%d. %s (%s) %s" % (i, v.get("title"), cid, tag))
    txt = "📋 Force-Sub channels (%d):\n\n%s" % (len(ch), "\n".join(rows))
    if dead:
        txt += "\n\n❌ %d dead channel hai. /cleanchannels se hata do." % dead
    await m.reply(txt)

@Client.on_message(filters.command("cleanchannels") & filters.private & admin_f)
async def cleanchannels(c, m):
    ch = db.data["channels"]
    if not ch:
        return await m.reply("Koi Force-Sub channel nahi hai.")
    items = list(ch.items())
    res = await asyncio.gather(*[channel_alive(c, cid) for cid, _ in items])
    removed = []
    for (cid, v), (ok, why) in zip(items, res):
        if ok is False:
            db.data["channels"].pop(cid, None)
            removed.append("🗑 %s (%s) - %s" % (v.get("title"), cid, why))
    if removed:
        await db.save(c)
        await m.reply("%s\n\nBache hue channels: %d" % ("\n".join(removed), len(db.data["channels"])))
    else:
        await m.reply("✅ Saare channels theek hain, kuch hatane ko nahi.")

@Client.on_message(filters.command("refreshlinks") & filters.private & admin_f)
async def refreshlinks(c, m):
    ok, bad = 0, []
    for cid, v in list(db.data["channels"].items()):
        try:
            l = await c.create_chat_invite_link(int(cid), name="ForceSub", creates_join_request=True)
            v["invite"] = l.invite_link
            ok += 1
        except Exception as e:
            bad.append("%s (%s): %s" % (v.get("title"), cid, e))
    await db.save(c)
    txt = "🔗 %d channels ke naye join-request links ban gaye." % ok
    if bad:
        txt += "\n\n❌ Fail:\n" + "\n".join(bad)
    await m.reply(txt)

# plain functions (called from plugins/done.py)
async def chan_collect(c, m, s):
    s["msgs"].append(m.id)
    fc = getattr(m, "forward_from_chat", None) or getattr(getattr(m, "forward_origin", None), "chat", None)
    if fc is not None and getattr(fc, "type", None) == ChatType.CHANNEL:
        if fc.id == db.sid:
            r = await m.reply("⛔ Ye storage channel hai, ise Force-Sub me nahi jod sakte.")
            s["junk"].append(r.id)
            return
        s["found"][fc.id] = fc.title
        await _refresh(s)
    else:
        r = await m.reply("⚠️ Ye channel ka forwarded message nahi hai. Channel se message forward karo (forward tag hidden nahi hona chahiye).")
        s["junk"].append(r.id)

@Client.on_message(filters.channel, group=2)
async def on_channel_post(c, m):
    if not CHANNELS or m.chat.id == db.sid:
        return
    for s in list(CHANNELS.values()):
        s["found"][m.chat.id] = m.chat.title
        await _refresh(s)

async def chan_cancel(c, m, s):
    CHANNELS.pop(m.chat.id, None)
    await clean(c, m.chat.id, s["junk"] + s["msgs"] + [m.id])
    await c.send_message(m.chat.id, "❌ Cancel ho gaya.")

async def chan_finish(c, m, s):
    CHANNELS.pop(m.chat.id, None)
    found = s["found"]
    if not found:
        await clean(c, m.chat.id, s["junk"] + s["msgs"] + [m.id])
        return await c.send_message(m.chat.id, "❌ Koi channel nahi mila.")
    lines = []
    for cid, title in found.items():
        try:
            if s["mode"] == "add":
                if cid == db.sid:
                    lines.append("⛔ %s - storage channel, skip" % title)
                elif str(cid) in db.data["channels"]:
                    lines.append("♻️ %s - pehle se list me hai" % title)
                else:
                    res = await asyncio.to_thread(_call, "getChatMember", {"chat_id": cid, "user_id": c.me.id})
                    st = (res.get("result") or {}).get("status")
                    if st not in ("administrator", "creator"):
                        lines.append("❌ %s - bot is channel me admin nahi hai" % title)
                    else:
                        await add_channel(c, cid, title=title)
                        lines.append("✅ %s - add ho gaya" % title)
            else:
                if db.data["channels"].pop(str(cid), None):
                    lines.append("🗑 %s - hata diya" % title)
                else:
                    lines.append("ℹ️ %s - list me tha hi nahi" % title)
        except Exception as e:
            lines.append("❌ %s - %s" % (title, e))
    await db.save(c)
    await clean(c, m.chat.id, s["junk"] + s["msgs"] + [m.id])
    await c.send_message(m.chat.id, "%s\n\nTotal Force-Sub channels ab: %d" % ("\n".join(lines), len(db.data["channels"])))
