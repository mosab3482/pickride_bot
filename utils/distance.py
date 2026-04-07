import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance (km) between two points
    on Earth using the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def cumulative_distance(points: list[tuple[float, float]]) -> float:
    """
    Calculate total distance from a list of (lat, lon) tuples.
    Each consecutive pair is measured and summed.
    Ignores very short segments (< 10 meters) to filter GPS noise.
    """
    MIN_SEGMENT_KM = 0.01  # 10 meters
    total = 0.0
    for i in range(1, len(points)):
        d = haversine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
        if d >= MIN_SEGMENT_KM:
            total += d
    return total
