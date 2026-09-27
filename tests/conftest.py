"""Shared fixtures and casefile sampling for the backtest-based test suite.

Both test_backtest_regression.py (model vs NEMDE) and test_refactor_snapshot.py
(model vs its own prior output) run the same sample of real casefiles, so the
sample selection and common fixtures live here to avoid the two drifting apart.
"""

import glob
from pathlib import Path

import git
import pytest

from nemde.casefile_io import normalize_casefile
from nemde.file_service import LocalFileService

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_DIR = DATA_DIR / "input"

N_SAMPLE = 15
N_INTERVALS = 288
N_QUICK = 2

requires_input_data = pytest.mark.skipif(
    not INPUT_DIR.is_dir(),
    reason="data/input not present locally (gitignored casefile data)",
)

# Every interval in a full month, for the exhaustive (non-LP) field-derivation
# checks in test_effective_ramp_rates.py and test_fcas_availability.py.
NOVEMBER_2025_CASEFILES = sorted(
    glob.glob(str(INPUT_DIR / "NemSpdOutputs_202511*_loaded" / "*.loaded"))
)


def load_casefile(file_path: str) -> dict:
    """Parse a raw `.loaded` XML casefile directly. Equivalent to
    LocalFileService.load_artefact, but takes an absolute path rather than one
    relative to a configured output_dir -- convenient for glob-based fixtures.
    """
    with open(file_path) as f:
        data = f.read()
    return normalize_casefile(data)


def _sample_intervals(n_sample: int = N_SAMPLE, n_total: int = N_INTERVALS) -> list[int]:
    """15 interval numbers (1-indexed) evenly spaced across the trading day."""
    return sorted({round(1 + k * (n_total - 1) / (n_sample - 1)) for k in range(n_sample)})


def _casefile_relpath(dir_name: str, date_str: str, interval: int) -> str:
    return f"input/{dir_name}/NEMSPDOutputs_{date_str}{interval:03d}00.loaded"


CASES_2021 = [
    _casefile_relpath("NemSpdOutputs_20210101_loaded", "20210101", i) for i in _sample_intervals()
]
CASES_2025 = [
    _casefile_relpath("NemSpdOutputs_20251130_loaded", "20251130", i) for i in _sample_intervals()
]


def _quick_subset(cases: list[str], n: int = N_QUICK) -> list[str]:
    """`n` casefiles spread across the day's sample, avoiding the endpoints."""
    positions = sorted({round((k + 1) * len(cases) / (n + 1)) - 1 for k in range(n)})
    return [cases[i] for i in positions]


# --quick smoke sample: a couple of casefiles from each year rather than all 30.
QUICK_CASES = frozenset(_quick_subset(CASES_2021) + _quick_subset(CASES_2025))


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Record current model output as the new refactor-snapshot baseline "
        "instead of comparing against the existing one.",
    )
    parser.addoption(
        "--quick",
        action="store_true",
        default=False,
        help=f"Smoke-test sample: solve only {N_QUICK} casefiles per year instead of "
        f"all {N_SAMPLE}. Applies to both the regression and refactor-snapshot suites.",
    )
    parser.addoption(
        "--run-regression",
        action="store_true",
        default=False,
        help="Run the NEMDE-comparison regression tests (minutes; needs data/input "
        "and a solver). Deselected by default.",
    )


def pytest_configure(config):
    if config.getoption("--quick") and config.getoption("--snapshot-update"):
        # A partial re-record leaves the other 26 baselines on the old model,
        # which is worse than not re-recording at all.
        raise pytest.UsageError("--snapshot-update records the full sample; drop --quick")
    config.addinivalue_line(
        "markers", "regression: model-vs-NEMDE gates; opt in with --run-regression"
    )


def _deselect_non_quick(config, items):
    """Drop casefile-parametrized tests outside QUICK_CASES.

    Both slow suites parametrize on `relative_path` at import time, so the
    sample cannot be narrowed by a fixture -- it is narrowed at collection.
    """
    selected, deselected = [], []
    for item in items:
        path = getattr(item, "callspec", None) and item.callspec.params.get("relative_path")
        (deselected if path and path not in QUICK_CASES else selected).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


def pytest_collection_modifyitems(config, items):
    if config.getoption("--quick"):
        _deselect_non_quick(config, items)
    if config.getoption("--run-regression"):
        return
    skip = pytest.mark.skip(reason="needs --run-regression (slow: solves real casefiles)")
    for item in items:
        if "regression" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def file_service() -> LocalFileService:
    return LocalFileService(params={"output_dir": str(DATA_DIR)})


@pytest.fixture(scope="session")
def git_sha() -> str:
    try:
        return git.Repo(search_parent_directories=True).head.object.hexsha
    except Exception:
        return "unknown"
