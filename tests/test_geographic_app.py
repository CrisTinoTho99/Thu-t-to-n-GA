"""Exercise the complete Streamlit road-demo flow without a public network."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from tsp.routing import approximate_matrix, approximate_route

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def road_app(monkeypatch):
    import tsp.ui.geographic_page as page

    def table(dataset, *, refresh=False):
        value = approximate_matrix(dataset)
        value.update(source="osrm", provider="mock-osrm", profile="driving")
        return value

    def route(dataset, order, *, refresh=False):
        value = approximate_route(dataset, order)
        value.update(source="osrm", provider="mock-osrm", profile="driving")
        return value

    client = Mock(table=Mock(side_effect=table), route=Mock(side_effect=route))
    monkeypatch.setattr(page, "road_client", lambda: client)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.radio(key="map_mode_selector").set_value(page.ROAD).run()
    assert not app.exception
    next(b for b in app.button if b.label == "Tải dữ liệu demo").click().run()
    assert not app.exception
    return app, client


def test_hcm_ga_demo_uses_one_matrix_and_reuses_geometry(road_app):
    app, client = road_app
    assert app.session_state.dataset.n_customers == 10
    assert app.session_state.results == []
    next(w for w in app.multiselect if w.label == "Thuật toán tối ưu bản đồ").set_value(["Genetic Algorithm"])
    next(b for b in app.button if b.label == "Tối ưu tuyến").click().run()
    assert not app.exception, [e.message for e in app.exception]
    schedule = app.session_state.delivery_simulation_schedule
    assert schedule["coordinate_mode"] == "geographic"
    assert schedule["route"][0] == schedule["route"][-1] == app.session_state.dataset.depot_index
    assert len(set(schedule["route"][1:-1])) == 10
    assert schedule["total_duration"] == pytest.approx(30)
    assert schedule["estimated_service_seconds"] == 1200
    assert schedule["total_distance"] > 1000
    assert client.table.call_count == client.route.call_count == 1
    saved_results = app.session_state.results
    next(n for n in app.number_input if n.label.startswith("Thời gian giao mỗi khách")).set_value(180).run()
    assert not app.exception
    assert app.session_state.results == saved_results
    assert app.session_state.delivery_simulation_schedule["route_key"] != schedule["route_key"]
    assert client.table.call_count == client.route.call_count == 1
    app.radio(key="page").set_value("Delivery Simulation").run()
    assert not app.exception
    assert client.table.call_count == client.route.call_count == 1
    app.radio(key="routing_source").set_value("Đường thẳng gần đúng").run()
    assert not app.exception
    assert app.session_state.results == []
    assert "delivery_simulation_schedule" not in app.session_state


def test_geo_point_and_mode_changes_invalidate_old_artifacts(road_app):
    app, _ = road_app
    before = app.session_state.dataset.fingerprint
    app.session_state.delivery_simulation_checkpoint = {"route_key": "old"}
    next(n for n in app.text_input if n.label == "Tên điểm").set_value("Kho demo sửa tên")
    next(b for b in app.button if b.label == "Lưu thay đổi").click().run()
    assert not app.exception
    assert app.session_state.dataset.fingerprint != before
    assert "delivery_simulation_checkpoint" not in app.session_state
    app.radio(key="map_mode_selector").set_value("Mô phỏng Euclid").run()
    assert not app.exception
    assert not app.session_state.dataset.is_geographic
    assert app.session_state.results == []


def test_network_error_is_visible_and_approximation_is_explicit(road_app):
    from tsp.routing import RoutingError

    app, client = road_app
    client.table.side_effect = RoutingError("mock network timeout")
    next(b for b in app.button if b.label == "Tối ưu tuyến").click().run()
    assert not app.exception
    assert app.session_state.results == []
    assert any("mock network timeout" in e.value for e in app.error)
    assert client.route.call_count == 0
    app.radio(key="routing_source").set_value("Đường thẳng gần đúng").run()
    next(b for b in app.button if b.label == "Tối ưu tuyến").click().run()
    assert not app.exception
    assert app.session_state.road_matrix["source"] == "approximate"
    assert app.warning
    assert client.table.call_count == 1
    assert client.route.call_count == 0


def test_refresh_recovers_from_table_and_route_version_mismatch(road_app):
    app, client = road_app
    original_table = client.table.side_effect
    original_route = client.route.side_effect

    def table(dataset, *, refresh=False):
        return {**original_table(dataset), "data_version": "v2" if refresh else "v1"}

    def route(dataset, order, *, refresh=False):
        return {**original_route(dataset, order), "data_version": "v2"}

    client.table.side_effect = table
    client.route.side_effect = route
    next(b for b in app.button if b.label == "Tối ưu tuyến").click().run()
    assert not app.exception
    assert any("khác phiên bản" in e.value or "version" in e.value for e in app.error)
    next(b for b in app.button if b.label == "Làm mới dữ liệu đường bộ").click().run()
    assert not app.exception
    assert not app.error
    assert app.session_state.delivery_simulation_schedule["coordinate_mode"] == "geographic"
    assert client.table.call_args.kwargs["refresh"] is True
    assert client.route.call_args.kwargs["refresh"] is True
