"""Road demo orchestration. Network calls belong to explicit computation, never playback."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
import uuid

import streamlit as st

from tsp.data_loader import dataset_to_csv, load_csv
from tsp.models import Dataset, GAConfig, Location
from tsp.routing import OSRMClient, RoutingError, approximate_matrix, approximate_route, load_hcm_demo
from tsp.services import ALGORITHMS, optimize
from tsp.simulation.component import render_map_editor, render_simulation
from tsp.simulation.models import SimulationConfig
from tsp.simulation.timeline import build_schedule
from tsp.ui.theme import header, route_chips

ROAD = "Bản đồ thực tế"
EUCLID = "Mô phỏng Euclid"


def invalidate_results(*, matrix: bool = True) -> None:
    """Discard every dependent artifact, including the old playback cursor."""
    st.session_state.results = []
    for key in ("delivery_simulation_checkpoint", "delivery_simulation_schedule",
                "delivery_simulation_settings", "road_routes", "road_route_errors", "road_refresh_geometry", "route_image"):
        st.session_state.pop(key, None)
    if matrix:
        st.session_state.pop("road_matrix", None)


def set_dataset(dataset: Dataset) -> None:
    st.session_state.dataset = dataset
    st.session_state.dataset_version = st.session_state.get("dataset_version", 0) + 1
    invalidate_results()
    # Imported CSVs may switch coordinate systems too.
    st.session_state.map_mode = ROAD if dataset.is_geographic else EUCLID


def switch_mode() -> None:
    dataset = st.session_state.dataset
    st.session_state["saved_geo_dataset" if dataset.is_geographic else "saved_xy_dataset"] = dataset
    if st.session_state.map_mode_selector == ROAD:
        demo = load_hcm_demo()
        replacement = st.session_state.get("saved_geo_dataset", demo)
    else:
        from tsp.data_loader import generate_random_dataset
        replacement = st.session_state.get("saved_xy_dataset") or generate_random_dataset(20)
    set_dataset(replacement)


@st.cache_resource
def road_client() -> OSRMClient:
    """One process-wide limiter and persistent bounded cache for public OSRM."""
    return OSRMClient(cache_dir=Path(__file__).resolve().parents[3] / ".cache" / "routing")


def compute_routes(config: GAConfig, selected: list[str], random_budget: int | None = None,
                   *, refresh: bool = False) -> None:
    if not selected:
        raise ValueError("Chọn ít nhất một thuật toán.")
    dataset = st.session_state.dataset
    if not dataset.is_geographic:
        results = optimize(dataset, config, selected, random_budget)
    else:
        matrix = st.session_state.get("road_matrix")
        source = st.session_state.get("routing_source", "OSRM · đường bộ")
        if refresh or matrix is None or matrix["dataset_fingerprint"] != dataset.fingerprint:
            with st.spinner("Đang lấy ma trận đường bộ từ OSRM…" if source.startswith("OSRM") else "Đang tạo ma trận đường thẳng gần đúng…"):
                matrix = road_client().table(dataset, refresh=refresh) if source.startswith("OSRM") else approximate_matrix(dataset)
        # A matrix change must invalidate the old run before installing the new one.
        invalidate_results(matrix=False)
        st.session_state.road_matrix = matrix
        st.session_state.road_refresh_geometry = refresh
        with st.spinner("Đang tối ưu cùng một ma trận chi phí…"):
            results = optimize(dataset, config, selected, random_budget, matrix=matrix["costs"],
                               objective=matrix["objective"], unit=matrix["unit"],
                               matrix_fingerprint=matrix["fingerprint"])
    st.session_state.results = results
    st.session_state.run_config = config
    st.session_state.run_number += 1


def _route_geometry(dataset, result, matrix):
    key = (matrix["fingerprint"], tuple(result.route))
    routes = st.session_state.setdefault("road_routes", {})
    errors = st.session_state.setdefault("road_route_errors", {})
    if key not in routes and key not in errors:
        try:
            with st.spinner("Đang lấy hình học đường đi theo thứ tự thuật toán đã chọn…"):
                routes[key] = (approximate_route(dataset, result.route) if matrix["source"] == "approximate"
                               else road_client().route(dataset, result.route,
                                                        refresh=bool(st.session_state.get("road_refresh_geometry"))))
        except (RoutingError, ValueError, OSError) as exc:
            errors[key] = str(exc)
    if key in errors:
        st.error(f"Không tải được tuyến: {errors[key]}")
        st.info("Có thể thử lại để lấy tuyến đã cache hoặc chọn Đường thẳng gần đúng và tối ưu lại. Không tự động thay dữ liệu đường bộ bằng đường thẳng.")
        if st.button("Thử tải tuyến lại"):
            errors.pop(key, None)
            st.rerun()
    return routes.get(key)


def _edit_points(dataset: Dataset, *, inline: bool = False) -> None:
    with (nullcontext() if inline else st.expander("Sửa điểm giao hàng, tọa độ và kho", expanded=False)):
        index = st.selectbox("Điểm cần sửa", range(len(dataset.locations)),
                             format_func=lambda i: dataset.locations[i].name, key="geo_edit_index")
        point = dataset.locations[index]
        with st.form(f"geo_point_{st.session_state.dataset_version}_{index}"):
            name = st.text_input("Tên điểm", point.name)
            left, right = st.columns(2)
            latitude = left.number_input("Latitude (vĩ độ)", -90.0, 90.0, float(point.latitude), format="%.6f", step=.0001)
            longitude = right.number_input("Longitude (kinh độ)", -180.0, 180.0, float(point.longitude), format="%.6f", step=.0001)
            depot = st.selectbox("Chọn kho", range(len(dataset.locations)), index=dataset.depot_index,
                                 format_func=lambda i: dataset.locations[i].name)
            apply, remove = st.columns(2)
            applied = apply.form_submit_button("Lưu thay đổi", type="primary")
            removed = remove.form_submit_button("Xóa điểm", disabled=len(dataset.locations) <= 2 or index == depot)
        if applied or removed:
            try:
                points = [replace(p, is_depot=i == depot) for i, p in enumerate(dataset.locations)]
                if removed:
                    del points[index]
                else:
                    points[index] = replace(points[index], name=name, x=longitude, y=latitude,
                                            latitude=latitude, longitude=longitude)
                set_dataset(Dataset(dataset.name, tuple(points)))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.caption("Để xóa kho hiện tại, chọn điểm khác làm kho và lưu trước. Luôn giữ ít nhất một khách hàng.")
        file = st.file_uploader("Nhập CSV GPS hoặc x/y cũ", type="csv", key="geo_csv")
        if st.button("Nhập dữ liệu", disabled=file is None):
            try:
                set_dataset(load_csv(file, name=Path(file.name).stem))
                st.rerun()
            except (ValueError, TypeError, UnicodeError) as exc:
                st.error(str(exc))
        st.download_button("Tải CSV tọa độ", dataset_to_csv(dataset), "locations_gps.csv", "text/csv")


def _map_editor(dataset: Dataset) -> None:
    event = render_map_editor(dataset)
    if not event or event.get("event_id") == st.session_state.get("last_geo_event"):
        return
    st.session_state.last_geo_event = event["event_id"]
    if len(dataset.locations) >= 25:
        st.warning("Demo công cộng giới hạn 25 địa điểm, kể cả kho.")
        return
    latitude, longitude = event["latitude"], event["longitude"]
    point = Location(f"C{uuid.uuid4().hex[:8]}", f"Điểm giao {dataset.n_customers + 1}",
                     longitude, latitude, latitude=latitude, longitude=longitude)
    set_dataset(Dataset(dataset.name, (*dataset.locations, point)))
    st.rerun()


def prepare_hcm_demo() -> None:
    """Callback runs before widgets: safely restore a complete, recorded scenario."""
    set_dataset(load_hcm_demo())
    st.session_state.routing_source = "OSRM · đường bộ"
    st.session_state.geo_solvers_5 = ["Genetic Algorithm"]
    st.session_state.run_hcm_demo_requested = True


def geographic_page() -> None:
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"],
    [data-testid="stMain"] .block-container,
    .stMain .block-container {
        max-width: none !important;
        width: 100%;
        padding-left: clamp(16px, 2vw, 40px);
        padding-right: clamp(16px, 2vw, 40px);
    }
    </style>""", unsafe_allow_html=True)
    header("Bản đồ giao hàng TP.HCM", "Tối ưu thứ tự giao hàng bằng thuật toán của dự án, xem xe đi theo đường OSRM và quay về kho.")
    st.button("▶ Chạy demo TP.HCM", on_click=prepare_hcm_demo, type="primary", key="run_hcm_demo")
    st.caption("Nạp 1 kho + 10 khách và chạy GA mặc định. Demo dùng dữ liệu đường bộ OSRM thật đã lưu; sau khi hiện tuyến, nhấn Play.")
    if st.session_state.pop("run_hcm_demo_requested", False):
        try:
            compute_routes(GAConfig(), ["Genetic Algorithm"])
        except (RoutingError, ValueError, TypeError, OSError) as exc:
            st.error(f"Chưa chạy được demo: {exc}")
    with st.expander("Dữ liệu và cấu hình tối ưu", expanded=not st.session_state.results):
        options = ALGORITHMS if st.session_state.dataset.n_customers <= 12 else ALGORITHMS[:-1]
        selected = st.multiselect("Thuật toán tối ưu bản đồ", options, default=["Genetic Algorithm"],
                                  key=f"geo_solvers_{len(options)}")
        left, middle, right = st.columns(3)
        if left.button("Tải dữ liệu demo", width="stretch"):
            set_dataset(load_hcm_demo())
            st.rerun()
        submitted = middle.button("Tối ưu tuyến", type="primary", width="stretch")
        refreshed = right.button("Làm mới dữ liệu đường bộ", width="stretch",
                                 disabled=not st.session_state.get("routing_source", "OSRM").startswith("OSRM"),
                                 help="Lấy lại ma trận và hình học từ provider, rồi tối ưu. Dùng khi dữ liệu cache khác phiên bản hoặc cần cập nhật.")
        if submitted or refreshed:
            try:
                compute_routes(st.session_state.run_config, selected, refresh=refreshed)
            except (RoutingError, ValueError, TypeError, OSError) as exc:
                st.error(f"Chưa thể tối ưu: {exc}")
        dataset = st.session_state.dataset
        st.caption(f"{dataset.name} · 1 kho + {dataset.n_customers} khách hàng · nhấp nền bản đồ để thêm điểm. Sửa dữ liệu sẽ xóa kết quả và vị trí phát cũ.")
        st.markdown("**Sửa điểm giao hàng, tọa độ và kho**")
        _edit_points(dataset, inline=True)
    matrix = st.session_state.get("road_matrix")
    results = st.session_state.results
    if not results or matrix is None:
        st.info("Tải demo TP.HCM rồi nhấn Tối ưu tuyến. Có thể thêm điểm bằng nhấp bản đồ trước khi tính.")
        _map_editor(dataset)
        return
    if matrix["source"] == "approximate":
        st.warning("ĐƯỜNG THẲNG GẦN ĐÚNG · khoảng cách cầu lớn và vận tốc giả định; xe không chạy theo mạng đường bộ.")
    if matrix.get("stale_cache"):
        st.warning(f"Đang dùng ma trận đã cache vì provider lỗi: {matrix.get('cache_error', 'không khả dụng')}")
    chosen = st.selectbox("Simulation route", [r.algorithm for r in results], key="geo_algorithm")
    result = next(r for r in results if r.algorithm == chosen)
    geometry = _route_geometry(dataset, result, matrix)
    if geometry is None:
        _map_editor(dataset)
        return
    if geometry.get("stale_cache"):
        st.warning(f"Đang dùng tuyến đã cache vì provider lỗi: {geometry.get('cache_error', 'không khả dụng')}")
    with st.expander("Cài đặt hành trình và thời lượng demo"):
        service = st.number_input("Thời gian giao mỗi khách (giây ước tính)", 0.0, 3600.0, 120.0, step=30.0, key="geo_service")
        demo_seconds = st.number_input("Thời lượng phát demo ở 1× (giây, tuyến tham chiếu)", 5.0, 600.0, 30.0, step=5.0, key="geo_demo_seconds")
    reference = next((r for r in results if r.algorithm == "Genetic Algorithm"), results[0])
    travel = sum(matrix["durations"][a][b] for a, b in zip(reference.route, reference.route[1:]))
    scale = max((travel + service * dataset.n_customers) / demo_seconds, .000001)
    try:
        schedule = build_schedule(dataset, result, SimulationConfig(service_seconds=service, demo_time_scale=scale),
                                  run_number=st.session_state.run_number, matrix=matrix, road_route=geometry)
    except ValueError as exc:
        st.error(f"Dữ liệu tuyến không khớp, hãy nhấn Làm mới dữ liệu đường bộ: {exc}")
        return
    st.session_state.delivery_simulation_schedule = schedule
    render_simulation(schedule)
    with st.expander("Chỉ số hành trình và nguồn dữ liệu"):
        a, b, c, d = st.columns(4)
        length = schedule["total_distance"]
        a.metric("Quãng đường", f"{length / 1000:.2f} km" if length >= 1000 else f"{length:.0f} m")
        b.metric("Di chuyển ước tính", f"{schedule['estimated_travel_seconds'] / 60:.1f} phút")
        c.metric("Giao hàng ước tính", f"{schedule['estimated_service_seconds'] / 60:.1f} phút")
        d.metric("Tính thuật toán", f"{result.runtime_seconds:.4f} s")
        st.caption(f"Tổng hành trình ước tính {schedule['estimated_journey_seconds'] / 60:.1f} phút · phát demo {schedule['total_duration']:.1f} giây ở 1×. Play/Pause/tua chỉ xử lý JavaScript, dùng lại tuyến đã lưu.")
        if matrix["source"] != "approximate":
            st.caption("OSRM · driving · ưu tiên tổng khoảng cách trên các đường đi nhanh nhất OSRM trả về (m); nếu provider thiếu khoảng cách, dùng thời gian (s). Ước tính theo dữ liệu đường bộ, không phải giao thông thời gian thực.")
        if matrix.get("bundled_snapshot"):
            st.info(f"Demo dùng ma trận đường bộ OSRM đã lưu ({matrix.get('recorded_at', '')}). Không cần kết nối OSRM cho bộ điểm này; không phải dữ liệu giao thông trực tiếp.")
        st.caption(f"Mục tiêu lần chạy: {matrix['objective']} ({matrix['unit']}) · cùng dataset và ma trận {matrix['fingerprint'][:12]} cho mọi thuật toán · {'cache' if matrix.get('cache_hit') else 'dữ liệu mới'}")
        if geometry.get("bundled_snapshot"):
            st.caption("Hình học tuyến lấy từ response OSRM đã đóng gói, khớp đúng tọa độ và thứ tự GA vừa tính.")
    if st.button("Chỉnh sửa trên bản đồ", help="Xóa kết quả hiện tại để thêm điểm bằng nhấp bản đồ."):
        invalidate_results()
        st.rerun()
    with st.expander("Thứ tự giao và dữ liệu tái lập"):
        route_chips([dataset.locations[i].name for i in result.route])
        payload = {"dataset": dataset.to_dict(), "matrix": matrix, "road_route": geometry,
                   "results": [r.to_dict() for r in results], "schedule": schedule}
        st.download_button("Tải dữ liệu tuyến và lịch trình JSON", json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
                           "road_delivery.json", "application/json")
