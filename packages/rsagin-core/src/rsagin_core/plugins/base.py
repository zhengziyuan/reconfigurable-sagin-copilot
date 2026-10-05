from __future__ import annotations

from typing import Any, Protocol


class ChannelModelPlugin(Protocol):
    id: str
    fidelity_level: str
    supported_links: list[str]
    valid_frequency_range_hz: tuple[float, float]

    def validate(self, scenario: Any, profile: Any) -> list[dict[str, Any]]:
        ...

    def compute_link(self, tx_node: Any, rx_point: Any, context: dict[str, Any]) -> Any:
        ...


class MetricPlugin(Protocol):
    id: str
    required_inputs: list[str]

    def compute(self, scenario: Any, link_results: Any, context: dict[str, Any]) -> Any:
        ...


class OptimizerPlugin(Protocol):
    id: str
    problem_type: str

    def solve(self, scenario: Any, metrics: Any, constraints: Any, objective: Any) -> Any:
        ...


class HardwareModelPlugin(Protocol):
    id: str
    hardware_type: str

    def response(self, incident: Any, outgoing: Any, frequency: float, codeword: Any, context: dict[str, Any]) -> Any:
        ...


class ReportPlugin(Protocol):
    id: str
    template_type: str

    def render(self, run_manifest: dict[str, Any], artifacts: dict[str, Any], context: dict[str, Any]) -> Any:
        ...
