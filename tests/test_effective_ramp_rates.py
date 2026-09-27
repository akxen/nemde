import os

import pandas as pd
import pytest

from nemde.inputs import (
    get_trader_effective_ramp_dn_rate,
    get_trader_effective_ramp_up_rate,
    get_trader_objects,
)
from tests.conftest import NOVEMBER_2025_CASEFILES, load_casefile, requires_input_data

pytestmark = requires_input_data


def check_effective_ramp_rates(casefile):
    """
    Check if computed effective ramp rates match historical solution data.

    Returns:
        is_match: Boolean indicating if all ramp rates are within tolerance
        max_difference: Maximum absolute difference found
        comparison: DataFrame with detailed comparison
    """
    traders = get_trader_objects(casefile=casefile)

    # Compute estimated effective ramp rates
    estimated = (
        pd.DataFrame(
            [
                {
                    "trader_id": trader.trader_id,
                    "ramp_up_rate": get_trader_effective_ramp_up_rate(trader=trader),
                    "ramp_dn_rate": get_trader_effective_ramp_dn_rate(trader=trader),
                }
                for trader in traders
            ]
        )
        .set_index("trader_id")
        .add_prefix("estimated_")
    )

    # Extract actual ramp rates from TraderSolution
    actual = (
        (
            pd.DataFrame(casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["TraderSolution"])
            .loc[lambda df_: df_["@Intervention"].eq("0")]
            .set_index("@TraderID")
        )[["@RampUpRate", "@RampDnRate"]]
        .rename(
            columns={
                "@RampUpRate": "actual_ramp_up_rate",
                "@RampDnRate": "actual_ramp_dn_rate",
            }
        )
        .astype(float)
    )

    # Compare estimated vs actual
    comparison = actual.join(estimated, how="outer").assign(
        actual_minus_estimated_ramp_up_rate=lambda df_: (
            df_["actual_ramp_up_rate"] - df_["estimated_ramp_up_rate"]
        ),
        actual_minus_estimated_ramp_dn_rate=lambda df_: (
            df_["actual_ramp_dn_rate"] - df_["estimated_ramp_dn_rate"]
        ),
    )

    # Calculate maximum difference
    max_difference = (
        comparison[
            [
                "actual_minus_estimated_ramp_up_rate",
                "actual_minus_estimated_ramp_dn_rate",
            ]
        ]
        .abs()
        .max()
        .max()
    )

    # Check if within tolerance
    is_match = max_difference < 0.1

    return is_match, max_difference, comparison


@pytest.fixture(params=NOVEMBER_2025_CASEFILES)
def casefile_path(request):
    """Fixture that provides paths to all test casefiles."""
    return request.param


def test_effective_ramp_rates_match_historical_data(casefile_path):
    """
    Test that effective ramp rate calculations match historical data.

    This test validates that the `get_trader_effective_ramp_up_rate` and
    `get_trader_effective_ramp_dn_rate` functions correctly compute the
    effective ramp rates by comparing computed values against historical
    TraderSolution data from actual NEMDE dispatch runs.

    The effective ramp rate is the minimum of the energy offer ramp rate
    and the SCADA ramp rate. For bidirectional units, it uses composite
    ramp rates that account for both generation and load sides.
    """
    casefile = load_casefile(casefile_path)
    casefile_id = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]["@CaseID"]

    is_match, max_difference, comparison = check_effective_ramp_rates(casefile)

    # Save comparison results for debugging
    os.makedirs("tests/outputs", exist_ok=True)
    comparison.to_csv(f"tests/outputs/effective_ramp_rates_comparison_{casefile_id}.csv")

    # Print details if not matching
    if not is_match:
        print(f"\nCasefile: {casefile_id}")
        print(f"Max difference: {max_difference}")
        print("\nLargest differences:")
        print(
            comparison.assign(
                max_abs_diff=lambda df_: (
                    df_[
                        [
                            "actual_minus_estimated_ramp_up_rate",
                            "actual_minus_estimated_ramp_dn_rate",
                        ]
                    ]
                    .abs()
                    .max(axis=1)
                )
            ).nlargest(10, "max_abs_diff")[
                [
                    "actual_ramp_up_rate",
                    "estimated_ramp_up_rate",
                    "actual_minus_estimated_ramp_up_rate",
                    "actual_ramp_dn_rate",
                    "estimated_ramp_dn_rate",
                    "actual_minus_estimated_ramp_dn_rate",
                ]
            ]
        )

    assert is_match, (
        f"Effective ramp rate calculations do not match historical data. "
        f"Maximum difference: {max_difference:.6f} (tolerance: 0.1). "
        f"Casefile: {casefile_id}. "
        f"See tests/outputs/effective_ramp_rates_comparison_{casefile_id}.csv for details."
    )
