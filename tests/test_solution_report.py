"""Solver-free checks on the solution viewer: the HTML page and the frames
behind it are built from a solution dict alone, so they can be exercised
without CBC or the gitignored casefile data.
"""

from nemde.solution_report import (
    build_solution_report,
    solution_context,
    solution_frames,
)
from tests.conftest import load_casefile

CASEFILE_2024 = "data/input/NemSpdOutputs_20240701_loaded/NEMSPDOutputs_2024070100100.loaded"

TRADE_TYPES = ["R1", "R6", "R60", "R5", "R5Reg", "L1", "L6", "L60", "L5", "L5Reg"]


def make_trader(trader_id: str, energy_target: float = 0.0, **overrides) -> dict:
    trader = {
        "@TraderID": trader_id,
        "@CaseID": "20240701001",
        "@Intervention": "0",
        "@EnergyTarget": energy_target,
        **{f"@{i}Target": 0.0 for i in TRADE_TYPES},
        **{f"@{i}Violation": 0.0 for i in TRADE_TYPES if i != "R1" and i != "L1"},
    }
    return {**trader, **overrides}


def make_solution(traders: list[dict] | None = None) -> dict:
    return {
        "CaseSolution": {"@InterventionStatus": "0"},
        "PeriodSolution": {
            "@CaseID": "20240701001",
            "@Intervention": "0",
            "@TotalObjective": -4_037_823.53,
            "@TotalInterconnectorViolation": 0.0,
            "@TotalGenericViolation": 0.0,
            "@TotalRampRateViolation": 0.4159,
            "@TotalUnitMWCapacityViolation": 0.0,
            "@TotalFastStartViolation": 0.0,
            "@TotalMNSPRampRateViolation": 0.0,
            "@TotalMNSPOfferViolation": 0.0,
            "@TotalMNSPCapacityViolation": 0.0,
            "@TotalUIGFViolation": 0.0,
        },
        "RegionSolution": [
            {
                "@RegionID": "NSW1",
                "@CaseID": "20240701001",
                "@Intervention": "0",
                "@EnergyPrice": 50.86,
                "@DispatchedGeneration": 7082.81,
                "@DispatchedLoad": 45.0,
                "@FixedDemand": 7188.4,
                "@NetExport": -150.59,
                "@SurplusGeneration": 0.0,
                "@ClearedDemand": 7235.55,
                **{f"@{i}Dispatch": 1.0 for i in TRADE_TYPES},
            }
        ],
        "TraderSolution": traders
        if traders is not None
        else [make_trader("BW01", 470.0), make_trader("IDLE1")],
        "InterconnectorSolution": [
            {
                "@InterconnectorID": "NSW1-QLD1",
                "@CaseID": "20240701001",
                "@Intervention": "0",
                "@Flow": -246.16,
                "@Losses": 5.3,
                "@Deficit": 0.0,
            }
        ],
        "ConstraintSolution": [
            {
                "@ConstraintID": "#BANGOWF2_E",
                "@CaseID": "20240701001",
                "@Intervention": "0",
                "@RHS": 82.8,
                "@Deficit": 0.0,
            }
        ],
        "ObjectiveBreakdown": [
            {"name": "OBJECTIVE", "value": -4_037_823.53},
            {"name": "E_MNSP_COST_FUNCTION", "value": 0.0},
        ],
        "SolverInfo": {"termination_condition": "optimal", "solve_seconds": 5.8},
    }


def test_report_renders_without_a_casefile_context():
    html = build_solution_report(solution=make_solution())

    assert html.startswith("<!DOCTYPE html>")
    assert "BW01" in html and "NSW1-QLD1" in html
    # The termination condition is the page's headline verdict, standing in for
    # the backtest report's pass/fail badge.
    assert "OPTIMAL" in html


def test_report_flags_a_non_zero_violation_and_reports_its_magnitude():
    html = build_solution_report(solution=make_solution())

    assert "Ramp rate" in html
    assert "0.4159" in html
    # A violation an order of magnitude below the cell's decimals must still
    # render as a number rather than as 0.0000.
    solution = make_solution()
    solution["PeriodSolution"]["@TotalUIGFViolation"] = 1e-05
    assert "1e-05" in build_solution_report(solution=solution)


def test_traders_dispatched_to_zero_are_marked_for_the_default_filter():
    context = solution_context(load_casefile(CASEFILE_2024))
    html = build_solution_report(solution=make_solution(), context=context)

    # One dispatched trader, one idle: the idle row carries the flag the
    # toolbar's checkbox hides by default, and its region rides on the row so
    # the region select can filter without re-reading the cells.
    assert '<tr data-region="NSW1" data-zero="0">' in html
    assert '<tr data-region="" data-zero="1">' in html


def test_zero_row_toggle_starts_on_when_there_is_nothing_to_hide():
    """A clean solve violates no constraint, so hiding the deficit-free rows
    would leave an empty table."""

    html = build_solution_report(solution=make_solution())

    assert 'class="zero-toggle" data-target="constraint-table" checked' in html
    assert 'class="zero-toggle" data-target="trader-table">' in html


def test_context_labels_traders_and_interconnectors_from_the_casefile():
    context = solution_context(load_casefile(CASEFILE_2024))

    assert context["case_id"] == "20240701001"
    assert context["period_id"].startswith("2024-07-01T")
    assert context["traders"]["BW01"]["region_id"] == "NSW1"
    assert context["traders"]["BW01"]["trader_type"] == "GENERATOR"
    assert context["traders"]["BW01"]["initial_mw"] is not None
    assert context["interconnectors"]["NSW1-QLD1"]["from_region"] == "NSW1"
    assert context["interconnectors"]["NSW1-QLD1"]["to_region"] == "QLD1"


def test_frames_join_the_casefile_labels_onto_the_solution():
    context = solution_context(load_casefile(CASEFILE_2024))
    frames = solution_frames(make_solution(), context)

    trader = frames["trader"].set_index("@TraderID").loc["BW01"]
    assert trader["region_id"] == "NSW1"
    assert trader["target_minus_initial"] == 470.0 - trader["initial_mw"]

    interconnector = frames["interconnector"].set_index("@InterconnectorID").loc["NSW1-QLD1"]
    assert (interconnector["from_region"], interconnector["to_region"]) == ("NSW1", "QLD1")


def test_frames_render_without_a_context():
    frames = solution_frames(make_solution())

    assert frames["trader"]["region_id"].eq("").all()
    assert frames["trader"]["target_minus_initial"].isna().all()
