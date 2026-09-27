import os

import pandas as pd
import pytest

from nemde.inputs import (
    FCAS_FLAG_MAP,
    FCAS_TRADE_TYPES,
    get_trader_objects,
    is_fcas_available,
)
from tests.conftest import NOVEMBER_2025_CASEFILES, load_casefile, requires_input_data

pytestmark = requires_input_data


def check_fcas_availability(casefile):
    """
    Check if computed FCAS availability matches historical solution data.

    Returns:
        is_match: Boolean indicating if all FCAS availability flags match
        mismatch_count: Number of mismatches found
        comparison: DataFrame with detailed comparison
    """
    traders = get_trader_objects(casefile=casefile)

    # Compute FCAS availability using the logic
    fcas_status = [
        {
            "trader_id": trader.trader_id,
            "trade_type": bid.trade_type,
            "direction": bid.direction,
            "fcas_is_available": is_fcas_available(trader=trader, bid=bid),
        }
        for trader in traders
        for bid in trader.bids
        if bid.trade_type in FCAS_TRADE_TYPES
    ]

    # Extract historical FCAS flags from TraderSolution
    trader_solution = (
        pd.DataFrame(casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["TraderSolution"])[
            [
                "@TraderID",
                "@R1Flags",
                "@R6Flags",
                "@R60Flags",
                "@R5Flags",
                "@R5RegFlags",
                "@L1Flags",
                "@L6Flags",
                "@L60Flags",
                "@L5Flags",
                "@L5RegFlags",
            ]
        ]
        .set_index(["@TraderID"])
        .stack()
        .rename_axis(["trader_id", "solution_trade_type"])
        .to_frame("solution_flag")
        .reset_index()
        .assign(
            trade_type=lambda x: x["solution_trade_type"].map(FCAS_FLAG_MAP),
            solution_fcas_is_available=lambda x: x["solution_flag"].apply(
                lambda x: int(x) % 2 == 1
            ),
        )
        .merge(
            pd.DataFrame(fcas_status)
            .groupby(["trader_id", "trade_type"])[["fcas_is_available"]]
            .any()
            .reset_index(),
            on=["trader_id", "trade_type"],
            how="outer",
        )
        .assign(is_match=lambda x: x["fcas_is_available"] == x["solution_fcas_is_available"])
    )

    mismatch_count = (~trader_solution["is_match"]).sum()
    is_match = mismatch_count == 0

    return is_match, mismatch_count, trader_solution


@pytest.fixture(params=NOVEMBER_2025_CASEFILES)
def casefile_path(request):
    """Fixture that provides paths to all test casefiles."""
    return request.param


def test_fcas_availability_matches_historical_data(casefile_path):
    """
    Test that the FCAS availability logic matches historical FCAS flags.

    This test validates that the `is_fcas_available` function correctly
    identifies when FCAS services are available by comparing computed
    availability against historical TraderSolution FCAS flags from
    actual NEMDE dispatch runs.
    """
    casefile = load_casefile(casefile_path)
    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]

    is_match, mismatch_count, comparison = check_fcas_availability(casefile)

    # Save comparison results for debugging
    os.makedirs("tests/outputs", exist_ok=True)
    comparison.to_csv(f"tests/outputs/fcas_availability_comparison_{casefile_id}.csv", index=False)

    # Print mismatches if any
    if not is_match:
        print(f"\nCasefile: {casefile_id}")
        print(f"Comparison count: {len(comparison)}")
        print(f"Match count: {comparison['is_match'].sum()}")
        print(f"Mismatch count: {mismatch_count}")
        print("\nMismatches:")
        print(comparison.loc[lambda df_: ~df_["is_match"]])

    assert is_match, (
        f"FCAS availability logic does not match historical data. "
        f"Found {mismatch_count} mismatches in casefile {casefile_id}. "
        f"See tests/outputs/fcas_availability_comparison_{casefile_id}.csv for details."
    )
