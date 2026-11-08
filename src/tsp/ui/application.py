"""Route research dashboard. Solvers run on submissions or once at startup."""
from __future__ import annotations

from pathlib import Path
import logging

import pandas as pd
import streamlit as st
import yaml

from tsp.data_loader import generate_random_dataset, load_csv, dataset_from_frame, dataset_to_csv
from tsp.models import GAConfig, Dataset, OptimizationResult
from tsp.services import ALGORITHMS, optimize, bundle_json, save_session, route_png
from tsp.evaluation.metrics import results_frame, improvement_percent
from tsp.visualization.route_plot import route_figure
from tsp.visualization.convergence_plot import convergence_figure, search_comparison_figure
from tsp.visualization.comparison_plot import comparison_figure
from tsp.ui.theme import apply_theme, brand, header, route_chips

ROOT = Path(__file__).resolve().parents[3]
PAGES = ["Dashboard", "Delivery Simulation", "Route Playground", "Genetic Algorithm Lab", "Algorithm Comparison", "Experiments & Analytics", "About & Documentation"]
LOGGER = logging.getLogger(__name__)
PLOT_CONFIG = {"displaylogo": False, "scrollZoom": False, "toImageButtonOptions": {"format": "png", "scale": 2}, "modeBarButtonsToAdd": ["resetScale2d"]}


def _defaults() -> dict:
    return yaml.safe_load((ROOT / "config/default.yaml").read_text(encoding="utf-8"))


def _initialize() -> None:
    """One small, real initial run makes the workspace immediately explorable."""
    if "dataset" not in st.session_state:
        settings = _defaults()
        dataset = generate_random_dataset(settings["dataset"]["customers"], settings["dataset"]["seed"], name="Urban delivery · 20 customers")
        config = GAConfig(**settings["ga"])
        st.session_state.dataset = dataset
        st.session_state.results = optimize(dataset, config, ALGORITHMS[:4])
        st.session_state.run_config = config
        st.session_state.run_number = 1
        st.session_state.dataset_version = 0


def _set_dataset(dataset: Dataset) -> None:
    st.session_state.dataset = dataset
    st.session_state.results = []
    st.session_state.dataset_version += 1
    st.session_state.pop("delivery_simulation_checkpoint", None)
    st.session_state.pop("delivery_simulation_schedule", None)


def _chart(figure, key: str) -> None:
    st.plotly_chart(figure, theme=None, width="stretch", config=PLOT_CONFIG, key=key)


def _sidebar() -> str:
    with st.sidebar:
        brand()
        st.caption("WORKSPACE")
        page = st.radio("Navigation", PAGES, label_visibility="collapsed", key="page")
        st.divider()
        st.caption("DATASET")
        dataset = st.session_state.dataset
        st.markdown(f"**{dataset.name}**")
        st.caption(f"{len(dataset.locations) - 1} customers + 1 warehouse · coordinate units")
        with st.form("dataset_generator"):
            source = st.selectbox("Dataset source", ["Random coordinates", "Sample · 5 customers", "Sample · 10 customers", "Sample · 20 customers", "Sample · 30 customers"])
            customers = st.number_input("Number of customers", 1, 100, 20, step=1)
            data_seed = st.number_input("Dataset seed", 0, 2**32 - 1, 42, step=1)
            if st.form_submit_button("Load dataset", width="stretch"):
                if source == "Random coordinates":
                    replacement = generate_random_dataset(int(customers), int(data_seed))
                else:
                    n = int(source.split("·")[1].split()[0])
                    sample = ROOT / "data/samples" / f"customers_{n}.csv"
                    replacement = load_csv(sample, name=f"Sample · {n} customers") if sample.exists() else generate_random_dataset(n, 1000 + n)
                _set_dataset(replacement)
                st.rerun()
        st.divider()
        st.caption("OPTIMIZATION ENGINE")
        with st.form("optimizer"):
            options = ALGORITHMS if len(dataset.locations) - 1 <= 12 else ALGORITHMS[:-1]
            selected = st.multiselect("Algorithms", options, default=ALGORITHMS[:4])
            with st.expander("Genetic Algorithm settings", expanded=False):
                population = st.number_input("Population size", 4, 500, 100, step=2)
                generations = st.number_input("Generations", 1, 2000, 200, step=10)
                crossover = st.slider("Crossover rate / pair", 0.0, 1.0, .9, .05)
                mutation = st.slider("Mutation rate / child", 0.0, 1.0, .2, .01)
                elite = st.number_input("Elitism count", 0, 499, 2)
                tournament = st.number_input("Tournament size", 2, 500, 3)
                patience = st.number_input("Early stopping patience (0 = off)", 0, 2000, 0)
            seed = st.number_input("Algorithm seed", 0, 2**32 - 1, 42)
            match = st.checkbox("Match Random Search budget to GA", value=True)
            budget = st.number_input("Random Search custom budget", 1, 1_000_000, 19700)
            submitted = st.form_submit_button("▶  Run optimization", type="primary", width="stretch")
        if submitted:
            try:
                config = GAConfig(population_size=int(population), generations=int(generations), crossover_rate=crossover, mutation_rate=mutation, elitism_count=int(elite), tournament_size=int(tournament), seed=int(seed), early_stopping_patience=int(patience))
                with st.spinner("Evaluating routes…"):
                    results = optimize(dataset, config, selected, None if match else int(budget))
                st.session_state.results = results
                st.session_state.run_config = config
                st.session_state.run_number += 1
                st.success("Optimization complete")
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
        st.caption("Reproducible by seed. Display changes reuse the saved run.")
        st.caption("EUCLIDEAN TSP · v1.1")
    return page


