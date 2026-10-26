import asyncio, html as _html, re, secrets, time
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

# errors that mean the CHANNEL is dead for us (deleted / bot kicked / bot not admin)
DEAD_HINTS = ("chat not found", "kicked", "not a member", "member list is inaccessible",
              "not enough rights", "chat_admin_required", "bot is not")
DEAD_ERR_NAMES = {"ChannelPrivate", "ChatAdminRequired", "ChannelInvalid"}

async def is_member(c, cid, uid):
    # returns True (joined) / False (not joined) / None (channel is dead -> ignore it)
    try:
        res = await asyncio.to_thread(_bot_api, "getChatMember", {"chat_id": cid, "user_id": uid})
        if res.get("ok"):
            r = res["result"]
            st = r.get("status")
            ok = st in ("creator", "administrator", "member") or (st == "restricted" and bool(r.get("is_member")))
            print("[FS] member check ch=%s user=%s status=%s -> %s" % (cid, uid, st, ok))
            return ok
        desc = (res.get("description") or "").lower()
        print("[FS] BotAPI getChatMember failed ch=%s user=%s: %s" % (cid, uid, desc))
        if any(h in desc for h in DEAD_HINTS):
            return None
    except Exception as e:
        print("[FS] BotAPI error:", repr(e))
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
        if type(e).__name__ in DEAD_ERR_NAMES:
            return None
        print("[FS] member check error", cid, repr(e))
        return False

async def channel_alive(c, cid):
    # (True, "ok") | (False, reason) | (None, error) -> None means "could not check", never delete
    try:
        res = await asyncio.to_thread(_bot_api, "getChatMember", {"chat_id": int(cid), "user_id": c.me.id})
        if not res.get("ok"):
            return False, res.get("description", "error")
        st = res["result"].get("status")
        if st in ("administrator", "creator"):
            return True, "ok"
        return False, "bot admin nahi hai (%s)" % st
    except Exception as e:
        return None, repr(e)

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
    #  - DEAD channels (deleted / bot removed / bot not admin) are ignored completely
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
    dead = [cid for cid, f in zip(cands, flags) if f is None]
    avail = [cid for cid, f in zip(cands, flags) if f is False][:need]
    print("[FS] user=%s recent=%d candidates=%d joined=%d dead=%d show=%d" %
          (uid, recent, len(cands), sum(1 for f in flags if f is True), len(dead), len(avail)))
    if dead:
        print("[FS] ignoring dead channels (use /cleanchannels):", dead)
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
def fill_text(txt, user, bot_name):
    # placeholders usable in first / last / greeting messages
    first = _html.escape(getattr(user, "first_name", None) or "friend")
    last = _html.escape(getattr(user, "last_name", None) or "")
    uname = getattr(user, "username", None)
    uid = getattr(user, "id", None)
    rep = {
        "{first}": first,
        "{last}": last,
        "{name}": (first + " " + last).strip(),
        "{mention}": ('<a href="tg://user?id=%s">%s</a>' % (uid, first)) if uid else first,
        "{username}": _html.escape("@" + uname) if uname else first,
        "{id}": str(uid or ""),
        "{bot}": _html.escape(bot_name or "Bot"),
    }
    for k, v in rep.items():
        txt = txt.replace(k, v)
    return txt

async def send_setting(c, uid, key, user=None):
    ref = db.data["settings"].get(key)
    if not ref:
        return
    if user is None:
        try:
            user = await c.get_users(uid)
        except Exception:
            user = None
    msg = None
    try:
        src = await c.get_messages(db.sid, ref)
        bot = c.me.first_name or "Bot"
        if src and not src.empty and src.text and "{" in src.text:
            msg = await c.send_message(uid, fill_text(src.text.html, user, bot), disable_web_page_preview=True)
        elif src and not src.empty and src.caption and "{" in src.caption:
            msg = await c.copy_message(uid, db.sid, ref, caption=fill_text(src.caption.html, user, bot))
    except Exception as e:
        print("[SETTING] personalise failed, sending plain:", repr(e))
        msg = None
    if msg is None:
        msg = await safe(c.copy_message, uid, db.sid, ref)
    if msg:
        auto_delete(msg)

# ─────────────── Timer (auto-delete of delivered files) ───────────────
MAX_TIMER = 2 * 86400            # 2d (Telegram lets bots delete only messages < 48h old)
TIMER_SAFETY = 600               # 2d is really executed ~10 min early so deletion still works

