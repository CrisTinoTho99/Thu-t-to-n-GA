"""Small OSRM adapter with explicit WGS84 coordinates and bounded public usage.

OSRM's table distance is the distance of its fastest road path, in metres. The
TSP solvers choose the visit order; this module never calls OSRM's Trip service.
Only JSON routing responses are cached. Map tiles are never downloaded here.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import numpy as np

from .data_loader import load_csv
from .distance import resolve_matrix
from .models import Dataset
from .validation import validate_route

PUBLIC_OSRM = "https://router.project-osrm.org"
CACHE_VERSION = 1
MAX_PUBLIC_POINTS = 25
MAX_CACHE_ENTRIES = 128
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / ".cache" / "routing"
DEMO_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "demo" / "hcm_osrm_snapshot.json"


class RoutingError(ValueError):
    """Unavailable provider or malformed routing response; user can retry/fallback."""


class NoRouteError(RoutingError):
    """At least one requested point or directed pair has no usable road path."""


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _coordinates(dataset: Dataset, maximum: int = MAX_PUBLIC_POINTS) -> list[list[float]]:
    if not dataset.is_geographic:
        raise RoutingError("Road routing requires explicit latitude/longitude, not Euclidean x/y.")
    if len(dataset.locations) > maximum:
        raise RoutingError(f"Public routing demo is limited to {maximum} locations including the warehouse.")
    # Domain validation already guarantees ranges and prohibits mixed coordinates.
    return [[float(p.longitude), float(p.latitude)] for p in dataset.locations]


def _number(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise RoutingError(f"OSRM returned invalid {field}.")
    return float(value)


def _provider_matrix(dataset: Dataset, value, field: str) -> list[list[float]]:
    if not isinstance(value, list) or any(not isinstance(row, list) for row in value):
        raise RoutingError(f"OSRM returned malformed {field} matrix.")
    if any(cell is None for row in value for cell in row):
        raise NoRouteError(f"No road exists for at least one directed pair in {field}; move/remove the unreachable location or explicitly choose approximate straight lines.")
    if any(isinstance(cell, bool) or not isinstance(cell, (int, float)) for row in value for cell in row):
        raise RoutingError(f"OSRM returned nonnumeric {field} matrix.")
    try:
        return resolve_matrix(dataset, value).tolist()
    except ValueError as exc:
        raise RoutingError(f"OSRM returned invalid {field}: {exc}") from exc


def _geometry(value) -> list[list[float]]:
    if not isinstance(value, list):
        raise RoutingError("OSRM returned missing leg geometry.")
    output = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise RoutingError("OSRM geometry must contain longitude/latitude pairs.")
        lon, lat = point[:2]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lon, lat)) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise RoutingError("OSRM geometry contains invalid longitude/latitude.")
        pair = [float(lon), float(lat)]
        if not output or output[-1] != pair:
            output.append(pair)
    if not output:
        raise RoutingError("OSRM returned an empty leg geometry.")
    if len(output) == 1:
        output.append(output[0].copy())
    return output


class OSRMClient:
    """User-triggered demo requests, shared 1 req/s throttle, timeout, JSON cache.

    A valid cached response is returned before any request. ``refresh=True``
    requests a new response; a previously valid cached result can still be used
    on failure, marked ``stale_cache`` and accompanied by ``cache_error``.
    There are no retries, automatic background requests, or tile prefetches.
    """

    _memory: OrderedDict[str, dict] = OrderedDict()
    _lock = threading.RLock()
    _last_request: dict[str, float] = {}

    def __init__(self, base_url: str = PUBLIC_OSRM, profile: str = "driving", *,
                 timeout: float = 15, min_interval: float = 1,
                 max_points: int = MAX_PUBLIC_POINTS, cache_dir: Path | str | None = DEFAULT_CACHE):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None:
            raise ValueError("OSRM base URL must be an HTTP(S) origin/path without credentials, query or fragment.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", profile):
            raise ValueError("Invalid OSRM profile.")
        if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(min_interval) or min_interval < 0:
            raise ValueError("Timeout must be positive and request interval nonnegative.")
        if isinstance(max_points, bool) or not isinstance(max_points, int) or not 2 <= max_points <= MAX_PUBLIC_POINTS:
            raise ValueError(f"max_points must be between 2 and {MAX_PUBLIC_POINTS}.")
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.timeout = float(timeout)
        self.min_interval = max(float(min_interval), 1.0) if parsed.hostname == "router.project-osrm.org" else float(min_interval)
        self.max_points = max_points
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None

    def _key(self, service, coordinates, options):
        return _digest({"schema": CACHE_VERSION, "provider": self.base_url,
                        "profile": self.profile, "service": service,
                        "coordinates_lon_lat": coordinates, "options": options})

    def _cached(self, key):
        with self._lock:
            if key in self._memory:
                self._memory.move_to_end(key)
                return deepcopy(self._memory[key])
        if self.cache_dir is not None:
            try:
                value = json.loads((self.cache_dir / f"{key}.json").read_text(encoding="utf-8"))
                if value.get("key") == key and isinstance(value.get("response"), dict):
                    return value["response"]
            except (OSError, ValueError, TypeError):
                pass
        return None

    def _snapshot(self, key):
        """Recorded public OSRM responses, only for their exact request keys.

        This is a distributable demo asset, not a substitute matrix for edited
        coordinates. Normal datasets and unrecorded tours still use the provider.
        """
        try:
            snapshot = json.loads(DEMO_SNAPSHOT.read_text(encoding="utf-8"))
            if (snapshot.get("cache_version") != CACHE_VERSION
                    or snapshot.get("provider") != self.base_url
                    or snapshot.get("profile") != self.profile):
                return None
            response = snapshot.get("responses", {}).get(key)
            if isinstance(response, dict):
                return response, snapshot.get("recorded_at", "2026-11-16")
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return None

    def _cache(self, key, response):
        with self._lock:
            self._memory[key] = deepcopy(response)
            self._memory.move_to_end(key)
            while len(self._memory) > MAX_CACHE_ENTRIES:
                self._memory.popitem(last=False)
        if self.cache_dir is not None:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                # Same-key writes are serialized and atomic to readers.
                with self._lock:
                    path = self.cache_dir / f"{key}.json"
                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(json.dumps({"key": key, "response": response}, allow_nan=False), encoding="utf-8")
                    temporary.replace(path)
                    paths = sorted(self.cache_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                    for old in paths[MAX_CACHE_ENTRIES:]:
                        old.unlink(missing_ok=True)
            except OSError:
                pass  # Read-only installation still benefits from bounded memory cache.

    def _fetch(self, service, coordinates, options):
        text = ";".join(f"{lon:.8f},{lat:.8f}" for lon, lat in coordinates)
        url = f"{self.base_url}/{service}/v1/{self.profile}/{text}?{urlencode(options)}"
        request = Request(url, headers={"User-Agent": "TSP-AI-Route-Optimizer/1.2 (educational interactive demo)", "Accept": "application/json"})
        try:
            # Shared across sessions/client instances for this provider.
            with self._lock:
                delay = self.min_interval - (time.monotonic() - self._last_request.get(self.base_url, -math.inf))
                if delay > 0:
                    time.sleep(delay)
                self._last_request[self.base_url] = time.monotonic()
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                raise RoutingError("OSRM response exceeds the demo size limit.")
            payload = json.loads(raw)
        except HTTPError as exc:
            try:
                payload = json.loads(exc.read(100_000))
                self._check_status(payload)
            except RoutingError:
                raise
            except (ValueError, UnicodeError):
                pass
            raise RoutingError(f"OSRM HTTP {exc.code}; retry later or explicitly choose approximate straight lines.") from exc
        except (URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
            if isinstance(exc, RoutingError):
                raise
            reason = getattr(exc, "reason", exc)
            if (isinstance(reason, PermissionError) or getattr(reason, "winerror", None) == 10013
                    or getattr(reason, "errno", None) in (13, 10013)):
                raise RoutingError("Kết nối OSRM bị chặn bởi quyền tiến trình (WinError 10013). "
                                   "Dùng nút Chạy demo TP.HCM với dữ liệu đường bộ đã lưu, "
                                   "hoặc chạy run_demo.ps1 từ PowerShell bình thường để routing các điểm mới.") from exc
            raise RoutingError(f"OSRM network/response error: {exc}. Retry later or use an existing cache / approximate straight lines.") from exc
        self._check_status(payload)
        return payload

    @staticmethod
    def _check_status(payload):
        if not isinstance(payload, dict):
            raise RoutingError("OSRM response is not a JSON object.")
        code = payload.get("code")
        if not isinstance(code, str):
            raise RoutingError("OSRM response lacks a valid status code.")
        if code in {"NoRoute", "NoTable", "NoSegment"}:
            raise NoRouteError(f"OSRM {code}: cannot find a road for one or more locations.")
        if code != "Ok":
            raise RoutingError(f"OSRM {code or 'invalid response'}: {str(payload.get('message', 'request failed'))[:300]}")

    def _response(self, service, coordinates, options, parse, refresh):
        key = self._key(service, coordinates, options)
        cached = self._cached(key)
        provenance = {}
        if cached is not None:
            try:
                parsed = parse(cached)
            except RoutingError:
                cached = None
        if cached is None:
            recorded = self._snapshot(key)
            if recorded is not None:
                try:
                    parsed = parse(recorded[0])
                except RoutingError:
                    pass
                else:
                    cached, recorded_at = recorded
                    provenance = {"bundled_snapshot": True, "recorded_at": recorded_at}
        if cached is not None and not refresh:
            return {**parsed, **provenance, "cache_hit": True, "stale_cache": False}
        try:
            response = self._fetch(service, coordinates, options)
            parsed = parse(response)
        except RoutingError as exc:
            if cached is None:
                raise
            return {**parse(cached), **provenance, "cache_hit": True, "stale_cache": True, "cache_error": str(exc)}
        self._cache(key, response)
        return {**parsed, "cache_hit": False, "stale_cache": False}

    def table(self, dataset: Dataset, *, refresh: bool = False) -> dict:
        coordinates = _coordinates(dataset, self.max_points)

        def parse(payload):
            self._check_status(payload)
            durations = _provider_matrix(dataset, payload.get("durations"), "duration")
            distances = _provider_matrix(dataset, payload["distances"], "distance") if "distances" in payload else None
            objective, unit = ("distance", "m") if distances is not None else ("duration", "s")
            result = {"distances": distances, "durations": durations,
                      "costs": distances if distances is not None else durations,
                      "objective": objective, "unit": unit, "provider": self.base_url,
                      "profile": self.profile, "source": "osrm",
                      "dataset_fingerprint": dataset.fingerprint,
                      "coordinates": coordinates, "data_version": payload.get("data_version")}
            result["fingerprint"] = _digest(result)
            return result

        return self._response("table", coordinates, {"annotations": "distance,duration"}, parse, refresh)

    def route(self, dataset: Dataset, route, *, refresh: bool = False) -> dict:
        coordinates = _coordinates(dataset, self.max_points)
        validate_route(route, dataset)
        ordered = [coordinates[index] for index in route]

        def parse(payload):
            self._check_status(payload)
            routes = payload.get("routes")
            if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
                raise NoRouteError("OSRM returned no route.")
            raw_legs = routes[0].get("legs")
            if not isinstance(raw_legs, list) or len(raw_legs) != len(route) - 1:
                raise RoutingError("OSRM leg count does not match solver route.")
            legs = []
            for start, end, raw in zip(route, route[1:], raw_legs):
                if not isinstance(raw, dict):
                    raise RoutingError("OSRM returned an invalid leg.")
                points = []
                if isinstance(raw.get("geometry"), dict):
                    points = raw["geometry"].get("coordinates")
                else:
                    steps = raw.get("steps", [])
                    if not isinstance(steps, list):
                        raise RoutingError("OSRM route steps must be an array.")
                    for step in steps:
                        if not isinstance(step, dict) or not isinstance(step.get("geometry"), dict):
                            raise RoutingError("OSRM route steps lack GeoJSON geometry.")
                        step_points = step["geometry"].get("coordinates")
                        if not isinstance(step_points, list):
                            raise RoutingError("OSRM route steps lack GeoJSON coordinates.")
                        points.extend(step_points)
                legs.append({"start_index": int(start), "end_index": int(end),
                             "geometry": _geometry(points),
                             "distance_m": _number(raw.get("distance"), "leg distance"),
                             "duration_s": _number(raw.get("duration"), "leg duration")})
            result = {"legs": legs, "provider": self.base_url, "profile": self.profile,
                      "source": "osrm", "dataset_fingerprint": dataset.fingerprint,
                      "data_version": payload.get("data_version")}
            result["fingerprint"] = _digest(result)
            return result

        options = {"steps": "true", "geometries": "geojson", "overview": "false",
                   "alternatives": "false", "continue_straight": "false"}
        return self._response("route", ordered, options, parse, refresh)


def haversine_m(first, second) -> float:
    """Distance between [longitude, latitude] pairs on a spherical Earth."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*first, *second))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6_371_008.8 * 2 * math.asin(min(1.0, math.sqrt(a)))


