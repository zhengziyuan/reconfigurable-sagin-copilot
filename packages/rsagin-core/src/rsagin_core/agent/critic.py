from __future__ import annotations

from typing import Any


def critique_plan(verification: dict[str, Any]) -> list[str]:
    notes = []
    if verification["quality"]["failed"]:
        notes.append("Run quality has failed checks; do not use this plan without remediation.")
    if verification["sla"]["failed"]:
        notes.append("Some SLA constraints are unmet; explain trade-offs or relax constraints.")
    if not notes:
        notes.append("Plan is internally consistent under the selected model profile.")
    return notes
