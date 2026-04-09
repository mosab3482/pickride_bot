import aiohttp
import logging

logger = logging.getLogger(__name__)

# ── In-memory caches ──────────────────────────────────────────────────────────
_geo_cache: dict[tuple, str] = {}
# Track which Google API features are available (discovered at runtime)
_google_geocoding_ok: bool | None = None   # None = untested
_google_places_ok:    bool | None = None   # None = untested

# ── Sri Lanka bounding box ────────────────────────────────────────────────────
_SL_LAT_MIN, _SL_LAT_MAX = 5.7, 10.0
_SL_LON_MIN, _SL_LON_MAX = 79.5, 82.0

# ── API endpoints ─────────────────────────────────────────────────────────────
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
PHOTON_SEARCH     = "https://photon.komoot.io/api/"
NOMINATIM_SEARCH  = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODE    = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_PLACES     = "https://maps.googleapis.com/maps/api/place/textsearch/json"

NOMINATIM_HEADERS = {
    "User-Agent":    "TeleCabsBot/2.0 contact:telecabs.app@gmail.com",
    "Accept-Language": "en",
}
PHOTON_HEADERS = {"User-Agent": "TeleCabsBot/2.0"}


def _in_sri_lanka(lat: float, lon: float) -> bool:
    return _SL_LAT_MIN <= lat <= _SL_LAT_MAX and _SL_LON_MIN <= lon <= _SL_LON_MAX


def _round_coords(lat: float, lon: float, decimals: int = 3) -> tuple:
    return (round(lat, decimals), round(lon, decimals))


# ─────────────────────────────────────────────────────────────────────────────
#  REVERSE GEOCODING (coordinates → place name)
# ─────────────────────────────────────────────────────────────────────────────
async def reverse_geocode(lat: float, lon: float, api_key: str = "") -> str:
    """Reverse-geocode coordinates to a human-readable place name.
    Priority: Google Geocoding API → Nominatim → Photon → raw coords
    """
    cache_key = _round_coords(lat, lon)
    if cache_key in _geo_cache:
        return _geo_cache[cache_key]

    result = None

    # 1) Try Google Geocoding if key available and not previously denied
    if api_key and _google_geocoding_ok is not False:
        result = await _reverse_via_google(lat, lon, api_key)

    # 2) Nominatim (free, solid Sri Lanka coverage)
    if not result:
        result = await _reverse_via_nominatim(lat, lon)

    # 3) Photon final fallback
    if not result:
        result = await _reverse_via_photon(lat, lon)

    result = result or f"{lat:.4f}, {lon:.4f}"
    _geo_cache[cache_key] = result
    return result


