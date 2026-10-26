import asyncio, time
from database import db
from helpers import safe

# persistent auto-delete: entries live in the DB, so a restart does not lose them
async def delete_loop(c):
    print("[TIMER] delete loop started")
    while True:
        await asyncio.sleep(20)
        try:
            now = time.time()
            due = [e for e in db.data["pending_del"] if e["t"] <= now]
            if not due:
                continue
            db.data["pending_del"] = [e for e in db.data["pending_del"] if e["t"] > now]
            db.dirty = True
            for e in due:
                ids = e["i"]
                for i in range(0, len(ids), 100):
                    await safe(c.delete_messages, e["c"], ids[i:i + 100])
            print("[TIMER] deleted %d batches, %d left" % (len(due), len(db.data["pending_del"])))
        except Exception as ex:
            print("[TIMER] loop error:", repr(ex))
