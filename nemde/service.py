"""Transport-agnostic solve core. The HTTP API (api.py) is a thin shell over it."""

from nemde.casefile_io import CasefileInput, normalize_casefile
from nemde.run import run_model


def solve(casefile: CasefileInput) -> dict:
    """Normalize the casefile and run the model. Single entrypoint for all transports."""

    data = normalize_casefile(casefile)
    return run_model(casefile=data)
