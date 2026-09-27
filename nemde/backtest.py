import json
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from ulid import ULID

from nemde.file_service import FileService
from nemde.model_options import SolveOptions
from nemde.report import build_html_report
from nemde.run import run_model

# pandas 2.2.2 false-positive: assign() on join() results triggers this despite
# operating on a local copy with no intent to mutate the original. Fixed in 2.2.3.
# pytest resets per-test filters, so the same filter is also declared in
# pyproject.toml's [tool.pytest.ini_options]; this one covers non-pytest use.
warnings.filterwarnings("ignore", category=FutureWarning, message="ChainedAssignmentError")


def run_created_at(run_id: str) -> pd.Timestamp:
    """The instant `run_id` was minted, recovered from the ULID itself.

    A ULID's leading 48 bits are its creation time, so the run id is the single
    source of truth for when a run started. Every timestamp is derived from it
    — the columns on the comparison frames, the summary, the artefact path — so
    they agree no matter how long the solve took. Independent utcnow() calls
    straddling a 300s solve can land either side of midnight and file a run
    under one date while stamping its rows with another. Callers may supply a
    run id of their own, so a non-ULID falls back to the wall clock.
    """

    try:
        return pd.Timestamp(ULID.from_str(run_id).datetime)
    except ValueError:
        return pd.Timestamp.utcnow()


def trim_tied_outliers(
    per_entity_diff: pd.Series, tolerance: float, max_outliers: int = 5
) -> tuple:
    """Drop up to `max_outliers` of the largest-magnitude diffs from a signed
    per-entity diff series, but only when the dropped diffs net close to
    zero — the signature of an alternate-optimal reallocation (one entity
    losing dispatch, another gaining it) rather than a genuine regression,
    which has nothing offsetting it and so won't cancel out. Returns
    (kept_diffs, n_trimmed).
    """
    ranked = per_entity_diff.reindex(per_entity_diff.abs().sort_values(ascending=False).index)
    for k in range(max_outliers + 1):
        dropped, kept = ranked.iloc[:k], ranked.iloc[k:]
        if abs(dropped.sum()) < tolerance and (kept.empty or kept.abs().max() < tolerance):
            return kept, k
    return ranked, 0


@dataclass(frozen=True)
class SolutionCheck:
    """How one solution collection is compared against NEMDE's own output.

    Deliberately the same shape as tests/test_refactor_snapshot.py's
    _COMPARISONS table, so the backtest gate and the snapshot gate cannot
    drift apart silently.

    gated_fields decide pass/fail; reported_fields are compared and written to
    the artefacts but never gate -- see the FCAS tie-breaking note below.
    """

    collection: str
    id_field: str
    id_col: str
    gated_fields: tuple[str, ...]
    reported_fields: tuple[str, ...] = ()
    # Fields NEMDE's own published solution never carries (checked across every
    # fixture casefile), so there is no "actual" to gate or diff against -- only
    # ever reported as the model's own estimate.
    model_only_fields: tuple[str, ...] = ()
    # Traders only: drop up to N tied-outlier traders before gating.
    trim_outliers: int = 0
    sort_summary: bool = False


@dataclass(frozen=True)
class CheckResult:
    within_tolerance: bool
    summary: pd.DataFrame
    comparison: pd.DataFrame
    max_err: float
    model_only: pd.DataFrame


# FCAS has no tie-breaking constraints in this model, so traders (and hence
# regions) with identical FCAS bid bands can land on different but equally
# optimal targets. Those fields are reported for visibility and excluded from
# the gate. @EnergyPrice is likewise excluded here because it has its own
# dedicated $/MWh tolerance further downstream.
CHECKS = {
    "region": SolutionCheck(
        collection="RegionSolution",
        id_field="@RegionID",
        id_col="region_id",
        gated_fields=(
            "@FixedDemand",
            "@NetExport",
            "@SurplusGeneration",
        ),
        reported_fields=(
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
            "@EnergyPrice",
        ),
        model_only_fields=(
            "@ClearedDemand",
            "@DispatchedGeneration",
            "@DispatchedLoad",
        ),
    ),
    "interconnector": SolutionCheck(
        collection="InterconnectorSolution",
        id_field="@InterconnectorID",
        id_col="interconnector_id",
        gated_fields=("@Flow", "@Losses", "@Deficit"),
    ),
    "trader": SolutionCheck(
        collection="TraderSolution",
        id_field="@TraderID",
        id_col="trader_id",
        gated_fields=("@EnergyTarget",),
        reported_fields=(
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
            "@R6Violation",
            "@R60Violation",
            "@R5Violation",
            "@R5RegViolation",
            "@L6Violation",
            "@L60Violation",
            "@L5Violation",
            "@L5RegViolation",
        ),
        trim_outliers=10,
        sort_summary=True,
    ),
}


