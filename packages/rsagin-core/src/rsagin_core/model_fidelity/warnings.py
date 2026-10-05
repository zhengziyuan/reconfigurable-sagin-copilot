from __future__ import annotations

from typing import Literal, TypedDict


class ValidationMessage(TypedDict):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
