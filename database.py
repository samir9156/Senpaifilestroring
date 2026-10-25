import asyncio, copy, io, json, time
from config import STORAGE, FS_WINDOW

DEFAULT = {
    "admins": [],
    "channels": {},   # cid -> {title, username, invite, manual}
    "links": {},      # token -> {ids, secure, time}
    "requests": {},   # cid -> {uid: timestamp}
    "settings": {"first": None, "last": None, "greeting": None},
    "users": [],
}

class Database:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULT)
        self.sid = None      # resolved storage channel id
        self.pin_id = None   # message id of pinned database.json
        self.dirty = False
        self.lock = asyncio.Lock()

    def _merge(self, loaded):
        for k, v in DEFAULT.items():
            val = loaded.get(k, copy.deepcopy(v))
            if k == "users" and isinstance(val, dict):
                val = [int(x) for x in val if str(x).lstrip("-").isdigit()]
            if k == "settings" and isinstance(val, dict):
                val = {**v, **val}
            if type(val) is not type(v):
                val = copy.deepcopy(v)
            self.data[k] = val

    async def load(self, c):
        chat = await c.get_chat(STORAGE)
        self.sid = chat.id
        pm = chat.pinned_message
        if pm and pm.document:
            m = await c.get_messages(self.sid, pm.id)
            f = await c.download_media(m, in_memory=True)
            loaded = json.loads(bytes(f.getbuffer()).decode())
            self._merge(loaded)
            self.pin_id = m.id
            print("[DB] Loaded from pinned message", m.id)
        else:
            print("[DB] No pinned DB found, starting fresh")
            await self.save(c)

    async def save(self, c):
        async with self.lock:
            try:
                self.dirty = False
                now = time.time()
                for cid in list(self.data["requests"]):
                    reqs = self.data["requests"][cid]
                    for uid in list(reqs):
                        if now - reqs[uid] > FS_WINDOW * 3:
                            del reqs[uid]
                raw = json.dumps(self.data, indent=1).encode()
                bio = io.BytesIO(raw)
                bio.name = "database.json"
                new = await c.send_document(self.sid, bio, caption="database.json (do not delete)")
                await c.pin_chat_message(self.sid, new.id, disable_notification=True)
                try:
                    nxt = await c.get_messages(self.sid, new.id + 1)
                    if nxt and not nxt.empty and nxt.service:
                        await nxt.delete()
                except Exception:
                    pass
                if self.pin_id:
                    try:
                        await c.delete_messages(self.sid, self.pin_id)
                    except Exception as e:
                        print("[DB] old db delete failed:", e)
                self.pin_id = new.id
                print("[DB] Saved ->", new.id)
            except Exception as e:
                self.dirty = True
                print("[DB] SAVE ERROR:", repr(e))

    async def autosave(self, c):
        while True:
            await asyncio.sleep(20)
            if self.dirty:
                await self.save(c)

    def mark_request(self, cid, uid):
        self.data["requests"].setdefault(str(cid), {})[str(uid)] = time.time()
        self.dirty = True

    def add_user(self, uid):
        if uid not in self.data["users"]:
            self.data["users"].append(uid)
            self.dirty = True

db = Database()
