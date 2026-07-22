# AKAZA X PROXY

> Telegram proxy extractor & verifier bot.
> **Brand**: AKAZA X PROXY · **Credit**: [@akaza_isnt](https://t.me/akaza_isnt) · **Version**: v6.2

---

## 🚀 Quick start (no Docker, no nano — phone friendly)

You need:
- A **Linux server** (VPS) OR **Termux** on Android
- A **bot token** from [@BotFather](https://t.me/BotFather)
- Your **Telegram user ID** from [@userinfobot](https://t.me/userinfobot)

### Step 1 — Get the code onto your server

**Option A: Clone from GitHub (recommended)**
```bash
git clone https://github.com/YOUR_USERNAME/akaza-x-proxy.git
cd akaza-x-proxy
```

**Option B: Upload the zip**
- Upload `akaza-x-proxy-deploy.zip` to your server (via SCP, Termux `cd /sdcard/Download && unzip ...`, etc.)
- Unzip it: `unzip akaza-x-proxy-deploy.zip && cd akaza-x-proxy`

### Step 2 — Run the setup wizard (one command)

```bash
bash setup.sh
```

That's it. The script is **fully self-contained and idempotent** — run it on a
brand-new server and it does everything itself. It will:
1. ✅ Install Python 3 (+ `venv`) automatically **if it's missing** — on apt, dnf/yum, pacman, apk, or Termux. Already installed? It's left as-is (no upgrades).
2. ✅ Install `unrar` / `p7zip` automatically if missing (for `.rar` / `.7z` archives)
3. ✅ Create the virtual environment (`.venv/`) — reused if it already exists
4. ✅ Install all dependencies (pyrogram, tgcrypto, requests, rarfile, py7zr, ...) — skipped when already up to date
5. ❓ Ask you to paste your `BOT_TOKEN` and `ADMIN_ID` (or read them from a `.env` file / environment variables)
6. ✅ Save them to a `.env` file (you don't edit any code!)
7. 🚀 Start the bot in the background with `nohup`

Fully hands-off (no prompts) — provide the two values up front:
```bash
BOT_TOKEN=123456:ABC-DEF ADMIN_ID=123456789 bash setup.sh
```

You'll see:
```
[AKAZA] Loaded configuration from .env
✅  AKAZA X PROXY is running.  Open Telegram and send /start
```

### Step 3 — Open Telegram and send `/start` to your bot

🎉 Done.

---

## How to edit `.env` later (no nano needed)

Your `.env` file lives in the bot folder. To edit it on a phone, you have 3 options:

### Option A — Re-run `setup.sh` (easiest)
```bash
cd akaza-x-proxy
bash setup.sh
```
It will show your current values. Press Enter to keep them, or type a new value.

### Option B — Use `echo` to rewrite `.env`
```bash
cd akaza-x-proxy
echo 'BOT_TOKEN=123456789:NEWtokenHERE'  >  .env
echo 'ADMIN_ID=123456789'                 >> .env
```
(Just replace with your real values.)

### Option C — Use any text editor you have
- **Termux**: `pkg install nano` then `nano .env`
- **VS Code (web/remote)**: open the file directly
- **GitHub web UI**: edit `.env` on GitHub (⚠️ but never commit a real token!)

---

## How to keep the bot running 24/7

### Easiest — use `screen` or `tmux`

```bash
# Install screen (if not present)
sudo apt install screen      # or: pkg install screen  (Termux)

# Start a named session
screen -S akaza

# Inside the session, run the bot
cd akaza-x-proxy
.venv/bin/python AKAZA_X_PROXY_Bot.py

# Detach: press Ctrl+A then D
# Reattach later:  screen -r akaza
```

The bot keeps running even when you close the terminal.

### Better — use `systemd` (Linux servers only)

```bash
sudo tee /etc/systemd/system/akaza-bot.service > /dev/null <<EOF
[Unit]
Description=AKAZA X PROXY Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/akaza-x-proxy
ExecStart=$HOME/akaza-x-proxy/.venv/bin/python $HOME/akaza-x-proxy/AKAZA_X_PROXY_Bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now akaza-bot

# Check status
sudo systemctl status akaza-bot

# View live logs
sudo journalctl -u akaza-bot -f
```

The bot will:
- Auto-start when the server boots
- Auto-restart if it crashes
- Survive you logging out

---

## How to update the bot

```bash
cd akaza-x-proxy
git pull                                      # get latest code
.venv/bin/pip install -r requirements.txt     # update deps if any changed
# Restart:
#   If using screen:     screen -r akaza, then Ctrl+C, then re-run
#   If using systemd:    sudo systemctl restart akaza-bot
```

Your `.env` and `akaza_data/` folder stay untouched — only the code updates.

---

## File structure

```
akaza-x-proxy/
├── AKAZA_X_PROXY_Bot.py    ← The bot (3,392 lines)
├── requirements.txt        ← Python deps
├── setup.sh                ← One-shot installer (run this first!)
├── .env                    ← YOUR secrets (auto-created — never commit to GitHub!)
├── .env.example            ← Template (safe to commit)
├── .gitignore              ← Excludes .env and data/ from GitHub
├── akaza_data/             ← Auto-created: users.json, logs, downloads
│   ├── users.json          ← All users + stats + ban/approve state
│   ├── working_proxies.json ← Per-user proxy history
│   ├── audit.log.jsonl     ← Admin action log
│   ├── downloads/          ← Temp file uploads
│   └── outputs/            ← Generated result files
├── Dockerfile              ← (optional) for Docker users
├── docker-compose.yml      ← (optional) for Docker users
├── entrypoint.sh           ← (optional) Docker entry point
├── LICENSE
└── README.md               ← This file
```

---

## What if I want to use Docker instead?

If you ever get Docker working, the files are already included:

```bash
cp .env.example .env
# Edit .env with your token + admin id
docker compose up -d --build
docker compose logs -f
```

But for phone deployment, the `bash setup.sh` flow is much simpler.

---

## Features

- **MTProto parallel downloads** — 16 workers, handles GB-sized files
- **21 proxy format patterns** — http/https/socks4/socks5 + many more
- **Archive support** — `.zip .rar .7z .tar .gz .bz2 .xz` + plain text formats
- **Smart verification** — up to 60 parallel workers, 8s timeout, HTTPS→HTTP fallback
- **Live dashboard** — download / extract / verify progress with timing
- **Per-user stats** — every working proxy stored with timestamp + latency
- **Settings panel** — toggle live notif, filter by type/latency, export TXT/CSV/JSON
- **Admin panel** — ban/unban, approve, lock bot, view any user's history
- **Broadcast** — message all users at once
- **Leaderboard** — top 10 users by working proxies
- **Audit log** — every admin action tracked
- **Rate limiting** — 5 files/hour for free users (admin + approved = unlimited)
- **Forward-protection** — admin messages can't be forwarded
- **`.env` config** — no code editing needed

---

## Commands

### User commands
| Command | Description |
|---------|-------------|
| `/start` | Dashboard (new users get a welcome tutorial) |
| `/help` | Full help menu |
| `/stats` | Your statistics |
| `/myinfo` | Your account details |
| `/myproxies` | Your working proxy history (with timestamps) |
| `/settings` | Toggle notifications + filters + export format |
| `/leaderboard` | Top 10 users 🏆 |
| `/about` | About the bot |

### Admin commands
| Command | Description |
|---------|-------------|
| `/admin` | Admin panel |
| `/ban` `/unban <id>` | Ban / unban a user |
| `/approve` `/unapprove <id>` | Approve / remove approval |
| `/lock` `/unlock` | Lock bot / open to all |
| `/users` | List all users |
| `/userinfo <id>` | User details |
| `/broadcast <msg>` | Message all users |
| `/backup` | Download `users.json` backup |
| `/health` | System health check |
| `/auditlog` | Last 15 admin actions |
| `/purgeaudit` | Clear audit log |
| `/clear` | Clear workspace cache |

---

## Troubleshooting

### "Python 3 is not installed"
```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip python3-venv

# Termux (Android)
pkg install python

# Alpine
apk add python3 py3-pip
```

### "`.rar` files not extracting"
Install `unrar`:
```bash
sudo apt install unrar p7zip-full     # Ubuntu/Debian
pkg install unrar                     # Termux
```

### Bot doesn't respond after setup
Check that your `BOT_TOKEN` is correct (get a fresh one from @BotFather if unsure).
Check that `ADMIN_ID` is YOUR user ID, not someone else's.

### How to reset everything
```bash
cd akaza-x-proxy
rm -rf .venv .env akaza_data
bash setup.sh
```

---

## Credit

**Developer**: [@akaza_isnt](https://t.me/akaza_isnt)

All credits reserved. Use responsibly.
