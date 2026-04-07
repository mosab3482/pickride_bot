# 🚕 PickRide — Telegram Taxi Bot

A fully-featured Telegram taxi bot built with **Python** + **PostgreSQL**.
Designed for **Railway** deployment with minimal API usage.

---

## 📁 Project Structure

```
pickride_bot/
├── main.py               # Entry point
├── config.py             # Configuration + Railway SSL handling
├── database.py           # All DB queries (asyncpg) + route cache
├── requirements.txt
├── .env.example          # Template for environment variables
├── Procfile              # Railway deployment
├── railway.toml          # Railway build/deploy config
├── setup.sql             # PostgreSQL setup (local only)
├── handlers/
│   ├── start.py          # /start, main menu, help, cancel
│   ├── driver.py         # Driver registration & dashboard
│   ├── rider.py          # Rider request flow + route cache
│   ├── trip.py           # Accept/Start/End trip + meter + waiting + rating
│   └── admin.py          # Admin control panel + cache cleanup
└── utils/
    ├── distance.py       # Haversine + cumulative GPS distance
    ├── geocoding.py      # OpenStreetMap Nominatim reverse geocoding
    └── fare.py           # Fare calculation with waiting time
```

---

## ⚙️ Setup

### Option A: Local Development

#### 1. Install Dependencies

```bash
cd pickride_bot
pip install -r requirements.txt
```

#### 2. Configure Environment

```bash
cp .env.example .env
nano .env   # Fill in your values
```

#### 3. Create PostgreSQL Database

```bash
psql -U postgres -f setup.sql
```

#### 4. Run the Bot

```bash
python main.py
```

> The bot will **automatically create all tables** on first launch.

### Option B: Railway Deployment

#### 1. Create Railway Project

- Go to [railway.app](https://railway.app)
- Create a new project from GitHub repo

#### 2. Add PostgreSQL

- In Railway dashboard → Add Plugin → PostgreSQL
- Railway auto-provides `DATABASE_URL` environment variable

#### 3. Set Environment Variables

In Railway → Settings → Variables:
```
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=your_telegram_user_id
DEFAULT_BASE_FARE=100
DEFAULT_PER_KM_RATE=100
DEFAULT_BASE_KM=1
DEFAULT_WAITING_RATE=5
DEFAULT_DRIVER_RADIUS=8
```

> ⚠️ Do NOT set `DATABASE_URL` manually — Railway provides it automatically.

#### 4. Deploy

Railway auto-deploys on push. The `Procfile` tells Railway to run as a **worker** (not web).

---

## 🤖 Features

### For Riders 🚕
- Choose vehicle type (Car, Tuk, Bike, Van)
- Share pickup location
- Search destination by text (OpenStreetMap)
- View fare estimate before confirming (with route caching)
- Real-time driver matching within configurable radius
- Get driver contact + WhatsApp link
- Rate driver after trip (1-5 stars)

### For Drivers 🚗
- Full registration flow (phone, vehicle, name, plate, location)
- Dashboard with Check-in, Mute/Unmute
- Google Maps navigation links (free, no API usage)
- Enter vehicle meter distance at trip end
- Enter waiting time at trip end
- Live GPS trip tracking (cumulative distance, stored in DB)
- Receive nearby ride requests
- Start/End trip controls

### For Admins 👑
- Inline admin panel (hidden from non-admins)
- Set pricing: base fare, per-KM rate, base KM, waiting rate
- Set driver search radius
- Enable/disable vehicle categories
- Block/unblock users
- View driver list, rider list, all users
- Trip statistics & revenue summary
- Clean route cache

---

## 💰 Fare Formula

```
if distance <= base_km:
    fare = base_fare
else:
    fare = base_fare + (distance - base_km) * per_km_rate

fare += waiting_min * waiting_rate
```

Default: Base = LKR 100 for first 1 km, then LKR 100/km, + LKR 5/min waiting

---

## 📍 Distance & Navigation

### GPS Tracking
- **Haversine formula** with **cumulative GPS tracking**
- Every live location update stored in database (survives restarts)
- Distance summed between consecutive points
- GPS noise filtered (< 10m ignored)
- Driver can override with vehicle meter reading

### Navigation (FREE)
- Uses **Google Maps direction links** — completely free, no API usage
- Format: `maps/dir/?api=1&origin=X&destination=Y`
- Driver opens link → free turn-by-turn navigation

---

## 🗺 Route Cache (Smart)

- Distances cached for **24 hours**
- Auto-extended when route is reused
- Expired entries cleaned on bot startup + manual admin cleanup
- Reduces API/computation load for frequent routes

---

## 🌍 Geocoding

Uses **OpenStreetMap Nominatim** (free, no API key needed):
- Reverse geocoding: coordinates → "Area, District"
- Location search: text → list of results
- Results cached in memory to reduce API calls

---

## 🔐 Admin Access

Add your Telegram user ID to `.env`:
```
ADMIN_IDS=your_user_id
```

To find your ID, message [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## 🚀 Railway Notes

- Uses `Procfile` with `worker` type (not `web`)
- SSL auto-configured for Railway PostgreSQL
- Handles `postgres://` → `postgresql://` URL conversion
- Graceful shutdown on `SIGTERM`
- No real-time GPS tracking — minimal database writes
- Only 4-5 writes per ride — stays within free tier
