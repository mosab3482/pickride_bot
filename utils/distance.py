import math
import logging
import aiohttp

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Distance Methods
#  - "google"    : Google Distance Matrix API (most accurate, paid)
#  - "osrm"      : OSRM Open-Source Routing (free, road-accurate)
#  - "haversine" : Straight-line × road_factor (offline fallback)
# ─────────────────────────────────────────────

# Sri Lanka has mountainous terrain — straight-line distances are
# significantly shorter than road distances. A 1.4× multiplier is more
# realistic than the standard 1.3× used for flat countries.
SL_ROAD_FACTOR = 1.4

METHOD_LABELS = {
    "google":    "🌐 Google Maps API",
    "osrm":      "🗺️ OSRM (Free Routing)",
    "haversine": "📐 Haversine (Straight-line est.)",
}

METHOD_DESCRIPTIONS = {
    "google":    "Road distance via Google Distance Matrix API.\nMost accurate but requires paid API key.",
    "osrm":      "Road distance via OSRM open-source routing.\nFree, accurate road distances — recommended.",
    "haversine": f"Straight-line distance × {SL_ROAD_FACTOR} multiplier.\nFast offline fallback, less accurate.",
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate straight-line distance in km between two GPS points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cumulative_distance(points: list[tuple[float, float]]) -> float:
    """Calculate total distance from a list of GPS points (for live tracking)."""
    MIN_SEGMENT_KM = 0.01
    total = 0.0
    for i in range(1, len(points)):
        d = haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
        if d >= MIN_SEGMENT_KM:
            total += d
    return total


# ─────────────────────────────────────────────
#  Method 1: Google Distance Matrix API
# ─────────────────────────────────────────────
async def google_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
    api_key: str,
) -> float | None:
    """Get road distance using Google Distance Matrix API."""
    if not api_key:
        return None
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins":      f"{origin_lat},{origin_lon}",
        "destinations": f"{dest_lat},{dest_lon}",
        "mode":   "driving",
        "units":  "metric",
        "key":    api_key,
        # Avoid ferries — keeps routes on roads
        "avoid":  "ferries",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"Google Distance Matrix HTTP {resp.status}")
                    return None
                data = await resp.json(content_type=None)

        api_status = data.get("status", "")
        if api_status != "OK":
            logger.warning(f"Google Distance Matrix API status: {api_status}")
            return None

        el = data["rows"][0]["elements"][0]
        el_status = el.get("status", "")
        if el_status != "OK":
            logger.warning(f"Google Distance Matrix element status: {el_status}")
            return None

        meters = el["distance"]["value"]
        km = round(meters / 1000, 2)
        logger.info(f"Google Distance Matrix: {km} km")
        return km

    except Exception as e:
        logger.warning(f"Google Distance Matrix error: {e}")
        return None


# ─────────────────────────────────────────────
#  Method 2: OSRM — multiple servers for reliability
# ─────────────────────────────────────────────
# We try multiple OSRM servers in order. The public demo server can be
# unreliable for Sri Lanka. routing.openstreetmap.de often gives better results.
_OSRM_SERVERS = [
    "https://router.project-osrm.org",
    "https://routing.openstreetmap.de/routed-car",
]

async def osrm_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
) -> float | None:
    """
    Get road distance using OSRM routing.
    Tries multiple public servers for better reliability.
    """
    coord_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"

    for base in _OSRM_SERVERS:
        url = f"{base}/route/v1/driving/{coord_str}?overview=false&annotations=false"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json(content_type=None)

            if data.get("code") != "Ok":
                continue

            routes = data.get("routes")
            if not routes:
                continue

            km = round(routes[0]["distance"] / 1000, 2)
            logger.info(f"OSRM ({base}): {km} km")
            return km

        except Exception as e:
            logger.warning(f"OSRM server {base} error: {e}")
            continue

    logger.warning("All OSRM servers failed")
    return None


# ─────────────────────────────────────────────
#  Unified distance function
# ─────────────────────────────────────────────
async def get_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
    api_key: str = "",
    method: str = "osrm",   # "google" | "osrm" | "haversine"
) -> tuple[float, str]:
    """
    Returns (distance_km, method_used).

    Strategy:
    - If Google API key is set AND method is "google"  → use Google
    - If method is "osrm"                               → use OSRM
    - Always fall back to haversine × SL_ROAD_FACTOR if API fails

    Auto-upgrade: If method == "osrm" but Google key is available and OSRM
    fails, we try Google before final haversine fallback.
    """
    method = (method or "osrm").lower()

    # ── Google ──────────────────────────────────────────────────────────────
    if method == "google":
        if not api_key:
            logger.warning("Google method selected but no API key — falling back to OSRM")
        else:
            d = await google_road_distance(origin_lat, origin_lon, dest_lat, dest_lon, api_key)
            if d is not None:
                return d, "google"
            logger.warning("Google Distance Matrix failed — trying OSRM")
            # Try OSRM before haversine
            d = await osrm_road_distance(origin_lat, origin_lon, dest_lat, dest_lon)
            if d is not None:
                return d, "osrm"

    # ── OSRM ────────────────────────────────────────────────────────────────
    elif method == "osrm":
        d = await osrm_road_distance(origin_lat, origin_lon, dest_lat, dest_lon)
        if d is not None:
            return d, "osrm"
        logger.warning("OSRM failed")
        # If we have a Google key, try it before haversine
        if api_key:
            logger.info("Trying Google as OSRM fallback")
            d = await google_road_distance(origin_lat, origin_lon, dest_lat, dest_lon, api_key)
            if d is not None:
                return d, "google"

    # ── Haversine fallback ───────────────────────────────────────────────────
    straight = haversine(origin_lat, origin_lon, dest_lat, dest_lon)
    approx   = round(straight * SL_ROAD_FACTOR, 2)
    logger.info(f"Haversine fallback: {straight:.2f} km straight → {approx} km estimated")
    return approx, "haversine"