def _select_result(key: str = "route_result") -> OptimizationResult | None:
    results = st.session_state.results
    if not results:
        return None
    label = st.selectbox("Route algorithm", [r.algorithm for r in results], key=key)
    return next(r for r in results if r.algorithm == label)


def _results_table(results: list[OptimizationResult]) -> None:
    frame = results_frame(results)
    st.dataframe(frame, hide_index=True, width="stretch", column_config={
        "algorithm": "Algorithm", "distance": st.column_config.NumberColumn("Distance (units)", format="%.3f"),
        "runtime_seconds": st.column_config.NumberColumn("Runtime (s)", format="%.4f"),
        "evaluations": "Evaluations*", "improvement_percent": st.column_config.NumberColumn("vs NN (%)", format="%.2f"), "seed": "Seed"})
    st.caption("Positive improvement = shorter than Nearest Neighbor. *Evaluation units differ for constructive, local and exact solvers; see Documentation.")


def _exports(dataset: Dataset, results: list[OptimizationResult], result: OptimizationResult | None) -> None:
    with st.expander("Export & save", expanded=False):
        a, b, c = st.columns(3)
        a.download_button("↓ Dataset CSV", dataset_to_csv(dataset), "locations.csv", "text/csv", width="stretch")
        b.download_button("↓ Results JSON", bundle_json(dataset, results), "optimization.json", "application/json", width="stretch")
        c.download_button("↓ Comparison CSV", results_frame(results).to_csv(index=False), "comparison.csv", "text/csv", width="stretch")
        if result:
            # On-demand image generation avoids repeating Matplotlib on every UI rerun.
            if st.button("Prepare route PNG", key="prepare_route_png"):
                st.session_state.route_image = (dataset.fingerprint, tuple(result.route), route_png(dataset, result.route))
            cached = st.session_state.get("route_image")
            if cached and cached[:2] == (dataset.fingerprint, tuple(result.route)):
                st.download_button("↓ Route PNG", cached[2], "route.png", "image/png")
            st.download_button("↓ Interactive route HTML", route_figure(dataset, result.route).to_html(include_plotlyjs=True), "route.html", "text/html")
        if st.button("Save run to results/raw", key="save_run"):
            path = save_session(dataset, results, ROOT / "results/raw")
            st.success(f"Saved: {path.relative_to(ROOT)}")


