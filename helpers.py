import asyncio, secrets, time
import requests
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as S
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import (InlineKeyboardMarkup, InlineKeyboardButton, BotCommand,
                            BotCommandScopeDefault, BotCommandScopeChat)
from config import ADMIN_ID, BOT_TOKEN, FS_WINDOW, AUTO_DELETE, REQUIRED_REQUESTS
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
def _bot_api(method, params):
    r = requests.post("https://api.telegram.org/bot%s/%s" % (BOT_TOKEN, method), json=params, timeout=20)
    return r.json()

async def is_member(c, cid, uid):
    # 1) Bot API getChatMember: most reliable (no Pyrogram peer-cache problems)
    try:
        res = await asyncio.to_thread(_bot_api, "getChatMember", {"chat_id": cid, "user_id": uid})
        if res.get("ok"):
            r = res["result"]
            st = r.get("status")
            ok = st in ("creator", "administrator", "member") or (st == "restricted" and bool(r.get("is_member")))
            print("[FS] member check ch=%s user=%s status=%s -> %s" % (cid, uid, st, ok))
            return ok
        print("[FS] BotAPI getChatMember failed ch=%s user=%s: %s" % (cid, uid, res.get("description")))
    except Exception as e:
        print("[FS] BotAPI error:", repr(e))
    # 2) fallback: Pyrogram
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
    # RULE (rolling 24 hrs):
    #  - user must send join-requests to 3 NEW channels per 24 hrs
    #  - joined channels / already requested channels are NEVER counted or shown
    #  - only what is really left is shown (max 3 - done today). 1 or 2 left -> only 1 or 2
    #  - nothing left -> free access
    # Returns the list of channels to SHOW; empty list = verified.
    now = time.time()
    reqs_all = db.data["requests"]
    recent = 0
    for cid in db.data["channels"]:
        ts = reqs_all.get(cid, {}).get(str(uid))
        if ts and now - ts < FS_WINDOW:
            recent += 1
    if recent >= REQUIRED_REQUESTS:
        return []
    need = REQUIRED_REQUESTS - recent
    cands = [cid for cid in db.data["channels"] if not reqs_all.get(cid, {}).get(str(uid))]
    flags = await asyncio.gather(*[is_member(c, int(cid), uid) for cid in cands]) if cands else []
    avail = [cid for cid, joined in zip(cands, flags) if not joined][:need]
    print("[FS] user=%s recent=%d candidates=%d joined=%d show=%d" % (uid, recent, len(cands), sum(1 for f in flags if f), len(avail)))
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

# ─────────────── Bot command menu ───────────────
USER_CMDS = [BotCommand("start", "Start the bot")]
ADMIN_CMDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("genlink1", "Single file - shareable link"),
    BotCommand("genlink2", "Single file - secured link (no forward/save)"),
    BotCommand("batch1", "Multiple files - shareable link"),
    BotCommand("batch2", "Multiple files - secured link"),
    BotCommand("done", "Finish current batch / channel session"),
    BotCommand("cancel", "Cancel current session"),
    BotCommand("addchannel", "Add Force-Sub channels"),
    BotCommand("deletechannels", "Remove Force-Sub channels"),
    BotCommand("channels", "List Force-Sub channels"),
    BotCommand("checkuser", "Check a user: joined / requested / pending"),
    BotCommand("setfirstmessage", "Set message shown before files"),
    BotCommand("setlastmessage", "Set message shown after files"),
    BotCommand("setgreeting", "Set greeting for normal /start"),
    BotCommand("clearmessage", "Remove first / last / greeting message"),
]
OWNER_CMDS = ADMIN_CMDS + [
    BotCommand("addauthedit", "Make a user admin"),
    BotCommand("delauth", "Remove a user from admins"),
]
_menu_done = set()

async def set_menu(c, uid=None, force=False):
    # uid=None -> default menu for everyone + owner menu. Else menu for that admin.
    try:
        if uid is None:
            await c.set_bot_commands(USER_CMDS, scope=BotCommandScopeDefault())
            uid = ADMIN_ID
        if uid in _menu_done and not force:
            return
        cmds = OWNER_CMDS if uid == ADMIN_ID else ADMIN_CMDS
        await c.set_bot_commands(cmds, scope=BotCommandScopeChat(chat_id=uid))
        _menu_done.add(uid)
        print("[MENU] commands set for", uid)
    except Exception as e:
        print("[MENU] set failed for", uid, repr(e))
