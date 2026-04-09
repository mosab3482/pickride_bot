import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Railway provides DATABASE_URL with ?sslmode=require
# Handle both local and Railway PostgreSQL
_raw_db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pickride")
# Railway sometimes uses postgres:// instead of postgresql://
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _raw_db_url

# Admin IDs
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()]

# Default settings (overridable via DB)
DEFAULT_BASE_FARE     = float(os.getenv("DEFAULT_BASE_FARE",     100))
DEFAULT_PER_KM_RATE   = float(os.getenv("DEFAULT_PER_KM_RATE",   50))
DEFAULT_BASE_KM       = float(os.getenv("DEFAULT_BASE_KM",        2))
DEFAULT_WAITING_RATE  = float(os.getenv("DEFAULT_WAITING_RATE",    5))
DEFAULT_DRIVER_RADIUS = float(os.getenv("DEFAULT_DRIVER_RADIUS",   8))

# Google Maps API key (used for real road-distance estimates)
# Enable the "Distance Matrix API" and "Directions API" in Google Cloud Console
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# ── Notification Groups ────────────────────────────────────────────────────────
# Telegram group/channel chat IDs for automatic notifications.
# Leave empty to disable that group notification.
_trips_gid   = os.getenv("TRIPS_GROUP_ID",   "")
_riders_gid  = os.getenv("RIDERS_GROUP_ID",  "")
_drivers_gid = os.getenv("DRIVERS_GROUP_ID", "")

TRIPS_GROUP_ID   = int(_trips_gid)   if _trips_gid.lstrip("-").isdigit()   else None
RIDERS_GROUP_ID  = int(_riders_gid)  if _riders_gid.lstrip("-").isdigit()  else None
DRIVERS_GROUP_ID = int(_drivers_gid) if _drivers_gid.lstrip("-").isdigit() else None

VEHICLE_TYPES = {
    "🏍️ Bike":     "bike",
    "🛺 Tuk":      "tuk",
    "🚗 Car":      "car",
    "🚙 Mini Van": "minivan",
    "🚐 Van":      "van",
    "🚌 Bus":      "bus",
}

VEHICLE_SEATS = {
    "bike":    "1 Seat",
    "tuk":     "2-3 Seats",
    "car":     "3-4 Seats",
    "minivan": "5 Seats",
    "van":     "10 Seats",
    "bus":     "25+ Seats",
}

VEHICLE_EMOJIS = {
    "bike":    "🏍️",
    "tuk":     "🛺",
    "car":     "🚗",
    "minivan": "🚙",
    "van":     "🚐",
    "bus":     "🚌",
}
