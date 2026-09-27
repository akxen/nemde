"""Golden-master harness: check the model's own dispatch output is stable
across a refactor, independent of whether it matches NEMDE.

Unlike test_backtest_regression.py (which compares the model against NEMDE's
published solution), this compares the model against a *snapshot of its own
prior output* for the same sample of casefiles. Use it to make large
refactors safe without re-litigating the NEMDE-matching gap tracked in
CHECKPOINT.md.

Usage:
    uv run pytest tests/test_refactor_snapshot.py                  # compare vs recorded snapshots
    uv run pytest tests/test_refactor_snapshot.py --snapshot-update # (re)record snapshots

Degenerate/tied solutions: when several dispatch allocations are equally
optimal (e.g. traders bidding identical FCAS bands), a harmless change
(solver version, constraint ordering, ...) can flip which one is chosen.
FCAS target fields are recorded for debugging but excluded from the pass/fail
gate, and the worst few trader energy-target diffs are trimmed before
checking tolerance, mirroring the same mitigations in nemde/backtest.py.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from nemde.backtest import trim_tied_outliers
from nemde.run import run_model
from tests.conftest import CASES_2021, CASES_2025, requires_input_data

pytestmark = requires_input_data

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"

# name -> (collection key, id field, [gated fields], [reported-only fields])
_COMPARISONS = {
    "RegionSolution": (
        "@RegionID",
        [
            "@ClearedDemand",
            "@DispatchedGeneration",
            "@DispatchedLoad",
            "@FixedDemand",
            "@NetExport",
        ],
        [
            "@L1Dispatch",
            "@L5Dispatch",
            "@L5RegDispatch",
            "@L60Dispatch",
            "@L6Dispatch",
            "@R1Dispatch",
            "@R5Dispatch",
            "@R5RegDispatch",
            "@R60Dispatch",
            "@R6Dispatch",
        ],
    ),
    "TraderSolution": (
        "@TraderID",
        ["@EnergyTarget"],
        [
            "@R1Target",
            "@R6Target",
            "@R60Target",
            "@R5Target",
            "@R5RegTarget",
            "@L1Target",
            "@L6Target",
            "@L60Target",
            "@L5Target",
            "@L5RegTarget",
        ],
    ),
    "InterconnectorSolution": (
        "@InterconnectorID",
        ["@Flow", "@Losses"],
        [],
    ),
}

ENERGY_PRICE_TOLERANCE = 0.1  # $/MWh
MW_TOLERANCE = 0.05  # MW -- tighter than backtest.py's NEMDE-comparison tolerance,
# since both sides here are our own model and should agree almost exactly.
OBJ_REL_TOLERANCE = 0.005  # 0.5%
N_OUTLIER_TRADERS = 10  # trim the worst N trader diffs before gating -- see module docstring


def _flatten(solution: dict, collection: str, id_field: str) -> pd.DataFrame:
    return (
        pd.DataFrame(solution[collection])
        .set_index([id_field, "@Intervention"])
        .stack(future_stack=True)
        .to_frame("value")
        .rename_axis([id_field, "intervention", "name"])
        .reset_index()
        .astype({"value": float})
    )


def _diff(baseline: dict, current: dict, collection: str, id_field: str) -> pd.DataFrame:
    old = _flatten(baseline, collection, id_field).rename(columns={"value": "baseline"})
    new = _flatten(current, collection, id_field).rename(columns={"value": "current"})
    return old.merge(new, on=[id_field, "intervention", "name"], how="outer").assign(
        signed_diff=lambda df_: df_["baseline"] - df_["current"],
        diff=lambda df_: (df_["baseline"] - df_["current"]).abs(),
    )


# Diagnostics run_model() attaches to the solution. Nothing gates on them and
# solve timings are not reproducible, so they stay out of the recorded baseline.
_NON_SNAPSHOT_KEYS = ("SolverInfo", "ObjectiveBreakdown")


def _load_or_record(snapshot_path: Path, solution: dict, update: bool) -> dict | None:
    solution = {k: v for k, v in solution.items() if k not in _NON_SNAPSHOT_KEYS}
    if update or not snapshot_path.exists():
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(solution, indent=1, sort_keys=True) + "\n")
        return None
    return json.loads(snapshot_path.read_text())


@pytest.mark.parametrize("relative_path", CASES_2021 + CASES_2025, ids=CASES_2021 + CASES_2025)
def test_snapshot_stable(file_service, relative_path, request):
    casefile = file_service.load_artefact(relative_path=Path(relative_path))
    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]

    solution = run_model(casefile=json.loads(json.dumps(casefile)))

    snapshot_path = SNAPSHOT_DIR / f"{casefile_id}.json"
    update = request.config.getoption("--snapshot-update")
    baseline = _load_or_record(snapshot_path, solution, update)
    if baseline is None:
        pytest.skip(f"recorded new snapshot for {casefile_id}")

    failures = []

    for collection, (id_field, gated_fields, _reported_only_fields) in _COMPARISONS.items():
        diff = _diff(baseline, solution, collection, id_field)
        gated = diff.loc[diff["name"].isin(gated_fields)]

        if collection == "TraderSolution":
            per_trader_signed = gated.groupby(id_field).apply(
                lambda g: g.loc[g["diff"].idxmax(), "signed_diff"], include_groups=False
            )
            kept, _n_trimmed = trim_tied_outliers(
                per_trader_signed, MW_TOLERANCE, N_OUTLIER_TRADERS
            )
            gated = gated.loc[gated[id_field].isin(kept.index)]

        max_err = float(gated["diff"].max()) if not gated.empty else 0.0
        if max_err >= MW_TOLERANCE:
            worst = gated.sort_values("diff", ascending=False).head(3)
            failures.append(
                f"{collection}: max diff {max_err:.4f} MW\n{worst.to_string(index=False)}"
            )

    price_diff = _diff(baseline, solution, "RegionSolution", "@RegionID")
    price_diff = price_diff.loc[price_diff["name"].eq("@EnergyPrice")]
    price_max_err = float(price_diff["diff"].max()) if not price_diff.empty else 0.0
    if price_max_err >= ENERGY_PRICE_TOLERANCE:
        failures.append(f"RegionSolution @EnergyPrice: max diff {price_max_err:.4f} $/MWh")

    baseline_obj = float(baseline["PeriodSolution"]["@TotalObjective"])
    current_obj = float(solution["PeriodSolution"]["@TotalObjective"])
    obj_rel_diff = (
        abs(baseline_obj - current_obj) / abs(baseline_obj) if baseline_obj else abs(current_obj)
    )
    if obj_rel_diff >= OBJ_REL_TOLERANCE:
        failures.append(
            f"PeriodSolution @TotalObjective: {baseline_obj:.2f} -> "
            f"{current_obj:.2f} ({obj_rel_diff:.2%})"
        )

    assert not failures, "\n\n".join(failures)
