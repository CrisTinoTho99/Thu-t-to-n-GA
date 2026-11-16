"""Validate GPS UI events at the Streamlit boundary without browser/network IO."""
from dataclasses import replace

import pytest

from tsp.models import Dataset, Location
from tsp.simulation.component import render_map_editor, validate_map_event


@pytest.fixture
def geography():
    return Dataset("GPS click fixture", (
        Location("D", "Kho", 106.7, 10.77, True, latitude=10.77, longitude=106.7),
        Location("C", "Khách", 106.71, 10.78, latitude=10.78, longitude=106.71),
    ))


def test_click_is_scoped_to_current_dataset(geography):
    event = {"kind": "add_point", "latitude": 10.775, "longitude": 106.705,
             "event_id": "map-mount:1", "dataset_fingerprint": geography.fingerprint}
    assert validate_map_event(event, geography) == event
    assert validate_map_event(event, replace(geography, name="Changed input")) is None


@pytest.mark.parametrize("change", [
    {"latitude": 91}, {"latitude": -91}, {"longitude": 181}, {"longitude": -181},
    {"latitude": True}, {"longitude": float("nan")}, {"latitude": float("inf")},
    {"event_id": ""}, {"event_id": []}, {"event_id": "x" * 101},
    {"latitude": "10.77"}, {"kind": "checkpoint"},
])
def test_untrusted_or_malformed_click_is_rejected(geography, change):
    event = {"kind": "add_point", "latitude": 10.775, "longitude": 106.705,
             "event_id": "map-mount:1", "dataset_fingerprint": geography.fingerprint}
    assert validate_map_event({**event, **change}, geography) is None


def test_legacy_xy_is_not_silently_interpreted_as_gps():
    euclidean = Dataset("Old CSV", (Location("D", "Depot", 10, 11, True), Location("C", "Client", 12, 13)))
    with pytest.raises(ValueError, match="latitude/longitude"):
        render_map_editor(euclidean)
