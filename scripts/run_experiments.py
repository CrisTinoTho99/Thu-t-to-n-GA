"""Run and export the project's reproducible experiments from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tsp.data_loader import dataset_to_csv, generate_random_dataset
from tsp.evaluation.benchmark import run_benchmark, save_benchmark
from tsp.models import GAConfig


def main() -> None:
    """Parse an explicit experiment configuration and save real measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", nargs="+", type=int, default=[5, 10, 20, 30])
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--population", type=int, default=100)
    parser.add_argument("--generations", type=int, default=200)
    parser.add_argument("--patience", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument("--write-samples", action="store_true",
                        help="Also write benchmark input datasets to data/samples.")
    args = parser.parse_args()
    config = GAConfig(population_size=args.population, generations=args.generations,
                      seed=args.seed, early_stopping_patience=args.patience)
    print(f"Running {args.repeats} GA and Random Search repeats per dataset...", flush=True)
    result = run_benchmark(tuple(args.customers), repeats=args.repeats,
                           base_seed=args.seed, config=config)
    paths = save_benchmark(result, args.output)
    if args.write_samples:
        sample_dir = ROOT / "data" / "samples"
        sample_dir.mkdir(parents=True, exist_ok=True)
        for key, dataset in result.datasets.items():
            (sample_dir / f"{key}.csv").write_text(dataset_to_csv(dataset), encoding="utf-8")
        square = "id,name,x,y,is_depot\nD,Warehouse,0,0,true\nA,Customer A,1,0,false\nB,Customer B,1,1,false\nC,Customer C,0,1,false\n"
        (sample_dir / "unit_square.csv").write_text(square, encoding="utf-8")
    print(result.summary.to_string(index=False), flush=True)
    for kind, path in paths.items():
        print(f"{kind}: {path}", flush=True)


if __name__ == "__main__":
    main()
