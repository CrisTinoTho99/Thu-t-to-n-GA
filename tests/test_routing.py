"""Deterministic OSRM adapter checks: no public requests are made by these tests."""
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from itertools import permutations
import json
from urllib.error import HTTPError, URLError

import numpy as np
import pytest

from tsp.algorithms.exact_solver import exact_solver
from tsp.algorithms.genetic_algorithm import genetic_algorithm
from tsp.algorithms.nearest_neighbor import nearest_neighbor
from tsp.algorithms.random_search import random_search
from tsp.algorithms.two_opt import two_opt
from tsp.data_loader import dataset_from_frame, dataset_to_csv, generate_random_dataset, load_csv
from tsp.distance import distance_matrix, route_distance
from tsp.models import Dataset, GAConfig, Location
from tsp.routing import OSRMClient, NoRouteError, RoutingError, approximate_matrix, approximate_route, load_hcm_demo
from tsp.services import ALGORITHMS, optimize


@pytest.fixture
def geo():
    return Dataset("GPS fixture", (
        Location("A", "A", 106.70, 10.78, False, latitude=10.78, longitude=106.70),
        Location("D", "Depot", 106.69, 10.77, True, latitude=10.77, longitude=106.69),
        Location("B", "B", 106.71, 10.76, False, latitude=10.76, longitude=106.71),
    ))


@pytest.fixture
def table():
    return {"code": "Ok", "distances": [[0, 320, 140], [180, 0, 280], [700, 190, 0]],
            "durations": [[0, 32, 14], [18, 0, 28], [70, 19, 0]]}


@pytest.fixture
def client(tmp_path):
    OSRMClient._memory.clear()
    return OSRMClient("https://routing.test", min_interval=0, cache_dir=tmp_path)


def fake_provider(monkeypatch, client, payload):
    requests = []
    def fetch(service, coordinates, options):
        requests.append((service, coordinates, options))
        return deepcopy(payload)
    monkeypatch.setattr(client, "_fetch", fetch)
    return requests


def test_geographic_csv_and_demo_roundtrip(geo):
    assert load_csv(dataset_to_csv(geo), name=geo.name) == geo
    assert list(geo.to_frame().columns) == ["id", "name", "latitude", "longitude", "is_depot"]
    demo = load_hcm_demo()
    assert demo.is_geographic and demo.n_customers == 10
    assert sum(point.is_depot for point in demo.locations) == 1
    assert all(10.7 < point.latitude < 10.9 and 106.6 < point.longitude < 106.8 for point in demo.locations)
    assert not generate_random_dataset(2).is_geographic
    with pytest.raises(ValueError, match="explicit"):
        distance_matrix(geo)


@pytest.mark.parametrize("latitude,longitude", [(91, 106), (10, 181), (-91, 106), (float("nan"), 106), (True, 106), (10, float("inf")), (106.7, 10.7)])
def test_bad_gps_and_likely_swapped_vietnam_coordinates_rejected(latitude, longitude):
    with pytest.raises(ValueError):
        Location("D", "Depot", longitude, latitude, True, latitude=latitude, longitude=longitude)


def test_partial_mixed_or_inconsistent_gps_rejected(geo):
    with pytest.raises(ValueError, match="together"):
        Location("D", "Depot", 0, 0, True, latitude=10)
    with pytest.raises(ValueError, match="longitude/latitude"):
        Location("D", "Depot", 10.77, 106.7, True, latitude=10.77, longitude=106.7)
    with pytest.raises(ValueError, match="mix"):
        Dataset("mixed", (geo.locations[1], Location("E", "Euclid", 0, 0)))
    frame = geo.to_frame().drop(columns=["longitude"])
    with pytest.raises(ValueError, match="longitude"):
        dataset_from_frame(frame)


def test_osrm_keeps_directed_costs_and_lon_lat_request_order(client, geo, table, monkeypatch):
    requests = fake_provider(monkeypatch, client, table)
    matrix = client.table(geo)
    assert matrix["costs"] == table["distances"]
    assert matrix["costs"][0][1] != matrix["costs"][1][0]
    assert matrix["objective"] == "distance" and matrix["unit"] == "m"
    assert requests == [("table", [[106.70, 10.78], [106.69, 10.77], [106.71, 10.76]], {"annotations": "distance,duration"})]
    assert matrix["dataset_fingerprint"] == geo.fingerprint
    assert not matrix["cache_hit"]
    cached = client.table(geo)
    assert cached["cache_hit"] and len(requests) == 1
    assert cached["fingerprint"] == matrix["fingerprint"]


