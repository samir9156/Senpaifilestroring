import asyncio, secrets, time
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as S
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID, FS_WINDOW, AUTO_DELETE, REQUIRED_REQUESTS
from database import db

def is_admin(uid):
    return uid == ADMIN_ID or uid in db.data["admins"]

admin_f = filters.create(lambda _, __, m: bool(m.from_user) and is_admin(m.from_user.id))
owner_f = filters.create(lambda _, __, m: bool(m.from_user) and m.from_user.id == ADMIN_ID)

def new_token():
    return secrets.token_urlsafe(8)

BATCH = {}      # admin chat_id -> batch session
CHANNELS = {}   # admin chat_id -> add/delete channel session

async def clean(c, chat_id, ids):
    ids = list(set(ids))
    for i in range(0, len(ids), 100):
        try:
            await c.delete_messages(chat_id, ids[i:i + 100])
        except Exception as e:
            print("[CLEAN] error:", repr(e))

async def safe(fn, *a, **k):
    for _ in range(5):
        try:
            return await fn(*a, **k)
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            print("[SAFE] error:", repr(e))
            return None
    return None

_tasks = set()

def auto_delete(msg, delay=AUTO_DELETE):
    async def _d():
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except Exception as e:
            print("[AUTODEL] failed:", repr(e))
    t = asyncio.create_task(_d())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)

# ─────────────── Force Sub ───────────────
async def is_member(c, cid, uid):
    try:
        mem = await c.get_chat_member(cid, uid)
        if mem.status in (S.MEMBER, S.ADMINISTRATOR, S.OWNER):
            return True
        if mem.status == S.RESTRICTED:
            return bool(getattr(mem, "is_member", True))
        return False
    except UserNotParticipant:
        return False
    except Exception as e:
        print("[FS] member check error", cid, repr(e))
        return False

async def get_invite(c, cid):
    ch = db.data["channels"].get(str(cid))
    if not ch:
        return None
    if ch.get("invite"):
        return ch["invite"]
    try:
        l = await c.create_chat_invite_link(int(cid), name="ForceSub", creates_join_request=True)
        ch["invite"] = l.invite_link
        db.dirty = True
        return ch["invite"]
    except Exception as e:
        print("[FS] invite create failed", cid, repr(e))
    if ch.get("manual"):
        return ch["manual"]
    if ch.get("username"):
        return "https://t.me/" + ch["username"]
    return None

async def get_pending(c, uid):
    # Rule: in every 24 hrs the user must send join-requests to ANY 3 channels
    # (channels where he is already joined don't count and are never shown).
    # If fewer than 3 channels are left for him, he only needs those.
    # Returns the list of channels to SHOW; empty list = verified.
    now = time.time()
    done, avail = 0, []
    for cid in list(db.data["channels"]):
        reqs = db.data["requests"].setdefault(cid, {})
        ts = reqs.get(str(uid))
        if ts and now - ts < FS_WINDOW:
            done += 1          # valid request in last 24h (counts even if admin approved it)
            continue
        member = await is_member(c, int(cid), uid)
        if ts:
            # old request expired -> forget it; decline if still pending so he can request again
            if not member:
                try:
                    await c.decline_chat_join_request(int(cid), uid)
                except Exception:
                    pass
            reqs.pop(str(uid), None)
            db.dirty = True
        if not member:
            avail.append(cid)
    need = min(REQUIRED_REQUESTS, done + len(avail))
    print("[FS] user=%s done=%d avail=%d need=%d" % (uid, done, len(avail), need))
    if done >= need:
        return []
    return avail

async def fs_markup(c, pending, token):
    rows, n = [], 0
    for cid in pending:
        link = await get_invite(c, cid)
        if not link:
            continue
        n += 1
        rows.append([InlineKeyboardButton("Join Channel %d" % n, url=link)])
    retry = "https://t.me/%s?start=%s" % (c.me.username, token)
    rows.append([InlineKeyboardButton("♻️ Try Again", url=retry)])
    return InlineKeyboardMarkup(rows)

async def add_channel(c, cid, manual=None, username=None, title=None):
    if cid == db.sid:
        return None
    try:
        chat = await c.get_chat(cid)
        t, un = chat.title, chat.username
    except Exception as e:
        if not title:
            raise
        print("[FS] get_chat failed, using Bot API title:", repr(e))
        t, un = title, None
    old = db.data["channels"].get(str(cid), {})
    db.data["channels"][str(cid)] = {
        "title": t,
        "username": username or un,
        "manual": manual or old.get("manual"),
        "invite": old.get("invite"),
    }
    await get_invite(c, cid)
    db.dirty = True
    return t

# ─────────────── Content delivery ───────────────
async def send_setting(c, uid, key):
    ref = db.data["settings"].get(key)
    if not ref:
        return
    m = await safe(c.copy_message, uid, db.sid, ref)
    if m:
        auto_delete(m)

async def send_content(c, uid, token):
    link = db.data["links"].get(token)
    print("[SEND] uid=%s token=%s found=%s" % (uid, token, bool(link)))
    if not link:
        await c.send_message(uid, "❌ Link invalid hai ya expire ho chuka hai.")
        return
    await send_setting(c, uid, "first")
    for mid in sorted(link["ids"]):
        for attempt in range(2):
            try:
                await c.copy_message(uid, db.sid, mid, protect_content=bool(link.get("secure")))
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                print("[SEND] copy failed", mid, repr(e))
                await c.send_message(uid, "⚠️ File send nahi hui: %s" % e)
                break
        await asyncio.sleep(0.4)
    await send_setting(c, uid, "last")
