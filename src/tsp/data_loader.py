"""Validated CSV, tabular, and seeded synthetic dataset input."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from .models import Dataset, Location, _integer, validate_seed
from .validation import MAX_CUSTOMERS

REQUIRED_COLUMNS = ("id", "name", "x", "y", "is_depot")


def _boolean(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in ("true", "false", "0", "1"):
        return value.strip().lower() in ("true", "1")
    raise ValueError("is_depot accepts only true/false or 1/0.")


def dataset_from_frame(frame: pd.DataFrame, name: str = "Custom dataset") -> Dataset:
    """Validate all required fields, preserving the input's row order."""
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("Input must be a pandas DataFrame.")
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    if frame.columns.duplicated().any():
        raise ValueError("CSV columns must be unique.")
    rows: list[Location] = []
    for position, (_, row) in enumerate(frame.iterrows(), start=1):
        if row[list(REQUIRED_COLUMNS)].isna().any():
            raise ValueError(f"Row {position}: required fields cannot be empty.")
        try:
            if isinstance(row["x"], (bool, np.bool_)) or isinstance(row["y"], (bool, np.bool_)):
                raise ValueError("Coordinates must be finite numbers.")
            rows.append(Location(str(row["id"]).strip(), str(row["name"]).strip(), float(row["x"]), float(row["y"]), _boolean(row["is_depot"])))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Row {position}: {exc}") from exc
    return Dataset(name, tuple(rows))


def load_csv(source: Any, name: str = "Uploaded dataset") -> Dataset:
    """Load a path or readable stream. A literal CSV string is also accepted."""
    if isinstance(source, str) and ("\n" in source or "\r" in source):
        source = StringIO(source)
    try:
        frame = pd.read_csv(source, dtype={"id": str, "name": str}, encoding="utf-8-sig")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError, OSError, ValueError) as exc:
        raise ValueError(f"Cannot read CSV: {exc}") from exc
    return dataset_from_frame(frame, name)


def dataset_to_csv(dataset: Dataset) -> str:
    return dataset.to_frame().to_csv(index=False, lineterminator="\n")


def generate_random_dataset(n_customers: int, seed: int = 42, name: str | None = None) -> Dataset:
    """Generate customers in [0,100)² and a fixed central depot (50,50)."""
    _integer(n_customers, "n_customers", 1, MAX_CUSTOMERS)
    validate_seed(seed)
    rng = np.random.default_rng(seed)
    coordinates = rng.uniform(0, 100, size=(n_customers, 2))
    locations = [Location("D0", "Warehouse", 50.0, 50.0, True)]
    locations.extend(Location(f"C{i + 1:03d}", f"Customer {i + 1:02d}", float(x), float(y)) for i, (x, y) in enumerate(coordinates))
    return Dataset(name or f"{n_customers} customers · seed {seed}", tuple(locations))