def test_provider_without_distance_uses_duration_objective(client, geo, table, monkeypatch):
    del table["distances"]
    fake_provider(monkeypatch, client, table)
    matrix = client.table(geo)
    assert matrix["distances"] is None
    assert matrix["objective"] == "duration" and matrix["unit"] == "s"
    assert matrix["costs"] == table["durations"]


@pytest.mark.parametrize("field", ["distances", "durations"])
def test_unreachable_pair_fails_instead_of_silent_straight_line(client, geo, table, monkeypatch, field):
    table[field][0][2] = None
    fake_provider(monkeypatch, client, table)
    with pytest.raises(NoRouteError, match="directed pair"):
        client.table(geo)


@pytest.mark.parametrize("bad", [[], [[0, 1], [2, 0]], [[0, -1, 2], [2, 0, 3], [4, 5, 0]], [[0, True, 2], [2, 0, 3], [4, 5, 0]]])
def test_bad_matrix_response_rejected(client, geo, table, monkeypatch, bad):
    table["distances"] = bad
    fake_provider(monkeypatch, client, table)
    with pytest.raises(RoutingError):
        client.table(geo)


def test_network_timeout_no_route_and_stale_cache(client, geo, table, monkeypatch):
    monkeypatch.setattr("tsp.routing.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(URLError("network down")))
    with pytest.raises(RoutingError, match="network"):
        client.table(geo)
    fake_provider(monkeypatch, client, table)
    fresh = client.table(geo)
    monkeypatch.setattr(client, "_fetch", lambda *args: (_ for _ in ()).throw(RoutingError("network down")))
    stale = client.table(geo, refresh=True)
    assert stale["cache_hit"] and stale["stale_cache"]
    assert stale["fingerprint"] == fresh["fingerprint"]
    assert "network down" in stale["cache_error"]
    # A new instance can read the persisted response, with input labels rebound.
    OSRMClient._memory.clear()
    renamed = replace(geo, name="renamed")
    other = OSRMClient(client.base_url, min_interval=0, cache_dir=client.cache_dir)
    rebound = other.table(renamed)
    assert rebound["cache_hit"]
    assert rebound["dataset_fingerprint"] == renamed.fingerprint
    assert rebound["fingerprint"] != fresh["fingerprint"]


def test_osrm_http_no_route_error_preserves_no_route_type(client, geo, monkeypatch):
    def error(*args, **kwargs):
        raise HTTPError("https://routing.test", 400, "Bad Request", {}, BytesIO(json.dumps({"code": "NoSegment"}).encode()))
    monkeypatch.setattr("tsp.routing.urlopen", error)
    with pytest.raises(NoRouteError, match="NoSegment"):
        client.table(geo)


def test_actual_request_sets_timeout_user_agent_and_throttles(client, geo, table, monkeypatch):
    calls, waits = [], []
    clock = [100.0]
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, maximum):
            assert maximum == 10_000_001
            return json.dumps(table).encode()
    def opening(request, *, timeout):
        calls.append((request, timeout))
        return Response()
    def sleeping(seconds):
        waits.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr("tsp.routing.urlopen", opening)
    monkeypatch.setattr("tsp.routing.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("tsp.routing.time.sleep", sleeping)
    client.min_interval = 1
    OSRMClient._last_request.clear()
    coordinates = [[point.longitude, point.latitude] for point in geo.locations]
    client._fetch("table", coordinates, {"annotations": "distance,duration"})
    client._fetch("table", coordinates, {"annotations": "distance,duration"})
    assert waits == [1]
    assert len(calls) == 2 and calls[0][1] == 15
    request = calls[0][0]
    assert "/106.70000000,10.78000000;106.69000000,10.77000000" in request.full_url
    assert "TSP-AI-Route-Optimizer" in request.get_header("User-agent")
    assert request.get_header("Accept") == "application/json"


@pytest.mark.parametrize("bad_code", [None, [], {}, 0])
def test_malformed_provider_status_is_a_routing_error(client, geo, monkeypatch, bad_code):
    fake_provider(monkeypatch, client, {"code": bad_code})
    with pytest.raises(RoutingError, match="status code"):
        client.table(geo)


def route_payload(geo, route):
    legs = []
    for a, b in zip(route, route[1:]):
        start = [geo.locations[a].longitude, geo.locations[a].latitude]
        end = [geo.locations[b].longitude, geo.locations[b].latitude]
        turn = [end[0], start[1]]
        legs.append({"distance": 123, "duration": 24,
                     "steps": [{"geometry": {"type": "LineString", "coordinates": [start, turn]}},
                               {"geometry": {"type": "LineString", "coordinates": [turn, end]}}]})
    return {"code": "Ok", "routes": [{"legs": legs}]}


def test_route_uses_solver_order_full_leg_geometry_and_return(client, geo, monkeypatch):
    route = [1, 2, 0, 1]
    requests = fake_provider(monkeypatch, client, route_payload(geo, route))
    result = client.route(geo, route)
    assert [(leg["start_index"], leg["end_index"]) for leg in result["legs"]] == [(1, 2), (2, 0), (0, 1)]
    assert result["legs"][0]["geometry"] == [[106.69, 10.77], [106.71, 10.77], [106.71, 10.76]]
    assert result["legs"][-1]["geometry"][-1] == [106.69, 10.77]
    assert result["dataset_fingerprint"] == geo.fingerprint
    options = requests[0][2]
    assert options["steps"] == "true" and options["continue_straight"] == "false"
    assert options["geometries"] == "geojson"
    cached = client.route(geo, route)
    assert cached["cache_hit"] and len(requests) == 1
    assert cached["fingerprint"] == result["fingerprint"]


@pytest.mark.parametrize("code", ["NoRoute", "NoSegment", "NoTable"])
def test_no_road_response_is_user_visible(client, geo, monkeypatch, code):
    fake_provider(monkeypatch, client, {"code": code})
    with pytest.raises(NoRouteError):
        client.route(geo, [1, 0, 2, 1])


def test_missing_or_bad_geometry_rejected(client, geo, monkeypatch):
    route = [1, 0, 2, 1]
    payload = route_payload(geo, route)
    payload["routes"][0]["legs"][0]["steps"] = []
    fake_provider(monkeypatch, client, payload)
    with pytest.raises(RoutingError, match="empty"):
        client.route(geo, route)


def test_request_limit_and_non_geo_input_block_before_network(client):
    with pytest.raises(RoutingError, match="latitude/longitude"):
        client.table(generate_random_dataset(2))
    points = tuple(Location(str(i), str(i), 106.7 + i * .0001, 10.7, i == 0, latitude=10.7, longitude=106.7 + i * .0001) for i in range(26))
    with pytest.raises(RoutingError, match="25"):
        client.table(Dataset("too many", points))


def test_approximate_is_explicit_consistent_and_network_free(geo):
    matrix = approximate_matrix(geo)
    route = approximate_route(geo, [1, 0, 2, 1])
    assert matrix["source"] == route["source"] == "approximate"
    assert matrix["provider"] == route["provider"] == "straight-line-haversine"
    assert matrix["unit"] == "m"
    assert matrix["costs"][0][1] == pytest.approx(matrix["costs"][1][0])
    assert all(leg["distance_m"] == matrix["distances"][leg["start_index"]][leg["end_index"]] for leg in route["legs"])
    assert all(leg["duration_s"] == pytest.approx(leg["distance_m"] / (30 / 3.6)) for leg in route["legs"])


def test_every_algorithm_evaluates_same_asymmetric_matrix(geo, table):
    matrix = np.asarray(table["distances"], dtype=float)
    config = GAConfig(population_size=10, generations=5)
    results = optimize(geo, config, ALGORITHMS, matrix=matrix, objective="distance", unit="m", matrix_fingerprint="same-provider-costs")
    optimum = min(route_distance([geo.depot_index, *order, geo.depot_index], matrix) for order in permutations(geo.customer_indices))
    for result in results:
        assert result.distance == pytest.approx(route_distance(result.route, matrix))
        assert result.parameters["matrix_fingerprint"] == "same-provider-costs"
        assert result.parameters["dataset_fingerprint"] == geo.fingerprint
        assert result.parameters["objective"] == "distance"
    exact = next(result for result in results if result.algorithm.startswith("Exact"))
    assert exact.distance == pytest.approx(optimum)
    assert matrix[1, 0] + matrix[0, 2] + matrix[2, 1] != matrix[1, 2] + matrix[2, 0] + matrix[0, 1]


def test_two_opt_does_not_use_symmetric_edge_delta():
    data = generate_random_dataset(4)
    matrix = np.full((5, 5), 100.0)
    np.fill_diagonal(matrix, 0)
    initial = [0, 1, 2, 3, 4, 0]
    for a, b in zip(initial, initial[1:]):
        matrix[a, b] = 10
    matrix[0, 3] = matrix[1, 4] = 1
    # Reversal 1..3 saves endpoint costs but increases its directed interior.
    assert route_distance([0, 3, 2, 1, 4, 0], matrix) > route_distance(initial, matrix)
    result = two_opt(data, initial_route=initial, matrix=matrix)
    assert result.route == initial and result.distance == 50


@pytest.mark.parametrize("solver", [nearest_neighbor, exact_solver, two_opt, genetic_algorithm, random_search])
def test_supplied_matrix_must_match_dataset_dimensions(geo, solver):
    with pytest.raises(ValueError, match="dimensions"):
        solver(geo, matrix=np.zeros((2, 2)))
