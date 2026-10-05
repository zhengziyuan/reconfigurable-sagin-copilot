import math
import numpy as np
import pytest

from rsagin_core.channel_models import channel_loss, fidelity_level
from rsagin_core.config import load_config
from rsagin_core.geo import EARTH_RADIUS_M, satellite_geometry
from rsagin_core.models import Node, NodeType, PositionLLA, scenario_from_config
from rsagin_core.optimization import optimize_deployment
from rsagin_core.resource_management import plan_resources
from rsagin_core.standards.rain_p838 import rain_coefficients, specific_rain_attenuation
from rsagin_core.simulation import _localization_peb
from rsagin_core.geo import bearing_unit_xy
from rsagin_core.radio import dbm_to_mw


@pytest.mark.parametrize("frequency,kh,ah,kv,av", [
    (1, 0.0000259, 0.9691, 0.0000308, 0.8592),
    (10, 0.01217, 1.2571, 0.01129, 1.2156),
    (28, 0.2051, 0.9679, 0.1964, 0.9277),
    (100, 1.3671, 0.6815, 1.3680, 0.6765),
])
def test_p838_matches_official_table_5(frequency, kh, ah, kv, av):
    k, alpha = rain_coefficients(frequency, polarization_tilt_deg=0)
    assert k == pytest.approx(kh, rel=0.003)
    assert alpha == pytest.approx(ah, abs=0.001)
    k, alpha = rain_coefficients(frequency, polarization_tilt_deg=90)
    assert k == pytest.approx(kv, rel=0.003)
    assert alpha == pytest.approx(av, abs=0.001)
    assert specific_rain_attenuation(frequency, 0) == 0
    assert specific_rain_attenuation(frequency, 40) > specific_rain_attenuation(frequency, 10)


def test_spherical_satellite_geometry_and_elevation_mask():
    receiver = PositionLLA(lat=0, lon=0)
    satellite = PositionLLA(lat=0, lon=0, alt_m=600_000)
    distance, elevation = satellite_geometry(satellite, receiver)
    assert distance == pytest.approx(600_000)
    assert elevation == pytest.approx(90)
    opposite = PositionLLA(lat=0, lon=180, alt_m=600_000)
    distance, elevation = satellite_geometry(opposite, receiver)
    assert distance == pytest.approx(2 * EARTH_RADIUS_M + 600_000)
    assert elevation == pytest.approx(-90)
    scenario = scenario_from_config(load_config("configs/scenarios/demo_low_altitude_emergency.yaml"))
    node = Node(id="hidden_sat", type=NodeType.SATELLITE_LEO, position=opposite)
    loss = channel_loss(scenario, node, receiver, 28e9, "standards_l1", scenario.grid)
    assert loss.los_probability == 0 and loss.components["visible"] == 0
    assert fidelity_level("multi_fidelity_l2_adapter") == 1


def test_nsga_parameters_are_reproducible_and_reported():
    scene = scenario_from_config(load_config("configs/scenarios/demo_low_altitude_emergency.yaml"))
    scene.grid.update(nx=5, ny=4)
    scene.optimization["nsga2"] = {"population_size": 8, "generations": 2, "seed": 321}
    first = optimize_deployment(scene, solver="nsga2_pareto", run_id="first")
    second = optimize_deployment(scene, solver="nsga2_pareto", run_id="second")
    assert first.selected_candidate_ids == second.selected_candidate_ids
    assert first.summary["seed"] == 321 and first.summary["generations"] == 2
    assert first.summary["pareto_front"] == second.summary["pareto_front"]


def test_resource_l1_uses_the_selected_channel_kernel():
    scene = scenario_from_config(load_config("configs/scenarios/demo_low_altitude_emergency.yaml"))
    scene.grid.update(nx=6, ny=5)
    ids = ["uav_relay_west", "ris_facade_south"]
    l0 = plan_resources(scene, ids, method="max_sinr", max_flows=8, iterations=2)
    l1 = plan_resources(scene, ids, method="max_sinr", max_flows=8, iterations=2, model_profile="standards_l1")
    assert l1["model_profile"] == "standards_l1"
    assert math.isfinite(l1["summary"]["sum_rate_mbps"])
    assert l0["summary"]["sum_rate_mbps"] != l1["summary"]["sum_rate_mbps"]
    for tx in l1["transmitters"]:
        assert tx["allocated_power_mw"] <= tx["max_power_mw"] * 1.001


def test_scalar_peb_matches_matrix_inverse_reference():
    scene = scenario_from_config(load_config("configs/scenarios/demo_low_altitude_emergency.yaml"))
    point = PositionLLA(lat=30.265, lon=120.135)
    nodes = scene.fixed_nodes
    links = [{"node_id": node.id, "rx_dbm": -95 + index * 5} for index, node in enumerate(nodes)]
    matrix = np.eye(2) * 0.015
    for node, link in zip(nodes, links):
        vector = np.array(bearing_unit_xy(node.position, point))
        weight = max(0.01, min(10.0, dbm_to_mw(link["rx_dbm"] + 105) / 10))
        matrix += weight * np.outer(vector, vector)
    expected = min(80, max(0.5, math.sqrt(float(np.trace(np.linalg.inv(matrix)))) * 6))
    assert _localization_peb(point, links, nodes) == pytest.approx(expected, rel=1e-12)
