"""Distance, closed-tour constraints, and depot validation."""

import numpy as np
import pytest

from tsp.distance import distance_matrix, route_distance
from tsp.models import Dataset, Location
from tsp.validation import validate_dataset, validate_route


def test_euclidean_matrix_is_symmetric_with_zero_diagonal(square):
    matrix = distance_matrix(square)
    assert matrix.shape == (4, 4)
    np.testing.assert_allclose(matrix, matrix.T)
    np.testing.assert_allclose(np.diag(matrix), 0)
    assert matrix[0, 1] == pytest.approx(1.0)
    assert matrix[0, 2] == pytest.approx(np.sqrt(2))
    assert route_distance([0, 1, 2, 3, 0], matrix) == pytest.approx(4.0)


def test_valid_route_visits_each_customer_once(square):
    validate_route([0, 1, 2, 3, 0], square)


@pytest.mark.parametrize(
    "route",
    [
        [0, 1, 2, 0],  # missing customer
        [0, 1, 1, 3, 0],  # duplicate customer
        [0, 1, 2, 3],  # no return to depot
        [1, 0, 2, 3, 1],  # wrong starting point
        [0, 1, 2, 4, 0],  # index outside dataset
        [0, 0, 1, 2, 3, 0],  # interior depot visit
    ],
)
def test_invalid_closed_tours_are_rejected(square, route):
    with pytest.raises(ValueError):
        validate_route(route, square)


def test_depot_does_not_have_to_be_row_zero(shifted_depot):
    assert shifted_depot.depot_index == 2
    validate_route([2, 0, 1, 3, 2], shifted_depot)
    assert route_distance([2, 0, 1, 3, 2], distance_matrix(shifted_depot)) == pytest.approx(4)


@pytest.mark.parametrize("depots", [(False, False), (True, True)])
def test_exactly_one_depot_is_required(depots):
    with pytest.raises(ValueError):
        dataset = Dataset("Invalid", (
            Location("A", "First", 0, 0, depots[0]),
            Location("B", "Second", 1, 0, depots[1]),
        ))
        validate_dataset(dataset)


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        dataset = Dataset("Invalid", (
            Location("A", "Depot", 0, 0, True),
            Location("A", "Customer", 1, 0, False),
        ))
        validate_dataset(dataset)


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_coordinates_rejected(coordinate):
    with pytest.raises(ValueError):
        dataset = Dataset("Invalid", (
            Location("D", "Depot", 0, 0, True),
            Location("A", "Customer", coordinate, 0, False),
        ))
        validate_dataset(dataset)
