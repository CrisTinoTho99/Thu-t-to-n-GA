"""Road geometry, directed matrix accounting and deterministic seek parity."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tsp.models import Dataset, Location, OptimizationResult
from tsp.simulation.models import SimulationConfig
from tsp.simulation.timeline import build_schedule, snapshot_at


def road_inputs():
    # Input markers intentionally differ from the provider's snapped road points.
    dataset = Dataset("Road fixture", (
        Location("D", "Kho", 106.70003, 10.77002, True, 10.77002, 106.70003),
        Location("A", "A", 106.70203, 10.77002, False, 10.77002, 106.70203),
        Location("B", "B", 106.70403, 10.77002, False, 10.77002, 106.70403),
    ))
    distances = [[0, 300, 600], [700, 0, 400], [500, 800, 0]]
    durations = [[0, 30, 60], [70, 0, 40], [50, 80, 0]]
    metadata = {"provider": "osrm-fixture", "profile": "driving", "source": "osrm",
                "dataset_fingerprint": dataset.fingerprint}
    matrix = {**metadata, "costs": distances, "distances": distances, "durations": durations,
              "objective": "distance", "unit": "m", "fingerprint": "matrix-one"}
    road_route = {**metadata, "fingerprint": "route-one", "legs": [
        {"start_index": 0, "end_index": 1, "distance_m": 300, "duration_s": 30,
         "geometry": [[106.7, 10.77], [106.7, 10.771], [106.702, 10.771], [106.702, 10.77]]},
        {"start_index": 1, "end_index": 2, "distance_m": 400, "duration_s": 40,
         "geometry": [[106.702, 10.77], [106.704, 10.77]]},
        {"start_index": 2, "end_index": 0, "distance_m": 500, "duration_s": 50,
         "geometry": [[106.704, 10.77], [106.7, 10.77]]},
    ]}
    result = OptimizationResult("GA fixture", [0, 1, 2, 0], 1200, .012, 42,
                                parameters={"matrix_fingerprint": "matrix-one"})
    return dataset, result, matrix, road_route


def road_schedule():
    dataset, result, matrix, road_route = road_inputs()
    return build_schedule(dataset, result, SimulationConfig(service_seconds=60, demo_time_scale=10),
                          matrix=matrix, road_route=road_route)


def test_road_schedule_uses_directed_solver_cells_and_provider_times():
    schedule = road_schedule()
    assert schedule["objective_value"] == schedule["total_distance"] == 1200
    assert schedule["distance_unit"] == "m"
    assert schedule["estimated_travel_seconds"] == 120
    assert schedule["estimated_service_seconds"] == 120
    assert schedule["estimated_journey_seconds"] == 240
    assert schedule["total_duration"] == 24
    assert [(p["kind"], p["start_time"], p["end_time"]) for p in schedule["phases"]] == [
        ("travel", 0, 3), ("service", 3, 9), ("travel", 9, 13),
        ("service", 13, 19), ("travel", 19, 24),
    ]
    assert sum(p["distance_end"] - p["distance_start"] for p in schedule["phases"]) == 1200


def test_reversed_road_tour_uses_reverse_costs_instead_of_symmetric_assumption():
    dataset, result, matrix, road_route = road_inputs()
    reverse_legs = []
    for leg in reversed(road_route["legs"]):
        start, end = leg["end_index"], leg["start_index"]
        reverse_legs.append({**leg, "start_index": start, "end_index": end,
                             "geometry": list(reversed(leg["geometry"])),
                             "distance_m": matrix["distances"][start][end],
                             "duration_s": matrix["durations"][start][end]})
    road_route["legs"] = reverse_legs
    reverse = replace(result, route=[0, 2, 1, 0], distance=2100)
    schedule = build_schedule(dataset, reverse, matrix=matrix, road_route=road_route)
    assert schedule["total_distance"] == 2100
    assert schedule["estimated_travel_seconds"] == 210


def test_vehicle_follows_bend_parks_on_road_and_rewinds_deliveries():
    schedule = road_schedule()
    halfway = snapshot_at(schedule, 1.5)
    assert halfway["x"] == pytest.approx(106.701)
    assert halfway["y"] == pytest.approx(10.771)  # straight-line route stays at 10.77
    assert halfway["distance_traveled"] == pytest.approx(150)
    serving = snapshot_at(schedule, 3)
    assert (serving["x"], serving["y"]) == (106.702, 10.77)
    assert serving["statuses"] == ["Warehouse", "Delivering", "Pending"]
    later = snapshot_at(schedule, 20)
    assert later["statuses"] == ["Warehouse", "Delivered", "Delivered"]
    earlier = snapshot_at(schedule, 2)
    assert earlier["statuses"] == ["Warehouse", "In Transit", "Pending"]
    assert len(earlier["visible_events"]) < len(later["visible_events"])
    returned = snapshot_at(schedule, 24)
    assert (returned["x"], returned["y"]) == (106.7, 10.77)
    assert returned["phase"] == "at_depot"
    assert returned["distance_traveled"] == 1200
    assert returned["progress_percent"] == 100


def test_geometry_endpoints_normalize_rounding_without_mutating_response():
    dataset, result, matrix, road_route = road_inputs()
    road_route["legs"][1]["geometry"][0][0] += .000001  # less than one metre
    before = deepcopy(road_route)
    schedule = build_schedule(dataset, result, matrix=matrix, road_route=road_route)
    travels = [p for p in schedule["phases"] if p["kind"] == "travel"]
    assert travels[0]["geometry"][-1] == travels[1]["geometry"][0]
    assert road_route == before


@pytest.mark.parametrize("change", ["dataset", "provider", "profile", "source", "edge", "gap", "return", "coordinate", "empty", "cost", "distance", "duration", "version"])
def test_incompatible_or_missing_road_data_rejected(change):
    dataset, result, matrix, road_route = road_inputs()
    if change == "dataset":
        matrix["dataset_fingerprint"] = "old-dataset"
    elif change in ("provider", "profile", "source"):
        road_route[change] = "other"
    elif change == "edge":
        road_route["legs"][0]["end_index"] = 2
    elif change == "gap":
        road_route["legs"][1]["geometry"][0][0] += .001
    elif change == "return":
        road_route["legs"][-1]["geometry"][-1][0] += .001
    elif change == "coordinate":
        road_route["legs"][0]["geometry"][0] = [10, 106]
    elif change == "empty":
        road_route["legs"][0]["geometry"] = []
    elif change == "cost":
        matrix["costs"] = [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
    elif change == "distance":
        road_route["legs"][0]["distance_m"] = float("nan")
    elif change == "duration":
        road_route["legs"][0]["duration_s"] = None
    elif change == "version":
        matrix["data_version"], road_route["data_version"] = "old", "new"
    with pytest.raises(ValueError):
        build_schedule(dataset, result, matrix=matrix, road_route=road_route)


def test_matrix_or_geometry_change_invalidates_route_checkpoint_identity():
    dataset, result, matrix, road_route = road_inputs()
    first = build_schedule(dataset, result, matrix=matrix, road_route=road_route)
    # Change an unused directed cell, even while the external fingerprint stays.
    matrix["durations"][1][0] += 5
    changed_matrix = build_schedule(dataset, result, matrix=matrix, road_route=road_route)
    assert changed_matrix["route_key"] != first["route_key"]
    road_route["legs"][0]["geometry"][1][1] += .0001
    changed_geometry = build_schedule(dataset, result, matrix=matrix, road_route=road_route)
    assert changed_geometry["route_key"] != changed_matrix["route_key"]
    with pytest.raises(ValueError, match="different routing matrix"):
        build_schedule(dataset, replace(result, parameters={"matrix_fingerprint": "old"}),
                       matrix=matrix, road_route=road_route)


def test_cache_status_does_not_reset_identical_road_playback():
    dataset, result, matrix, road_route = road_inputs()
    first = build_schedule(dataset, result, matrix=matrix, road_route=road_route)
    matrix.update(cache_hit=True, stale_cache=True, cache_error="provider temporarily offline")
    road_route.update(cache_hit=True, stale_cache=False)
    second = build_schedule(dataset, result, matrix=matrix, road_route=road_route)
    assert first["route_key"] == second["route_key"]


def test_geographic_schedule_requires_matching_routing_inputs():
    dataset, result, matrix, road_route = road_inputs()
    for kwargs in ({}, {"matrix": matrix}, {"road_route": road_route}):
        with pytest.raises(ValueError, match="requires"):
            build_schedule(dataset, result, **kwargs)


def test_duration_only_provider_preserves_seconds_objective_and_metres_display():
    dataset, result, matrix, road_route = road_inputs()
    matrix.update(objective="duration", unit="s", costs=matrix["durations"], distances=None)
    schedule = build_schedule(dataset, replace(result, distance=120), matrix=matrix, road_route=road_route)
    assert schedule["objective_value"] == 120
    assert schedule["objective_unit"] == "s"
    assert schedule["total_distance"] == 1200
    assert schedule["distance_unit"] == "m"


@pytest.mark.parametrize("value", [0, -1, True, float("inf"), float("nan")])
def test_invalid_demo_time_scale_rejected(value):
    with pytest.raises(ValueError):
        SimulationConfig(demo_time_scale=value)


def test_python_and_javascript_agree_on_bent_road_route():
    schedule = road_schedule()
    node = shutil.which("node")
    assert node, "Node.js is required for frontend/backend parity checks."
    engine = (Path(__file__).resolve().parents[1] / "src/tsp/simulation/frontend/engine.js").as_uri()
    times = [0, .1, 1.5, 2.99, 3, 8.99, 9, 13, 19, 23.99, 24, 5, 0]
    source = f"""import {{snapshotAt}} from {json.dumps(engine)};
let input=''; for await (const c of process.stdin) input+=c;
const {{schedule,times}}=JSON.parse(input);
process.stdout.write(JSON.stringify(times.map(t=>snapshotAt(schedule,t))));
"""
    output = subprocess.run([node, "--input-type=module", "-e", source],
                            input=json.dumps({"schedule": schedule, "times": times}),
                            capture_output=True, text=True, check=True, timeout=20)
    for time, actual in zip(times, json.loads(output.stdout)):
        expected = snapshot_at(schedule, time)
        for key, value in expected.items():
            if isinstance(value, (int, float)):
                assert actual[key] == pytest.approx(value), (time, key)
            else:
                assert actual[key] == value, (time, key)
