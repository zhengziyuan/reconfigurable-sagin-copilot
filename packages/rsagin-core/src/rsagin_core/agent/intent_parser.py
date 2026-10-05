from __future__ import annotations

from rsagin_core.planning.intent import parse_planning_intent


def parse_intent(text: str) -> dict:
    return parse_planning_intent(text)
