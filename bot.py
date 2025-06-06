import os
import json
import asyncio
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, errors
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import PeerUser, User
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
            # Fix old groups list format if needed
            if isinstance(data.get("groups"), list):
                data["groups"] = {str(gid): 15 for gid in data["groups"]}
                save_data(data)
            # Ensure required keys exist
            defaults = {
                "groups": {},
                "frequency": 15,
                "mode": "random",
                "last_sent_ad_index": 0,
                "admins": [6249999953],
                "allgroup": False,
                "log": []
            }
            for k,v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(Fore.RED + f"Resetting corrupted data.json: {e}")
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
        json.dump(data, f, indent=2)

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

async def ad_sender():
    global client
    while True:
        try:
            data = load_data()
            ads = await client(GetHistoryRequest(peer="me", limit=50, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            saved_messages = [m for m in ads.messages if m.message or m.media]
            if not saved_messages:
                print(Fore.RED + "No saved messages found.")
                await asyncio.sleep(60)
                continue

            dialogs = await client.get_dialogs()
            group_dict = {str(g.entity.id): g.name for g in dialogs if g.is_group}

            if data.get("allgroup"):
                target_groups = group_dict.keys()
            else:
                target_groups = list(data["groups"].keys())

            if not target_groups:
                print(Fore.YELLOW + "No groups to send ads.")
                await asyncio.sleep(60)
                continue

            print(Fore.CYAN + f"Sending ads to {len(target_groups)} group(s)...")

            now = datetime.now()
            sent_today = {}  # group_id -> count today
            # Count how many ads sent today per group from logs
            for entry in data["log"]:
                t = datetime.fromisoformat(entry["time"])
                if (now - t).days == 0:
                    gid = entry.get("group")
                    sent_today[gid] = sent_today.get(gid, 0) + 1

            for gid_str in target_groups:
                try:
                    gid = int(gid_str)
                    freq_min = data["groups"].get(gid_str, data["frequency"])
                    # Limit max 75 messages per day per group (as example)
                    if sent_today.get(gid_str, 0) >= 75:
                        print(Fore.YELLOW + f"Group {gid_str} reached daily message limit.")
                        continue

                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:  # order mode
                        idx = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[idx]
                        data["last_sent_ad_index"] = (data["last_sent_ad_index"] + 1) % len(saved_messages)
                        save_data(data)

                    await client.forward_messages(gid, msg.id, "me")
                    print(Fore.GREEN + f"Forwarded ad to {gid_str}")

                    data['log'].append({"time": datetime.now().isoformat(), "group": gid_str})
                    save_data(data)

                    # Random delay between 10 and 20 seconds before next group
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to group {gid_str}: {e}")

            print(Fore.CYAN + f"Ad cycle done. Sleeping for {data['frequency']} minutes.")
            await asyncio.sleep(data["frequency"] * 60)

        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
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
        cmd = cmd_text.split(maxsplit=1)[0].lower()
        args = cmd_text[len(cmd):].strip() if len(cmd_text) > len(cmd) else ""

        # Non-admin private message handler
        if not is_admin and is_private:
            # Forward message to all admins
            for admin in admins:
                try:
                    await client.send_message(admin, f"📩 *New DM*\n👤 {sender.first_name} (@{sender.username})\n🆔 {sender.id}\n📝 {event.text}")
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
            return  # ignore non-admin commands

        # Admin commands start here

        if cmd == "!help":
            help_text = (
                "**Available commands:**\n"
                "!addgroup <group_id> - Adds a group to the ad list\n"
                "!rmgroup <group_id> - Removes a group\n"
                "!setfreq <minutes> - Sets global ad frequency\n"
                "!setfreq <group_id> <minutes> - Sets frequency for a specific group\n"
                "!setmode random/order - Switches ad sending mode\n"
                "!status - Shows current mode, groups, and global frequency\n"
                "!groups - Lists all added group IDs\n"
                "!log <days> - Shows logs of ad sends in last N days\n"
                "!addadmin <user_id> - Adds another admin\n"
                "!uptime - Shows how long the bot has been running\n"
                "!backup - Sends the data.json backup\n"
                "!restore - Waits for file reply and restores data.json\n"
                "!join - Add group from group itself\n"
                "!allgroup on/off - Enable/disable forwarding to all groups\n"
            )
            await event.reply(help_text)
            return

        elif cmd == "!addgroup":
            if not args.isdigit():
                await event.reply("Usage: !addgroup <group_id>")
                return
            gid = args
            if gid in data["groups"]:
                await event.reply(f"Group `{gid}` is already added.")
                return
            data["groups"][gid] = data["frequency"]
            save_data(data)
            await event.reply(f"✅ Group `{gid}` added with frequency {data['frequency']} minutes.")

        elif cmd == "!rmgroup":
            if not args.isdigit():
                await event.reply("Usage: !rmgroup <group_id>")
                return
            gid = args
            if gid not in data["groups"]:
                await event.reply(f"Group `{gid}` is not in the list.")
                return
            data["groups"].pop(gid)
            save_data(data)
            await event.reply(f"✅ Group `{gid}` removed.")

        elif cmd == "!setfreq":
            parts = args.split()
            if len(parts) == 1:
                # set global frequency
                try:
                    freq = int(parts[0])
                    if freq < 1:
                        await event.reply("Frequency must be >= 1 minute.")
                        return
                    data["frequency"] = freq
                    save_data(data)
                    await event.reply(f"✅ Global frequency set to {freq} minutes.")
                except:
                    await event.reply("Usage: !setfreq <minutes> or !setfreq <group_id> <minutes>")
            elif len(parts) == 2:
                gid, freq_str = parts
                if not gid.isdigit() or not freq_str.isdigit():
                    await event.reply("Usage: !setfreq <minutes> or !setfreq <group_id> <minutes>")
                    return
                freq = int(freq_str)
                if freq < 1:
                    await event.reply("Frequency must be >= 1 minute.")
                    return
                data["groups"][gid] = freq
                save_data(data)
                await event.reply(f"✅ Frequency for group `{gid}` set to {freq} minutes.")
            else:
                await event.reply("Usage: !setfreq <minutes> or !setfreq <group_id> <minutes>")

        elif cmd == "!setmode":
            mode = args.lower()
            if mode not in ("random", "order"):
                await event.reply("Usage: !setmode random / order")
                return
            data["mode"] = mode
            save_data(data)
            await event.reply(f"✅ Mode set to `{mode}`.")

        elif cmd == "!status":
            groups = data.get("groups", {})
            group_list = "\n".join(f"{gid} : {freq} min" for gid, freq in groups.items()) or "No groups added."
            status_text = (
                f"**Bot Status**\n"
                f"Mode: {data.get('mode')}\n"
                f"Global frequency: {data.get('frequency')} minutes\n"
                f"Groups ({len(groups)}):\n{group_list}\n"
                f"All group forwarding: {'ON' if data.get('allgroup') else 'OFF'}"
            )
            await event.reply(status_text)

        elif cmd == "!groups":
            groups = data.get("groups", {})
            if not groups:
                await event.reply("No groups added.")
                return
            text = "📋 *Group List:*\n"
            dialogs = await client.get_dialogs()
            names_map = {str(d.entity.id): d.name for d in dialogs if d.is_group}
            for gid, freq in groups.items():
                name = names_map.get(gid, "Unknown")
                text += f"{name} — `{gid}` (Freq: {freq} min)\n"
            await event.reply(text)

        elif cmd == "!log":
            try:
                days = int(args) if args else 1
                now = datetime.now()
                cutoff = now - timedelta(days=days)
                logs = [entry for entry in data.get("log", []) if datetime.fromisoformat(entry["time"]) >= cutoff]
                if not logs:
                    await event.reply(f"No logs in last {days} day(s).")
                    return
                text = f"📜 Logs for last {days} day(s):\n"
                for entry in logs[-50:]:  # last 50 logs max
                    t = datetime.fromisoformat(entry["time"])
                    g = entry.get("group", "Unknown")
                    text += f"{t.strftime('%Y-%m-%d %H:%M')} - Sent ad to group {g}\n"
                await event.reply(text)
            except:
                await event.reply("Usage: !log <days>")

        elif cmd == "!addadmin":
            if not args.isdigit():
                await event.reply("Usage: !addadmin <user_id>")
                return
            new_admin = int(args)
            if new_admin in data.get("admins", []):
                await event.reply("User is already an admin.")
                return
            data["admins"].append(new_admin)
            save_data(data)
            await event.reply(f"✅ Added user `{new_admin}` as admin.")

        elif cmd == "!uptime":
            uptime_str = format_uptime()
            await event.reply(f"⏳ Uptime: {uptime_str}")

        elif cmd == "!backup":
            # Send data.json file to admin
            try:
                await event.reply("Backing up data.json...")
                await client.send_file(event.sender_id, DATA_FILE)
            except Exception as e:
                await event.reply(f"Failed to send backup: {e}")

        elif cmd == "!restore":
            await event.reply("Please send the backup file (reply to this message with the data.json file).")

            def check(event2):
                return event2.is_reply and event2.file and event2.sender_id == sender.id

            try:
                file_event = await client.wait_for(events.NewMessage, timeout=60, predicate=check)
                file = file_event.file
                await file_event.download_media(DATA_FILE)
                await event.reply("Restored data.json successfully. Restart the bot to apply changes.")
            except asyncio.TimeoutError:
                await event.reply("Timed out waiting for backup file.")

        elif cmd == "!join":
            if not event.is_group:
                await event.reply("This command can only be used inside a group.")
                return
            gid = str(event.chat_id)
            if gid in data["groups"]:
                await event.reply("Group already added.")
                return
            data["groups"][gid] = data["frequency"]
            save_data(data)
            await event.reply(f"✅ Added this group (`{gid}`) to the ad list.")

        elif cmd == "!allgroup":
            param = args.lower()
            if param not in ("on", "off"):
                await event.reply("Usage: !allgroup on/off")
                return
            data["allgroup"] = (param == "on")
            save_data(data)
            await event.reply(f"✅ All group forwarding turned {'ON' if data['allgroup'] else 'OFF'}.")

        else:
            # Unknown command for admins
            pass

    @client.on(events.NewMessage(incoming=True))
    async def group_reply_detector(event):
        if not event.is_group or not event.is_reply:
            return

        sender = await event.get_sender()
        if sender is None or (isinstance(sender, User) and sender.bot):
            return

        replied_msg = await event.get_reply_message()
        if not replied_msg:
            return

        me = await client.get_me()
        # Check if the replied message is from this bot
        if replied_msg.from_id and isinstance(replied_msg.from_id, PeerUser):
            if replied_msg.from_id.user_id == me.id:
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
    global client

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

    await client.start()

    try:
        data = load_data()
        for admin in data.get("admins", []):
            await client.send_message(admin, "✅ Bot started and running on Render.")
    except Exception as e:
        print(Fore.RED + f"Couldn't notify admin: {e}")

    await asyncio.gather(
        start_web_server(),
        command_handler(),
        ad_sender()
    )

if __name__ == "__main__":
    asyncio.run(main())
