"""The shipped road demo must work with an empty cache and blocked sockets."""
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from urllib.error import URLError

import pytest
from streamlit.testing.v1 import AppTest

from tsp.models import GAConfig, Dataset
from tsp.routing import OSRMClient, RoutingError, load_hcm_demo
from tsp.services import optimize
from tsp.simulation.models import SimulationConfig
from tsp.simulation.timeline import build_schedule, snapshot_at

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def offline_client(tmp_path, monkeypatch):
    monkeypatch.setattr(OSRMClient, "_memory", OrderedDict())
    client = OSRMClient(cache_dir=tmp_path)
    monkeypatch.setattr(client, "_fetch", Mock(side_effect=RoutingError("WinError 10013: socket blocked")))
    return client


def test_recorded_osrm_demo_runs_real_ga_with_no_cache_or_network(offline_client):
    dataset = load_hcm_demo()
    matrix = offline_client.table(dataset)
    assert matrix["bundled_snapshot"] and matrix["source"] == "osrm"
    result = optimize(dataset, GAConfig(), ["Genetic Algorithm"], matrix=matrix["costs"],
                      objective=matrix["objective"], unit=matrix["unit"], matrix_fingerprint=matrix["fingerprint"])[0]
    road = offline_client.route(dataset, result.route)
    assert road["bundled_snapshot"] and road["source"] == "osrm"
    schedule = build_schedule(dataset, result, SimulationConfig(service_seconds=120), matrix=matrix, road_route=road)
    finished = snapshot_at(schedule, schedule["total_duration"])
    assert result.distance == pytest.approx(13429.2)
    assert finished["delivered_count"] == 10 and finished["phase"] == "at_depot"
    assert len(road["legs"]) == 11
    assert any(len(leg["geometry"]) > 2 for leg in road["legs"])
    offline_client._fetch.assert_not_called()


def test_edited_point_cannot_reuse_recorded_matrix(offline_client):
    data = load_hcm_demo()
    point = data.locations[1]
    changed = replace(point, latitude=point.latitude + .001, y=point.y + .001)
    dataset = Dataset(data.name, (data.locations[0], changed, *data.locations[2:]))
    with pytest.raises(RoutingError, match="10013"):
        offline_client.table(dataset)
    offline_client._fetch.assert_called_once()


def test_failed_refresh_preserves_recorded_road_data_with_label(offline_client):
    data = load_hcm_demo()
    value = offline_client.table(data, refresh=True)
    assert value["source"] == "osrm"
    assert value["bundled_snapshot"] and value["stale_cache"]
    assert "10013" in value["cache_error"]


def test_corrupt_cache_does_not_break_bundled_demo(offline_client):
    data = load_hcm_demo()
    coords = [[p.longitude, p.latitude] for p in data.locations]
    key = offline_client._key("table", coords, {"annotations": "distance,duration"})
    offline_client._cache(key, {"code": "corrupt"})
    assert offline_client.table(data)["bundled_snapshot"]
    offline_client._fetch.assert_not_called()


def test_socket_permission_failure_has_actionable_message(monkeypatch, tmp_path):
    client = OSRMClient(cache_dir=tmp_path)
    monkeypatch.setattr("tsp.routing.urlopen", Mock(side_effect=URLError(PermissionError(10013, "forbidden socket"))))
    with pytest.raises(RoutingError, match="run_demo.ps1"):
        client._fetch("table", [[106.7, 10.7], [106.71, 10.71]], {"annotations": "distance,duration"})


def test_demo_link_is_ready_for_play_with_network_blocked(offline_client, monkeypatch):
    import tsp.ui.geographic_page as page
    monkeypatch.setattr(page, "road_client", lambda: offline_client)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    app.query_params["demo"] = "hcm"
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]
    assert app.radio(key="page").value == "Delivery Simulation"
    assert app.session_state.dataset.n_customers == 10
    assert app.session_state.delivery_simulation_schedule["coordinate_mode"] == "geographic"
    assert not any(w.label == "Dataset source" for w in app.selectbox)
    assert not any(w.label == "Algorithms" for w in app.multiselect)
    before = app.session_state.run_number
    app.run()
    assert app.session_state.run_number == before
    offline_client._fetch.assert_not_called()


def test_one_click_demo_restores_full_data_from_an_edited_scenario(offline_client, monkeypatch):
    import tsp.ui.geographic_page as page
    monkeypatch.setattr(page, "road_client", lambda: offline_client)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.radio(key="map_mode_selector").set_value(page.ROAD).run()
    assert app.session_state.dataset.n_customers == 10
    app.radio(key="routing_source").set_value("Đường thẳng gần đúng").run()
    next(b for b in app.button if b.key == "run_hcm_demo").click().run()
    assert not app.exception
    assert not app.error
    assert app.session_state.road_matrix["source"] == "osrm"
    assert app.radio(key="routing_source").value == "OSRM · đường bộ"
    assert len(app.session_state.results) == 1
    assert app.session_state.delivery_simulation_schedule["total_duration"] == pytest.approx(30)
    offline_client._fetch.assert_not_called()