def _dashboard() -> None:
    header("Every stop. A smarter route.", "Explore delivery routes, inspect evolution, and compare the evidence behind each solution.")
    st.button("▶ Open delivery simulation", on_click=_open_simulation, help="Animate any of the saved algorithm routes.")
    dataset, results = st.session_state.dataset, st.session_state.results
    result = _select_result()
    nn = next((r for r in results if r.algorithm == "Nearest Neighbor"), None)
    improvement = improvement_percent(result.distance, nn.distance) if nn and result else None
    cols = st.columns(4)
    cols[0].metric("TOTAL LOCATIONS", len(dataset.locations), f"{len(dataset.locations)-1} customers + warehouse", delta_color="off")
    cols[1].metric("ROUTE DISTANCE", f"{result.distance:,.2f}" if result else "—", "Euclidean units", delta_color="off")
    cols[2].metric("EXECUTION TIME", f"{result.runtime_seconds:.3f} s" if result else "—", "Measured solver runtime", delta_color="off")
    cols[3].metric("IMPROVEMENT VS NN", f"{improvement:+.2f}%" if improvement is not None else "—", "Same coordinates", delta_color="off")
    st.write("")
    main, side = st.columns([3.5, 1.35], gap="medium")
    with main, st.container(border=True):
        st.subheader("Route explorer")
        st.caption("A closed delivery loop · drag to zoom · double-click to reset")
        _chart(route_figure(dataset, result.route if result else None), "dashboard_route")
    with side, st.container(border=True):
        st.subheader("Run overview")
        st.caption("GENETIC ALGORITHM")
        if result:
            st.markdown(f"**{result.algorithm}**")
            st.caption(f"Run #{st.session_state.run_number} · seed {result.seed if result.seed is not None else 'deterministic'}")
            st.divider()
            st.metric("Evaluated solutions / steps", f"{result.evaluations:,}")
            ga = next((r for r in results if r.algorithm == "Genetic Algorithm"), None)
            if ga:
                st.caption(f"GA completed {len(ga.history)-1} generations")
            st.markdown("**Visit order**")
            route_chips([dataset.locations[i].id for i in result.route])
            st.caption("The highlighted diamond is the warehouse. Every customer is visited once.")
        else:
            st.info("Dataset ready. Choose algorithms and press Run optimization in the sidebar.")
    a, b = st.columns(2)
    ga = next((r for r in results if r.algorithm == "Genetic Algorithm"), None)
    with a, st.container(border=True):
        st.subheader("Learning the route")
        st.caption("Actual population distance by generation")
        if ga:
            _chart(convergence_figure(ga.history), "dashboard_convergence")
        else:
            st.info("Run the Genetic Algorithm to view convergence.")
    with b, st.container(border=True):
        st.subheader("Algorithm performance")
        distance, runtime = st.tabs(["Distance", "Runtime"])
        with distance:
            if results:
                _chart(comparison_figure(results), "dashboard_dist")
        with runtime:
            if results:
                _chart(comparison_figure(results, metric="runtime_seconds"), "dashboard_time")
    st.subheader("Results at a glance")
    if results:
        _results_table(results)
    _exports(dataset, results, result)


