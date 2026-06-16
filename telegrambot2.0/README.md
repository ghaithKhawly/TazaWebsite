# 🌿 تازا بوت – Taza Telegram Bot

A "Too Good To Go" clone for the Syrian market — connects customers with restaurants selling surplus food at a discount. All in Arabic, cash on pickup, zero friction.

---

## Architecture

```
Telegram ──► Render (aiohttp webhook) ──► python-telegram-bot
                                               │
                                        Google Sheets (DB)
                                        APScheduler (reminders)
Mini App (GitHub Pages) ──► Render API (/api/*)
```

**Free tier stack:** Render (web service) + Google Sheets API + UptimeRobot pings.

---

## Step 1: Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Follow prompts, copy the **Bot Token**
3. Set bot commands (optional but recommended):
   ```
   /start - بدء
   /menu - تصفح الأكياس
   /orders - طلباتي
   /setlocation - تغيير منطقتي
   /vendor - تسجيل اهتمام متجر أو مطعم
   /newbag - كيس جديد (للمطاعم)
   /mybags - أكياسي اليوم (للمطاعم)
   /panel - لوحة المطعم (للمطاعم)
   /addrestaurant - إضافة مطعم (للإدارة)
   /allorders - جميع الطلبات (للإدارة)
   /vendorleads - طلبات انضمام التجار (للإدارة)
   /broadcast - رسالة جماعية (للإدارة)
   /initsheets - تهيئة قاعدة البيانات (للإدارة - مرة واحدة)
   ```
