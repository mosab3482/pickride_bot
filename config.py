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

VEHICLE_TYPES = {
    "🚗 Car": "car",
    "🛺 Tuk": "tuk",
    "🏍️ Bike": "bike",
    "🚐 Van": "van",
}

VEHICLE_SEATS = {
    "car":  "3-4 Seats",
    "tuk":  "2-3 Seats",
    "bike": "1 Seat",
    "van":  "5+ Seats",
}

VEHICLE_EMOJIS = {
    "car":  "🚗",
    "tuk":  "🛺",
    "bike": "🏍️",
    "van":  "🚐",
}
