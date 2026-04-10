from database import get_setting

# Vehicle types supported
VEHICLE_TYPES = ("bike", "tuk", "car", "minivan", "van", "bus")

VEHICLE_EMOJIS = {
    "bike":    "🏍️",
    "tuk":     "🛺",
    "car":     "🚗",
    "minivan": "🚙",
    "van":     "🚐",
    "bus":     "🚌",
}


async def get_vehicle_rates(vehicle_type: str) -> tuple[float, float, float, float]:
    """
    Returns (base_fare, per_km_rate, base_km, waiting_rate) for a given vehicle type.
    Falls back to global rate if no vehicle-specific rate is set.
    """
    # Global defaults
    global_base   = float(await get_setting("base_fare")    or 100)
    global_rate   = float(await get_setting("per_km_rate")  or 50)
    global_basekm = float(await get_setting("base_km")      or 2)
    global_wait   = float(await get_setting("waiting_rate") or 5)

    vt = vehicle_type.lower() if vehicle_type else "car"

    # Per-vehicle overrides (None = not set → use global)
    base_raw   = await get_setting(f"base_fare_{vt}")
    rate_raw   = await get_setting(f"per_km_rate_{vt}")
    basekm_raw = await get_setting(f"base_km_{vt}")
    wait_raw   = await get_setting(f"waiting_rate_{vt}")

    base_fare   = float(base_raw)   if base_raw   else global_base
    per_km_rate = float(rate_raw)   if rate_raw   else global_rate
    base_km     = float(basekm_raw) if basekm_raw else global_basekm
    waiting_rate = float(wait_raw)  if wait_raw   else global_wait

    return base_fare, per_km_rate, base_km, waiting_rate


async def calculate_fare(
    distance_km: float,
    waiting_min: float = 0,
    vehicle_type: str = "car",
) -> tuple:
    """
    Returns (fare, base_fare, per_km_rate, base_km, waiting_rate)

    Formula:
        if distance <= base_km  → fare = base_fare
        else → fare = base_fare + (distance - base_km) * per_km_rate
        + waiting_min * waiting_rate
    """
    base_fare, per_km_rate, base_km, waiting_rate = await get_vehicle_rates(vehicle_type)

    if distance_km <= base_km:
        fare = base_fare
    else:
        fare = base_fare + (distance_km - base_km) * per_km_rate

    if waiting_min > 0:
        fare += waiting_min * waiting_rate

    return round(fare, 2), base_fare, per_km_rate, base_km, waiting_rate
