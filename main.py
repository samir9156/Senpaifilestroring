    if not await load_storage(app):
        print("❌ Storage channel error: channel resolve nahi hua.")
        print("Check: bot us channel me ADMIN hai (post/pin/delete) aur STORAGE_CHANNEL_INPUT sahi ID hai.")
        await app.stop()
        return
    # channel private karne ke baad bhi restart par resolve ho, iske liye ID + access hash admin ko bhej do (ek baar)
    if not os.environ.get("STORAGE_ACCESS_HASH"):
        try:
            ah = getattr((await app.resolve_peer(db.sid)), "access_hash", None)
            if ah:
                await app.send_message(
                    ADMIN_ID,
                    "🔑 Channel ko private karna ho to Railway Variables me ye dono rakho:\n\n"
                    "<code>STORAGE_CHANNEL_INPUT=%s</code>\n<code>STORAGE_ACCESS_HASH=%s</code>" % (db.sid, ah))
        except Exception as e:
            print("[PEER] access hash nahi mila:", repr(e))
    asyncio.create_task(db.autosave(app))
    asyncio.create_task(poll(app))
    asyncio.create_task(delete_loop(app))
    await set_menu(app)
    try:
        await app.send_message(ADMIN_ID, "✅ Bot online! DB loaded. Channels: %d" % len(db.data["channels"]))
    except Exception as e:
        print("[WARN] Admin ko message nahi gaya (pehle bot ko /start karo):", repr(e))
    await idle()
    await db.save(app)
    await app.stop()

try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    pass
