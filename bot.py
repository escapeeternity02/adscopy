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

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        print(Fore.RED + "Resetting corrupted data.json...")
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
    print(Fore.YELLOW + "Web server running.")

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

            groups = await client.get_dialogs()
            group_dict = {g.entity.id: g.name for g in groups if g.is_group}

            target_groups = data["groups"].keys() if not data.get("allgroup") else group_dict.keys()
            print(Fore.CYAN + f"Sending ads to {len(target_groups)} group(s)...")

            for gid in target_groups:
                try:
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1
                        save_data(data)

                    await client.forward_messages(gid, msg.id, "me")
                    print(Fore.GREEN + f"Forwarded ad to {gid}")

                    data['log'].append({"time": str(datetime.now()), "group": gid})
                    save_data(data)

                    freq = data["groups"].get(str(gid), data["frequency"])
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to group {gid}: {e}")

            print(Fore.CYAN + f"Ad cycle done. Sleeping for {data['frequency']} minutes.")
            await asyncio.sleep(data["frequency"] * 60)
        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
            await asyncio.sleep(30)

async def command_handler(client):
    @client.on(events.NewMessage())
    async def handler(event):
        sender = await event.get_sender()
        is_private = event.is_private
        data = load_data()
        admins = data.get("admins", [])
        is_admin = sender.id in admins
        cmd = event.raw_text.strip()

        if not is_admin and is_private:
            for admin in admins:
                await client.send_message(admin, f"📩 *New DM*
👤 {sender.first_name} (@{sender.username})
🆔 {sender.id}
📝 {event.text}")

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

        if cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if str(gid) not in data["groups"]:
                    data["groups"][str(gid)] = data["frequency"]
                    save_data(data)
                    await event.reply(f"✅ Added group {gid}")
                else:
                    await event.reply("Group already in list.")
            except:
                await event.reply("❌ Usage: !addgroup <group_id>")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                data["groups"].pop(str(gid), None)
                save_data(data)
                await event.reply(f"✅ Removed group {gid}")
            except:
                await event.reply("❌ Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setfreq"):
            parts = cmd.split()
            try:
                if len(parts) == 2:
                    data["frequency"] = int(parts[1])
                    save_data(data)
                    await event.reply(f"✅ Global frequency set to {parts[1]} min")
                elif len(parts) == 3:
                    gid = parts[1]
                    freq = int(parts[2])
                    if gid in data["groups"]:
                        data["groups"][gid] = freq
                        save_data(data)
                        await event.reply(f"✅ Frequency for group {gid} set to {freq} min")
            except:
                await event.reply("❌ Usage: !setfreq <minutes> or !setfreq <group_id> <minutes>")

        elif cmd.startswith("!setmode"):
            try:
                mode = cmd.split()[1].lower()
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"✅ Mode set to {mode}")
                else:
                    await event.reply("❌ Use: !setmode random | order")
            except:
                await event.reply("❌ Usage: !setmode <random/order>")

        elif cmd == "!status":
            await event.reply(f"👥 Groups: {list(data['groups'].keys())}\n📤 Mode: {data['mode']}\n⏱ Global Freq: {data['frequency']} min\nAll Group: {data.get('allgroup')}")

        elif cmd == "!groups":
            groups = await client.get_dialogs()
            group_names = {g.entity.id: g.name for g in groups if g.is_group}
            lines = [f"{gid} - {group_names.get(int(gid), 'Unknown')}" for gid in data["groups"]]
            await event.reply("\n".join(lines) or "No groups added")

        elif cmd.startswith("!addadmin"):
            try:
                new_admin = int(cmd.split()[1])
                if new_admin not in admins:
                    admins.append(new_admin)
                    data["admins"] = admins
                    save_data(data)
                    await event.reply("✅ Added admin")
            except:
                await event.reply("❌ Usage: !addadmin <user_id>")

        elif cmd.startswith("!log"):
            try:
                days = int(cmd.split()[1])
                cutoff = datetime.now() - timedelta(days=days)
                logs = [l for l in data.get("log", []) if datetime.fromisoformat(l["time"]) > cutoff]
                lines = [f"{l['time']} – Group {l['group']}" for l in logs]
                await event.reply("\n".join(lines) or "No logs")
            except:
                await event.reply("❌ Usage: !log <days>")

        elif cmd == "!uptime":
            await event.reply(f"⏱ Uptime: {format_uptime()}")

        elif cmd == "!backup":
            await client.send_file(sender.id, DATA_FILE)

        elif cmd == "!restore":
            await event.reply("📩 Please reply to this message with the backup file.")

        elif cmd == "!allgroup on":
            data["allgroup"] = True
            save_data(data)
            await event.reply("✅ All-group mode ON")

        elif cmd == "!allgroup off":
            data["allgroup"] = False
            save_data(data)
            await event.reply("✅ All-group mode OFF")

        elif cmd == "!test":
            ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            if not ads.messages:
                await event.reply("❌ No saved message found.")
                return
            msg = ads.messages[0]
            for gid in data["groups"]:
                await client.forward_messages(int(gid), msg.id, "me")
                await asyncio.sleep(3)
            await event.reply("✅ Sent test ad to all selected groups.")

        elif cmd.startswith("!dm"):
            parts = cmd.split(maxsplit=2)
            if len(parts) < 3:
                await event.reply("❌ Usage: !dm <user_id/@username> <message>")
                return
            target = parts[1]
            message = parts[2]
            try:
                entity = await client.get_entity(target)
                await client.send_message(entity, message)
                await event.reply(f"✅ Message sent to {target}")
            except Exception as e:
                await event.reply(f"❌ Failed to send message: {e}")

        elif cmd == "!help":
            await event.reply(
                "🛠 Commands:\n"
                "!addgroup <id> – Add group\n!rmgroup <id> – Remove group\n!setfreq <min> | <gid> <min>\n"
                "!setmode random/order\n!status – Show status\n!groups – List groups\n!log <days> – Log\n"
                "!addadmin <id> – Add admin\n!uptime – Show uptime\n!backup – Export config\n!restore – Import config\n"
                "!allgroup on/off\n!test – Send test ad\n!dm <id/@user> <msg>\n!help – This help menu")

    @client.on(events.NewMessage())
    async def group_reply_detector(event):
        if event.is_group and event.is_reply:
            replied_msg = await event.get_reply_message()
            sender = await event.get_sender()

            if isinstance(sender, User) and sender.bot:
                return

            if replied_msg.from_id and isinstance(replied_msg.from_id, PeerUser):
                if replied_msg.from_id.user_id == (await client.get_me()).id:
                    group = await event.get_chat()
                    data = load_data()
                    for admin in data.get("admins", []):
                        try:
                            await client.send_message(
                                admin,
                                f"🆕 Someone replied to ad in {group.title}\n"
                                f"👤 User: {sender.first_name} (@{sender.username})\n"
                                f"🆔 ID: {sender.id}\n"
                                f"📝 Reply:\n{event.text}"
                            )
                        except Exception as e:
                            print(f"Failed to send DM to admin: {e}")

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

    try:
        data = load_data()
        for admin in data.get("admins", []):
            await client.send_message(admin, "✅ Bot started and running on Render.")
    except:
        print(Fore.RED + "Couldn't notify admin.")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
