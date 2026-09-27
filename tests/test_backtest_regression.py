"""Regression harness: run the LP model against a sample of real casefiles
and check the same quality gates as the `nemde-backtest` CLI.

Purpose: give a pass/fail signal against *NEMDE's own* solution, as opposed to
test_refactor_snapshot.py, which only checks the model against its own prior output.

Opt-in: these need data/input, a solver, and several minutes, so they are
deselected unless you pass --run-regression. They used to carry a blanket
`@pytest.mark.skip`, which meant that if the 2025 objective gap ever closed,
nothing would say so. The gap is now a strict xfail instead: the day it starts
passing, the suite reports an unexpected pass rather than staying quiet.

    uv run pytest tests/test_backtest_regression.py --run-regression
"""

from pathlib import Path

import pytest
from ulid import ULID

from nemde.backtest import persist_backtest, run_backtest
from nemde.file_service import LocalFileService
from tests.conftest import CASES_2021, CASES_2025, requires_input_data

pytestmark = [requires_input_data, pytest.mark.regression]

# Each casefile is solved once and its gate results reused by both the dispatch
# and objective tests -- a solve is minutes, and the gates are pure reads off it.
_RESULTS: dict[str, dict] = {}


def _gates(file_service: LocalFileService, git_sha: str, relative_path: str) -> dict:
    if relative_path not in _RESULTS:
        casefile = file_service.load_artefact(relative_path=Path(relative_path))
        backtest = run_backtest(casefile=casefile, run_id=str(ULID()), git_sha=git_sha)
        persist_backtest(backtest=backtest, file_service=file_service)
        _RESULTS[relative_path] = backtest.result
    return _RESULTS[relative_path]


def _assert_dispatch_gates(result: dict) -> None:
    assert result["termination_condition"] == "optimal", (
        f"solver did not reach optimality: {result['termination_condition']} "
        f"after {result['solve_seconds']}s"
    )
    assert result["region"], f"region gate failed: {result['region_max_err']:.4f} MW"
    assert result["energy_price"], (
        f"energy price gate failed: {result['energy_price_max_err']:.4f} $/MWh"
    )
    assert result["trader"], f"trader gate failed: {result['trader_max_err']:.4f} MW"
    assert result["interconnect"], (
        f"interconnector gate failed: {result['interconnect_max_err']:.4f} MW"
    )


@pytest.mark.parametrize("relative_path", CASES_2021 + CASES_2025, ids=CASES_2021 + CASES_2025)
def test_backtest_dispatch_gates(file_service, git_sha, relative_path):
    _assert_dispatch_gates(_gates(file_service, git_sha, relative_path))


@pytest.mark.parametrize("relative_path", CASES_2021, ids=CASES_2021)
def test_backtest_objective_gate_2021(file_service, git_sha, relative_path):
    result = _gates(file_service, git_sha, relative_path)
    assert result["objective"], f"objective gate failed: {result['obj_rel_diff']:.2%}"


# The ~86% objective gap on 2025 casefiles is a known open investigation, not a
# regression. strict=True so that closing it is reported as an unexpected pass
# rather than silently absorbed.
@pytest.mark.xfail(strict=True, reason="known 2025 objective gap")
@pytest.mark.parametrize("relative_path", CASES_2025, ids=CASES_2025)
def test_backtest_objective_gate_2025(file_service, git_sha, relative_path):
    result = _gates(file_service, git_sha, relative_path)
    assert result["objective"], f"objective gate failed: {result['obj_rel_diff']:.2%}"
