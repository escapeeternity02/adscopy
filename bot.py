# bot.py
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
ADMIN_IDS = [6249999953]  # Add multiple admin IDs here
START_TIME = time.time()

os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

# ========== Data Handling ==========
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        print(Fore.RED + "Resetting corrupted data.json...")
        data = {
            "groups": [],
            "frequency": 15,
            "per_group_freq": {},
            "mode": "random",
            "last_sent_ad_index": 0,
            "admins": ADMIN_IDS,
            "allgroup": False,
            "log": []
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ========== Web Server ==========
async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Bot is running on Render")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    print(Fore.YELLOW + "Web server running.")

# ========== Ad Sender ==========
async def ad_sender(client):
    while True:
        try:
            data = load_data()
            ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            saved_messages = [m for m in ads.messages if m.message or m.media]

            if not saved_messages:
                print(Fore.RED + "No saved messages found.")
                await asyncio.sleep(60)
                continue

            group_ids = data['groups']
            if data.get("allgroup"):
                dialogs = await client.get_dialogs()
                group_ids = [d.entity.id for d in dialogs if d.is_group]

            print(Fore.CYAN + f"Sending ads to {len(group_ids)} group(s)...")
            for gid in group_ids:
                try:
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1

                    await client.forward_messages(gid, msg.id, "me")
                    print(Fore.GREEN + f"Forwarded ad to {gid}")

                    data['log'].append({"time": time.time(), "group": gid, "msg_id": msg.id})
                    save_data(data)

                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to group {gid}: {e}")

            save_data(data)
            await asyncio.sleep(data['frequency'] * 60)
        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
            await asyncio.sleep(30)

# ========== Command Handler ==========
async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        is_admin = sender.id in load_data().get("admins", [])
        is_private = event.is_private
        cmd = event.raw_text.strip()
        data = load_data()

        if not is_admin and is_private:
            msg = f"📩 *New DM Received*\n👤 Name: {sender.first_name}\n🆔 User ID: {sender.id}\n🔗 Username: @{sender.username or 'N/A'}\n📝 Message:\n{cmd}"
            await client.send_message(ADMIN_IDS[0], msg)
            return

        if not is_admin:
            return

        parts = cmd.split()
        if cmd.startswith("!addgroup"):
            try:
                gid = int(parts[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Added group {gid}")
                else:
                    await event.reply("Group already added.")
            except:
                await event.reply("❌ Usage: !addgroup <group_id>")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(parts[1])
                data["groups"] = [g for g in data["groups"] if g != gid]
                save_data(data)
                await event.reply(f"✅ Removed group {gid}")
            except:
                await event.reply("❌ Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setfreq"):
            if len(parts) == 2:
                try:
                    freq = int(parts[1])
                    data["frequency"] = freq
                    save_data(data)
                    await event.reply(f"✅ Global frequency set to {freq} minutes")
                except:
                    await event.reply("❌ Usage: !setfreq <minutes>")
            elif len(parts) == 3:
                try:
                    gid = int(parts[1])
                    freq = int(parts[2])
                    data["per_group_freq"][str(gid)] = freq
                    save_data(data)
                    await event.reply(f"✅ Frequency for group {gid} set to {freq} minutes")
                except:
                    await event.reply("❌ Usage: !setfreq <group_id> <minutes>")

        elif cmd.startswith("!setmode"):
            mode = parts[1].lower()
            if mode in ["random", "order"]:
                data["mode"] = mode
                save_data(data)
                await event.reply(f"✅ Mode set to {mode}")
            else:
                await event.reply("❌ Use: !setmode random | order")

        elif cmd == "!status":
            await event.reply(f"👥 Groups: {data['groups']}\n📤 Mode: {data['mode']}\n⏱ Frequency: {data['frequency']} min\n🌐 AllGroup: {data['allgroup']}")

        elif cmd == "!groups":
            await event.reply("📋 Current groups:\n" + "\n".join(map(str, data["groups"])))

        elif cmd.startswith("!log"):
            try:
                days = int(parts[1])
                since = time.time() - (days * 86400)
                logs = [l for l in data['log'] if l['time'] > since]
                lines = [f"🕒 {datetime.fromtimestamp(l['time'])} | Group: {l['group']} | MsgID: {l['msg_id']}" for l in logs]
                await event.reply("\n".join(lines) or "No logs found.")
            except:
                await event.reply("❌ Usage: !log <days>")

        elif cmd.startswith("!addadmin"):
            try:
                uid = int(parts[1])
                if uid not in data['admins']:
                    data['admins'].append(uid)
                    save_data(data)
                    await event.reply(f"✅ Added admin {uid}")
                else:
                    await event.reply("Already an admin.")
            except:
                await event.reply("❌ Usage: !addadmin <user_id>")

        elif cmd == "!uptime":
            uptime = str(timedelta(seconds=int(time.time() - START_TIME)))
            await event.reply(f"⏱ Uptime: {uptime}")

        elif cmd == "!backup":
            await client.send_file(sender.id, DATA_FILE)

        elif cmd == "!restore":
            await event.reply("📥 Send the backup file now.")
            response = await client.wait_for(events.NewMessage(from_users=sender.id))
            if response.file:
                await response.download_media(file=DATA_FILE)
                await event.reply("✅ Data restored.")

        elif cmd == "!allgroup on":
            data['allgroup'] = True
            save_data(data)
            await event.reply("✅ All groups mode ON")

        elif cmd == "!allgroup off":
            data['allgroup'] = False
            save_data(data)
            await event.reply("✅ All groups mode OFF")

        elif cmd == "!help":
            await event.reply(
                "🛠 Available Commands:\n"
                "!addgroup <id> – Add group ID\n"
                "!rmgroup <id> – Remove group ID\n"
                "!setfreq <min> or !setfreq <group_id> <min>\n"
                "!setmode random/order\n"
                "!status – View settings\n"
                "!groups – List groups\n"
                "!log <days> – Show ad log\n"
                "!addadmin <id> – Add admin\n"
                "!uptime – Show uptime\n"
                "!backup / !restore – Manage backup\n"
                "!allgroup on/off – Toggle all-group mode\n"
                "!help – Show this menu"
            )

        elif cmd == "!join" and event.is_group:
            gid = event.chat_id
            if gid not in data['groups']:
                data['groups'].append(gid)
                save_data(data)
                await event.reply("✅ This group has been added to the ad list.")

# ========== Main ==========
async def main():
    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print(Fore.RED + f"No credentials file at {path}")
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

    await client.connect()
    if not await client.is_user_authorized():
        print(Fore.RED + "Not logged in.")
        return

    await client.send_message(ADMIN_IDS[0], "✅ Bot started and running on Render.")
    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
