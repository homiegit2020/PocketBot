# Pocket Option Quant Algorithm Bot

## Deploy on Railway in 1 Click

### Step 1: Upload to GitHub
- Extract `LODU.zip`
- Create a new GitHub repository
- Upload all files

### Step 2: Deploy on Railway
- Go to https://railway.app
- Click **New Project** → **Deploy from GitHub repo**
- Select your repository
- Railway auto-detects the `Procfile`

### Step 3: Set Environment Variables
In Railway dashboard → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | Your Telegram bot token (from @BotFather) |
| `API_ID` | Your Telegram API ID (from my.telegram.org) |
| `API_HASH` | Your Telegram API Hash |
| `ADMIN_ID` | Your Telegram user ID |

### Step 4: Deploy
Click **Deploy** — Railway runs:
```
python -m playwright install chromium && python main.py
```

### Step 5: Bot is Live
Send `/start` to your bot on Telegram.

---

## Features
- ✅ Auto account creation on Pocket Option (email only)
- ✅ Auto login for existing accounts
- ✅ Auto session extraction — no manual cookie copying
- ✅ RSI + MACD signal generation
- ✅ Martingale money management (5 steps, 2.3× multiplier)
- ✅ 10 trades per session, 3 sessions total
- ✅ Real-time trade result updates (edited messages)
- ✅ Full admin panel (ban, broadcast, CSV export, stats)
- ✅ 24/7 operation with auto-restart
- ✅ Session auto-refresh every 6 hours
- ✅ Health check endpoint at `/health`

## Bot Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot / link account |
| `/account` | View account info and balances |
| `/settings` | Configure trading settings |
| `/admin` | Admin panel (admin only) |

## Architecture
```
main.py               — Bot entry point, scheduler, web server
handlers/
  start.py            — /start, account creation, login FSM
  account.py          — /account
  settings.py         — /settings
  trading.py          — Session flow, trade execution
  admin.py            — Admin panel
services/
  pocket_auth.py      — PO authentication (3 methods)
  trading_engine.py   — WebSocket connection, Martingale trades
  signals.py          — RSI + MACD signal generation
  session_manager.py  — Auto session refresh
database/
  models.py           — SQLAlchemy models
  db.py               — Async DB operations
utils/
  logger.py           — Structured logging
  keyboards.py        — Inline keyboards
  messages.py         — Message templates
```

## Support
Bot runs 24/7 automatically after deployment.
No manual intervention required.