async def _reverse_via_google(lat: float, lon: float, api_key: str) -> str | None:
    """Reverse geocode using Google Geocoding API."""
    global _google_geocoding_ok
    try:
        params = {
            "latlng":      f"{lat},{lon}",
            "key":         api_key,
            "result_type": "sublocality|locality|administrative_area_level_2",
            "language":    "en",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GOOGLE_GEOCODE, params=params,
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        status = data.get("status", "")
        if status in ("REQUEST_DENIED", "OVER_DAILY_LIMIT", "OVER_QUERY_LIMIT"):
            logger.warning(f"Google Geocoding API: {status} — disabling for this session")
            _google_geocoding_ok = False
            return None

        _google_geocoding_ok = True
        if status != "OK":
            return None

        results = data.get("results", [])
        if not results:
            return None

        components = results[0].get("address_components", [])
        locality = sublocality = district = state = None
        for comp in components:
            types = comp.get("types", [])
            if "sublocality" in types or "sublocality_level_1" in types:
                sublocality = comp["long_name"]
            elif "locality" in types:
                locality = comp["long_name"]
            elif "administrative_area_level_2" in types:
                district = comp["long_name"]
            elif "administrative_area_level_1" in types:
                state = comp["long_name"]

        area   = sublocality or locality or district or "Unknown"
        region = district or state or ""
        return f"{area}, {region}" if region and region != area else area

    except Exception as e:
        logger.warning(f"Google reverse geocode error: {e}")
        return None


async def _reverse_via_nominatim(lat: float, lon: float) -> str | None:
    params = {
        "lat": lat, "lon": lon, "format": "json",
        "zoom": 14, "addressdetails": 1,
    }
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
        district = addr.get("state_district") or addr.get("state") or ""
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


# ─────────────────────────────────────────────────────────────────────────────
#  FORWARD SEARCH  (text → list of places)  — Sri Lanka geo-fenced
# ─────────────────────────────────────────────────────────────────────────────
async def search_location(query: str, api_key: str = "") -> list[dict]:
    """
    Search for a place by name — Sri Lanka only.
    Priority: Google Places → Photon → Nominatim
    """
    # 1) Google Places — best coverage (hotels, landmarks, local names)
    if api_key and _google_places_ok is not False:
        results = await _search_via_google(query, api_key)
        if results:
            return results

    # 2) Photon — good OSM coverage
    results = await _search_via_photon(query)
    if results:
        return results

    # 3) Nominatim — thorough but slower, Sri Lanka only
    logger.info(f"Photon found 0 results for '{query}', trying Nominatim…")
    return await _search_via_nominatim(query)


async def _search_via_google(query: str, api_key: str) -> list[dict]:
    """Google Places Text Search restricted to Sri Lanka."""
    global _google_places_ok
    try:
        params = {
            "query":    query + " Sri Lanka",
            "key":      api_key,
            "language": "en",
            "location": "7.8731,80.7718",
            "radius":   300000,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GOOGLE_PLACES, params=params,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)

        status = data.get("status", "")
        if status in ("REQUEST_DENIED", "OVER_DAILY_LIMIT", "OVER_QUERY_LIMIT"):
            logger.warning(f"Google Places API: {status} — disabling for this session")
            _google_places_ok = False
            return []

        _google_places_ok = True
        if status not in ("OK", "ZERO_RESULTS"):
            return []

        results = []
        for place in data.get("results", [])[:8]:
            loc = place.get("geometry", {}).get("location", {})
            lat_val = loc.get("lat")
            lon_val = loc.get("lng")
            if lat_val is None or lon_val is None:
                continue
            if not _in_sri_lanka(lat_val, lon_val):
                continue

            name    = place.get("name", "")
            address = place.get("formatted_address", "")
            address = address.replace(", Sri Lanka", "").strip().rstrip(",")
            display = f"{name}, {address}" if address and address != name else name

            results.append({
                "name":      display[:70] + ("…" if len(display) > 70 else ""),
                "full_name": display,
                "lat":       lat_val,
                "lon":       lon_val,
            })

        logger.info(f"Google Places found {len(results)} results for '{query}'")
        return results

    except Exception as e:
        logger.warning(f"Google Places search error: {e}")
        return []


async def _search_via_photon(query: str) -> list[dict]:
    """Photon search restricted to Sri Lanka bounding box."""
    params = {
        "q":    query,
        "limit": 8,
        "lang": "en",
        # Bias towards Sri Lanka center
        "lat":  7.8731,
        "lon":  80.7718,
        # Hard bounding box
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
    """Nominatim search — Sri Lanka only."""
    params = {
        "q":             query,
        "format":        "json",
        "limit":         8,
        "addressdetails": 1,
        "countrycodes":  "lk",
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
            addr    = item.get("address", {})
            # Build a short, clean display name
            area    = (addr.get("amenity") or addr.get("tourism") or
                       addr.get("suburb") or addr.get("neighbourhood") or
                       addr.get("village") or addr.get("town") or
                       addr.get("city") or item.get("display_name", "Unknown").split(",")[0])
            district = addr.get("state_district") or addr.get("state") or ""
            display  = f"{area}, {district}" if district else area
            display  = display.strip(", ")

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
