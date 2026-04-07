import asyncpg
import ssl
import logging
import time
from config import (
    DATABASE_URL, DEFAULT_BASE_FARE, DEFAULT_PER_KM_RATE,
    DEFAULT_BASE_KM, DEFAULT_DRIVER_RADIUS, DEFAULT_WAITING_RATE,
)

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # Railway PostgreSQL requires SSL
        kwargs = {"min_size": 2, "max_size": 10}
        if "sslmode" in DATABASE_URL or "railway" in DATABASE_URL:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl"] = ssl_ctx
        _pool = await asyncpg.create_pool(DATABASE_URL, **kwargs)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ─────────────────────────────────────────────
#  INIT DB
# ─────────────────────────────────────────────
async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     BIGINT PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                phone       TEXT,
                role        TEXT DEFAULT 'rider',
                is_blocked  BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS drivers (
                user_id         BIGINT PRIMARY KEY REFERENCES users(user_id),
                full_name       TEXT,
                plate_number    TEXT,
                vehicle_type    TEXT,
                current_lat     DOUBLE PRECISION,
                current_lon     DOUBLE PRECISION,
                is_online       BOOLEAN DEFAULT TRUE,
                is_muted        BOOLEAN DEFAULT FALSE,
                rating_sum      DOUBLE PRECISION DEFAULT 0,
                rating_count    INT DEFAULT 0,
                registered_at   TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS rides (
                ride_id         SERIAL PRIMARY KEY,
                rider_id        BIGINT REFERENCES users(user_id),
                driver_id       BIGINT REFERENCES users(user_id),
                vehicle_type    TEXT,
                pickup_lat      DOUBLE PRECISION,
                pickup_lon      DOUBLE PRECISION,
                dropoff_lat     DOUBLE PRECISION,
                dropoff_lon     DOUBLE PRECISION,
                pickup_name     TEXT,
                dropoff_name    TEXT,
                status          TEXT DEFAULT 'pending',
                distance_km     DOUBLE PRECISION DEFAULT 0,
                fare            DOUBLE PRECISION DEFAULT 0,
                waiting_min     DOUBLE PRECISION DEFAULT 0,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                started_at      TIMESTAMPTZ,
                completed_at    TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS location_points (
                id          SERIAL PRIMARY KEY,
                ride_id     INT REFERENCES rides(ride_id) ON DELETE CASCADE,
                driver_id   BIGINT,
                lat         DOUBLE PRECISION,
                lon         DOUBLE PRECISION,
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS settings (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ratings (
                id          SERIAL PRIMARY KEY,
                ride_id     INT REFERENCES rides(ride_id),
                rider_id    BIGINT,
                driver_id   BIGINT,
                stars       INT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS blocked_categories (
                vehicle_type TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS route_cache (
                route_key       TEXT PRIMARY KEY,
                distance_km     DOUBLE PRECISION,
                estimated_fare  DOUBLE PRECISION,
                expires_at      BIGINT,
                last_used       BIGINT,
                usage_count     INT DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id     BIGINT PRIMARY KEY,
                added_by    BIGINT,
                added_at    TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Add unique index on ratings to prevent duplicates
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ratings_ride_rider
            ON ratings(ride_id, rider_id);
        """)

        # Add waiting_min column if missing (for existing databases)
        try:
            await conn.execute("""
                ALTER TABLE rides ADD COLUMN IF NOT EXISTS waiting_min
                DOUBLE PRECISION DEFAULT 0;
            """)
        except Exception:
            pass  # Column already exists

        # Insert default settings if not present
        defaults = {
            "base_fare":     str(DEFAULT_BASE_FARE),
            "per_km_rate":   str(DEFAULT_PER_KM_RATE),
            "base_km":       str(DEFAULT_BASE_KM),
            "waiting_rate":  str(DEFAULT_WAITING_RATE),
            "driver_radius": str(DEFAULT_DRIVER_RADIUS),
        }
        for key, val in defaults.items():
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING
            """, key, val)

    logger.info("Database initialized successfully.")


# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
async def get_setting(key: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return row["value"] if row else None


async def set_setting(key: str, value: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value=$2
        """, key, value)


# ─────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────
async def upsert_user(user_id: int, username: str, first_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET username=$2, first_name=$3
        """, user_id, username, first_name)


async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)


async def set_user_phone(user_id: int, phone: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone=$2 WHERE user_id=$1", user_id, phone)


async def set_user_role(user_id: int, role: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET role=$2 WHERE user_id=$1", user_id, role)


async def block_user(user_id: int, blocked: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_blocked=$2 WHERE user_id=$1", user_id, blocked)


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")


async def get_all_riders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE role='rider' ORDER BY created_at DESC")


# ─────────────────────────────────────────────
#  DRIVERS
# ─────────────────────────────────────────────
async def upsert_driver(user_id: int, full_name: str, plate: str, vehicle_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO drivers (user_id, full_name, plate_number, vehicle_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                full_name=$2, plate_number=$3, vehicle_type=$4
        """, user_id, full_name, plate, vehicle_type)
        await conn.execute("UPDATE users SET role='driver' WHERE user_id=$1", user_id)


async def get_driver(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM drivers WHERE user_id=$1", user_id)


async def delete_driver(user_id: int):
    """Delete driver record — used by /regis to allow full re-registration."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM drivers WHERE user_id=$1", user_id)
        await conn.execute(
            "UPDATE users SET role='rider' WHERE user_id=$1", user_id
        )


async def update_driver_location(user_id: int, lat: float, lon: float):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE drivers SET current_lat=$2, current_lon=$3
            WHERE user_id=$1
        """, user_id, lat, lon)


async def set_driver_mute(user_id: int, muted: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE drivers SET is_muted=$2 WHERE user_id=$1", user_id, muted)


async def set_driver_online(user_id: int, online: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE drivers SET is_online=$2 WHERE user_id=$1", user_id, online)


async def get_all_drivers():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT d.*, u.username, u.first_name, u.phone, u.is_blocked
            FROM drivers d JOIN users u ON d.user_id=u.user_id
            ORDER BY d.registered_at DESC
        """)


async def get_nearby_drivers(lat: float, lon: float, radius_km: float, vehicle_type: str):
    """Return online, unmuted, unblocked drivers within radius_km."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT d.user_id, d.current_lat, d.current_lon, d.full_name,
                   u.username, u.phone
            FROM drivers d JOIN users u ON d.user_id=u.user_id
            WHERE d.vehicle_type=$1
              AND d.is_online=TRUE
              AND d.is_muted=FALSE
              AND d.current_lat IS NOT NULL
              AND d.current_lon IS NOT NULL
              AND u.is_blocked=FALSE
        """, vehicle_type)

        from utils.distance import haversine
        nearby = []
        for row in rows:
            dist = haversine(lat, lon, row["current_lat"], row["current_lon"])
            if dist <= radius_km:
                nearby.append(dict(row) | {"dist_km": dist})
        return nearby


async def update_driver_rating(driver_id: int, stars: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE drivers SET rating_sum=rating_sum+$2, rating_count=rating_count+1
            WHERE user_id=$1
        """, driver_id, stars)


# ─────────────────────────────────────────────
#  RIDES
# ─────────────────────────────────────────────
async def create_ride(rider_id: int, vehicle_type: str,
                      pickup_lat: float, pickup_lon: float,
                      dropoff_lat: float, dropoff_lon: float,
                      pickup_name: str, dropoff_name: str,
                      distance_km: float, fare: float) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO rides
                (rider_id, vehicle_type, pickup_lat, pickup_lon,
                 dropoff_lat, dropoff_lon, pickup_name, dropoff_name,
                 distance_km, fare, status)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending')
            RETURNING ride_id
        """, rider_id, vehicle_type,
             pickup_lat, pickup_lon,
             dropoff_lat, dropoff_lon,
             pickup_name, dropoff_name,
             distance_km, fare)
        return row["ride_id"]


async def get_ride(ride_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM rides WHERE ride_id=$1", ride_id)


async def accept_ride(ride_id: int, driver_id: int) -> bool:
    """Atomically accept a ride. Returns True if successful (first acceptor)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("""
            UPDATE rides SET status='accepted', driver_id=$2
            WHERE ride_id=$1 AND status='pending'
        """, ride_id, driver_id)
        return result == "UPDATE 1"


async def start_ride(ride_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE rides SET status='in_progress', started_at=NOW()
            WHERE ride_id=$1
        """, ride_id)


async def complete_ride(ride_id: int, distance_km: float, fare: float,
                        waiting_min: float = 0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE rides SET status='completed', completed_at=NOW(),
                distance_km=$2, fare=$3, waiting_min=$4
            WHERE ride_id=$1
        """, ride_id, distance_km, fare, waiting_min)


async def cancel_ride(ride_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE rides SET status='cancelled' WHERE ride_id=$1
        """, ride_id)


async def get_active_ride_for_rider(rider_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM rides
            WHERE rider_id=$1 AND status IN ('pending','accepted','in_progress')
            ORDER BY created_at DESC LIMIT 1
        """, rider_id)


async def get_active_ride_for_driver(driver_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM rides
            WHERE driver_id=$1 AND status IN ('accepted','in_progress')
            ORDER BY created_at DESC LIMIT 1
        """, driver_id)


async def get_trip_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status='completed') as completed,
                COUNT(*) FILTER (WHERE status='cancelled') as cancelled,
                COUNT(*) FILTER (WHERE status='pending')   as pending,
                COUNT(*) FILTER (WHERE status='in_progress') as in_progress,
                COUNT(*) as total,
                COALESCE(SUM(fare) FILTER (WHERE status='completed'), 0) as total_revenue
            FROM rides
        """)


# ─────────────────────────────────────────────
#  LOCATION POINTS
# ─────────────────────────────────────────────
async def add_location_point(ride_id: int, driver_id: int, lat: float, lon: float):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO location_points (ride_id, driver_id, lat, lon)
            VALUES ($1, $2, $3, $4)
        """, ride_id, driver_id, lat, lon)


async def get_location_points(ride_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT lat, lon FROM location_points
            WHERE ride_id=$1 ORDER BY recorded_at ASC
        """, ride_id)


# ─────────────────────────────────────────────
#  RATINGS
# ─────────────────────────────────────────────
async def save_rating(ride_id: int, rider_id: int, driver_id: int, stars: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO ratings (ride_id, rider_id, driver_id, stars)
            VALUES ($1,$2,$3,$4) ON CONFLICT (ride_id, rider_id) DO NOTHING
        """, ride_id, rider_id, driver_id, stars)
        await update_driver_rating(driver_id, stars)


# ─────────────────────────────────────────────
#  BLOCKED CATEGORIES
# ─────────────────────────────────────────────
async def block_category(vehicle_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO blocked_categories (vehicle_type) VALUES ($1)
            ON CONFLICT DO NOTHING
        """, vehicle_type)


async def unblock_category(vehicle_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM blocked_categories WHERE vehicle_type=$1", vehicle_type)


async def get_blocked_categories():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT vehicle_type FROM blocked_categories")
        return {r["vehicle_type"] for r in rows}


# ─────────────────────────────────────────────
#  ROUTE CACHE — 24h + auto-extend
# ─────────────────────────────────────────────
def _make_route_key(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Create a normalized cache key from rounded coordinates."""
    return f"{round(lat1,3)}_{round(lon1,3)}__{round(lat2,3)}_{round(lon2,3)}"


async def get_cached_route(lat1: float, lon1: float,
                           lat2: float, lon2: float) -> dict | None:
    """Get cached route if valid. Auto-extends expiry on hit."""
    route_key = _make_route_key(lat1, lon1, lat2, lon2)
    now = int(time.time())
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM route_cache WHERE route_key=$1", route_key
        )
        if not row:
            return None
        if row["expires_at"] < now:
            # Expired — delete and return None
            await conn.execute(
                "DELETE FROM route_cache WHERE route_key=$1", route_key
            )
            return None
        # Cache hit — extend expiry + bump usage
        await conn.execute("""
            UPDATE route_cache
            SET expires_at=$2, last_used=$3, usage_count=usage_count+1
            WHERE route_key=$1
        """, route_key, now + 86400, now)
        return dict(row)


async def set_cached_route(lat1: float, lon1: float,
                           lat2: float, lon2: float,
                           distance_km: float, estimated_fare: float):
    """Store route in cache with 24h TTL."""
    route_key = _make_route_key(lat1, lon1, lat2, lon2)
    now = int(time.time())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO route_cache
                (route_key, distance_km, estimated_fare, expires_at, last_used, usage_count)
            VALUES ($1, $2, $3, $4, $5, 1)
            ON CONFLICT (route_key) DO UPDATE SET
                distance_km=$2, estimated_fare=$3,
                expires_at=$4, last_used=$5, usage_count=1
        """, route_key, distance_km, estimated_fare, now + 86400, now)


async def cleanup_expired_cache():
    """Remove all expired route cache entries."""
    now = int(time.time())
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM route_cache WHERE expires_at < $1", now
        )
        logger.info(f"Route cache cleanup: {result}")


# ─────────────────────────────────────────────
#  DYNAMIC ADMINS
# ─────────────────────────────────────────────
async def add_admin(user_id: int, added_by: int):
    """Add a new admin to the database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO admins (user_id, added_by)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, added_by)


async def remove_admin(user_id: int) -> bool:
    """Remove an admin. Returns True if removed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM admins WHERE user_id=$1", user_id
        )
        return result == "DELETE 1"


async def get_all_admins() -> list:
    """Get all dynamically added admins."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM admins ORDER BY added_at DESC"
        )


async def is_db_admin(user_id: int) -> bool:
    """Check if user is a dynamic admin (added via bot)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM admins WHERE user_id=$1", user_id
        )
        return row is not None

