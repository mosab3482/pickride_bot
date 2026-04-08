import aiohttp
import logging

logger = logging.getLogger(__name__)

# ── In-memory reverse geocode cache ──────────────────────────────────────────
_geo_cache: dict[tuple, str] = {}

# ── Sri Lanka bounding box (geo-fence) ───────────────────────────────────────
# Any result outside this box is filtered out
_SL_LAT_MIN, _SL_LAT_MAX = 5.7, 10.0
_SL_LON_MIN, _SL_LON_MAX = 79.5, 82.0

# ── API endpoints ─────────────────────────────────────────────────────────────
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
PHOTON_SEARCH     = "https://photon.komoot.io/api/"
NOMINATIM_SEARCH  = "https://nominatim.openstreetmap.org/search"

NOMINATIM_HEADERS = {
    "User-Agent":    "TeleCabsBot/2.0 contact:telecabs.app@gmail.com",
    "Accept-Language": "en",
}
PHOTON_HEADERS = {"User-Agent": "TeleCabsBot/2.0"}


def _in_sri_lanka(lat: float, lon: float) -> bool:
    return _SL_LAT_MIN <= lat <= _SL_LAT_MAX and _SL_LON_MIN <= lon <= _SL_LON_MAX


def _round_coords(lat: float, lon: float, decimals: int = 3) -> tuple:
    return (round(lat, decimals), round(lon, decimals))


# ─────────────────────────────────────────────
#  REVERSE GEOCODING
# ─────────────────────────────────────────────
async def reverse_geocode(lat: float, lon: float) -> str:
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
    params = {"lat": lat, "lon": lon, "format": "json", "zoom": 14, "addressdetails": 1}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                NOMINATIM_REVERSE, params=params, headers=NOMINATIM_HEADERS,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        addr = data.get("address", {})
        area = (
            addr.get("suburb") or addr.get("neighbourhood") or
            addr.get("village") or addr.get("town") or
            addr.get("city") or addr.get("county") or "Unknown Area"
        )
        district = addr.get("state_district") or addr.get("state") or addr.get("country") or ""
        return f"{area}, {district}" if district else area
    except Exception as e:
        logger.warning(f"Nominatim reverse error: {e}")
        return None


async def _reverse_via_photon(lat: float, lon: float) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://photon.komoot.io/reverse",
                params={"lat": lat, "lon": lon, "limit": 1, "lang": "en"},
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
#  Geo-fenced to Sri Lanka
# ─────────────────────────────────────────────
async def search_location(query: str) -> list[dict]:
    """
    Search for a place by name — Sri Lanka only.
    Uses Photon first, then Nominatim as fallback.
    """
    results = await _search_via_photon(query)
    if not results:
        logger.info(f"Photon empty for '{query}', trying Nominatim…")
        results = await _search_via_nominatim(query)
    return results


async def _search_via_photon(query: str) -> list[dict]:
    """
    Photon search restricted to Sri Lanka bounding box.
    bbox = lon_min,lat_min,lon_max,lat_max
    """
    params = {
        "q":    query,
        "limit": 8,
        "lang": "en",
        # Bias results to center of Sri Lanka
        "lat":  7.8731,
        "lon":  80.7718,
        # Bounding box filter: only Sri Lanka
        "bbox": f"{_SL_LON_MIN},{_SL_LAT_MIN},{_SL_LON_MAX},{_SL_LAT_MAX}",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                PHOTON_SEARCH, params=params, headers=PHOTON_HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)

        results = []
        for feat in data.get("features", []):
            props  = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [])
            if len(coords) < 2:
                continue
            lon_val, lat_val = float(coords[0]), float(coords[1])

            # Hard geo-fence: skip anything outside Sri Lanka
            if not _in_sri_lanka(lat_val, lon_val):
                continue

            name_parts = []
            if props.get("name"):
                name_parts.append(props["name"])
            city = props.get("city") or props.get("town") or props.get("village")
            if city:
                name_parts.append(city)
            if props.get("state"):
                name_parts.append(props["state"])

            display = ", ".join(name_parts) if name_parts else query
            results.append({
                "name":      display[:70] + ("…" if len(display) > 70 else ""),
                "full_name": display,
                "lat":       lat_val,
                "lon":       lon_val,
            })

        logger.info(f"Photon found {len(results)} Sri Lanka results for '{query}'")
        return results

    except Exception as e:
        logger.warning(f"Photon search error: {e}")
        return []


async def _search_via_nominatim(query: str) -> list[dict]:
    """Nominatim search — Sri Lanka only via countrycodes filter."""
    params = {
        "q":            query,
        "format":       "json",
        "limit":        6,
        "addressdetails": 1,
        "countrycodes": "lk",   # Sri Lanka ISO code
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                NOMINATIM_SEARCH, params=params, headers=NOMINATIM_HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)

        results = []
        for item in data:
            lat_val = float(item["lat"])
            lon_val = float(item["lon"])
            if not _in_sri_lanka(lat_val, lon_val):
                continue
            display = item.get("display_name", "Unknown")
            results.append({
                "name":      display[:70] + ("…" if len(display) > 70 else ""),
                "full_name": display,
                "lat":       lat_val,
                "lon":       lon_val,
            })

        logger.info(f"Nominatim found {len(results)} Sri Lanka results for '{query}'")
        return results

    except Exception as e:
        logger.warning(f"Nominatim search error: {e}")
        return []
