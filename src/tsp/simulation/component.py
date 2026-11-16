"""Bidirectional Streamlit wrapper for the local delivery simulation frontend."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.components.v1 import declare_component
from tsp.models import Dataset

FRONTEND = Path(__file__).resolve().parent / "frontend"
CHECKPOINT_KEY = "delivery_simulation_checkpoint"
_component = declare_component("delivery_simulation", path=str(FRONTEND))


def validate_checkpoint(value: Any, schedule: dict[str, Any]) -> dict[str, Any] | None:
    """Accept only a bounded, finite checkpoint for the currently selected run."""
    if not isinstance(value, dict) or value.get("route_key") != schedule["route_key"]:
        return None
    time, speed = value.get("time"), value.get("speed")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (time, speed)):
        return None
    if not 0 <= time <= schedule["total_duration"] or speed not in (0.5, 1, 2, 4):
        return None
    state = value.get("state")
    if not isinstance(state, str) or state not in {"idle", "playing", "paused", "stopped", "completed"}:
        return None
    sequence = value.get("sequence", 0)
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        return None
    started = value.get("started")
    if not isinstance(started, bool):
        return None
    if state != "idle" and not started:
        return None
    if state == "idle" and (time != 0 or started):
        return None
    if state == "completed" and (time != schedule["total_duration"] or not started):
        return None
    return {"route_key": schedule["route_key"], "time": float(time), "speed": float(speed),
            "state": state, "started": started, "sequence": sequence}


def render_simulation(schedule: dict[str, Any]) -> dict[str, Any] | None:
    """Mount one stable component; persist control events, never individual frames."""
    previous = validate_checkpoint(st.session_state.get(CHECKPOINT_KEY), schedule)
    if previous is None:
        st.session_state.pop(CHECKPOINT_KEY, None)
    value = _component(schedule=schedule, checkpoint=previous,
                       key="delivery_vehicle_component", default=None)
    current = validate_checkpoint(value, schedule)
    if current is not None:
        if previous is None or current["sequence"] >= previous["sequence"]:
            st.session_state[CHECKPOINT_KEY] = current
            return current
    return previous


def validate_map_event(value: Any, dataset: Dataset) -> dict[str, Any] | None:
    """Only accept a new, finite GPS click belonging to the displayed input."""
    if (not isinstance(value, dict) or value.get("kind") != "add_point"
            or value.get("dataset_fingerprint") != dataset.fingerprint):
        return None
    latitude, longitude = value.get("latitude"), value.get("longitude")
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) for v in (latitude, longitude)):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    event_id = value.get("event_id")
    if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 100:
        return None
    return {"kind": "add_point", "latitude": float(latitude), "longitude": float(longitude),
            "event_id": event_id, "dataset_fingerprint": dataset.fingerprint}


def render_map_editor(dataset: Dataset) -> dict[str, Any] | None:
    """Display the same Leaflet component as an editor without invoking routing.

    The caller deduplicates event_id and applies point changes to the Dataset;
    this boundary rejects stale events emitted before a dataset change.
    """
    if not dataset.is_geographic:
        raise ValueError("The map editor requires explicit latitude/longitude data.")
    value = _component(editor={"locations": dataset.to_dict()["locations"],
                               "dataset_fingerprint": dataset.fingerprint},
                       key="delivery_map_editor", default=None)
    return validate_map_event(value, dataset)
