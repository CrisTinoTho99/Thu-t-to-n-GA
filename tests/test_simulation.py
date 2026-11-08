"""Independent timetable checks, input guards, and Python/JavaScript parity."""
from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
import subprocess

import pytest

from tsp.distance import distance_matrix, route_distance
from tsp.models import Dataset, Location, OptimizationResult
from tsp.simulation.models import SimulationConfig
from tsp.simulation.timeline import build_schedule, snapshot_at

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/simulation_cases.json").read_text(encoding="utf-8"))


def dataset_and_result(locations=None, route=None):
    """Use an independently known 3-4-5 triangle with the depot in row one."""
    locations = locations or FIXTURE["schedule"]["locations"]
    dataset = Dataset("Simulation fixture", tuple(Location(**row) for row in locations))
    route = route or FIXTURE["schedule"]["route"]
    result = OptimizationResult("Fixture route", list(route), route_distance(route, distance_matrix(dataset)), 0.001, 1, seed=42)
    return dataset, result


@pytest.fixture
def schedule():
    dataset, result = dataset_and_result()
    return build_schedule(dataset, result, SimulationConfig(base_speed=1, service_seconds=2), run_number=1)


def assert_expected(actual, expected):
    for field, value in expected.items():
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            assert actual[field] == pytest.approx(value), field
        else:
            assert actual[field] == value, field
    assert math.isfinite(actual["heading"])


def test_known_timetable_includes_service_and_final_return(schedule):
    assert schedule["depot_index"] == 1
    assert schedule["route"] == [1, 0, 2, 1]
    assert schedule["total_distance"] == pytest.approx(12)
    assert schedule["total_duration"] == pytest.approx(16)
    assert [(p["kind"], p["start_time"], p["end_time"]) for p in schedule["phases"]] == [
        ("travel", 0, 3), ("service", 3, 5), ("travel", 5, 9), ("service", 9, 11), ("travel", 11, 16)
    ]
    assert [stop["index"] for stop in schedule["stops"]] == [0, 2]
    assert [stop["delivery_time"] for stop in schedule["stops"]] == [5, 11]


@pytest.mark.parametrize("case", FIXTURE["snapshots"], ids=lambda case: f"{case['state']}@{case['time']}")
def test_snapshot_matches_independent_fixture(schedule, case):
    assert_expected(snapshot_at(schedule, case["time"], case["state"]), case["expected"])


def test_event_history_is_derived_reversible_and_never_duplicated(schedule):
    ids = [event["id"] for event in schedule["events"]]
    assert len(ids) == len(set(ids))
    assert [event["time"] for event in schedule["events"]] == sorted(event["time"] for event in schedule["events"])
    completed = snapshot_at(schedule, 16)
    earlier = snapshot_at(schedule, 3)
    repeated = snapshot_at(schedule, 16)
    assert repeated["visible_events"] == completed["visible_events"]
    assert len(earlier["visible_events"]) < len(completed["visible_events"])
    assert completed["visible_events"] == ids
    assert snapshot_at(schedule, 8, "idle")["visible_events"] == []
    assert [e["type"] for e in schedule["events"] if e["time"] == 5] == ["delivered", "departed"]


def test_distance_conservation_and_time_clamping(schedule):
    for time in [-1, 0, .001, 3, 4.99, 5, 9, 10.99, 11, 13.2, 16, 20]:
        snapshot = snapshot_at(schedule, time)
        assert snapshot["distance_traveled"] + snapshot["remaining_distance"] == pytest.approx(12)
        assert 0 <= snapshot["elapsed"] <= 16
        assert snapshot["remaining_time"] >= 0
        assert 0 <= snapshot["progress_percent"] <= 100
    assert snapshot_at(schedule, 11)["delivered_count"] == 2
    assert snapshot_at(schedule, 11)["phase"] == "moving"  # delivery count does not mean returned


