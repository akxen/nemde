"""Detailed single-casefile check: like test_backtest_regression.py's trader/region
gates, but with exact price-tie-group handling (via get_price_tied_bands) instead of
the generic largest-diffs-net-to-zero heuristic in nemde/backtest.py. Kept narrow
(one 2021 interval) since it's a precision check, not a sampling-based regression gate.
"""

import copy
from pathlib import Path

import pandas as pd
from ulid import ULID

from nemde.backtest import CHECKS, check_collection
from nemde.inputs import get_price_tied_bands
from nemde.run import run_model
from tests.conftest import requires_input_data

pytestmark = requires_input_data

CASEFILE_PATH = "input/NemSpdOutputs_20210101_loaded/NEMSPDOutputs_2021010100100.loaded"

# Trade type(s) whose price bands determine which traders are interchangeable
# (price-tied) for a given dispatch target field. When two or more traders are
# price-tied, the LP has multiple equally-optimal ways to split dispatch between
# them, and this model doesn't implement AEMO's exact tie-break rule (only an
# approximate one for ENOF/LDOF via S_TRADER_PRICE_TIED_*, none at all for
# FCAS -- see model.define_tie_breaking_constraints) - so the split between
# tied traders is expected to differ from NEMDE's, even though their combined
# total will match. Fields not listed here (violations) have no such ambiguity.
FIELD_TRADE_TYPES = {
    "@EnergyTarget": ["ENOF", "LDOF", "BDOF"],
    "@R6Target": ["R6SE"],
    "@R60Target": ["R60S"],
    "@R5Target": ["R5MI"],
    "@R5RegTarget": ["R5RE"],
    "@L6Target": ["L6SE"],
    "@L60Target": ["L60S"],
    "@L5Target": ["L5MI"],
    "@L5RegTarget": ["L5RE"],
}


def _tie_group_map(casefile, trader_ids):
    """
    Map each trader_id to a group id, where two traders share a group id for a
    given field iff they are price-tied for one of that field's trade types
    (see FIELD_TRADE_TYPES). Traders with no ties are their own singleton group.
    """
    parent = {tid: tid for tid in trader_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    group_map = {}
    for field, trade_types in FIELD_TRADE_TYPES.items():
        for trade_type in trade_types:
            for tie in get_price_tied_bands(casefile, trade_type=trade_type):
                trader_1, trader_2 = tie[0], tie[4]
                if trader_1 in parent and trader_2 in parent:
                    union(trader_1, trader_2)
        group_map[field] = {tid: find(tid) for tid in trader_ids}
        # Reset parent for the next field's independent grouping
        parent = {tid: tid for tid in trader_ids}

    return group_map


def check_trader_solution(casefile, solution):
    to_check = [
        "@EnergyTarget",
        "@R6Target",
        "@R60Target",
        "@R5Target",
        "@R5RegTarget",
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
    ]

    actual = (
        pd.DataFrame(casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["TraderSolution"])
        .drop("@PeriodID", axis=1)
        .set_index(["@TraderID", "@Intervention"])
        .stack(future_stack=True)
        .to_frame("actual")
        .rename_axis(["trader_id", "intervention", "name"])
        .reset_index()
        .loc[lambda df_: df_["name"].isin(to_check)]
        .set_index(["trader_id", "intervention", "name"])
        .astype(float)
    )

    estimated = (
        pd.DataFrame(solution["TraderSolution"])
        .set_index(["@TraderID", "@Intervention"])
        .stack(future_stack=True)
        .to_frame("estimated")
        .rename_axis(["trader_id", "intervention", "name"])
        .reset_index()
        .loc[lambda df_: df_["name"].isin(to_check)]
        .set_index(["trader_id", "intervention", "name"])
        .astype(float)
    )

    comparison = (
        actual.join(estimated, how="left")
        .assign(actual_minus_estimated=lambda df_: df_["actual"] - df_["estimated"])
        .reset_index()
    )

    summary = comparison.groupby("name")[["actual_minus_estimated"]].apply(
        lambda grp: grp["actual_minus_estimated"].abs().max()
    )

    # For price-tied fields, dispatch can be split differently among tied
    # traders than NEMDE's (unimplemented) tie-break rule chose, while still
    # summing to the same total. Compare grouped sums instead of raw per-trader
    # values for those fields so genuine dispatch bugs are still caught.
    group_map = _tie_group_map(casefile, comparison["trader_id"].unique())
    grouped = comparison.copy()
    grouped["group_id"] = grouped.apply(
        lambda row: group_map.get(row["name"], {}).get(row["trader_id"], row["trader_id"]),
        axis=1,
    )
    grouped_summary = (
        grouped.groupby(["name", "intervention", "group_id"])[["actual", "estimated"]]
        .sum()
        .assign(actual_minus_estimated=lambda df_: (df_["actual"] - df_["estimated"]).abs())
        .groupby("name")["actual_minus_estimated"]
        .max()
    )

    within_tolerance = grouped_summary.max() < 0.1

    return within_tolerance, summary, comparison


def test_casefile_solution(file_service, git_sha):
    casefile = file_service.load_artefact(relative_path=Path(CASEFILE_PATH))
    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]
    run_id = str(ULID())

    solution = run_model(casefile=copy.deepcopy(casefile))

    region = check_collection(
        casefile=casefile,
        solution=solution,
        spec=CHECKS["region"],
        run_id=run_id,
        git_sha=git_sha,
    )
    region_within_tolerance = region.within_tolerance
    region_summary, region_comparison = region.summary, region.comparison

    trader_within_tolerance, trader_summary, trader_comparison = check_trader_solution(
        casefile=casefile, solution=solution
    )

    output_dir = Path("tests/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    region_summary.to_csv(output_dir / f"region_solution_summary_{casefile_id}.csv", index=False)
    region_comparison.to_csv(
        output_dir / f"region_solution_comparison_{casefile_id}.csv", index=False
    )

    trader_summary.to_frame("value").assign(casefile_id=casefile_id).to_csv(
        output_dir / f"trader_solution_summary_{casefile_id}.csv"
    )
    trader_comparison.assign(casefile_id=casefile_id).to_csv(
        output_dir / f"trader_solution_comparison_{casefile_id}.csv", index=False
    )

    assert region_within_tolerance
    assert trader_within_tolerance
