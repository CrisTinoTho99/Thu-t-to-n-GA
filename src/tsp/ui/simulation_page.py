"""Delivery simulation page and configuration, using saved solver results."""
from __future__ import annotations

import json

import streamlit as st

from tsp.models import Dataset, OptimizationResult
from tsp.simulation.models import SimulationConfig
from tsp.simulation.timeline import build_schedule
from tsp.simulation.component import CHECKPOINT_KEY, render_simulation
from tsp.ui.theme import header, route_chips


def demo_speed(distance: float, customers: int, service_seconds: float, target_seconds: float = 30) -> float:
    """Fit the reference route once; other algorithms keep the same physical speed."""
    if distance == 0:
        return 1.0
    travel_time = max(target_seconds - customers * service_seconds, target_seconds * .35)
    return max(.000001, distance / travel_time)


def simulation_page() -> None:
    """Configure and mount the vehicle player without invoking any solver."""
    header("Delivery Simulation", "Watch a saved route become a delivery journey. Play, pause, seek, and inspect every stop.")
    dataset: Dataset = st.session_state.dataset
    results: list[OptimizationResult] = st.session_state.results
    if not results:
        st.info("No computed route for this dataset yet. Select algorithms and press Run optimization in the sidebar, then return here.")
        return
    selected = st.selectbox("Simulation route", [r.algorithm for r in results], key="delivery_algorithm")
    result = next(r for r in results if r.algorithm == selected)
    settings_key = "delivery_simulation_settings"
    settings = st.session_state.get(settings_key)
    if not settings or settings["dataset_fingerprint"] != dataset.fingerprint:
        # A shared reference speed keeps comparisons meaningful when switching routes.
        reference = next((r for r in results if r.algorithm == "Genetic Algorithm"), results[0])
        settings = {"dataset_fingerprint": dataset.fingerprint,
                    "base_speed": demo_speed(reference.distance, dataset.n_customers, .35),
                    "service_seconds": .35}
        st.session_state[settings_key] = settings
    with st.expander("Journey settings", expanded=False):
        with st.form("delivery_settings_form"):
            left, right = st.columns(2)
            speed = left.number_input("Base speed (units / simulation second)", min_value=.000001,
                                      value=float(settings["base_speed"]), format="%.6f")
            dwell = right.number_input("Delivery stop (simulation seconds)", min_value=0.0,
                                       max_value=30.0, value=float(settings["service_seconds"]), step=.05)
            st.caption("These settings apply to every route on this dataset. Playback speed (0.5×–4×) is controlled below the map.")
            apply, fit = st.columns(2)
            applied = apply.form_submit_button("Apply journey settings", width="stretch")
            fitted = fit.form_submit_button("Fit selected route to ~30 seconds", width="stretch")
        if applied or fitted:
            try:
                if fitted:
                    if dataset.n_customers * dwell >= 30:
                        raise ValueError("Delivery stops already take 30 seconds or more. Reduce the stop duration before fitting a 30-second demo.")
                    if result.distance == 0:
                        raise ValueError("This route has zero travel distance. Its duration is determined entirely by delivery stops.")
                    speed = result.distance / (30 - dataset.n_customers * dwell)
                config = SimulationConfig(base_speed=float(speed), service_seconds=float(dwell))
                settings = {"dataset_fingerprint": dataset.fingerprint,
                            "base_speed": config.base_speed, "service_seconds": config.service_seconds}
                st.session_state[settings_key] = settings
                st.session_state.pop(CHECKPOINT_KEY, None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    try:
        config = SimulationConfig(base_speed=float(settings["base_speed"]),
                                  service_seconds=float(settings["service_seconds"]))
        schedule = build_schedule(dataset, result, config, run_number=st.session_state.run_number)
    except ValueError as exc:
        st.error(f"This route cannot be simulated: {exc}")
        return
    st.session_state.delivery_simulation_schedule = schedule
    a, b, c, d = st.columns(4)
    a.metric("CUSTOMERS", dataset.n_customers)
    b.metric("ROUTE DISTANCE", f"{schedule['total_distance']:,.3f} units")
    c.metric("SIMULATED JOURNEY", f"{schedule['total_duration']:.1f} s")
    d.metric("RESULT SEED", str(result.seed) if result.seed is not None else "Deterministic")
    st.caption("Straight-line Euclidean simulation · coordinate units · one vehicle · all playback statistics update inside the player")
    render_simulation(schedule)
    with st.expander("Visit order & reproducible simulation data"):
        route_chips([dataset.locations[i].name for i in result.route])
        st.caption(f"Reference speed {config.base_speed:.6f} units/s · service {config.service_seconds:g} s per customer. Algorithm runtime is separate from simulated travel time.")
        st.download_button("↓ Simulation schedule JSON", json.dumps(schedule, ensure_ascii=False, indent=2, allow_nan=False),
                           "delivery_simulation.json", "application/json")
