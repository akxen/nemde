"""Library module: fast-start two-pass solve orchestration, called by service.py."""

import time

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition

from nemde.inputs import construct_case
from nemde.model import construct_model
from nemde.model_options import SolveOptions
from nemde.solution import get_objective_breakdown, get_solution


class SolveFailure(RuntimeError):
    """The solver did not return an optimal solution.

    Raised rather than returning stale variable values, which would otherwise be
    reported downstream as a disagreement with NEMDE rather than as a failure to
    solve -- an expensive confusion during an accuracy investigation.
    """


def make_solver(time_limit: int = SolveOptions.solver_time_limit):
    """Build the CBC solver used by both passes."""

    opt = pyo.SolverFactory("cbc", solver_io="lp")

    # This build of CBC has no ASL interface, so pyomo's CBC plugin reports
    # sos2=False (that flag only reflects whether CBC's *ASL/.nl* mode can
    # read SOS sets) and its LP writer refuses to emit the loss model's
    # native SOS2 constraint. CBC's own LP-format reader (-import) does
    # support an LP-format SOS section independent of ASL, so override the
    # advertised capability rather than switch solver_io.
    opt._capabilities.sos2 = True

    options = {
        "sec": time_limit,
        "loglevel": 2,
        "ratio": 0.0001,
        "integerT": 1e-5,
        "primalT": 1e-6,
        "dualT": 1e-6,
    }
    return opt, options


def solve_pass(model, opt, options, label: str, tee: bool = False) -> dict:
    """Solve `model` in place and return {termination_condition, solver_status,
    solve_seconds} for it.

    Raises SolveFailure unless the solve terminated optimally. An infeasible,
    unbounded or time-limited solve leaves Pyomo holding whatever variable
    values it last had; extracting those and comparing them against NEMDE
    produces a plausible-looking but meaningless discrepancy.
    """

    t0 = time.time()
    results = opt.solve(model, tee=tee, options=options, keepfiles=False)
    elapsed = time.time() - t0

    condition = results.solver.termination_condition
    status = results.solver.status
    info = {
        "termination_condition": str(condition),
        "solver_status": str(status),
        "solve_seconds": round(elapsed, 3),
    }

    if condition != TerminationCondition.optimal or status != SolverStatus.ok:
        raise SolveFailure(
            f"{label} pass did not solve to optimality: "
            f"termination_condition={condition}, status={status}, "
            f"elapsed={elapsed:.1f}s (limit {options['sec']}s)"
        )

    return info


def solve_without_inflexibility_profile(model, options: SolveOptions) -> tuple[list, dict]:
    """First pass: solve with the fast-start inflexibility-profile constraints
    deactivated, purely to discover which fast-start units come online. Those
    units' CurrentMode is then updated for the second pass.

    Note: There is sometimes a problem with CBC that makes it difficult to
    deactivate a constraint block (e.g. model.C_TRADER_INFLEXIBILITY_PROFILE)
    and then solve the model. Running inside Docker container seems to fix
    this issue for now.

    Returns (fast_start_units_coming_online, solver_info).
    """

    opt, solver_options = make_solver(options.solver_time_limit)

    model.C_TRADER_INFLEXIBILITY_PROFILE.deactivate()
    info = solve_pass(
        model,
        opt,
        solver_options,
        label="first (no inflexibility profile)",
        tee=options.solver_log,
    )

    starting = [
        i
        for i, j, k in model.S_TRADER_ENERGY_OFFERS
        if (i in model.S_TRADER_FAST_START)
        and (model.E_TRADER_TARGET[i, j].expr() > model.P_FAST_START_THRESHOLD.value)
        and (model.P_TRADER_CURRENT_MODE[i].value == 0)
    ]
    return starting, info


def solve_with_inflexibility_profile(model, starting, options: SolveOptions) -> dict:
    """Second pass: mark the units found by the first pass as starting, then
    solve with the inflexibility-profile constraints active. Returns solver_info.
    """

    opt, solver_options = make_solver(options.solver_time_limit)

    for i in starting:
        model.P_TRADER_CURRENT_MODE[i] = 1
        model.P_TRADER_CURRENT_MODE_TIME[i] = 0

    return solve_pass(
        model,
        opt,
        solver_options,
        label="second (with inflexibility profile)",
        tee=options.solver_log,
    )


def run_model(casefile, options: SolveOptions | None = None):
    """Construct and solve the model for one casefile.

    Parameters
    ----------
    casefile : dict
        xmltodict-shaped NEMDE casefile, as produced by casefile_io.normalize_casefile.
    options : SolveOptions, optional
        Debugging/solver switches -- target pinning, constraint disabling, time
        limit. See nemde/model_options.py.

    Returns
    -------
    dict
        NEMDE-shaped solution, plus a "SolverInfo" key carrying each pass's
        termination condition and wall-time.
    """

    options = options or SolveOptions()

    # Construct serialized casefile and model object
    serialized_case = construct_case(data=casefile, mode="pricing")

    # Two full construct+solve passes are required, not one reused model: the
    # first solve (with inflexibility constraints deactivated) only determines
    # which fast-start units come online, which then changes CurrentMode/
    # CurrentModeTime inputs and reactivates a different constraint block for
    # the second solve. Rebuilding from serialized_case is simpler and more
    # robust than mutating model_1's active constraint set in place (see the
    # CBC deactivate/resolve caveat noted in the docstrings below).
    model_1 = construct_model(data=serialized_case, options=options)
    units_starting, info_1 = solve_without_inflexibility_profile(model=model_1, options=options)

    model_2 = construct_model(data=serialized_case, options=options)
    info_2 = solve_with_inflexibility_profile(
        model=model_2, starting=units_starting, options=options
    )

    solution = get_solution(model=model_2)
    solution["ObjectiveBreakdown"] = get_objective_breakdown(model_2)
    solution["SolverInfo"] = {
        "first_pass": info_1,
        "second_pass": info_2,
        "fast_start_units_starting": sorted(units_starting),
        "solve_seconds": round(info_1["solve_seconds"] + info_2["solve_seconds"], 3),
        "termination_condition": info_2["termination_condition"],
    }

    return solution
