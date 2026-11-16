"""Package already cached genuine OSRM responses; never sends network requests."""
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    entries = {}
    recorded = []
    for path in sorted((ROOT / ".cache" / "routing").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        response = value.get("response", {})
        # The curated demo has eleven points, and each recorded closed tour has eleven legs.
        table = len(response.get("distances", [])) == 11
        route = response.get("routes", [{}])[0]
        if response.get("code") == "Ok" and (table or len(route.get("legs", [])) == 11):
            entries[value["key"]] = response
            recorded.append(path.stat().st_mtime)
    if len(entries) < 2:
        raise RuntimeError("Need a genuine HCM table and at least one complete road route in the cache.")
    result = {
        "schema_version": 1, "cache_version": 1,
        "provider": "https://router.project-osrm.org", "profile": "driving",
        "recorded_at": datetime.fromtimestamp(max(recorded), timezone.utc).isoformat(),
        "description": "Recorded OSRM Table/Route responses for the public HCM demo; exact request keys only. No live traffic.",
        "attribution": "Routing: OSRM; road data © OpenStreetMap contributors (ODbL), https://www.openstreetmap.org/copyright",
        "responses": entries,
    }
    target = ROOT / "data" / "demo" / "hcm_osrm_snapshot.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    print(f"Recorded demo: {len(entries)} genuine responses, {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
