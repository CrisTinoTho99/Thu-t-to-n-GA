"""App-level flows and protection against unintended solver reruns."""
from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

from tsp.data_loader import generate_random_dataset
from tsp.models import GAConfig
from tsp.services import optimize, bundle_json, route_png

ROOT = Path(__file__).resolve().parents[1]


def test_all_pages_and_snapshot_reuse():
    """Changing navigation and generation must preserve the exact saved run."""
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not app.exception
    saved = json.dumps([r.to_dict() for r in app.session_state.results], sort_keys=True)
    for page in ["Route Playground", "Genetic Algorithm Lab", "Algorithm Comparison", "Experiments & Analytics", "About & Documentation", "Dashboard"]:
        app.radio(key="page").set_value(page).run()
        assert not app.exception, [(e.message, e.stack_trace) for e in app.exception]
        assert json.dumps([r.to_dict() for r in app.session_state.results], sort_keys=True) == saved
        assert app.session_state.run_number == 1
        if page == "Genetic Algorithm Lab":
            snapshot = next(s for s in app.slider if s.label == "Generation snapshot")
            snapshot.set_value(0).run()
            assert not app.exception
            assert json.dumps([r.to_dict() for r in app.session_state.results], sort_keys=True) == saved


def test_manual_data_and_explicit_optimization():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.radio(key="page").set_value("Route Playground").run()
    next(b for b in app.button if b.label == "Use pasted coordinates").click().run()
    assert not app.exception
    assert len(app.session_state.dataset.locations) == 4
    assert app.session_state.results == []
    next(b for b in app.button if "Run optimization" in b.label).click().run()
    assert not app.exception
    assert len(app.session_state.results) == 4
    assert app.session_state.run_number == 2
    assert min(r.distance for r in app.session_state.results) == pytest.approx(4)


def test_invalid_input_keeps_existing_dataset():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.radio(key="page").set_value("Route Playground").run()
    fingerprint = app.session_state.dataset.fingerprint
    app.text_area[0].set_value("id,name,x,y,is_depot\n1,bad,nan,1,true").run()
    next(b for b in app.button if b.label == "Use pasted coordinates").click().run()
    assert not app.exception
    assert app.error
    assert app.session_state.dataset.fingerprint == fingerprint


def test_service_bundle_png_and_solver_validation():
    dataset = generate_random_dataset(4)
    results = optimize(dataset, GAConfig(population_size=8, generations=3), ["Genetic Algorithm", "Random Search"])
    assert results[0].evaluations == results[1].evaluations
    bundle = json.loads(bundle_json(dataset, results))
    assert bundle["dataset_fingerprint"] == dataset.fingerprint
    assert len(bundle["results"]) == 2
    assert route_png(dataset, results[0].route).startswith(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError):
        optimize(dataset, GAConfig(), [])


def test_interactive_benchmark_submission(tmp_path, monkeypatch):
    """Exercise the actual benchmark form and exports without replacing release evidence."""
    import tsp.evaluation.benchmark as module
    real_save = module.save_benchmark
    monkeypatch.setattr(module, "save_benchmark", lambda result, output_dir: real_save(result, tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.session_state.run_config = GAConfig(population_size=6, generations=2)
    app.radio(key="page").set_value("Experiments & Analytics").run()
    next(m for m in app.multiselect if m.label.startswith("Customer counts")).set_value([5])
    next(n for n in app.number_input if n.label == "Stochastic runs per dataset").set_value(2)
    next(b for b in app.button if b.label == "Run benchmark & save").click().run()
    assert not app.exception
    assert app.session_state.benchmark.metadata["repeats"] == 2
    assert (tmp_path / "raw/benchmark.json").exists()
    assert len(app.session_state.benchmark.raw) == 7  # 2 GA, 2 RS, NN, 2-opt, exact
