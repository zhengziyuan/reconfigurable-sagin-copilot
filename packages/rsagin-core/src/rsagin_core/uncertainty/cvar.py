from __future__ import annotations


def cvar(values: list[float], alpha: float = 0.1, lower_tail: bool = True) -> float:
    if not values:
        return 0.0
    ordered = sorted(values, reverse=not lower_tail)
    count = max(1, int(len(ordered) * alpha))
    return sum(ordered[:count]) / count
