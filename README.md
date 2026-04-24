# 🚕 TeleCabs — Telegram Taxi Bot

A production-ready, fully-featured Telegram taxi dispatch bot built with **Python** and **PostgreSQL**.
Supports multiple vehicle types, dynamic pricing per category, real-time driver matching, trip tracking, admin control panel, and Telegram group notifications.

---

## 📋 Table of Contents

1. [Features](#-features)
2. [Project Structure](#-project-structure)
3. [Environment Variables](#-environment-variables)
4. [Deploy on Railway](#-deploy-on-railway-recommended)
5. [Local Development](#-local-development)
6. [Admin Panel](#-admin-panel)
7. [Fare System](#-fare-system)
8. [Trip Flow](#-trip-flow)
9. [Notification Groups](#-notification-groups)
10. [Distance Methods](#-distance-methods)
11. [Admin Slash Commands](#-admin-slash-commands)

---

## ✅ Features

### 🚕 For Riders
- Choose vehicle type: Bike, Tuk, Car, Mini Van, Van, Bus
- Share pickup via GPS or text search
- Search drop-off location by name (Google Places or OpenStreetMap)
- View full fare estimate **before** confirming (distance, rate, waiting rate)
- Real-time driver matching within configurable radius
- Get driver contact + WhatsApp link on acceptance
- Notifications when driver arrives at pickup
- Rate driver after trip (1–5 stars + written comment)

### 🚗 For Drivers
- Full registration: name, phone, vehicle type, plate number, location
- Driver dashboard: Check-in, Mute/Unmute notifications, Settings
- Receive nearby ride requests (filtered by vehicle type + radius)
- Google Maps navigation link to pickup and drop-off (free, no API cost)
- **Arrived at Pickup** button — notifies rider automatically
- Start trip with meter reminder (*Set meter to 0*)
- Enter vehicle meter reading at trip end
- Enter waiting time at trip end
- GPS trip tracking (cumulative, stored in DB, survives restarts)

### 👑 For Admins
- Hidden admin panel (only visible to admins in main menu)
- **Per-category pricing** — set Base Fare, Per-KM Rate, Base KM, and Waiting Rate **individually** for each vehicle type (Bike, Tuk, Car, Mini Van, Van, Bus)
- Global pricing fallback if no category-specific rate is set
- Set driver search radius
- Enable/disable vehicle categories
- Block/unblock users (by ID, @username, or name)
- Add/remove additional admins (DB-level)
- View driver list, rider list, all users
- Trip statistics and revenue summary
- Clean route cache
- Full slash command set for quick management

---

## 📁 Project Structure

```
pickride_bot/
├── main.py               # Entry point — registers all handlers
├── config.py             # Env loading, Railway SSL fix, admin IDs
├── database.py           # All DB queries using asyncpg + route cache
├── requirements.txt      # Python dependencies
├── Procfile              # Railway: runs as worker (not web)
├── railway.toml          # Railway build config
├── .env.example          # Template — copy to .env and fill in
├── setup.sql             # (Local only) Creates DB and user
├── handlers/
│   ├── start.py          # /start, /cancel, /cancelride, main menu
│   ├── driver.py         # Driver registration, dashboard, checkin
│   ├── rider.py          # Ride request flow, fare estimate, confirm
│   ├── trip.py           # Accept, Arrived, Start, End trip, rating
│   └── admin.py          # Admin panel callbacks + slash commands
└── utils/
    ├── distance.py       # Google Maps, OSRM, Haversine, GPS cumulative
    ├── geocoding.py      # Google Places + Nominatim geocoding
    └── fare.py           # Per-vehicle fare calculation + waiting time
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in all values.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ Yes | Your bot token from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection URL (Railway provides this automatically) |
| `ADMIN_IDS` | ✅ Yes | Comma-separated Telegram user IDs of super admins |
| `GOOGLE_MAPS_API_KEY` | Optional | For accurate road distances. Leave empty to use free Haversine |
| `DEFAULT_BASE_FARE` | Optional | Default base fare (LKR). Default: `100` |
| `DEFAULT_PER_KM_RATE` | Optional | Default per-km rate (LKR). Default: `100` |
| `DEFAULT_BASE_KM` | Optional | Free km included in base fare. Default: `1` |
| `DEFAULT_WAITING_RATE` | Optional | Waiting charge per minute (LKR). Default: `5` |
| `DEFAULT_DRIVER_RADIUS` | Optional | Driver search radius (km). Default: `8` |
| `TRIPS_GROUP_ID` | Optional | Group to receive trip requests + invoices + feedback |
| `RIDERS_GROUP_ID` | Optional | Group to receive new rider registrations |
| `DRIVERS_GROUP_ID` | Optional | Group to receive new driver registrations |

> 💡 To find your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).
> Multiple admin IDs: `ADMIN_IDS=111111,222222,333333`

---

## 🚀 Deploy on Railway (Recommended)

Railway is the easiest way to deploy TeleCabs. Follow these steps exactly:

### Step 1 — Fork or Push to GitHub

Make sure your code is in a GitHub repository.

### Step 2 — Create a Railway Project

1. Go to [railway.app](https://railway.app) and log in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Railway will detect the `Procfile` automatically

### Step 3 — Add PostgreSQL Database

1. In your Railway project dashboard, click **+ New**
2. Select **Database** → **Add PostgreSQL**
3. Railway automatically creates and injects `DATABASE_URL` into your project
4. ⚠️ **Do NOT manually set `DATABASE_URL`** — Railway handles it

### Step 4 — Set Environment Variables

1. Click on your **bot service** (not the database)
2. Go to **Variables** tab
3. Add the following (click **+ New Variable** for each):

```
BOT_TOKEN          = your_telegram_bot_token
ADMIN_IDS          = your_telegram_user_id
GOOGLE_MAPS_API_KEY = your_google_api_key   ← optional but recommended
TRIPS_GROUP_ID     = -100xxxxxxxxx           ← optional
RIDERS_GROUP_ID    = -100xxxxxxxxx           ← optional
DRIVERS_GROUP_ID   = -100xxxxxxxxx           ← optional
DEFAULT_BASE_FARE  = 100
DEFAULT_PER_KM_RATE = 100
DEFAULT_BASE_KM    = 1
DEFAULT_WAITING_RATE = 5
DEFAULT_DRIVER_RADIUS = 8
```

> ⚠️ Do NOT add `DATABASE_URL` here — Railway injects it automatically from the PostgreSQL plugin.

### Step 5 — Deploy

- Railway will auto-deploy when you push to GitHub
- Go to **Deployments** tab to watch the build log
- Once deployed, the bot will:
  - Connect to PostgreSQL
  - Create all tables automatically
  - Start polling for messages

### Step 6 — Verify

- Open Telegram and message your bot `/start`
- You should see the main menu appear
- If you set `ADMIN_IDS` correctly, you'll see the **👑 Admin Control ⚙️** button

### Troubleshooting Railway

| Problem | Solution |
|---|---|
| Bot not responding | Check **Logs** tab in Railway for errors |
| Database error | Make sure PostgreSQL plugin is added to the same project |
| `BOT_TOKEN` error | Double-check the token from BotFather, no spaces |
| Admin button not showing | Make sure your Telegram ID matches `ADMIN_IDS` exactly |
| Google Maps not working | Verify the API key has **Distance Matrix API** and **Places API** enabled |

---

## 💻 Local Development

### 1. Clone and Install

```bash
git clone https://github.com/your-repo/pickride_bot.git
cd pickride_bot
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL

```bash
# Create database
psql -U postgres -f setup.sql

# Or manually:
createdb pickride
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env     # Fill in BOT_TOKEN, DATABASE_URL, ADMIN_IDS
```

Local `DATABASE_URL` format:
```
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/pickride
```

### 4. Run

```bash
python main.py
```

The bot will create all database tables on first launch automatically.

---

## 👑 Admin Panel

Access the admin panel by tapping **👑 Admin Control ⚙️** in the main menu (only visible to admins).

### GUI Panel Sections

| Section | What you can do |
|---|---|
| 💰 Pricing Settings | Set global Base Fare, Per-KM Rate, Base KM, Waiting Rate |
| 🚗 Vehicle Pricing | Set separate pricing for each vehicle type (overrides global) |
| 📍 System Settings | Set driver search radius |
| 🗺️ Distance Method | Switch between Google Maps, OSRM, or Haversine |
| 🚫 Category Control | Enable or disable vehicle categories |
| 👤 User Management | Block or unblock users (by ID, @username, or name) |
| 👑 Admin Management | Add/remove extra admins (super admins only) |
| 🚖 Driver List | View all registered drivers + status |
| 🚶 Rider List | View all registered riders |
| 👥 All Users | View all users with roles |
| 📊 Trip Stats | Total, completed, cancelled, in-progress rides |
| 💵 Revenue | Total revenue from completed trips |
| 🧹 Clean Cache | Remove expired route cache entries |

### Per-Vehicle Pricing

Each vehicle type (Bike, Tuk, Car, Mini Van, Van, Bus) can have its **own**:
- **Base Fare** — starting fare (LKR)
- **Per-KM Rate** — cost per km after base KM (LKR)
- **Base KM** — free distance included in base fare (km)
- **Waiting Rate** — charge per waiting minute (LKR/min)

If no custom rate is set for a vehicle, it falls back to the global rate automatically.

---

## 💰 Fare System

### Formula

```
if distance <= base_km:
    fare = base_fare
else:
    fare = base_fare + (distance - base_km) × per_km_rate

fare += waiting_minutes × waiting_rate
```

### Example

| Setting | Value |
|---|---|
| Base Fare | LKR 300 |
| Base KM | 2 km |
| Per-KM Rate | LKR 100/km |
| Waiting Rate | LKR 5/min |

- **1.5 km ride, 0 min wait** → LKR 300 (within base km)
- **5 km ride, 0 min wait** → LKR 300 + (5−2) × 100 = **LKR 600**
- **5 km ride, 10 min wait** → LKR 600 + 10×5 = **LKR 650**

### Transparency

The **waiting rate is displayed** to the rider at:
1. Fare estimate (before confirming the ride)
2. Driver acceptance notification
3. Final invoice (both rider and driver)
4. TRIPS group invoice

This prevents drivers from charging unauthorized rates.

---

## 🔄 Trip Flow

```
RIDER                          DRIVER
  │                               │
  │── 🚕 Request Ride             │
  │   Select vehicle type         │
  │   Share pickup location        │
  │   Search destination           │
  │   View fare estimate           │
  │── ✅ Confirm Ride              │
  │                    ←── 🔔 New Ride Request notification
  │                    ←── 🟨 Accept Ride button
  │                               │── Accept
  │── ✅ Ride Accepted!            │
  │   Driver info + WhatsApp       │── 🗺 Navigate to PICKUP
  │   Waiting Rate shown           │── 🚨 I'VE ARRIVED AT PICKUP
  │                               │       ↓ (tap when at pickup)
  │── 🚨 Driver has arrived!      │
  │   Call/WhatsApp driver         │── ⚠️ SET METER TO 0 — 🟢 START TRIP
  │                               │       ↓ (tap when rider boards)
  │── 🟢 Trip started!            │── 🏁 Navigate to DROP-OFF
  │                               │   [ride in progress]
  │                               │── 🔴 End Trip (reply keyboard)
  │                               │       ↓
  │                               │   Enter meter distance (km)
  │                               │   Enter waiting time (min)
  │── ✅ Trip Completed!          │── ✅ Trip Completed!
  │   Full invoice shown           │   Full invoice shown
  │── ⭐ Rate your driver          │
  │── 💬 Leave a comment          │
```

---

## 📢 Notification Groups

Add the bot as an **admin** to Telegram groups, then get each group's ID using `/groupid` command inside the group.

| Group | What it receives |
|---|---|
| `TRIPS_GROUP_ID` | New ride requests, completed trip invoices, rider feedback/ratings |
| `RIDERS_GROUP_ID` | New rider registrations |
| `DRIVERS_GROUP_ID` | New driver registrations |

---

## 📏 Distance Methods

| Method | Accuracy | Cost | Requires |
|---|---|---|---|
| 🌐 Google Maps API | ⭐⭐⭐⭐⭐ Best | Paid (free tier available) | `GOOGLE_MAPS_API_KEY` |
| 🗺️ OSRM | ⭐⭐⭐⭐ Good | Free | Internet |
| 📐 Haversine | ⭐⭐ Straight-line only | Free | Nothing |

> If `GOOGLE_MAPS_API_KEY` is set, the bot **automatically uses Google Maps** for best accuracy regardless of the saved DB setting.

Switch methods via **Admin Panel → 🗺️ Distance Method**.

---

## 🛠 Admin Slash Commands

These commands work in private chat with the bot (admin only):

| Command | Description |
|---|---|
| `/help` | Show all admin commands |
| `/status` | Bot status, online drivers, trip counts |
| `/rates` | View all current pricing rates |
| `/setbase car 300` | Set base fare for car (or global if no category) |
| `/setrate car 100` | Set per-km rate for car |
| `/basekm 2` | Set global base KM |
| `/setradius 10` | Set driver search radius (km) |
| `/blockcat bike` | Disable a vehicle category |
| `/unblockcat bike` | Enable a vehicle category |
| `/block @username` | Block a user (ID / @username / name) |
| `/unblock @username` | Unblock a user |
| `/drivers` | List all drivers |
| `/riders` | List all riders |
| `/users` | All registered users |
| `/trips` | Trip statistics |
| `/revenue` | Revenue summary |
| `/groupid` | Get current chat's ID |
| `/whoami` | Show your Telegram ID and admin role |
| `/session` | Current session settings |
| `/restart` | Restart bot session |
| `/resetbot` | Hard-reset all stuck user sessions |
| `/apistatus` | Test Google Maps, OSRM, and geocoding APIs |

---

## 🔐 Security Notes

- **Super Admins** are set in `.env` (`ADMIN_IDS`) and cannot be removed via bot
- **Extra admins** can be added via Admin Panel → Admin Management (super admin only)
- Blocked users cannot request rides or register as drivers
- All fare rates are system-controlled — riders see the official waiting rate to prevent overcharging

---

## 📦 Requirements

```
python-telegram-bot>=20.0
asyncpg
python-dotenv
aiohttp
```

Install with:
```bash
pip install -r requirements.txt
```

---

*Built for Sri Lanka taxi operations. Prices in LKR. Easily adaptable for any market.*