def _playground() -> None:
    header("Route Playground", "Bring your own coordinates. Shape the dataset, choose a warehouse, and solve it.")
    dataset = st.session_state.dataset
    st.info("CSV schema: id, name, x, y, is_depot. Exactly one warehouse and at least one customer are required.")
    upload, manual = st.tabs(["Upload CSV", "Paste coordinates"])
    with upload:
        file = st.file_uploader("Choose a CSV dataset", type="csv")
        if st.button("Import CSV", disabled=file is None):
            try:
                _set_dataset(load_csv(file, name=Path(file.name).stem))
                st.rerun()
            except (ValueError, TypeError, UnicodeError) as exc:
                st.error(str(exc))
    with manual:
        text = st.text_area("CSV coordinates", "id,name,x,y,is_depot\nW,Warehouse,0,0,true\nA,Customer A,1,0,false\nB,Customer B,1,1,false\nC,Customer C,0,1,false", height=160)
        if st.button("Use pasted coordinates"):
            try:
                _set_dataset(load_csv(text, name="Manual coordinates"))
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
    left, right = st.columns([1.2, 1.6])
    with left:
        st.subheader("Coordinate editor")
        st.caption("Add or delete rows, then Apply changes. ID and name are required.")
        with st.form("editor"):
            name = st.text_input("Dataset name", dataset.name)
            edited = st.data_editor(dataset.to_frame(), num_rows="dynamic", hide_index=True, width="stretch", key=f"editor_{st.session_state.dataset_version}", column_config={"is_depot": st.column_config.CheckboxColumn("Warehouse"), "x": st.column_config.NumberColumn("X"), "y": st.column_config.NumberColumn("Y")})
            depot_id = st.selectbox("Choose warehouse ID (overrides checkbox)", ["Use warehouse checkbox"] + [str(i) for i in dataset.to_frame()["id"]])
            if st.form_submit_button("Apply changes", type="primary"):
                try:
                    if depot_id != "Use warehouse checkbox":
                        edited["is_depot"] = edited["id"].astype(str) == depot_id
                    _set_dataset(dataset_from_frame(edited, name=name))
                    st.rerun()
                except (ValueError, TypeError) as exc:
                    st.error(str(exc))
        if st.button("Reset to minimal dataset", help="Keep the first customer and warehouse; the minimum solvable dataset has two locations."):
            indices = [dataset.depot_index, dataset.customer_indices[0]]
            _set_dataset(Dataset("Minimal dataset", tuple(dataset.locations[i] for i in indices)))
            st.rerun()
    with right, st.container(border=True):
        result = _select_result("playground_result")
        _chart(route_figure(dataset, result.route if result else None), "playground_route")
        if result:
            route_chips([dataset.locations[i].name for i in result.route])
        else:
            st.caption("Apply your data, then run optimization from the sidebar.")
    _exports(dataset, st.session_state.results, result)


def _lab() -> None:
    header("Genetic Algorithm Lab", "Inspect the population history. Every snapshot comes from the saved optimization run.")
    result = next((r for r in st.session_state.results if r.algorithm == "Genetic Algorithm"), None)
    if result is None:
        st.info("Select Genetic Algorithm and run optimization in the sidebar.")
        return
    st.caption("Configure population, generations, crossover, mutation, elitism, tournament and patience in the sidebar. Apply them with Run optimization.")
    history = result.history
    generation = st.slider("Generation snapshot", 0, len(history)-1, len(history)-1, key=f"generation_{st.session_state.run_number}") if len(history) > 1 else 0
    snapshot = history[generation]
    cols = st.columns(4)
    cols[0].metric("GENERATION", snapshot["generation"])
    cols[1].metric("BEST DISTANCE", f"{snapshot['best_distance']:.3f}")
    cols[2].metric("BEST FITNESS", f"{snapshot['best_fitness']:.6f}")
    cols[3].metric("AVERAGE FITNESS", f"{snapshot['average_fitness']:.6f}")
    a, b = st.columns(2)
    with a, st.container(border=True):
        _chart(route_figure(st.session_state.dataset, snapshot["route"], title=f"Generation {generation}"), "lab_route")
    with b, st.container(border=True):
        _chart(convergence_figure(history), "lab_convergence")
    st.subheader("Best chromosome")
    route_chips([st.session_state.dataset.locations[i].id for i in snapshot["route"][1:-1]])
    st.caption("Chromosome stores customer indices only. The warehouse is added at both ends for evaluation and rendering. Fitness = 1 / (distance + 1e-12).")
    st.json(result.parameters, expanded=False)
    with st.expander("Generation data"):
        st.dataframe(pd.DataFrame(history).drop(columns="route"), hide_index=True, width="stretch")


