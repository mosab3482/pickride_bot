import math
import logging
import aiohttp

logger = logging.getLogger(__name__)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cumulative_distance(points: list[tuple[float, float]]) -> float:
    MIN_SEGMENT_KM = 0.01
    total = 0.0
    for i in range(1, len(points)):
        d = haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
        if d >= MIN_SEGMENT_KM:
            total += d
    return total


async def google_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
    api_key: str,
) -> float | None:
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
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=6)) as resp:
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
        logger.warning(f"Google Distance Matrix: {e}")
        return None


async def get_road_distance(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
    api_key: str = "",
) -> tuple[float, str]:
    if api_key:
        d = await google_road_distance(origin_lat, origin_lon, dest_lat, dest_lon, api_key)
        if d is not None:
            return d, "google"
    approx = round(haversine(origin_lat, origin_lon, dest_lat, dest_lon) * 1.3, 2)
    return approx, "haversine"
