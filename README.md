# 📁 Multi-File Sharing Bot (Upgraded)

A production-ready Telegram file-sharing bot built with **Pyrogram** and **MongoDB**.  
Users must join all required channels before they can access any files.  
Membership is checked on every interaction and revoked automatically if a user leaves.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Force Subscribe** | Configurable list of required channels via a single env var |
| **Smart Join Buttons** | Shows inline buttons **only** for channels the user hasn't joined yet |
| **✅ Verify Membership** | One-tap re-check after the user joins |
| **MongoDB tracking** | Stores user ID, name, verification status, missing channels, last-verified timestamp |
| **Continuous monitoring** | Every message interaction re-checks membership; access revoked automatically |
| **Auto Link Generation** | Bot automatically generates a shareable deep-link on every DB channel post |
| **Multi-file (batch) links** | `/batch <first_id> <last_id>` — one link delivers a range of files |
| **Forward → Link shortcut** | Forward any DB-channel message to the bot and get a share link instantly |
| **Auto-delete** | Files sent to users are deleted automatically after 5 minutes |
| **Admin commands** | `/stats`, `/users`, `/broadcast` |
| **Protect Content** | Optionally prevent users from forwarding files |
| **Docker + Heroku ready** | Dockerfile, docker-compose, Procfile all included |

---

## 🔗 File Sharing Features (ported from muti-file-sharing)

### Auto Link Generation
Every time a file is posted to the DB channel, the bot automatically attaches
a **"🔗 Get File"** button. Anyone with admin access to the channel can forward
that link directly — no manual steps required.

### Batch Files (`/batch`)
Send a range of files with a single link:

```
/batch 101 120
```

This generates one deep-link that, when clicked, delivers messages 101–120
from the DB channel to the user in a single operation.

### Forward → Link Shortcut
Admins can forward any message from the DB channel into a private chat with
the bot. The bot instantly replies with a copyable share link for that file.

---

## 🔧 Configuration

All configuration is done through **environment variables**.  
Copy `env` to `.env` and fill in your values:

```bash
cp env .env
```

### Required variables

| Variable | Description |
|---|---|
| `TG_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `APP_ID` | API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | API Hash from [my.telegram.org](https://my.telegram.org) |
| `OWNER_ID` | Your Telegram user ID |
| `CHANNEL_ID` | ID of the private channel used to store files |
| `DATABASE_URL` | Full MongoDB connection string |
| `FORCE_SUB_CHANNELS` | JSON array of required channels (see below) |

### FORCE_SUB_CHANNELS format

```json
[
  {"id": -1001111111111, "name": "My Public Channel", "username": "mypublicchan"},
  {"id": -1002222222222, "name": "My Private Channel"}
]
```

- `id` — channel ID (required, always negative for channels)
- `name` — display name shown on join buttons
- `username` — omit for private channels; the bot will use the exported invite link

---

## 🤖 Bot Admin Setup

The bot **must be an admin** in the following chats:

| Chat | Required permissions |
|---|---|
| **DB Channel** (`CHANNEL_ID`) | Post messages, Delete messages |
| **Every force-sub channel** | Invite users via link |

---

## 🚀 Deployment

### Option 1 — Local (plain Python)

```bash
git clone https://github.com/nakflix/Muti-file-sharing-upgraded.git
cd Muti-file-sharing-upgraded
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env .env   # edit .env with your values
python main.py
```

### Option 2 — Docker (recommended for production)

```bash
docker compose up -d --build
docker compose logs -f bot
```

### Option 3 — Heroku

1. Fork this repo.
2. Create a new Heroku app.
3. Go to **Settings → Config Vars** and add every variable from `env`.
4. Connect the repo and deploy the `main` branch.
5. Enable the `worker` dyno; disable the `web` dyno.

---

## 🛠 Admin Commands

| Command | Description |
|---|---|
| `/stats` | Bot uptime, total users, verified count |
| `/users` | User summary |
| `/broadcast` | Reply to any message with `/broadcast` to send it to all users |
| `/batch <first_id> <last_id>` | Generate a multi-file deep link |

---

## 📂 Project Structure

```
Muti-file-sharing-upgraded/
├── main.py                 # Entry point
├── levi.py                 # Pyrogram Bot client (startup logic)
├── config.py               # All configuration, loaded from env vars
├── helper_func.py          # Membership checks, encode/decode, utilities
├── database/
│   ├── __init__.py
│   └── mongodb.py          # Async MongoDB layer (motor)
├── plugins/
│   ├── __init__.py
│   ├── web_server.py       # aiohttp keep-alive server
│   ├── start.py            # /start, verify callback, file delivery, monitoring
│   ├── admin.py            # /stats, /users, /broadcast
│   └── channel_post.py     # Auto-link on DB channel post, /batch, forward→link
├── Dockerfile
├── docker-compose.yml
├── Procfile
├── requirements.txt
├── env                     # Example environment variables
└── .gitignore
```

---

## 🔒 Security Notes

- Never commit your `.env` file — it is in `.gitignore`.
- Use `PROTECT_CONTENT=True` to prevent users from forwarding files out of the bot.
- Rotate your bot token immediately if it is ever exposed publicly.
