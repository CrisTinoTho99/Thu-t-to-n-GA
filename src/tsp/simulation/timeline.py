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

from tsp.distance import distance_matrix, route_distance
from tsp.models import Dataset, OptimizationResult
from tsp.validation import validate_route
from .models import SimulationConfig

PLAYBACK_STATES = frozenset({"idle", "playing", "paused", "stopped", "completed"})


def build_schedule(
    dataset: Dataset,
    result: OptimizationResult,
    config: SimulationConfig | None = None,
    run_number: int = 1,
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
    matrix = distance_matrix(dataset)
    measured_distance = route_distance(route, matrix)
    if (isinstance(result.distance, bool) or not isinstance(result.distance, Real)
            or not math.isfinite(result.distance) or result.distance < 0
            or not math.isclose(result.distance, measured_distance, rel_tol=1e-9, abs_tol=1e-9)):
        raise ValueError("Result distance does not match this dataset and route.")
    identity = {
        "schema_version": 1, "dataset_fingerprint": dataset.fingerprint,
        "algorithm": result.algorithm, "route": route, "run_number": int(run_number),
        "base_speed": config.base_speed, "service_seconds": config.service_seconds,
    }
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, allow_nan=False)
    route_key = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    phases: list[dict[str, Any]] = []
    stops: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    elapsed = 0.0
    distance_so_far = 0.0
    heading = 0.0

    def event(kind: str, time: float, index: int, position: int) -> None:
        events.append({
            "id": f"{route_key}:{len(events)}:{kind}",
            "type": kind, "time": time, "index": index, "route_position": position,
        })

    event("started", 0.0, dataset.depot_index, 0)
    for position, (start_index, end_index) in enumerate(zip(route, route[1:]), start=1):
        start, end = dataset.locations[start_index], dataset.locations[end_index]
        length = float(matrix[start_index, end_index])
        if length > 0:
            heading = math.atan2(end.y - start.y, end.x - start.x)
        event("departed", elapsed, start_index, position - 1)
        arrival = elapsed + length / config.base_speed
        next_distance = distance_so_far + length
        if not math.isfinite(arrival) or not math.isfinite(next_distance):
            raise ValueError("Simulation duration or distance exceeds finite numeric limits.")
        phases.append({
            "kind": "travel", "start_time": elapsed, "end_time": arrival,
            "start_index": start_index, "end_index": end_index,
            "distance_start": distance_so_far, "distance_end": next_distance,
            "heading": heading, "route_position": position,
        })
        elapsed, distance_so_far = arrival, next_distance
        if position == len(route) - 1:
            event("returned", elapsed, end_index, position)
            event("completed", elapsed, end_index, position)
            continue
        event("arrived", elapsed, end_index, position)
        delivery = elapsed + config.service_seconds
        if not math.isfinite(delivery):
            raise ValueError("Simulation duration exceeds finite numeric limits.")
        phases.append({
            "kind": "service", "start_time": elapsed, "end_time": delivery,
            "start_index": end_index, "end_index": end_index,
            "distance_start": distance_so_far, "distance_end": distance_so_far,
            "heading": heading, "route_position": position,
        })
        stops.append({"index": end_index, "route_position": position,
                      "arrival_time": elapsed, "delivery_time": delivery})
        elapsed = delivery
        event("delivered", elapsed, end_index, position)
    return {
        **identity, "route_key": route_key, "dataset_name": dataset.name,
        "seed": int(result.seed) if result.seed is not None else None,
        "locations": [asdict(location) for location in dataset.locations],
        "depot_index": dataset.depot_index, "total_distance": distance_so_far,
        "total_duration": elapsed, "phases": phases, "stops": stops, "events": events,
    }


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
    heading = schedule["phases"][-1 if complete else 0]["heading"]
    phase_name = "at_depot"
    destination = None
    traveled = total_distance if complete else 0.0
    if current is not None:
        destination = current["end_index"]
        start, end = locations[current["start_index"]], locations[destination]
        heading = current["heading"]
        if current["kind"] == "service":
            x, y = end["x"], end["y"]
            traveled = current["distance_end"]
            phase_name = "delivering"
            statuses[destination] = "Delivering"
        else:
            duration = current["end_time"] - current["start_time"]
            # The active phase cannot have zero duration by its selection rule.
            fraction = max(0.0, min(1.0, (elapsed - current["start_time"]) / duration))
            x = (1.0 - fraction) * start["x"] + fraction * end["x"]
            y = (1.0 - fraction) * start["y"] + fraction * end["y"]
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