def _stack(frame: pd.DataFrame, spec: SolutionCheck, value_col: str, fields: list[str]):
    return (
        frame.set_index([spec.id_field, "@Intervention"])
        .stack(future_stack=True)
        .to_frame(value_col)
        .rename_axis([spec.id_col, "intervention", "name"])
        .reset_index()
        .loc[lambda df_: df_["name"].isin(fields)]
        .set_index([spec.id_col, "intervention", "name"])
        .replace("", np.nan)
        .astype(float)
    )


def check_collection(
    casefile: dict,
    solution: dict,
    spec: SolutionCheck,
    run_id: str,
    git_sha: str,
    tolerance: float = 0.1,
) -> CheckResult:
    """Compare one solution collection against NEMDE's published values."""

    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]
    fields = list(spec.gated_fields) + list(spec.reported_fields)
    stamp = dict(
        casefile_id=casefile_id,
        run_id=run_id,
        git_sha=git_sha,
        timestamp=run_created_at(run_id).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    actual = _stack(
        pd.DataFrame(casefile["NEMSPDCaseFile"]["NemSpdOutputs"][spec.collection]).drop(
            "@PeriodID", axis=1, errors="ignore"
        ),
        spec,
        "actual",
        fields,
    )
    solution_frame = pd.DataFrame(solution[spec.collection])
    estimated = _stack(solution_frame, spec, "estimated", fields)

    comparison = (
        actual.join(estimated, how="left")
        .assign(actual_minus_estimated=lambda df_: df_["actual"] - df_["estimated"])
        .reset_index()
        .assign(**stamp)
    )

    model_only = (
        _stack(solution_frame, spec, "estimated", list(spec.model_only_fields))
        .reset_index()
        .assign(**stamp)
        if spec.model_only_fields
        else pd.DataFrame()
    )

    summary = (
        comparison.groupby("name")[["actual_minus_estimated"]]
        .apply(lambda grp: grp["actual_minus_estimated"].abs().max())
        .to_frame("value")
    )
    if spec.sort_summary:
        summary = summary.sort_values(by="value", ascending=False)
    summary = summary.reset_index().assign(**stamp)

    gated = comparison.loc[lambda df_: df_["name"].isin(spec.gated_fields)]

    if spec.trim_outliers:
        # Marginal units with identical energy bid bands may produce different
        # but equally valid allocations. Drop up to trim_outliers entities
        # before checking tolerance -- but only when their diffs net close to
        # zero (see trim_tied_outliers), so a genuine regression concentrated
        # in one or two entities isn't trimmed away just for being the largest.
        per_entity_signed = gated.groupby(spec.id_col)["actual_minus_estimated"].apply(
            lambda x: x.loc[x.abs().idxmax()]
        )
        kept, _n_trimmed = trim_tied_outliers(per_entity_signed, tolerance, spec.trim_outliers)
        max_err = float(kept.abs().max()) if not kept.empty else 0.0
    else:
        max_err = float(gated["actual_minus_estimated"].abs().max()) if not gated.empty else 0.0

    return CheckResult(
        within_tolerance=bool(max_err < tolerance),
        summary=summary,
        comparison=comparison,
        max_err=max_err,
        model_only=model_only,
    )


def check_objective_value(
    casefile: dict, solution: dict, run_id: str, git_sha: str, rel_tolerance: float = 0.05
) -> tuple:
    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]

    period_out = casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["PeriodSolution"]
    actual_obj = float(period_out["@TotalObjective"])
    estimated_obj = float(solution["PeriodSolution"]["@TotalObjective"])

    abs_diff = abs(actual_obj - estimated_obj)
    rel_diff = abs_diff / abs(actual_obj) if actual_obj != 0 else abs_diff

    row = pd.DataFrame(
        [
            {
                "casefile_id": casefile_id,
                "run_id": run_id,
                "git_sha": git_sha,
                "actual_objective": actual_obj,
                "estimated_objective": estimated_obj,
                "abs_diff": abs_diff,
                "rel_diff": rel_diff,
                "timestamp": run_created_at(run_id).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ]
    )

    within_tolerance = rel_diff < rel_tolerance
    return within_tolerance, row


def check_period_solution(
    casefile: dict, solution: dict, run_id: str, git_sha: str
) -> list[pd.DataFrame]:
    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]

    to_check = [
        "@TotalObjective",
        "@TotalRampRateViolation",
        "@TotalUnitMWCapacitySurplusViolation",
        "@TotalUnitMWCapacityDeficitViolation",
    ]

    actual = (
        pd.DataFrame([casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["PeriodSolution"]])
        .set_index("@Intervention")
        .stack(future_stack=True)
        .to_frame("actual")
        .rename_axis(["intervention", "name"])
        .reset_index()
        .loc[lambda df_: df_["name"].isin(to_check)]
        .set_index(["intervention", "name"])
        .astype(float)
    )

    estimated = (
        pd.DataFrame([solution["PeriodSolution"]])
        .set_index("@Intervention")
        .stack(future_stack=True)
        .to_frame("estimated")
        .rename_axis(["intervention", "name"])
        .reset_index()
        .loc[lambda df_: df_["name"].isin(to_check)]
        .set_index(["intervention", "name"])
        .astype(float)
    )

    comparison = (
        actual.join(estimated, how="left")
        .assign(actual_minus_estimated=lambda df_: df_["actual"] - df_["estimated"])
        .reset_index()
        .assign(
            casefile_id=casefile_id,
            run_id=run_id,
            git_sha=git_sha,
            timestamp=run_created_at(run_id).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    )

    return comparison


@dataclass(frozen=True)
class BacktestResult:
    """Everything one backtest produced, with no I/O performed.

    `result` is the gate summary, `summary` its machine-readable twin
    (run_summary.json), `html_report` the standalone report. The comparison
    frames are kept so persist_backtest() can write the CSVs without
    re-solving.
    """

    result: dict
    summary: dict
    html_report: str
    region: CheckResult
    interconnector: CheckResult
    trader: CheckResult
    objective_comparison: pd.DataFrame
    period_comparison: pd.DataFrame


def run_backtest(
    casefile: dict,
    run_id: str | None = None,
    git_sha: str = "",
    tolerance: float = 0.1,
    obj_rel_tolerance: float = 0.05,
    energy_price_tolerance: float = 1.0,
    options: SolveOptions | None = None,
) -> BacktestResult:
    """Solve `casefile` and compare it against NEMDE's own published solution.

    Pure: no filesystem, no git, no network. Callers that want artefacts on
    disk pass the result to persist_backtest().
    """

    run_id = run_id or str(ULID())
    data = json.loads(json.dumps(casefile))
    casefile_id = data["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]

    solution = run_model(casefile=data, options=options)
    solver_info = solution.get("SolverInfo", {})

    checks = {
        name: check_collection(
            casefile=data,
            solution=solution,
            spec=spec,
            run_id=run_id,
            git_sha=git_sha,
            tolerance=tolerance,
        )
        for name, spec in CHECKS.items()
    }
    region, interconnector, trader = checks["region"], checks["interconnector"], checks["trader"]

    (objective_within_tolerance, objective_comparison) = check_objective_value(
        casefile=data,
        solution=solution,
        run_id=run_id,
        git_sha=git_sha,
        rel_tolerance=obj_rel_tolerance,
    )

    energy_price_max_err = float(
        region.comparison.loc[lambda df_: df_["name"].eq("@EnergyPrice"), "actual_minus_estimated"]
        .abs()
        .max()
    )
    energy_price_within_tolerance = energy_price_max_err < energy_price_tolerance

    period_solution_comparison = check_period_solution(
        casefile=data, solution=solution, run_id=run_id, git_sha=git_sha
    )

    actual_obj = objective_comparison["actual_objective"].iloc[0]
    estimated_obj = objective_comparison["estimated_objective"].iloc[0]
    obj_rel_diff = objective_comparison["rel_diff"].iloc[0]

    result = {
        "casefile_id": casefile_id,
        "run_id": run_id,
        "git_sha": git_sha,
        # An infeasible or time-limited solve looks exactly like a large
        # disagreement with NEMDE unless the termination condition is reported.
        "termination_condition": solver_info.get("termination_condition"),
        "solve_seconds": solver_info.get("solve_seconds"),
        "region": region.within_tolerance,
        "region_max_err": region.max_err,
        "energy_price": energy_price_within_tolerance,
        "energy_price_max_err": energy_price_max_err,
        "trader": trader.within_tolerance,
        "trader_max_err": trader.max_err,
        "interconnect": interconnector.within_tolerance,
        "interconnect_max_err": float(interconnector.summary["value"].max()),
        "objective": objective_within_tolerance,
        "actual_obj": actual_obj,
        "estimated_obj": estimated_obj,
        "obj_rel_diff": obj_rel_diff,
        "passed": (
            region.within_tolerance
            and energy_price_within_tolerance
            and trader.within_tolerance
            and interconnector.within_tolerance
            and objective_within_tolerance
        ),
    }

    html_report = build_html_report(
        result=result,
        run_id=run_id,
        git_sha=git_sha,
        tolerance=tolerance,
        obj_rel_tolerance=obj_rel_tolerance,
        energy_price_tolerance=energy_price_tolerance,
        region_comparison=region.comparison,
        region_model_only=region.model_only,
        trader_comparison=trader.comparison,
        interconnector_comparison=interconnector.comparison,
    )

    # Machine-readable twin of the console output and the HTML report: the gate
    # results, the solver's verdict, the objective decomposition and the worst
    # trader diffs, in a form an agent can diff across runs without re-parsing prose.
    summary = {
        **result,
        "timestamp": run_created_at(run_id).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "options": asdict(options) if options is not None else asdict(SolveOptions()),
        "tolerances": {
            "mw": tolerance,
            "objective_rel": obj_rel_tolerance,
            "energy_price": energy_price_tolerance,
        },
        "solver": solver_info,
        "gates": {
            name: {"pass": check.within_tolerance, "max_err": check.max_err}
            for name, check in checks.items()
        },
        "objective_breakdown": solution.get("ObjectiveBreakdown", []),
        "top_trader_diffs": (
            trader.comparison.loc[lambda df_: df_["name"].eq("@EnergyTarget")]
            .reindex(
                trader.comparison.loc[lambda df_: df_["name"].eq("@EnergyTarget")][
                    "actual_minus_estimated"
                ]
                .abs()
                .sort_values(ascending=False)
                .index
            )
            .head(20)[["trader_id", "actual", "estimated", "actual_minus_estimated"]]
            .to_dict(orient="records")
        ),
    }

    return BacktestResult(
        result=result,
        summary=summary,
        html_report=html_report,
        region=region,
        interconnector=interconnector,
        trader=trader,
        objective_comparison=objective_comparison,
        period_comparison=period_solution_comparison,
    )


def run_artefact_dir(casefile_id: str, run_id: str) -> str:
    """Directory one run's artefacts are written to, relative to `output/`.

    Shared by persist_backtest() and solution_report.persist_solution() so a
    solve-only run files alongside a backtest of the same casefile rather than
    inventing a second naming scheme.

    A date partition, then one directory per run with the timestamp first, so
    a name sort in a file browser is a chronological sort across every casefile
    and the whole artefact set for a run sits together. Both levels come off the
    same ULID instant, so a solve that straddles midnight cannot file a run
    under one date and stamp its rows with another. Colons are omitted from the
    timestamp: legal on APFS, but they break on Windows/exFAT shares and need
    quoting in a shell. Nothing downstream parses this path — every CSV already
    carries casefile_id, run_id, git_sha and timestamp as columns, so cross-run
    analysis globs output/*/*/<name>.csv and reads the identifiers from the frame.
    """

    created_at = run_created_at(run_id)
    return (
        f"output_date_utc={created_at.strftime('%Y-%m-%d')}/"
        f"{created_at.strftime('%Y%m%dT%H%M%SZ')}__casefile={casefile_id}__run={run_id}"
    )


def persist_backtest(backtest: BacktestResult, file_service: FileService) -> None:
    """Write the full artefact set for one backtest through `file_service`."""

    run_dir = run_artefact_dir(
        casefile_id=backtest.result["casefile_id"], run_id=backtest.result["run_id"]
    )

    artefacts = {
        "html_report.html": backtest.html_report,
        "region_solution_summary.csv": backtest.region.summary.round(3),
        "region_solution_comparison.csv": backtest.region.comparison.round(3),
        "region_solution_model_only.csv": backtest.region.model_only.round(3),
        "interconnector_solution_summary.csv": backtest.interconnector.summary.round(3),
        "interconnector_solution_comparison.csv": backtest.interconnector.comparison.round(3),
        "trader_solution_summary.csv": backtest.trader.summary,
        "trader_solution_comparison.csv": backtest.trader.comparison.sort_values(
            by="actual_minus_estimated", key=lambda x: x.abs(), ascending=False
        ).round(3),
        "period_solution_comparison.csv": backtest.period_comparison,
        "objective_comparison.csv": backtest.objective_comparison.round(3),
        "run_summary.json": backtest.summary,
    }

    for name, data in artefacts.items():
        file_service.save_artefact(data=data, relative_path=Path(f"output/{run_dir}/{name}"))