def _comparison() -> None:
    header("Algorithm Comparison", "The same stops, different strategies. Compare measured quality, work, and runtime.")
    results, dataset = st.session_state.results, st.session_state.dataset
    if not results:
        st.info("Run two or more algorithms from the sidebar to compare routes.")
        return
    _results_table(results)
    a, b = st.columns(2)
    with a:
        _chart(comparison_figure(results), "comparison_dist")
    with b:
        _chart(comparison_figure(results, metric="runtime_seconds"), "comparison_time")
    if any(r.algorithm in {"Genetic Algorithm", "Random Search"} for r in results):
        with st.container(border=True):
            st.subheader("Search progress on a common budget axis")
            st.caption("Recorded best distance vs complete-tour evaluations. Random Search is sampled at batch boundaries; GA at generation boundaries.")
            _chart(search_comparison_figure(results), "comparison_search_progress")
    for start in range(0, len(results), 2):
        for col, result in zip(st.columns(2), results[start:start+2]):
            with col, st.container(border=True):
                st.subheader(result.algorithm)
                st.caption(f"{result.distance:.3f} units · {result.runtime_seconds:.4f} s")
                _chart(route_figure(dataset, result.route), f"compare_route_{start}_{result.algorithm}")
    st.caption("GA is a heuristic: a shorter route is not guaranteed. 2-opt is shown separately; the GA does not use local search.")
    _exports(dataset, results, min(results, key=lambda r: r.distance))


def _experiments() -> None:
    from tsp.evaluation.benchmark import run_benchmark, save_benchmark
    import plotly.express as px
    header("Experiments & Analytics", "Repeatable trials, fixed datasets, recorded seeds. Results come from measured runs.")
    with st.form("benchmark_form"):
        a, b, c = st.columns(3)
        counts = a.multiselect("Customer counts (+ one warehouse)", [5, 10, 20, 30], default=[5, 10, 20, 30])
        repeats = b.number_input("Stochastic runs per dataset", 2, 30, 10)
        base_seed = c.number_input("Starting algorithm seed", 0, 2**32-31, 42)
        st.caption("Uses the last applied GA settings. Random Search receives each GA run's actual evaluation count. NN / 2-opt / exact run once per dataset.")
        submitted = st.form_submit_button("Run benchmark & save", type="primary", disabled=not counts)
    if submitted:
        try:
            with st.spinner("Running repeated experiments. This may take a few minutes…"):
                benchmark = run_benchmark(customer_counts=tuple(counts), repeats=int(repeats), base_seed=int(base_seed), config=st.session_state.run_config)
                # Keep interactive trials separate from the reproducible release benchmark.
                paths = save_benchmark(benchmark, output_dir=ROOT / "results/interactive")
                st.session_state.benchmark = benchmark
            st.success("Benchmark complete. Saved under results/interactive.")
        except (ValueError, TypeError, OSError) as exc:
            LOGGER.exception("Benchmark failed")
            st.error(str(exc))
    benchmark = st.session_state.get("benchmark")
    summary_path = ROOT / "results/final/benchmark_summary.csv"
    if benchmark is not None:
        summary, raw = benchmark.summary, benchmark.raw
        st.caption("Showing the benchmark run in this session.")
    elif summary_path.exists():
        summary = pd.read_csv(summary_path)
        raw_path = ROOT / "results/raw/benchmark_runs.csv"
        raw = pd.read_csv(raw_path) if raw_path.exists() else pd.DataFrame()
        st.caption("Showing the saved release benchmark. Configure and run a new trial above.")
    else:
        st.info("No saved benchmark yet. Run an experiment to populate these charts.")
        return
    st.dataframe(summary, hide_index=True, width="stretch")
    if not raw.empty:
        # Benchmark columns are inspected so exports and charts retain their original labels.
        count_col = "customer_count"
        if count_col in raw and "distance" in raw:
            fig = px.box(raw, x=count_col, y="distance", color="algorithm", points="all", template="plotly_dark", labels={count_col: "Customers", "distance": "Distance (coordinate units)"})
            fig.update_layout(paper_bgcolor="#0b1120", plot_bgcolor="#0b1120", height=440)
            _chart(fig, "benchmark_distribution")
    a, b = st.columns(2)
    a.download_button("↓ Summary CSV", summary.to_csv(index=False), "benchmark_summary.csv", "text/csv")
    b.download_button("↓ Raw trials CSV", raw.to_csv(index=False), "benchmark_raw.csv", "text/csv")
    st.caption("Standard deviation uses sample SD (ddof=1) for repeated runs. Exact optimum is available for 5 and 10 customers only. Runtime depends on this machine.")


