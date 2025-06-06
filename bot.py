import os
import json
import asyncio
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
DATA_FILE = "data.json"
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

start_time = time.time()

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        data = {
            "groups": [],
            "frequency": 15,
            "per_group_freq": {},
            "mode": "random",
            "last_sent_ad_index": 0,
            "admins": ["@EscapeEternity"],
            "allgroup": False,
            "log": []
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Bot is running on Render")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

async def ad_sender(client):
    while True:
        data = load_data()
        ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0, offset_date=None, max_id=0, min_id=0, add_offset=0, hash=0))
        saved_messages = [m for m in ads.messages if m.message or m.media]

        if not saved_messages:
            await asyncio.sleep(60)
            continue

        target_groups = data["groups"]
        if data.get("allgroup"):
            dialogs = await client.get_dialogs()
            target_groups = [d.id for d in dialogs if d.is_group]

        for gid in target_groups:
            try:
                freq = data["per_group_freq"].get(str(gid), data["frequency"])
                if data["mode"] == "random":
                    msg = random.choice(saved_messages)
                else:
                    index = data["last_sent_ad_index"] % len(saved_messages)
                    msg = saved_messages[index]
                    data["last_sent_ad_index"] += 1
                    save_data(data)

                await client.forward_messages(gid, msg.id, "me")
                log_entry = {"group": gid, "msg_id": msg.id, "time": datetime.utcnow().isoformat()}
                data["log"].append(log_entry)
                save_data(data)
                await asyncio.sleep(random.uniform(10, 20))
            except Exception as e:
                print(Fore.RED + f"Error sending to group {gid}: {e}")

        await asyncio.sleep(data["frequency"] * 60)

async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        is_private = event.is_private
        data = load_data()
        cmd = event.raw_text.strip()
        is_admin = str(sender.id) in map(str, data.get("admins", [])) or sender.username in data.get("admins", [])

        if not is_admin and is_private:
            fwd = f"📩 *New DM Received*\n👤 Name: {sender.first_name}\n🆔 ID: {sender.id}\n🔗 Username: @{sender.username or 'N/A'}\n📝 Message:\n{event.text}"
            await client.send_message(data['admins'][0], fwd)
            return

        if not is_admin:
            return

        try:
            if cmd.startswith("!addgroup"):
                gid = int(cmd.split()[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Added group {gid}")
                else:
                    await event.reply("Group already added.")

            elif cmd.startswith("!rmgroup"):
                gid = int(cmd.split()[1])
                data["groups"] = [g for g in data["groups"] if g != gid]
                save_data(data)
                await event.reply(f"✅ Removed group {gid}")

            elif cmd.startswith("!setfreq"):
                parts = cmd.split()
                if len(parts) == 2:
                    data["frequency"] = int(parts[1])
                    save_data(data)
                    await event.reply(f"✅ Global frequency set to {parts[1]} min")
                elif len(parts) == 3:
                    gid, freq = parts[1], int(parts[2])
                    data["per_group_freq"][gid] = freq
                    save_data(data)
                    await event.reply(f"✅ Frequency for group {gid} set to {freq} min")

            elif cmd.startswith("!setmode"):
                mode = cmd.split()[1].lower()
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"✅ Mode set to {mode}")

            elif cmd == "!status":
                await event.reply(f"Mode: {data['mode']}\nGlobal Freq: {data['frequency']}\nGroups: {data['groups']}")

            elif cmd == "!groups":
                await event.reply("\n".join([str(g) for g in data["groups"]]) or "No groups added.")

            elif cmd.startswith("!addadmin"):
                aid = cmd.split()[1]
                if aid not in data["admins"]:
                    data["admins"].append(aid)
                    save_data(data)
                    await event.reply(f"✅ Added admin {aid}")

            elif cmd.startswith("!log"):
                days = int(cmd.split()[1])
                cutoff = datetime.utcnow() - timedelta(days=days)
                logs = [l for l in data["log"] if datetime.fromisoformat(l["time"]) > cutoff]
                await event.reply("📝 Logs:\n" + "\n".join([f"Group: {l['group']}, Time: {l['time']}" for l in logs]))

            elif cmd == "!uptime":
                uptime = timedelta(seconds=int(time.time() - start_time))
                await event.reply(f"⏱ Uptime: {uptime}")

            elif cmd == "!backup":
                await client.send_file(event.chat_id, DATA_FILE, caption="📦 Backup")

            elif cmd == "!restore":
                await event.reply("📤 Send the new data.json as reply to this message.")

            elif event.reply_to_msg_id:
                reply = await event.get_reply_message()
                if reply.file:
                    await reply.download_media(file=DATA_FILE)
                    await event.reply("✅ Restored backup.")

            elif cmd == "!test":
                ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0, offset_date=None, max_id=0, min_id=0, add_offset=0, hash=0))
                if ads.messages:
                    for gid in data["groups"]:
                        await client.forward_messages(gid, ads.messages[0].id, "me")
                    await event.reply("✅ Test message sent.")

            elif cmd.startswith("!allgroup"):
                mode = cmd.split()[1]
                if mode == "on":
                    data["allgroup"] = True
                else:
                    data["allgroup"] = False
                save_data(data)
                await event.reply(f"✅ Allgroup set to {data['allgroup']}")

            elif cmd == "!help":
                await event.reply(
                    "🛠 Commands:\n"
                    "!addgroup <id> – Add group\n"
                    "!rmgroup <id> – Remove group\n"
                    "!setfreq <min> – Global frequency\n"
                    "!setfreq <group_id> <min> – Per-group freq\n"
                    "!setmode random/order – Mode\n"
                    "!status – Show status\n"
                    "!groups – List groups\n"
                    "!log <days> – Show logs\n"
                    "!addadmin <user_id> – Add admin\n"
                    "!uptime – Show uptime\n"
                    "!backup – Backup config\n"
                    "!restore – Restore from file\n"
                    "!test – Send test ad\n"
                    "!allgroup on/off – Toggle all-group mode\n"
                )
        except Exception as e:
            await event.reply(f"❌ Error: {e}")

async def main():
    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print(Fore.RED + f"No credentials file at {path}")
        return

    with open(path, "r") as f:
        credentials = json.load(f)

    client = TelegramClient(
        os.path.join(CREDENTIALS_FOLDER, session_name),
        credentials["api_id"],
        credentials["api_hash"],
        proxy=tuple(credentials.get("proxy")) if credentials.get("proxy") else None
    )

    await client.connect()
    if not await client.is_user_authorized():
        print(Fore.RED + "Not logged in.")
        return

    try:
        admin_entity = await client.get_entity(load_data()["admins"][0])
        await client.send_message(admin_entity, "✅ Bot started and running on Render.")
    except Exception as e:
        print(Fore.RED + f"Couldn't notify admin: {e}")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
