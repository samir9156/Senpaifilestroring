import io, time
from pyrogram import Client, filters
from config import ADMIN_ID
from database import db
from helpers import admin_f

DAY = 86400

@Client.on_message(filters.command("stats") & filters.private & admin_f)
async def stats(c, m):
    now = time.time()
    info = db.data["userinfo"]
    total = len(db.data["users"])
    new24 = sum(1 for v in info.values() if now - v.get("f", 0) < DAY)
    new7 = sum(1 for v in info.values() if now - v.get("f", 0) < 7 * DAY)
    act24 = sum(1 for v in info.values() if now - v.get("l", 0) < DAY)
    act7 = sum(1 for v in info.values() if now - v.get("l", 0) < 7 * DAY)
    links = db.data["links"]
    batches = sum(1 for l in links.values() if len(l.get("ids", [])) > 1)
    secured = sum(1 for l in links.values() if l.get("secure"))
    req24, req_users, req_total = 0, set(), 0
    for cid, d in db.data["requests"].items():
        for uid, ts in d.items():
            req_total += 1
            req_users.add(uid)
            if now - ts < DAY:
                req24 += 1
    txt = (
        "📊 Bot Stats\n\n"
        "👥 Total users: %d\n"
        "🆕 New users (24h / 7d): %d / %d\n"
        "🔥 Active users (24h / 7d): %d / %d\n\n"
        "🔗 Links: %d (single %d, batch %d, secured %d)\n"
        "📢 Force-Sub channels: %d\n"
        "📨 Join requests (24h / total): %d / %d\n"
        "🙋 Users who sent requests: %d\n"
        "👮 Admins: %d (+ owner)\n\n"
        "ℹ️ Purane users ka join/active time pata nahi hota, isliye New/Active me sirf naye data wale gine jate hain."
    ) % (total, new24, new7, act24, act7, len(links), len(links) - batches, batches, secured,
         len(db.data["channels"]), req24, req_total, len(req_users), len(db.data["admins"]))
    await m.reply(txt)

@Client.on_message(filters.command("users") & filters.private & admin_f)
async def users(c, m):
    info = db.data["userinfo"]
    rows = []
    for uid in db.data["users"]:
        v = info.get(str(uid), {})
        first = time.strftime("%Y-%m-%d %H:%M", time.gmtime(v["f"])) + " UTC" if v.get("f") else "-"
        rows.append((v.get("f", 0), "%s | %s | %s | %s" % (uid, v.get("n") or "-", ("@" + v["u"]) if v.get("u") else "-", first)))
    rows.sort(key=lambda x: x[0], reverse=True)
    head = "TOTAL USERS: %d\nuser_id | name | username | first seen\n%s\n" % (len(rows), "-" * 40)
    bio = io.BytesIO((head + "\n".join(r for _, r in rows)).encode())
    bio.name = "users.txt"
    await c.send_document(m.chat.id, bio, caption="👥 Total users: %d" % len(rows))
