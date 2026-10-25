import asyncio
import requests
from config import BOT_TOKEN, ADMIN_ID
from database import db
from helpers import add_channel

API = "https://api.telegram.org/bot%s/" % BOT_TOKEN

def _call(method, params=None, timeout=40):
    r = requests.post(API + method, json=params or {}, timeout=timeout)
    return r.json()

async def register_channel(c, cid, title=None):
    if cid == db.sid or str(cid) in db.data["channels"]:
        return
    try:
        res = await asyncio.to_thread(_call, "getChatMember", {"chat_id": cid, "user_id": c.me.id})
        st = (res.get("result") or {}).get("status")
        if st not in ("administrator", "creator"):
            print("[AUTO] skip, bot not admin in", cid, res)
            return
        t = await add_channel(c, cid, title=title)
        await db.save(c)
        print("[AUTO] channel added", cid, t)
        await c.send_message(ADMIN_ID, "✅ Force-Sub channel add hua: %s (%s)" % (t, cid))
    except Exception as e:
        print("[AUTO] register error", cid, repr(e))

async def unregister_channel(c, cid):
    if str(cid) in db.data["channels"]:
        t = db.data["channels"].pop(str(cid))
        await db.save(c)
        print("[AUTO] channel removed", cid)
        try:
            await c.send_message(ADMIN_ID, "🗑 Force-Sub se hata diya: %s (%s)" % (t.get("title"), cid))
        except Exception:
            pass

# Bot API poller: reliably receives my_chat_member (bot made admin / removed),
# including changes that happened while the bot was offline (last ~24h).
async def poll(c):
    try:
        await asyncio.to_thread(_call, "deleteWebhook", {"drop_pending_updates": False})
    except Exception as e:
        print("[AUTO] deleteWebhook failed:", repr(e))
    print("[AUTO] auto-detect poller started")
    offset = None
    while True:
        try:
            params = {"timeout": 25, "allowed_updates": ["my_chat_member"]}
            if offset:
                params["offset"] = offset
            res = await asyncio.to_thread(_call, "getUpdates", params, 40)
            if not res.get("ok"):
                print("[AUTO] getUpdates error:", res)
                await asyncio.sleep(10)
                continue
            for u in res.get("result", []):
                offset = u["update_id"] + 1
                mc = u.get("my_chat_member")
                if not mc:
                    continue
                chat = mc.get("chat", {})
                if chat.get("type") != "channel":
                    continue
                st = mc["new_chat_member"]["status"]
                print("[AUTO] my_chat_member", chat.get("id"), chat.get("title"), "->", st)
                if st == "administrator":
                    await register_channel(c, chat["id"], chat.get("title"))
                else:
                    await unregister_channel(c, chat["id"])
        except Exception as e:
            print("[AUTO] poll error:", repr(e))
            await asyncio.sleep(5)