4. Get your Telegram user ID: message [@userinfobot](https://t.me/userinfobot)
5. Create a **private group** for admin order forwarding → add your bot → get group chat ID via [@RawDataBot](https://t.me/RawDataBot)

---

## Step 2: Set Up Google Sheets

### 2a. Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. **New Project** → name it `taza-bot`
3. Enable APIs:
   - Go to **APIs & Services > Library**
   - Enable **Google Sheets API**
   - Enable **Google Drive API**

### 2b. Create a Service Account

1. **APIs & Services > Credentials > Create Credentials > Service Account**
2. Name: `taza-bot-sa`, click **Create and Continue**, skip optional steps
3. Open the service account → **Keys** tab → **Add Key > Create new key > JSON**
4. Download the JSON file — keep it safe

### 2c. Create the Spreadsheet

1. Go to [sheets.google.com](https://sheets.google.com) → **New Spreadsheet**
2. Name it exactly: `Taza Bot DB` (or whatever you'll set as `SPREADSHEET_NAME`)
3. Share the spreadsheet with the service account email (from the JSON: `client_email`)
   - Click **Share** → paste the email → **Editor** → **Send**

### 2d. Encode the JSON Credentials

Convert the JSON key to a single-line string for the environment variable:

```bash
python3 -c "import json,sys; d=open('path/to/key.json').read(); print(json.dumps(d))"
```

Copy the output (it will be a quoted string) — this goes into `GOOGLE_SHEETS_CREDENTIALS`.

---

## Step 3: Deploy on Render

### 3a. Push to GitHub

```bash
git init
git add .
git commit -m "Initial Taza bot"
git remote add origin https://github.com/YOUR_USERNAME/taza-bot.git
git push -u origin main
```

### 3b. Create Render Web Service

1. Go to [render.com](https://render.com) → **New > Web Service**
2. Connect your GitHub repo
3. Settings:
   | Field | Value |
   |-------|-------|
   | **Name** | `taza-bot` |
   | **Environment** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `python bot.py` |
   | **Instance Type** | Free |

4. Under **Environment Variables**, add all variables from `.env.example`:

   | Key | Value |
   |-----|-------|
   | `BOT_TOKEN` | Your bot token |
   | `ADMIN_CHAT_IDS` | Your Telegram ID (comma-sep for multiple) |
   | `ADMIN_GROUP_CHAT_ID` | Your admin group chat ID |
   | `WEBHOOK_URL` | `https://taza-bot.onrender.com` (your Render URL) |
   | `WEBAPP_BASE_URL` | `https://YOUR_USERNAME.github.io/taza-webapp` |
   | `GOOGLE_SHEETS_CREDENTIALS` | The single-line JSON string |
   | `SPREADSHEET_NAME` | `Taza Bot DB` |

5. Click **Create Web Service** → wait for first deploy

### 3c. Initialize the Database Sheets

Once the bot is running, message your bot:
```
/initsheets
```
This creates all required sheets in your Google Spreadsheet with proper headers.

---

## Step 4: Keep Render Awake with UptimeRobot

Render free tier sleeps after 15 minutes of inactivity. UptimeRobot pings it every 5 minutes to prevent this.

1. Go to [uptimerobot.com](https://uptimerobot.com) → **Create Free Account**
2. **Add New Monitor**:
   | Setting | Value |
   |---------|-------|
   | Monitor Type | `HTTP(s)` |
   | Friendly Name | `Taza Bot` |
   | URL | `https://taza-bot.onrender.com/health` |
   | Monitoring Interval | `5 minutes` |
3. Click **Create Monitor**

---

## Step 5: Add Your First Restaurant

In Telegram, message your bot as admin:
```
/addrestaurant
```
Follow the prompts. The restaurant manager will receive a welcome message and can immediately start adding bags with `/newbag`.

---

## Step 6: Deploy the Mini App (GitHub Pages)

The static webapp lives in the `webapp/` folder. You can deploy it in two ways:

### Option A — Separate repository (simple)

1. Create a new repo (example: `taza-webapp`).
2. Copy the contents of `webapp/` into the repo root.
3. Edit both [webapp/index.html](webapp/index.html) and [webapp/restaurant.html](webapp/restaurant.html):
    - Replace `https://YOUR-RENDER-APP.onrender.com` in the `taza-api-base` meta tag with your Render URL.
4. Enable **GitHub Pages**:
    - Settings → Pages → Deploy from branch → `main` / root.
5. Set `WEBAPP_BASE_URL` in Render to your GitHub Pages URL.

### Option B — Same repo using GitHub Actions

1. Keep `webapp/` in this repo.
2. Add a GitHub Actions workflow that deploys `webapp/` to `gh-pages`.
3. Enable Pages for the `gh-pages` branch.

Example workflow:

```yaml
name: Deploy WebApp
on:
   push:
      branches: ["main"]
      paths: ["webapp/**"]
jobs:
   deploy:
      runs-on: ubuntu-latest
      steps:
         - uses: actions/checkout@v4
         - name: Deploy
            uses: peaceiris/actions-gh-pages@v4
            with:
               github_token: ${{ secrets.GITHUB_TOKEN }}
               publish_dir: ./webapp
```

---

---

## Local Development

```bash
# Install deps
pip install -r requirements.txt

# Copy env file and fill in values
cp .env.example .env
# Edit .env with your values

# For local testing use polling instead of webhook:
# Temporarily replace asyncio.run(run()) in bot.py with polling mode,
# or use ngrok to expose localhost for webhook testing.

# Run
python bot.py
```

> **Local webhook testing with ngrok:**
> ```bash
> ngrok http 8443
> # Set WEBHOOK_URL=https://xxxx.ngrok.io in your .env
> ```

---

## Data Model (Google Sheets Tabs)

| Sheet | Key Columns |
|-------|-------------|
| `users` | user_id, name, phone, default_area, role |
| `restaurants` | restaurant_id, name, area, pickup_address, manager_chat_id, is_active |
| `bags` | bag_id, restaurant_id, date, type, original_price, discounted_price, remaining, pickup_start, pickup_end, is_active |
| `orders` | order_id, user_id, bag_id, order_code, status, customer_name, customer_phone |
| `config` | key, value (next_order_code, admin_group_chat_id) |
| `locks` | bag_id, locked, locked_at (concurrency control) |
| `vendor_leads` | lead_id, shop_name, category, area, whatsapp, closing_time, interest_level, main_concern, status |

---

## Vendor Validation Flow

The bot now supports a lightweight founding-vendor signup flow for QR cards, vendor invitation cards, and direct outreach.

- `/vendor` starts a guided form for shop owners.
- Deep links such as `https://t.me/YOUR_BOT?start=vendor_card` also start the same form.
- The form captures shop name, category, area, pickup address, contact person, WhatsApp, closing time, surplus type, interest level, and main concern.
- Leads are stored in the `vendor_leads` sheet and forwarded to the admin group.
- Admins can run `/vendorleads` to view the latest leads from inside Telegram.

Run `/initsheets` once after deploying this update so the new `vendor_leads` tab is created.

---

## Concurrency Strategy

Reservations use a **locks sheet** as a distributed mutex:

1. Before reserving, bot tries to write `locked=1` to the bag's lock row
2. If lock is held and < 10 seconds old → retry (up to 8 times, with jitter)
3. If lock is stale (> 10s) → it's treated as released (guards against crashed processes)
4. After reservation, lock is always released in a `finally` block

This prevents overselling without needing a real database. For production scale (> 50 concurrent users), replace Google Sheets with Supabase or Firebase.

---

## Scheduler Jobs

| Job | Frequency | What it does |
|-----|-----------|--------------|
| `pickup_reminders` | Every 1 min | Sends reminder 30 min before pickup window |
| `post_pickup_ratings` | Every 1 min | Asks for rating 5–10 min after pickup window closes |
| `daily_summaries` | 23:00 daily | Sends daily revenue summary to each restaurant |

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Telegram bot token from BotFather |
| `ADMIN_CHAT_IDS` | ✅ | Comma-separated admin Telegram IDs |
| `ADMIN_GROUP_CHAT_ID` | ✅ | Private group chat ID for order forwarding |
| `WEBHOOK_URL` | ✅ | Public HTTPS URL of your Render service |
| `WEBAPP_BASE_URL` | ✅ | Base URL of the GitHub Pages Mini App |
| `WEBAPP_CORS_ORIGIN` | ❌ | Allowed origin for Mini App API (defaults to WEBAPP_BASE_URL) |
| `GOOGLE_SHEETS_CREDENTIALS` | ✅ | Full service account JSON as single-line string |
| `SPREADSHEET_NAME` | ✅ | Exact name of your Google Spreadsheet |
| `PORT` | ✅ | HTTP port (Render sets this automatically) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Bot doesn't respond | Check Render logs. Ensure webhook URL is correct and HTTPS. |
| "Sheet not found" error | Run `/initsheets` from admin account |
| Google Sheets quota exceeded | Bot auto-retries with backoff. If persistent, reduce usage or upgrade quota. |
| Orders not forwarded to restaurant | Check `manager_chat_id` is correct; manager must have started the bot first |
| Render sleeps despite UptimeRobot | Ensure `/health` endpoint returns 200; check UptimeRobot monitor status |

---

## File Structure

```
taza-bot/
├── bot.py          # Main bot, webhook server, all handlers
├── sheets.py       # Google Sheets CRUD, locking, atomic reserve
├── scheduler.py    # APScheduler jobs (reminders, summaries)
├── requirements.txt
├── .env.example
├── webapp/          # Telegram Mini App (static)
│   ├── index.html
│   ├── restaurant.html
│   ├── style.css
│   └── app.js
└── README.md
```
