"""Small geometric instances shared by scientific correctness tests."""

import pytest

from tsp.models import Dataset, Location


@pytest.fixture
def square():
    """A unit square, with three customers and a depot at the origin."""
    return Dataset(
        name="Unit square",
        locations=(
            Location("D", "Depot", 0.0, 0.0, True),
            Location("A", "East", 1.0, 0.0, False),
            Location("B", "North east", 1.0, 1.0, False),
            Location("C", "North", 0.0, 1.0, False),
        ),
    )


@pytest.fixture
def shifted_depot():
    """Same geometry with the depot deliberately outside row zero."""
    return Dataset(
        name="Depot in row 2",
        locations=(
            Location("A", "East", 1.0, 0.0, False),
            Location("B", "North east", 1.0, 1.0, False),
            Location("D", "Depot", 0.0, 0.0, True),
            Location("C", "North", 0.0, 1.0, False),
        ),
    )
