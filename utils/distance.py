import math
import logging
import aiohttp

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Distance Methods
#  - "google"    : Google Distance Matrix API (most accurate, costs money)
#  - "osrm"      : OSRM Open-Source Routing (free, road-accurate)
#  - "haversine" : Straight-line × 1.3 factor (offline fallback)
# ─────────────────────────────────────────────

METHOD_LABELS = {
    "google":    "🌐 Google Maps API",
    "osrm":      "🗺️ OSRM (Free Routing)",
    "haversine": "📐 Haversine (Straight-line)",
}

METHOD_DESCRIPTIONS = {
    "google":    "Road distance via Google Distance Matrix API.\nMost accurate but requires paid API key.",
    "osrm":      "Road distance via OSRM open-source routing.\nFree, accurate road distances — recommended.",
    "haversine": "Straight-line distance × 1.3 multiplier.\nFast offline fallback, less accurate.",
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
        "mode": "driving", "units": "metric", "key": api_key,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        if data.get("status") != "OK":
            return None
        el = data["rows"][0]["elements"][0]
        if el.get("status") != "OK":
            return None
        return round(el["distance"]["value"] / 1000, 2)
    except Exception as e:
        logger.warning(f"Google Distance Matrix error: {e}")
        return None


# ─────────────────────────────────────────────
#  Method 2: OSRM (Open Source Routing Machine)
# ─────────────────────────────────────────────
async def osrm_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
) -> float | None:
    """
    Get road distance using the public OSRM demo server (free, no API key).
    Uses router.project-osrm.org — the global public instance.
    """
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        f"?overview=false&annotations=false"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        if data.get("code") != "Ok":
            return None
        routes = data.get("routes")
        if not routes:
            return None
        distance_m = routes[0]["distance"]
        return round(distance_m / 1000, 2)
    except Exception as e:
        logger.warning(f"OSRM routing error: {e}")
        return None


# ─────────────────────────────────────────────
#  Unified distance function — reads method from DB setting
# ─────────────────────────────────────────────
async def get_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
    api_key: str = "",
    method: str = "osrm",           # "google" | "osrm" | "haversine"
) -> tuple[float, str]:
    """
    Returns (distance_km, method_used).
    Falls back to haversine if chosen method fails.
    """
    method = (method or "osrm").lower()

    if method == "google":
        d = await google_road_distance(origin_lat, origin_lon, dest_lat, dest_lon, api_key)
        if d is not None:
            return d, "google"
        logger.warning("Google Maps failed — falling back to haversine")

    elif method == "osrm":
        d = await osrm_road_distance(origin_lat, origin_lon, dest_lat, dest_lon)
        if d is not None:
            return d, "osrm"
        logger.warning("OSRM failed — falling back to haversine")

    # Fallback: haversine × 1.3
    approx = round(haversine(origin_lat, origin_lon, dest_lat, dest_lon) * 1.3, 2)
    return approx, "haversine"
