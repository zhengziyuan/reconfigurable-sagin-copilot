from __future__ import annotations

import random
from typing import Any


def sample_uncertainty(base_weather: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    rain = float(base_weather.get("rain_rate_mm_h", 12.0))
    humidity = float(base_weather.get("water_vapor_density_g_m3", 7.5))
    pressure = float(base_weather.get("pressure_hpa", 1013.25))
    return {
        "rain_rate_mm_h": max(0.0, rng.gauss(rain, max(2.0, 0.28 * rain))),
        "water_vapor_density_g_m3": max(0.5, rng.gauss(humidity, 1.8)),
        "pressure_hpa": max(850.0, rng.gauss(pressure, 8.0)),
        "shadow_loss_scale": max(0.65, min(1.45, rng.gauss(1.0, 0.18))),
        "traffic_scale": max(0.55, min(1.70, rng.gauss(1.0, 0.25))),
        "hardware_gain_error_db": max(-3.0, min(3.0, rng.gauss(0.0, 1.1))),
    }
