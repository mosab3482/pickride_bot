import aiohttp
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# In-memory cache: (lat_rounded, lon_rounded) → "Area, District"
_geo_cache: dict[tuple, str] = {}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {
    "User-Agent": "PickRideBot/1.0 (pickride-support@example.com)"
}


def _round_coords(lat: float, lon: float, decimals: int = 3) -> tuple:
    """Round coordinates to reduce cache misses for nearby points."""
    return (round(lat, decimals), round(lon, decimals))


async def reverse_geocode(lat: float, lon: float) -> str:
    """
    Return a human-readable location name using Nominatim.
    Format: "Area, District" or "City, Country" as fallback.
    Results are cached.
    """
    cache_key = _round_coords(lat, lon)
    if cache_key in _geo_cache:
        return _geo_cache[cache_key]

    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 14,
        "addressdetails": 1,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return f"{lat:.4f}, {lon:.4f}"
                data = await resp.json()

        addr = data.get("address", {})

        # Priority order for area name
        area = (
            addr.get("suburb") or
            addr.get("neighbourhood") or
            addr.get("village") or
            addr.get("town") or
            addr.get("city") or
            addr.get("county") or
            "Unknown Area"
        )

        district = (
            addr.get("state_district") or
            addr.get("state") or
            addr.get("country") or
            ""
        )

        result = f"{area}, {district}" if district else area
        _geo_cache[cache_key] = result
        return result

    except Exception as e:
        logger.warning(f"Nominatim error for ({lat},{lon}): {e}")
        return f"{lat:.4f}, {lon:.4f}"


async def search_location(query: str) -> list[dict]:
    """
    Search for a location by text query.
    Returns list of {'name': str, 'lat': float, 'lon': float}
    """
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "addressdetails": 1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

        results = []
        for item in data:
            display = item.get("display_name", "Unknown")
            # Shorten display name to first 60 chars
            short_name = display[:60] + ("..." if len(display) > 60 else "")
            results.append({
                "name": short_name,
                "full_name": display,
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            })
        return results
    except Exception as e:
        logger.warning(f"Nominatim search error: {e}")
        return []
