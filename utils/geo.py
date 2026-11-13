import math
from typing import Tuple


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Ikki koordinata orasidagi masofani (metrlarda) Haversine formulasi orqali hisoblaydi.
    """
    R = 6371000.0  # Yer radiusi metrlarda

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = R * c
    return round(distance, 2)


def is_within_radius(
    user_lat: float,
    user_lon: float,
    target_lat: float,
    target_lon: float,
    radius_meters: float
) -> Tuple[bool, float]:
    """
    Foydalanuvchi belgilangan radius ichida ekanligini tekshiradi.
    Qaytaradi: (ichidami, masofa_metrlarda)
    """
    dist = calculate_distance(user_lat, user_lon, target_lat, target_lon)
    return dist <= radius_meters, dist
