import os
import json
import asyncio
import random
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
DATA_FILE = "data.json"
ADMIN_ID = 6249999953

os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        print(Fore.RED + "Resetting corrupted data.json...")
        data = {
            "frequency": 10,
            "mode": "random",
            "last_sent_ad_index": 0
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

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

            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group]

            print(Fore.CYAN + f"Sending ads to {len(groups)} group(s)...")
            for group in groups:
                try:
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1
                        save_data(data)

                    await client.forward_messages(group.id, msg.id, "me")
                    print(Fore.GREEN + f"Forwarded ad to {group.id}")
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to group {group.id}: {e}")

            print(Fore.CYAN + f"Ad cycle done. Sleeping for {data['frequency']} minutes.")
            await asyncio.sleep(data["frequency"] * 60)
        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
            await asyncio.sleep(30)

async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        is_private = event.is_private
        is_admin = sender.id == ADMIN_ID
        data = load_data()
        cmd = event.raw_text.strip()

        if not is_admin and is_private:
            fwd_text = (
                f"📩 *New DM Received*\n"
                f"👤 Name: {sender.first_name}\n"
                f"🆔 User ID: {sender.id}\n"
                f"🔗 Username: @{sender.username if sender.username else 'N/A'}\n"
                f"📝 Message:\n{event.text}"
            )
            await client.send_message(ADMIN_ID, fwd_text)
            return

        if not is_admin:
            return

        if cmd.startswith("!setfreq"):
            try:
                freq = int(cmd.split()[1])
                data["frequency"] = freq
                save_data(data)
                await event.reply(f"✅ Frequency set to {freq} minutes")
            except:
                await event.reply("❌ Usage: !setfreq <minutes>")

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
            dialogs = await client.get_dialogs()
            groups = [d.id for d in dialogs if d.is_group]
            await event.reply(f"👥 Groups: {groups}\n📤 Mode: {data['mode']}\n⏱ Frequency: {data['frequency']} min")

        elif cmd == "!test":
            try:
                ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                     offset_date=None, max_id=0, min_id=0,
                                                     add_offset=0, hash=0))
                if not ads.messages:
                    await event.reply("❌ No saved message found.")
                    return
                msg = ads.messages[0]
                dialogs = await client.get_dialogs()
                for group in dialogs:
                    if group.is_group:
                        await client.forward_messages(group.id, msg.id, "me")
                        await asyncio.sleep(3)
                await event.reply("✅ Sent test ad to all joined groups.")
            except Exception as e:
                await event.reply(f"❌ Error: {e}")

        elif cmd == "!groups":
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group]
            if not groups:
                await event.reply("❌ No groups found.")
            else:
                reply = "👥 Group List:\n"
                for g in groups:
                    reply += f"- {g.name} (ID: {g.id})\n"
                await event.reply(reply)

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
                "🛠 Available Commands:\n"
                "!setfreq <minutes> – Set ad interval\n"
                "!setmode random/order – Set ad selection mode\n"
                "!status – View current settings\n"
                "!test – Send latest ad to groups\n"
                "!groups – List all joined groups\n"
                "!dm <user_id/@username> <msg> – DM a user\n"
                "!help – Show this menu"
            )

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
        await client.send_message(ADMIN_ID, "✅ Bot started and running on Render.")
    except:
        print(Fore.RED + "Couldn't notify admin.")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
