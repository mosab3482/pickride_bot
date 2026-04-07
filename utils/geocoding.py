import aiohttp
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  In-memory reverse-geocode cache
# ─────────────────────────────────────────────
_geo_cache: dict[tuple, str] = {}

# ─── API endpoints ───────────────────────────
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
PHOTON_SEARCH     = "https://photon.komoot.io/api/"
NOMINATIM_SEARCH  = "https://nominatim.openstreetmap.org/search"

# Nominatim requires a valid User-Agent with real app + contact info
NOMINATIM_HEADERS = {
    "User-Agent": "PickRideBot/2.0 contact:pickride.app@gmail.com",
    "Accept-Language": "en",
}

# Photon (by Komoot) — no auth required
PHOTON_HEADERS = {
    "User-Agent": "PickRideBot/2.0",
}


def _round_coords(lat: float, lon: float, decimals: int = 3) -> tuple:
    return (round(lat, decimals), round(lon, decimals))


# ─────────────────────────────────────────────
#  REVERSE GEOCODING  (coords → name)
# ─────────────────────────────────────────────
async def reverse_geocode(lat: float, lon: float) -> str:
    """Return a human-readable name for given coordinates."""
    cache_key = _round_coords(lat, lon)
    if cache_key in _geo_cache:
        return _geo_cache[cache_key]

    result = (
        await _reverse_via_nominatim(lat, lon)
        or await _reverse_via_photon(lat, lon)
        or f"{lat:.4f}, {lon:.4f}"
    )

    _geo_cache[cache_key] = result
    return result


async def _reverse_via_nominatim(lat: float, lon: float) -> str | None:
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 14,
        "addressdetails": 1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                NOMINATIM_REVERSE,
                params=params,
                headers=NOMINATIM_HEADERS,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Nominatim reverse {resp.status}")
                    return None
                data = await resp.json(content_type=None)

        addr = data.get("address", {})
        area = (
            addr.get("suburb") or addr.get("neighbourhood") or
            addr.get("village") or addr.get("town") or
            addr.get("city") or addr.get("county") or "Unknown Area"
        )
        district = (
            addr.get("state_district") or addr.get("state") or
            addr.get("country") or ""
        )
        return f"{area}, {district}" if district else area
    except Exception as e:
        logger.warning(f"Nominatim reverse error: {e}")
        return None


async def _reverse_via_photon(lat: float, lon: float) -> str | None:
    """Reverse geocode using Photon (fallback)."""
    params = {"lat": lat, "lon": lon, "limit": 1, "lang": "en"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://photon.komoot.io/reverse",
                params=params,
                headers=PHOTON_HEADERS,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        features = data.get("features", [])
        if not features:
            return None
        props = features[0].get("properties", {})
        parts = [
            props.get("name", ""),
            props.get("city", "") or props.get("town", "") or props.get("village", ""),
            props.get("state", ""),
        ]
        return ", ".join(p for p in parts if p) or None
    except Exception as e:
        logger.warning(f"Photon reverse error: {e}")
        return None


# ─────────────────────────────────────────────
#  FORWARD SEARCH  (text → list of places)
# ─────────────────────────────────────────────
async def search_location(query: str) -> list[dict]:
    """
    Search for a location by text.
    Returns list of {'name': str, 'lat': float, 'lon': float}
    Tries Photon first (no API key, no rate-limit issues),
    then falls back to Nominatim.
    """
    results = await _search_via_photon(query)
    if not results:
        logger.info(f"Photon returned no results for '{query}', trying Nominatim…")
        results = await _search_via_nominatim(query)
    return results


async def _search_via_photon(query: str) -> list[dict]:
    """
    Photon by Komoot → https://photon.komoot.io/
    Completely free, no key, reliable.
    """
    params = {
        "q": query,
        "limit": 6,
        "lang": "en",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                PHOTON_SEARCH,
                params=params,
                headers=PHOTON_HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                logger.info(f"Photon search status: {resp.status} for '{query}'")
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)

        results = []
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue

            lon_val, lat_val = coords[0], coords[1]

            # Build a readable name
            name_parts = []
            if props.get("name"):
                name_parts.append(props["name"])
            if props.get("city") or props.get("town") or props.get("village"):
                name_parts.append(
                    props.get("city") or props.get("town") or props.get("village")
                )
            if props.get("state"):
                name_parts.append(props["state"])
            if props.get("country"):
                name_parts.append(props["country"])

            display = ", ".join(name_parts) if name_parts else query
            short_name = display[:70] + ("…" if len(display) > 70 else "")

            results.append({
                "name": short_name,
                "full_name": display,
                "lat": float(lat_val),
                "lon": float(lon_val),
            })

        logger.info(f"Photon found {len(results)} results for '{query}'")
        return results

    except Exception as e:
        logger.warning(f"Photon search error for '{query}': {e}")
        return []


async def _search_via_nominatim(query: str) -> list[dict]:
    """Nominatim search fallback."""
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "addressdetails": 1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                NOMINATIM_SEARCH,
                params=params,
                headers=NOMINATIM_HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                logger.info(f"Nominatim search status: {resp.status} for '{query}'")
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)

        results = []
        for item in data:
            display = item.get("display_name", "Unknown")
            short_name = display[:70] + ("…" if len(display) > 70 else "")
            results.append({
                "name": short_name,
                "full_name": display,
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            })

        logger.info(f"Nominatim found {len(results)} results for '{query}'")
        return results

    except Exception as e:
        logger.warning(f"Nominatim search error for '{query}': {e}")
        return []
