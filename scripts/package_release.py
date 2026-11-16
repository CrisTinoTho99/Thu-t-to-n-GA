"""Package source, measured results, documentation and available artifacts."""
import argparse
from pathlib import Path
from os import walk
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", ".git", ".qa", ".cache", ".build", "node_modules", "__pycache__", ".pytest_cache", "tmp", "release", "interactive"}


def main() -> None:
    """Create a distribution without environment files or private configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked-only", action="store_true",
                        help="Package paths in the Git index; stage new project files first.")
    args = parser.parse_args()
    destination = ROOT / "release" / "TSP-AI-Route-Optimizer.zip"
    destination.parent.mkdir(exist_ok=True)
    paths = []
    if args.tracked_only:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                                check=True, capture_output=True).stdout.decode("utf-8")
        candidates = (ROOT / name for name in listed.split("\0") if name)
    else:
        discovered = []
        for directory, subdirectories, filenames in walk(ROOT):
            subdirectories[:] = sorted(name for name in subdirectories
                                       if name not in EXCLUDED and not name.endswith(".egg-info"))
            discovered.extend(Path(directory) / filename for filename in filenames)
        candidates = iter(discovered)
    for path in candidates:
        if (path.is_file() and not set(path.relative_to(ROOT).parts) & EXCLUDED
                and path.suffix not in {".log", ".pyc"} and path.name != "secrets.toml"):
            paths.append(path)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(paths):
            archive.write(path, Path("TSP-AI-Route-Optimizer") / path.relative_to(ROOT))
    print(f"Packaged {len(paths)} files: {destination}")


if __name__ == "__main__":
    main()
