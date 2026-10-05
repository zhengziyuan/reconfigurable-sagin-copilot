from __future__ import annotations


def parse_tle_lines(lines: list[str]) -> list[dict]:
    satellites = []
    cleaned = [line.strip() for line in lines if line.strip()]
    for index in range(0, len(cleaned) - 2, 3):
        name, line1, line2 = cleaned[index:index + 3]
        if line1.startswith("1 ") and line2.startswith("2 "):
            satellites.append({"name": name, "line1": line1, "line2": line2})
    return satellites
