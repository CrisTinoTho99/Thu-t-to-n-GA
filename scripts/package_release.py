"""Package source, measured results, documentation and available artifacts."""
from pathlib import Path
from os import walk
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", ".git", ".qa", "node_modules", "__pycache__", ".pytest_cache", "tmp", "release", "interactive"}


def main() -> None:
    """Create a distribution without environment files or private configuration."""
    destination = ROOT / "release" / "TSP-AI-Route-Optimizer.zip"
    destination.parent.mkdir(exist_ok=True)
    paths = []
    for directory, subdirectories, filenames in walk(ROOT):
        subdirectories[:] = sorted(name for name in subdirectories
                                   if name not in EXCLUDED and not name.endswith(".egg-info"))
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix not in {".log", ".pyc"} and filename != "secrets.toml":
                paths.append(path)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(paths):
            archive.write(path, Path("TSP-AI-Route-Optimizer") / path.relative_to(ROOT))
    print(f"Packaged {len(paths)} files: {destination}")


if __name__ == "__main__":
    main()