def approximate_matrix(dataset: Dataset, speed_kmh: float = 30) -> dict:
    """Explicit straight-line approximation in metres; no network calls."""
    coordinates = _coordinates(dataset)
    if isinstance(speed_kmh, bool) or not isinstance(speed_kmh, (int, float)) or not math.isfinite(speed_kmh) or speed_kmh <= 0:
        raise ValueError("Approximation speed must be positive km/h.")
    distances = [[haversine_m(a, b) for b in coordinates] for a in coordinates]
    durations = (np.asarray(distances) / (speed_kmh / 3.6)).tolist()
    result = {"distances": distances, "durations": durations, "costs": distances,
              "objective": "distance", "unit": "m", "provider": "straight-line-haversine",
              "profile": f"constant-{speed_kmh:g}-kmh", "source": "approximate",
              "dataset_fingerprint": dataset.fingerprint, "coordinates": coordinates,
              "speed_kmh": speed_kmh, "cache_hit": False, "stale_cache": False}
    result["fingerprint"] = _digest(result)
    return result


def approximate_route(dataset: Dataset, route, speed_kmh: float = 30) -> dict:
    matrix = approximate_matrix(dataset, speed_kmh)
    validate_route(route, dataset)
    coordinates = matrix["coordinates"]
    legs = [{"start_index": int(a), "end_index": int(b), "geometry": [coordinates[a], coordinates[b]],
             "distance_m": matrix["distances"][a][b], "duration_s": matrix["durations"][a][b]}
            for a, b in zip(route, route[1:])]
    result = {"legs": legs, "provider": matrix["provider"], "profile": matrix["profile"],
              "source": "approximate", "dataset_fingerprint": dataset.fingerprint,
              "cache_hit": False, "stale_cache": False}
    result["fingerprint"] = _digest(result)
    return result


def load_hcm_demo() -> Dataset:
    """Warehouse + ten illustrative delivery locations in central Ho Chi Minh City."""
    return load_csv(Path(__file__).resolve().parents[2] / "data" / "samples" / "hcm_geographic.csv",
                    name="TP.HCM · 1 kho + 10 điểm giao hàng")
