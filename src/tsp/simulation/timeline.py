"""Build one immutable schedule and sample every displayed value from its clock.

This module does not run an optimizer or change its route. The frontend uses the
same JSON schedule and snapshot semantics; shared fixtures check both samplers.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from numbers import Integral, Real
from typing import Any

import numpy as np

from tsp.distance import distance_matrix, route_distance
from tsp.models import Dataset, OptimizationResult
from tsp.validation import validate_route
from .models import SimulationConfig

PLAYBACK_STATES = frozenset({"idle", "playing", "paused", "stopped", "completed"})


def _nonnegative_matrix(value: Any, size: int, label: str) -> np.ndarray:
    """Validate a directed matrix without symmetrizing or replacing its cells."""
    try:
        if np.asarray(value).dtype.kind == "b":
            raise ValueError("Boolean costs are invalid.")
        matrix = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must contain numeric costs.") from exc
    if matrix.shape != (size, size) or not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError(f"{label} must be a finite nonnegative {size} by {size} matrix.")
    if not np.allclose(np.diag(matrix), 0, rtol=0, atol=1e-9):
        raise ValueError(f"{label} diagonal must be zero.")
    return matrix


def _geometry(value: Any) -> tuple[list[list[float]], list[float]]:
    """Validate GeoJSON order (longitude, latitude), then measure its segments."""
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError("Every road leg needs at least two geometry coordinates.")
    coordinates: list[list[float]] = []
    cumulative = [0.0]
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Road geometry coordinates must be [longitude, latitude].")
        if any(isinstance(number, bool) or not isinstance(number, Real) or not math.isfinite(number)
               for number in point):
            raise ValueError("Road geometry coordinates must be finite numbers.")
        lon, lat = map(float, point)
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError("Road geometry is outside longitude/latitude bounds.")
        coordinates.append([lon, lat])
        if len(coordinates) > 1:
            previous_lon, previous_lat = coordinates[-2]
            dlat = math.radians(lat - previous_lat)
            dlon = math.radians(lon - previous_lon)
            a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(previous_lat))
                 * math.cos(math.radians(lat)) * math.sin(dlon / 2) ** 2)
            length = 6371008.8 * 2 * math.atan2(math.sqrt(min(1.0, a)), math.sqrt(max(0.0, 1 - a)))
            cumulative.append(cumulative[-1] + length)
    return coordinates, cumulative


def _sample_geometry(phase: dict[str, Any], fraction: float) -> tuple[float, float, float]:
    """Sample a prepared polyline in O(log n), including duplicate vertices."""
    from bisect import bisect_right

    coordinates = phase["geometry"]
    cumulative = phase["geometry_cumulative_m"]
    target = fraction * cumulative[-1]
    segment = min(len(coordinates) - 2, bisect_right(cumulative, target) - 1)
    segment = max(0, segment)
    start, end = coordinates[segment], coordinates[segment + 1]
    length = cumulative[segment + 1] - cumulative[segment]
    part = max(0.0, min(1.0, (target - cumulative[segment]) / length)) if length > 0 else 1.0
    return (start[0] + part * (end[0] - start[0]),
            start[1] + part * (end[1] - start[1]),
            math.atan2(end[1] - start[1], end[0] - start[0]) if length > 0 else phase["heading"])


def _prepare_legs(legs: list[dict[str, Any]], route: list[int]) -> list[dict[str, Any]]:
    """Keep snapped stop positions continuous; reject disconnected road pieces.

    OSRM snaps input markers to the road. Marker coordinates can differ from the
    returned coordinates, but neighbouring leg endpoints must agree. Up to one
    metre of serialization rounding is normalized; larger gaps require rerouting
    instead of inventing a straight connector and calling it a road.
    """
    prepared = []
    for position, leg in enumerate(legs):
        if not isinstance(leg, dict) or leg.get("start_index") != route[position] or leg.get("end_index") != route[position + 1]:
            raise ValueError("Road geometry leg order does not match the solver route.")
        geometry, _ = _geometry(leg.get("geometry"))
        if prepared:
            anchor = prepared[-1]["geometry"][-1]
            if _geometry([anchor, geometry[0]])[1][-1] > 1.0:
                raise ValueError("Road leg endpoints are disconnected; reroute before playback.")
            geometry[0] = anchor.copy()
        prepared.append({**leg, "geometry": geometry})
    final, origin = prepared[-1]["geometry"][-1], prepared[0]["geometry"][0]
    if _geometry([final, origin])[1][-1] > 1.0:
        raise ValueError("The road route does not return to the same snapped warehouse.")
    prepared[-1]["geometry"][-1] = origin.copy()
    return prepared


def build_schedule(
    dataset: Dataset,
    result: OptimizationResult,
    config: SimulationConfig | None = None,
    run_number: int = 1,
    *,
    matrix: Any = None,
    road_route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Precompute travel/service phases and ordered events for a measured route.

    The identity changes with dataset, algorithm, route, optimization run or
    physical settings. Playback speed is deliberately absent from that identity.
    The route must be closed and its recorded distance must match the dataset.
    """
    config = config if config is not None else SimulationConfig()
    if not isinstance(config, SimulationConfig):
        raise ValueError("config must be a validated SimulationConfig.")
    if not isinstance(result, OptimizationResult):
        raise ValueError("result must be an OptimizationResult.")
    if not isinstance(result.algorithm, str) or not result.algorithm.strip():
        raise ValueError("Result algorithm name is required.")
    if result.seed is not None and (isinstance(result.seed, bool)
                                   or not isinstance(result.seed, Integral) or result.seed < 0):
        raise ValueError("Result seed must be a nonnegative integer or None.")
    if isinstance(run_number, bool) or not isinstance(run_number, Integral) or run_number < 0:
        raise ValueError("run_number must be a nonnegative integer.")
    validate_route(result.route, dataset)
    route = [int(index) for index in result.route]
    geographic = bool(getattr(dataset, "is_geographic", False))
    routing_matrix = matrix if isinstance(matrix, dict) else None
    objective, objective_unit = "distance", "coordinate units"
    if geographic:
        if routing_matrix is None or road_route is None:
            raise ValueError("A geographic schedule requires its solver matrix and routed geometry.")
        if routing_matrix.get("dataset_fingerprint") != dataset.fingerprint:
            raise ValueError("The routing matrix belongs to another dataset.")
        if road_route.get("dataset_fingerprint") != dataset.fingerprint:
            raise ValueError("The road geometry belongs to another dataset.")
        for name in ("provider", "profile", "source"):
            if not routing_matrix.get(name) or road_route.get(name) != routing_matrix[name]:
                raise ValueError(f"The routing matrix and geometry must use the same {name}.")
        objective = routing_matrix.get("objective")
        objective_unit = routing_matrix.get("unit")
        if (objective, objective_unit) not in (("distance", "m"), ("duration", "s")):
            raise ValueError("Road objective must be distance in m or duration in s.")
        costs = _nonnegative_matrix(routing_matrix.get("costs"), len(dataset.locations), "Cost matrix")
        durations = _nonnegative_matrix(routing_matrix.get("durations"), len(dataset.locations), "Duration matrix")
        distances = (None if routing_matrix.get("distances") is None else
                     _nonnegative_matrix(routing_matrix["distances"], len(dataset.locations), "Distance matrix"))
        expected_costs = distances if objective == "distance" else durations
        if expected_costs is None or not np.allclose(costs, expected_costs, rtol=1e-12, atol=1e-9):
            raise ValueError("Objective costs differ from the matching routing matrix.")
        legs = road_route.get("legs")
        if not isinstance(legs, list) or len(legs) != len(route) - 1:
            raise ValueError("Road geometry must contain exactly one leg per route edge.")
        legs = _prepare_legs(legs, route)
        matrix_version, geometry_version = routing_matrix.get("data_version"), road_route.get("data_version")
        if matrix_version and geometry_version and matrix_version != geometry_version:
            raise ValueError("The routing matrix and geometry use different provider data versions.")
        for leg in legs:
            for field in ("duration_s", "distance_m"):
                value = leg.get(field)
                if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Road leg {field} must be finite and nonnegative.")
        recorded_matrix = result.parameters.get("matrix_fingerprint")
        if recorded_matrix is not None and recorded_matrix != routing_matrix.get("fingerprint"):
            raise ValueError("The solver result belongs to a different routing matrix.")
        for name, expected in (("dataset_fingerprint", dataset.fingerprint),
                               ("objective", objective), ("unit", objective_unit)):
            if name in result.parameters and result.parameters[name] != expected:
                raise ValueError(f"The solver result has a different {name}.")
    else:
        if road_route is not None or routing_matrix is not None:
            raise ValueError("Road routing data requires geographic coordinates.")
        costs = distance_matrix(dataset) if matrix is None else _nonnegative_matrix(matrix, len(dataset.locations), "Cost matrix")
        distances, durations, legs = costs, None, None
    measured_distance = route_distance(route, costs)
    if (isinstance(result.distance, bool) or not isinstance(result.distance, Real)
            or not math.isfinite(result.distance) or result.distance < 0
            or not math.isclose(result.distance, measured_distance, rel_tol=1e-9, abs_tol=1e-9)):
        raise ValueError("Result distance does not match this dataset and route.")
    identity = {
        "schema_version": 1, "dataset_fingerprint": dataset.fingerprint,
        "algorithm": result.algorithm, "route": route, "run_number": int(run_number),
        "base_speed": config.base_speed, "service_seconds": config.service_seconds,
        "demo_time_scale": config.demo_time_scale,
    }
    if geographic:
        # Hash content too: even a caller mutating a matrix without refreshing
        # its supplied fingerprint cannot reuse a checkpoint for stale data.
        transient = {"cache_hit", "stale_cache", "cache_error"}
        content = json.dumps({"matrix": {k: v for k, v in routing_matrix.items() if k not in transient},
                              "road_route": {k: v for k, v in road_route.items() if k not in transient}},
                             sort_keys=True, ensure_ascii=False, allow_nan=False)
        identity.update({"matrix_fingerprint": routing_matrix.get("fingerprint"),
                         "road_route_fingerprint": road_route.get("fingerprint"),
                         "routing_content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    elif matrix is not None:
        identity["matrix_fingerprint"] = hashlib.sha256(costs.tobytes()).hexdigest()
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False)
    route_key = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    phases: list[dict[str, Any]] = []
    stops: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    elapsed = 0.0
    distance_so_far = 0.0
    heading = 0.0
    estimated_travel = 0.0
    parking_positions: dict[int, list[float]] = {}

    def event(kind: str, time: float, index: int, position: int) -> None:
        events.append({
            "id": f"{route_key}:{len(events)}:{kind}",
            "type": kind, "time": time, "index": index, "route_position": position,
        })

    event("started", 0.0, dataset.depot_index, 0)
    for position, (start_index, end_index) in enumerate(zip(route, route[1:]), start=1):
        start, end = dataset.locations[start_index], dataset.locations[end_index]
        road_geometry = None
        if geographic:
            leg = legs[position - 1]
            if leg.get("start_index") != start_index or leg.get("end_index") != end_index:
                raise ValueError("Road geometry leg order does not match the solver route.")
            geometry, cumulative = _geometry(leg.get("geometry"))
            road_geometry = {"geometry": geometry, "geometry_cumulative_m": cumulative}
            parking_positions.setdefault(start_index, geometry[0])
            parking_positions[end_index] = geometry[-1]
        if distances is None:
            # A duration-only provider cannot label its objective as distance.
            # The route endpoint still supplies physical metres for display.
            length = float(leg.get("distance_m", float("nan")))
            if not math.isfinite(length) or length < 0:
                raise ValueError("Road leg distance must be finite and nonnegative.")
        else:
            length = float(distances[start_index, end_index])
        travel_seconds = float(durations[start_index, end_index]) if geographic else length / config.base_speed
        estimated_travel += travel_seconds
        if length > 0:
            heading = math.atan2(end.y - start.y, end.x - start.x)
        if road_geometry:
            heading = _sample_geometry({**road_geometry, "heading": heading}, 0.0)[2]
        event("departed", elapsed, start_index, position - 1)
        arrival = elapsed + travel_seconds / config.demo_time_scale
        next_distance = distance_so_far + length
        if not math.isfinite(arrival) or not math.isfinite(next_distance):
            raise ValueError("Simulation duration or distance exceeds finite numeric limits.")
        phases.append({
            "kind": "travel", "start_time": elapsed, "end_time": arrival,
            "start_index": start_index, "end_index": end_index,
            "distance_start": distance_so_far, "distance_end": next_distance,
            "heading": heading, "route_position": position,
            **(road_geometry or {}),
        })
        elapsed, distance_so_far = arrival, next_distance
        if road_geometry:
            heading = _sample_geometry({**road_geometry, "heading": heading}, 1.0)[2]
        if position == len(route) - 1:
            event("returned", elapsed, end_index, position)
            event("completed", elapsed, end_index, position)
            continue
        event("arrived", elapsed, end_index, position)
        delivery = elapsed + config.service_seconds / config.demo_time_scale
        if not math.isfinite(delivery):
            raise ValueError("Simulation duration exceeds finite numeric limits.")
        phases.append({
            "kind": "service", "start_time": elapsed, "end_time": delivery,
            "start_index": end_index, "end_index": end_index,
            "distance_start": distance_so_far, "distance_end": distance_so_far,
            "heading": heading, "route_position": position,
            **({"parking_position": road_geometry["geometry"][-1]} if road_geometry else {}),
        })
        stops.append({"index": end_index, "route_position": position,
                      "arrival_time": elapsed, "delivery_time": delivery})
        elapsed = delivery
        event("delivered", elapsed, end_index, position)
    payload = {
        **identity, "route_key": route_key, "dataset_name": dataset.name,
        "seed": int(result.seed) if result.seed is not None else None,
        "locations": [asdict(location) for location in dataset.locations],
        "depot_index": dataset.depot_index, "total_distance": distance_so_far,
        "total_duration": elapsed, "phases": phases, "stops": stops, "events": events,
        "mode": "geographic" if geographic else "euclidean",
        "coordinate_mode": "geographic" if geographic else "euclidean",
        "distance_unit": "m" if geographic else "coordinate units",
        "objective": objective, "objective_unit": objective_unit, "objective_value": measured_distance,
        "estimated_travel_seconds": estimated_travel,
        "estimated_service_seconds": dataset.n_customers * config.service_seconds,
        "estimated_journey_seconds": estimated_travel + dataset.n_customers * config.service_seconds,
    }
    if geographic:
        payload.update({"provider": routing_matrix["provider"], "profile": routing_matrix["profile"],
                        "source": routing_matrix["source"],
                        "final_heading": heading,
                        "geometry_reported_distance_m": sum(float(leg["distance_m"]) for leg in legs),
                        "geometry_reported_duration_seconds": sum(float(leg["duration_s"]) for leg in legs),
                        "parking_positions": {str(index): point for index, point in parking_positions.items()}})
    return payload


def snapshot_at(
    schedule: dict[str, Any], time: float, playback_state: str = "paused"
) -> dict[str, Any]:
    """Derive a complete frame without mutating a schedule or delivery counters.

    Intervals are half-open: arrival immediately enters a positive service
    interval; the delivery instant immediately enters the next travel interval.
    Zero-duration phases are skipped, while their events retain route order.
    Idle is an unstarted session and deliberately hides even time-zero events.
    """
    if isinstance(time, bool) or not isinstance(time, Real) or not math.isfinite(time):
        raise ValueError("Simulation time must be a finite number.")
    if not isinstance(playback_state, str) or playback_state not in PLAYBACK_STATES:
        raise ValueError("Unknown playback state.")
    total_duration = schedule["total_duration"]
    total_distance = schedule["total_distance"]
    elapsed = 0.0 if playback_state == "idle" else max(0.0, min(float(time), total_duration))
    active = playback_state != "idle"
    complete = active and elapsed >= total_duration
    locations = schedule["locations"]
    depot_index = schedule["depot_index"]
    depot = locations[depot_index]
    statuses = ["Warehouse" if point["is_depot"] else "Pending" for point in locations]
    delivered = {stop["index"] for stop in schedule["stops"]
                 if active and stop["delivery_time"] <= elapsed}
    for index in delivered:
        statuses[index] = "Delivered"
    current = (next((phase for phase in schedule["phases"] if phase["end_time"] > elapsed), None)
               if active and not complete else None)
    x, y = depot["x"], depot["y"]
    parked_depot = schedule.get("parking_positions", {}).get(str(depot_index))
    if parked_depot is not None:
        x, y = parked_depot
    heading = schedule["phases"][-1 if complete else 0]["heading"]
    if complete:
        heading = schedule.get("final_heading", heading)
    phase_name = "at_depot"
    destination = None
    traveled = total_distance if complete else 0.0
    if current is not None:
        destination = current["end_index"]
        start, end = locations[current["start_index"]], locations[destination]
        heading = current["heading"]
        if current["kind"] == "service":
            x, y = end["x"], end["y"]
            if current.get("parking_position") is not None:
                x, y = current["parking_position"]
            traveled = current["distance_end"]
            phase_name = "delivering"
            statuses[destination] = "Delivering"
        else:
            duration = current["end_time"] - current["start_time"]
            # The active phase cannot have zero duration by its selection rule.
            fraction = max(0.0, min(1.0, (elapsed - current["start_time"]) / duration))
            x = (1.0 - fraction) * start["x"] + fraction * end["x"]
            y = (1.0 - fraction) * start["y"] + fraction * end["y"]
            if current.get("geometry") is not None:
                x, y, heading = _sample_geometry(current, fraction)
            traveled = current["distance_start"] + fraction * (current["distance_end"] - current["distance_start"])
            phase_name = "moving"
            if destination != depot_index:
                statuses[destination] = "In Transit"
    traveled = max(0.0, min(traveled, total_distance))
    progress = (100.0 * elapsed / total_duration if total_duration > 0 else (100.0 if complete else 0.0))
    distance_progress = (100.0 * traveled / total_distance if total_distance > 0 else (100.0 if complete else 0.0))
    return {
        "x": x, "y": y, "heading": heading, "phase": phase_name,
        "destination_index": destination, "delivered_count": len(delivered),
        "remaining_count": len(schedule["stops"]) - len(delivered),
        "distance_traveled": traveled, "remaining_distance": max(0.0, total_distance - traveled),
        "progress_percent": progress, "distance_progress_percent": distance_progress,
        "elapsed": elapsed, "remaining_time": max(0.0, total_duration - elapsed),
        "statuses": statuses,
        "visible_events": [item["id"] for item in schedule["events"]
                           if active and item["time"] <= elapsed],
    }
