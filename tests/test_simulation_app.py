"""Saved-result integration and checkpoint validation for the vehicle player."""
from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

from tsp.data_loader import generate_random_dataset
from tsp.algorithms.nearest_neighbor import nearest_neighbor
from tsp.simulation.component import validate_checkpoint
from tsp.simulation.timeline import build_schedule

ROOT = Path(__file__).resolve().parents[1]


def test_simulation_navigation_and_algorithm_switch_preserve_solver_results():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    saved = json.dumps([r.to_dict() for r in app.session_state.results], sort_keys=True)
    next(b for b in app.button if b.label == "▶ Open delivery simulation").click().run()
    assert not app.exception
    assert app.radio(key="page").value == "Delivery Simulation"
    initial = app.session_state.delivery_simulation_schedule
    speed = initial["base_speed"]
    keys = set()
    for algorithm in ["Genetic Algorithm", "Nearest Neighbor", "Random Search"]:
        app.selectbox(key="delivery_algorithm").set_value(algorithm).run()
        assert not app.exception
        schedule = app.session_state.delivery_simulation_schedule
        result = next(r for r in app.session_state.results if r.algorithm == algorithm)
        assert schedule["route"] == result.route
        assert schedule["total_distance"] == pytest.approx(result.distance)
        assert schedule["base_speed"] == speed
        keys.add(schedule["route_key"])
    assert len(keys) == 3
    assert app.session_state.run_number == 1
    assert json.dumps([r.to_dict() for r in app.session_state.results], sort_keys=True) == saved


def test_simulation_empty_state_and_journey_settings():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.radio(key="page").set_value("Delivery Simulation").run()
    original_key = app.session_state.delivery_simulation_schedule["route_key"]
    next(n for n in app.number_input if n.label.startswith("Base speed")).set_value(8.0)
    next(n for n in app.number_input if n.label.startswith("Delivery stop")).set_value(1.25)
    next(b for b in app.button if b.label == "Apply journey settings").click().run()
    assert not app.exception
    schedule = app.session_state.delivery_simulation_schedule
    assert schedule["base_speed"] == 8
    assert schedule["service_seconds"] == 1.25
    assert schedule["route_key"] != original_key
    assert app.session_state.run_number == 1
    app.session_state.results = []
    app.run()
    assert not app.exception
    assert any("No computed route" in i.value for i in app.info)


def test_checkpoint_boundary_is_scoped_and_finite():
    data = generate_random_dataset(3)
    schedule = build_schedule(data, nearest_neighbor(data))
    checkpoint = {"route_key": schedule["route_key"], "time": 0.0,
                  "speed": 1.0, "state": "paused", "started": True, "sequence": 1}
    assert validate_checkpoint(checkpoint, schedule) == checkpoint
    for change in [{"time": float("nan")}, {"time": -1}, {"speed": 0},
                   {"route_key": "old-result"}, {"state": "unknown"},
                   {"sequence": -1}, {"state": "idle"},
                   {"state": "completed"}, {"started": "true"},
                   {"state": []}, {"state": {}}, {"started": False}]:
        assert validate_checkpoint({**checkpoint, **change}, schedule) is None