def parse_timer(text):
    # returns seconds, 0 = skip, None = not understood
    t = (text or "").strip().lower()
    if t in ("skip", "/skip", "no", "none", "off", "0"):
        return 0
    m = re.fullmatch(r"(\d+)\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes)?", t)
    if not m:
        return None
    n = int(m.group(1))
    u = m.group(2) or "m"
    return n * (86400 if u.startswith("d") else 3600 if u.startswith("h") else 60)

def fmt_timer(sec):
    if sec % 86400 == 0:
        d = sec // 86400
        return "%d day%s (%d hrs)" % (d, "" if d == 1 else "s", d * 24)
    if sec >= 3600 and sec % 3600 == 0:
        return "%d hr" % (sec // 3600)
    return "%d min" % max(1, sec // 60)

TIMER_HELP = ("⏱ Auto-delete timer set karo (user ko jaane ke baad files itne time me delete ho jayengi).\n\n"
              "Minutes bhejo: 1, 10, 30, 60, 70, 80, 90 ...\n"
              "1d = 24 hrs, 2d = 48 hrs\n\n"
              "Timer nahi chahiye to: skip")

async def ask_timer(c, chat_id, junk):
    p = await c.send_message(chat_id, TIMER_HELP)
    junk.append(p.id)
    for _ in range(3):
        try:
            r = await c.listen(chat_id, timeout=180)
        except Exception:
            return 0
        junk.append(r.id)
        if (r.text or "").strip().lower().startswith("/cancel"):
            return 0
        sec = parse_timer(r.text)
        if sec is None:
            e = await c.send_message(chat_id, "⚠️ Samajh nahi aaya. Example: 10 , 90 , 1d , 2d ya skip")
            junk.append(e.id)
            continue
        if sec > MAX_TIMER:
            e = await c.send_message(chat_id, "⚠️ Max 2d (48 hrs) tak hi ho sakta hai (Telegram limit). Dobara bhejo.")
            junk.append(e.id)
            continue
        return sec
    return 0

async def send_content(c, uid, token, user=None):
    link = db.data["links"].get(token)
    print("[SEND] uid=%s token=%s found=%s" % (uid, token, bool(link)))
    if not link:
        await c.send_message(uid, "❌ Link invalid hai ya expire ho chuka hai.")
        return
    await send_setting(c, uid, "first", user)
    sent = []
    for mid in sorted(link["ids"]):
        for attempt in range(2):
            try:
                m = await c.copy_message(uid, db.sid, mid, protect_content=bool(link.get("secure")))
                if m is not None and getattr(m, "id", None):
                    sent.append(m.id)
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                print("[SEND] copy failed", mid, repr(e))
                await c.send_message(uid, "⚠️ File send nahi hui: %s" % e)
                break
        await asyncio.sleep(0.4)
    timer = int(link.get("timer") or 0)
    if timer and sent:
        try:
            n = await c.send_message(uid, "⏳ <b>Note:</b> Ye files %s me delete ho jayengi. Forward ya save kar lo." % fmt_timer(timer))
            sent.append(n.id)
        except Exception as e:
            print("[SEND] timer note failed:", repr(e))
        delay = min(timer, MAX_TIMER - TIMER_SAFETY) if timer >= MAX_TIMER else timer
        db.schedule_delete(uid, sent, delay)
        print("[TIMER] scheduled delete of %d msgs for user %s in %ss" % (len(sent), uid, delay))
    await send_setting(c, uid, "last", user)

# ─────────────── Buttons ───────────────
def norm_url(u):
    u = u.strip()
    if u.startswith("@") and len(u) > 1:
        return "https://t.me/" + u[1:]
    if re.match(r"^(https?|tg)://", u, re.I):
        return u
    if u.lower().startswith(("t.me/", "telegram.me/")):
        return "https://" + u
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/\S*)?$", u, re.I):
        return "https://" + u
    return None

def parse_buttons(text):
    # one line = one row, "&&" = more buttons in the same row. Format: Text - link
    rows = []
    for line in (text or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        row = []
        for part in line.split("&&"):
            part = part.strip()
            if " - " in part:
                t, u = part.rsplit(" - ", 1)
            elif "|" in part:
                t, u = part.rsplit("|", 1)
            else:
                return None
            t, url = t.strip(), norm_url(u)
            if not t or not url:
                return None
            row.append([t, url])
        rows.append(row)
    return rows or None

def buttons_markup(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, url=u) for t, u in r] for r in rows])

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
    BotCommand("cleanchannels", "Remove dead / expired Force-Sub channels"),
    BotCommand("refreshlinks", "Create fresh join-request links"),
    BotCommand("stats", "Users, links, channels, requests count"),
    BotCommand("button", "Button bot: add buttons to a post"),
    BotCommand("autobutton", "Auto buttons on every new channel post"),
    BotCommand("users", "Download user list (txt)"),
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
