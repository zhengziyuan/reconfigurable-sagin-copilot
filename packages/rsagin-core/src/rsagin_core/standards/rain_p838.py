"""ITU-R P.838-3 equations (1)-(5), Tables 1-4. Frequency in GHz."""
from __future__ import annotations

import math

SOURCE = "https://www.itu.int/rec/R-REC-P.838-3-200503-I/en"

# (a, b, c) Gaussian terms, followed by slope and intercept.
_FITS = {
    "kh": ([(-5.33980, -0.10008, 1.13098), (-0.35351, 1.26970, 0.45400), (-0.23789, 0.86036, 0.15354), (-0.94158, 0.64552, 0.16817)], -0.18961, 0.71147),
    "kv": ([(-3.80595, 0.56934, 0.81061), (-3.44965, -0.22911, 0.51059), (-0.39902, 0.73042, 0.11899), (0.50167, 1.07319, 0.27195)], -0.16398, 0.63297),
    "ah": ([(-0.14318, 1.82442, -0.55187), (0.29591, 0.77564, 0.19822), (0.32177, 0.63773, 0.13164), (-5.37610, -0.96230, 1.47828), (16.1721, -3.29980, 3.43990)], 0.67849, -1.95537),
    "av": ([(-0.07771, 2.33840, -0.76284), (0.56727, 0.95545, 0.54039), (-0.20238, 1.14520, 0.26809), (-48.2991, 0.791669, 0.116226), (48.5833, 0.791459, 0.116479)], -0.053739, 0.83433),
}


def rain_coefficients(frequency_ghz: float, elevation_deg: float = 0.0, polarization_tilt_deg: float = 45.0) -> tuple[float, float]:
    if not math.isfinite(frequency_ghz) or not 1 <= frequency_ghz <= 1000:
        raise ValueError("ITU-R P.838-3 requires frequency between 1 and 1000 GHz.")
    log_f = math.log10(frequency_ghz)
    values = {}
    for name, (terms, slope, intercept) in _FITS.items():
        value = sum(a * math.exp(-((log_f - b) / c) ** 2) for a, b, c in terms) + slope * log_f + intercept
        values[name] = 10 ** value if name.startswith("k") else value
    kh, kv, ah, av = (values[key] for key in ("kh", "kv", "ah", "av"))
    geometry = math.cos(math.radians(elevation_deg)) ** 2 * math.cos(2 * math.radians(polarization_tilt_deg))
    k = (kh + kv + (kh - kv) * geometry) / 2
    alpha = (kh * ah + kv * av + (kh * ah - kv * av) * geometry) / (2 * k)
    return k, alpha


def specific_rain_attenuation(frequency_ghz: float, rain_rate_mm_h: float, elevation_deg: float = 0.0, polarization_tilt_deg: float = 45.0) -> float:
    if not math.isfinite(rain_rate_mm_h) or rain_rate_mm_h < 0:
        raise ValueError("Rain rate must be finite and non-negative.")
    k, alpha = rain_coefficients(frequency_ghz, elevation_deg, polarization_tilt_deg)
    return k * rain_rate_mm_h ** alpha