@pytest.mark.parametrize("dwell", [0, 2])
def test_coincident_coordinates_and_zero_duration_safe(dwell):
    locations = [
        {"id": "A", "name": "A", "x": 0, "y": 0, "is_depot": False},
        {"id": "D", "name": "Depot", "x": 0, "y": 0, "is_depot": True},
        {"id": "B", "name": "B", "x": 0, "y": 0, "is_depot": False},
    ]
    dataset, result = dataset_and_result(locations)
    schedule = build_schedule(dataset, result, SimulationConfig(base_speed=1, service_seconds=dwell))
    assert schedule["total_distance"] == 0
    assert schedule["total_duration"] == 2 * dwell
    initial = snapshot_at(schedule, 0, "idle")
    assert initial["progress_percent"] == initial["delivered_count"] == 0
    assert initial["visible_events"] == []
    for time in [0, 1, 2, 3, 4]:
        snapshot = snapshot_at(schedule, time)
        assert snapshot["x"] == snapshot["y"] == 0
        for key in ["heading", "distance_traveled", "remaining_distance", "progress_percent", "distance_progress_percent"]:
            assert math.isfinite(snapshot[key])
    if dwell:
        assert snapshot_at(schedule, 0)["statuses"] == ["Delivering", "Warehouse", "Pending"]
        assert snapshot_at(schedule, 2)["statuses"] == ["Delivered", "Warehouse", "Delivering"]
    finished = snapshot_at(schedule, 2 * dwell)
    assert finished["delivered_count"] == 2
    assert finished["progress_percent"] == 100


def test_single_customer_zero_service_still_requires_return():
    locations = [
        {"id": "D", "name": "Depot", "x": 2, "y": -1, "is_depot": True},
        {"id": "A", "name": "A", "x": 5, "y": 3, "is_depot": False},
    ]
    dataset, result = dataset_and_result(locations, [0, 1, 0])
    schedule = build_schedule(dataset, result, SimulationConfig(base_speed=2, service_seconds=0))
    assert schedule["total_duration"] == pytest.approx(5)
    halfway = snapshot_at(schedule, 2.5)
    assert (halfway["x"], halfway["y"]) == (5, 3)
    assert halfway["delivered_count"] == 1
    assert halfway["phase"] == "moving"
    assert halfway["destination_index"] == 0
    assert snapshot_at(schedule, 5)["phase"] == "at_depot"


@pytest.mark.parametrize("speed,dwell", [(0, 1), (-1, 1), (float("nan"), 1), (float("inf"), 1), (True, 1), (1, -1), (1, float("nan")), (1, True)])
def test_invalid_simulation_config(speed, dwell):
    with pytest.raises((ValueError, TypeError)):
        SimulationConfig(base_speed=speed, service_seconds=dwell)


@pytest.mark.parametrize("time", [float("nan"), float("inf"), True, "3"])
def test_invalid_snapshot_time(schedule, time):
    with pytest.raises((ValueError, TypeError)):
        snapshot_at(schedule, time)


def test_route_binding_changes_for_new_result_dataset_or_physics():
    dataset, result = dataset_and_result()
    config = SimulationConfig(base_speed=1, service_seconds=2)
    first = build_schedule(dataset, result, config, run_number=1)
    assert first["route_key"] == build_schedule(dataset, result, config, run_number=1)["route_key"]
    assert first["route_key"] != build_schedule(dataset, result, config, run_number=2)["route_key"]
    assert first["route_key"] != build_schedule(dataset, result, SimulationConfig(base_speed=2, service_seconds=2))["route_key"]
    assert first["route_key"] != build_schedule(dataset, replace(result, algorithm="Other solver"), config)["route_key"]
    renamed = Dataset("Changed dataset", dataset.locations)
    assert first["route_key"] != build_schedule(renamed, result, config)["route_key"]


def test_invalid_route_and_distance_rejected():
    dataset, result = dataset_and_result()
    with pytest.raises(ValueError):
        build_schedule(dataset, replace(result, route=[1, 0, 1]), SimulationConfig())
    with pytest.raises(ValueError):
        build_schedule(dataset, replace(result, distance=13), SimulationConfig())


def test_generated_python_schedule_and_javascript_snapshots_agree(schedule):
    """Execute the frontend engine against an actual Python-produced schedule."""
    node = shutil.which("node")
    assert node, "Node.js is required to validate frontend/backend parity."
    cases = [{"time": row["time"], "state": row["state"]} for row in FIXTURE["snapshots"]]
    module_uri = (ROOT / "src/tsp/simulation/frontend/engine.js").as_uri()
    source = f"""import {{snapshotAt}} from {json.dumps(module_uri)};
let text=''; for await (const chunk of process.stdin) text+=chunk;
const input=JSON.parse(text);
process.stdout.write(JSON.stringify(input.cases.map(c=>snapshotAt(input.schedule,c.time,c.state))));
"""
    process = subprocess.run([node, "--input-type=module", "-e", source], input=json.dumps({"schedule": schedule, "cases": cases}), capture_output=True, text=True, check=True, timeout=20)
    actual = json.loads(process.stdout)
    for case, js in zip(cases, actual):
        py = snapshot_at(schedule, case["time"], case["state"])
        assert_expected(js, py)
