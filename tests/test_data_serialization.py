"""CSV validation and portable results with real values."""

from io import StringIO
import json

import pytest

from tsp.algorithms.genetic_algorithm import genetic_algorithm
from tsp.data_loader import dataset_from_frame, dataset_to_csv, generate_random_dataset, load_csv
from tsp.models import Dataset, GAConfig, OptimizationResult


def test_csv_round_trip_preserves_dataset(square):
    csv = dataset_to_csv(square)
    if isinstance(csv, bytes):
        csv = csv.decode("utf-8-sig")
    loaded = load_csv(StringIO(csv), name=square.name)
    assert loaded.to_dict() == square.to_dict()
    assert loaded.fingerprint == square.fingerprint


@pytest.mark.parametrize("column", ["id", "name", "x", "y", "is_depot"])
def test_missing_required_csv_columns_rejected(square, column):
    frame = square.to_frame().drop(columns=[column])
    with pytest.raises(ValueError):
        dataset_from_frame(frame)


@pytest.mark.parametrize("value", ["not a number", "", float("inf")])
def test_invalid_csv_coordinates_rejected(square, value):
    frame = square.to_frame().astype({"x": object})
    frame.loc[1, "x"] = value
    with pytest.raises(ValueError):
        dataset_from_frame(frame)


def test_csv_boolean_false_is_not_truthy_string():
    dataset = load_csv(StringIO(
        "id,name,x,y,is_depot\nD,Depot,0,0,true\nA,Customer,1,1,false\n"
    ))
    assert dataset.depot_index == 0
    assert len(dataset.customer_indices) == 1


def test_unknown_csv_boolean_rejected():
    with pytest.raises(ValueError):
        load_csv(StringIO(
            "id,name,x,y,is_depot\nD,Depot,0,0,true\nA,Customer,1,1,perhaps\n"
        ))


def test_missing_names_rejected(square):
    frame = square.to_frame()
    frame.loc[1, "name"] = None
    with pytest.raises(ValueError):
        dataset_from_frame(frame)


def test_generated_dataset_is_reproducible():
    first = generate_random_dataset(10, seed=42)
    second = generate_random_dataset(10, seed=42)
    assert first.to_dict() == second.to_dict()
    assert len(first.locations) == 11


def test_result_json_round_trip_contains_route_parameters_seed_and_history(square):
    result = genetic_algorithm(square, GAConfig(population_size=12, generations=4, seed=17))
    payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False, allow_nan=False))
    assert payload["route"] == result.route
    assert payload["distance"] == result.distance
    assert payload["seed"] == 17
    assert payload["parameters"]["population_size"] == 12
    assert payload["history"] == result.history
    assert payload["runtime_seconds"] >= 0
    assert payload["evaluations"] == result.evaluations
    restored = OptimizationResult.from_dict(payload)
    assert restored.to_dict() == result.to_dict()
    assert Dataset.from_dict(json.loads(json.dumps(square.to_dict()))).to_dict() == square.to_dict()