def _documentation() -> None:
    header("About & Documentation", "Understand the model, the implementation, and the limits of the evidence.")
    st.markdown("""### A delivery loop on a coordinate plane
The Traveling Salesperson Problem asks for the shortest closed tour visiting every customer once.
Here, one warehouse is fixed. Distances are straight lines in **coordinate units**, rather than road travel distances or travel times.

### The genetic algorithm
A chromosome is a permutation of customer indices. A random population evolves through tournament selection,
Order Crossover (OX), inversion mutation, and elitism. Crossover is sampled once per parent pair; mutation once per child.
Fitness is the reciprocal of distance plus a small epsilon. Selection minimizes distance, which is consistent with maximizing this fitness.

**Workflow:** random permutations → evaluate → tournament selection → OX → inversion → preserve elites → next generation.
The saved history includes generation zero. The lab slider reads these snapshots without running the solver again.

### Interpreting comparisons
- **Random Search:** independent random permutations under a recorded evaluation budget.
- **Nearest Neighbor:** repeatedly visit the nearest unvisited customer; ties follow dataset order.
- **Nearest Neighbor + 2-opt:** reverse route segments when they shorten the NN tour. Separate from the pure GA.
- **Exact (Held–Karp):** dynamic programming for at most 12 customers. It certifies the optimum only for these small datasets.

GA / Random Search count complete route evaluations. NN counts one constructed route evaluation; its greedy candidate checks are excluded.
2-opt counts candidate tours plus the initial route evaluation, and Held–Karp counts dynamic-program transitions. Compare objective budgets directly for GA versus Random Search;
use wall-clock runtime for broader computational comparisons.

### Use the workspace
1. Load random or sample data in the sidebar, or edit/import it in Route Playground.
2. Choose algorithms and configure the GA. Press **Run optimization** to apply changes.
3. Inspect routes, history, comparison and benchmark pages.
4. Export dataset CSV, complete results JSON, tables, PNG or interactive HTML.

### Scope and limitations
One vehicle, one warehouse, symmetric Euclidean distances. No vehicle capacity, time windows, traffic, geocoding or road network.
GA and local search are heuristics without a global optimality guarantee. Seeds reproduce routes and histories under the same software versions;
runtimes vary. The interface supports at most 100 generated customers to keep interaction practical. Uploaded datasets are capped at 500 customers.
GA replay uses generation snapshots. Delivery Simulation animates saved solver routes with independent playback controls;
its times describe a Euclidean simulation, not real delivery times.

**Stack:** Python · Streamlit · NumPy · Pandas · Plotly · Matplotlib · Pytest
""")
    for label, filename in [("Architecture", "architecture.md"), ("Algorithm design", "algorithm_design.md"), ("Simulation design", "simulation_design.md"), ("Experimental protocol", "experimental_protocol.md"), ("User guide", "user_guide.md"), ("Full report", "report_content.md")]:
        path = ROOT / "docs" / filename
        if path.exists():
            with st.expander(label):
                st.markdown(path.read_text(encoding="utf-8"))


def _open_simulation() -> None:
    """Navigate through a callback before the sidebar radio is instantiated."""
    st.session_state.page = "Delivery Simulation"


def main() -> None:
    """Initialize once, route pages, and preserve computations between widget events."""
    st.set_page_config(page_title="TSP AI Route Optimizer", page_icon="⌘", layout="wide", initial_sidebar_state="expanded")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    apply_theme()
    _initialize()
    page = _sidebar()
    from tsp.ui.simulation_page import simulation_page
    {"Dashboard": _dashboard, "Delivery Simulation": simulation_page,
     "Route Playground": _playground, "Genetic Algorithm Lab": _lab,
     "Algorithm Comparison": _comparison, "Experiments & Analytics": _experiments,
     "About & Documentation": _documentation}[page]()
    st.divider()
    st.caption("TSP AI Route Optimizer · Genetic Algorithm research workspace · All distances use Euclidean coordinate units")
