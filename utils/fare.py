from database import get_setting


async def calculate_fare(distance_km: float, waiting_min: float = 0) -> tuple:
    """
    Returns (fare, base_fare, per_km_rate, base_km, waiting_rate)
    Formula:
        if distance <= base_km  → fare = base_fare
        else → fare = base_fare + (distance - base_km) * per_km_rate
        + waiting_min * waiting_rate
    """
    base_fare    = float(await get_setting("base_fare")    or 100)
    per_km_rate  = float(await get_setting("per_km_rate")  or 50)
    base_km      = float(await get_setting("base_km")      or 2)
    waiting_rate = float(await get_setting("waiting_rate") or 5)

    if distance_km <= base_km:
        fare = base_fare
    else:
        fare = base_fare + (distance_km - base_km) * per_km_rate

    # Add waiting time charge
    if waiting_min > 0:
        fare += waiting_min * waiting_rate

    return round(fare, 2), base_fare, per_km_rate, base_km, waiting_rate
