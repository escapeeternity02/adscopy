import os
import json
import asyncio
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.tl.types import MessageEntityBotCommand, PeerUser, User
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
DATA_FILE = "data.json"
START_TIME = time.time()

os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

client = None

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if isinstance(data.get("groups"), list):
                data["groups"] = {str(gid): 15 for gid in data["groups"]}
                save_data(data)
            if "log" not in data:
                data["log"] = []
            return data
    except:
        data = {
            "groups": {},
            "frequency": 15,
            "mode": "random",
            "last_sent_ad_index": 0,
            "admins": [6249999953],
            "allgroup": False,
            "log": []
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def format_uptime():
    uptime = time.time() - START_TIME
    return str(timedelta(seconds=int(uptime)))

async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Bot is running on Render")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

async def ad_sender():
    global client
    while True:
        try:
            data = load_data()
            ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            saved_messages = [m for m in ads.messages if m.message or m.media]

            if not saved_messages:
                await asyncio.sleep(60)
                continue

            dialogs = await client.get_dialogs()
            group_dict = {str(g.entity.id): g.name for g in dialogs if g.is_group}

            target_groups = data["groups"].keys() if not data.get("allgroup") else group_dict.keys()
            if not target_groups:
                print(Fore.YELLOW + "No groups to send ads.")
                await asyncio.sleep(60)
                continue

            for gid in target_groups:
                try:
                    gid_str = str(gid)
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1
                        save_data(data)

                    await client.forward_messages(int(gid), msg.id, "me")
                    data['log'].append({"time": str(datetime.now()), "group": gid_str})
                    save_data(data)

                    freq = data["groups"].get(gid_str, data["frequency"])
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to {gid}: {e}")
                    continue

            await asyncio.sleep(data["frequency"] * 60)
        except Exception as e:
            print(Fore.RED + f"ad_sender error: {e}")
            await asyncio.sleep(30)

async def command_handler():
    global client

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        if sender is None:
            return

        is_private = event.is_private
        data = load_data()
        admins = data.get("admins", [])
        is_admin = sender.id in admins
        cmd_text = event.raw_text.strip()
        cmd_parts = cmd_text.split()
        cmd = cmd_parts[0].lower() if cmd_parts else ""

        if not is_admin and is_private:
            for admin in admins:
                try:
                    await client.send_message(admin, f"📩 New DM\n👤 {sender.first_name} (@{sender.username})\n🆔 {sender.id}\n📝 {event.text}")
                except:
                    pass

            await event.reply(
                "👋 Welcome! I am a promotional bot.\nIf you’re interested in buying, choose an option below 👇",
                buttons=[
                    [Button.url("💸 Buy Now", "https://t.me/EscapeEternity")],
                    [Button.url("📞 Contact Admin", "https://t.me/EscapeEternity")]
                ]
            )
            return

        if not is_admin:
            return

        if cmd == "!help":
            help_text = (
                "🛠️ *Bot Commands:*\n"
                "!addgroup <group_id> - Add group\n"
                "!rmgroup <group_id> - Remove group\n"
                "!setfreq <minutes> - Set global freq\n"
                "!setfreq <group_id> <minutes> - Per-group freq\n"
                "!setmode random/order - Set ad mode\n"
                "!status - Show status\n"
                "!groups - List all groups\n"
                "!log <days> - Show logs\n"
                "!addadmin <user_id> - Add admin\n"
                "!uptime - Show uptime\n"
                "!backup - Send backup\n"
                "!restore - Restore from file\n"
                "!allgroup on/off - Toggle all-group mode\n"
                "!test - Forward latest ad to you\n"
                "!dm <user_id> <text> - Send DM to user"
            )
            await event.reply(help_text)

        elif cmd == "!dm" and len(cmd_parts) >= 3:
            uid = int(cmd_parts[1])
            msg = " ".join(cmd_parts[2:])
            try:
                await client.send_message(uid, msg)
                await event.reply("✅ DM sent.")
            except:
                await event.reply("❌ Failed to send DM.")

        elif cmd == "!test":
            ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            latest_msg = next((m for m in ads.messages if m.message or m.media), None)
            if latest_msg:
                await client.forward_messages(sender.id, latest_msg.id, "me")
            else:
                await event.reply("No saved messages found.")

        elif cmd == "!addgroup" and len(cmd_parts) == 2:
            gid = cmd_parts[1]
            data["groups"][gid] = data["frequency"]
            save_data(data)
            await event.reply(f"✅ Group {gid} added.")

        elif cmd == "!rmgroup" and len(cmd_parts) == 2:
            gid = cmd_parts[1]
            data["groups"].pop(gid, None)
            save_data(data)
            await event.reply(f"❌ Group {gid} removed.")

        elif cmd == "!setfreq" and len(cmd_parts) in [2, 3]:
            if len(cmd_parts) == 2:
                data["frequency"] = int(cmd_parts[1])
                save_data(data)
                await event.reply("✅ Global frequency updated.")
            else:
                gid = cmd_parts[1]
                freq = int(cmd_parts[2])
                data["groups"][gid] = freq
                save_data(data)
                await event.reply(f"✅ Frequency for group {gid} set to {freq}.")

        elif cmd == "!setmode" and len(cmd_parts) == 2:
            if cmd_parts[1] in ["random", "order"]:
                data["mode"] = cmd_parts[1]
                save_data(data)
                await event.reply(f"✅ Mode set to {cmd_parts[1]}.")

        elif cmd == "!status":
            text = (
                f"🔧 Mode: {data['mode']}\n"
                f"🕒 Global Frequency: {data['frequency']}\n"
                f"📢 Groups: {len(data['groups'])}\n"
                f"🌐 AllGroup: {'ON' if data.get('allgroup') else 'OFF'}")
            await event.reply(text)

        elif cmd == "!groups":
            groups = data.get("groups", {})
            if not groups:
                await event.reply("No groups added.")
            else:
                await event.reply("\n".join([f"{k}: {v} min" for k, v in groups.items()]))

        elif cmd == "!log" and len(cmd_parts) == 2:
            try:
                days = int(cmd_parts[1])
                cutoff = datetime.now() - timedelta(days=days)
                logs = [entry for entry in data.get("log", []) if datetime.fromisoformat(entry["time"]) > cutoff]
                out = f"📝 Logs (last {days} days):\n" + "\n".join([f"{l['time']} -> {l['group']}" for l in logs])
                await event.reply(out or "No logs found.")
            except:
                await event.reply("Invalid log command.")

        elif cmd == "!uptime":
            await event.reply(f"⏱️ Uptime: {format_uptime()}")

        elif cmd == "!addadmin" and len(cmd_parts) == 2 and cmd_parts[1].isdigit():
            uid = int(cmd_parts[1])
            if uid not in data["admins"]:
                data["admins"].append(uid)
                save_data(data)
                await event.reply("✅ Admin added.")
            else:
                await event.reply("User is already admin.")

        elif cmd == "!backup":
            await client.send_file(sender.id, DATA_FILE)

        elif cmd == "!restore" and event.is_reply:
            file = await event.get_reply_message()
            if file and file.file:
                await file.download_media(file=DATA_FILE)
                await event.reply("✅ Data restored.")

        elif cmd == "!allgroup" and len(cmd_parts) == 2:
            if cmd_parts[1] == "on":
                data["allgroup"] = True
                save_data(data)
                await event.reply("✅ Allgroup mode ON")
            elif cmd_parts[1] == "off":
                data["allgroup"] = False
                save_data(data)
                await event.reply("✅ Allgroup mode OFF")

async def main():
    global client

    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print("❌ No credentials found.")
        return

    with open(path, "r") as f:
        credentials = json.load(f)

    proxy_args = tuple(credentials.get("proxy")) if credentials.get("proxy") else None
    client = TelegramClient(
        os.path.join(CREDENTIALS_FOLDER, session_name),
        credentials["api_id"],
        credentials["api_hash"],
        proxy=proxy_args
    )

    await client.start()

    try:
        data = load_data()
        for admin in data.get("admins", []):
            await client.send_message(admin, "✅ Bot started and running on Render.")
    except:
        pass

    await asyncio.gather(
        start_web_server(),
        command_handler(),
        ad_sender()
    )

if __name__ == "__main__":
    asyncio.run(main())
