"""Command-line entry points: `nemde-backtest` (model vs NEMDE) and
`nemde-solve` (solve and inspect, no comparison). A thin wrapper over
nemde.backtest and nemde.solution_report — argument parsing and terminal
output only, no comparison or reporting logic.
"""

import glob
import logging
import sys

import click
from ulid import ULID

from nemde.backtest import persist_backtest, run_backtest
from nemde.file_service import LocalFileService
from nemde.model_options import SolveOptions
from nemde.report import resolve_git_sha
from nemde.run import run_model
from nemde.solution_report import (
    build_solution_report,
    persist_solution,
    solution_context,
    solution_frames,
)


@click.command()
@click.argument("pattern")
@click.option(
    "--max",
    "max_casefiles",
    default=10,
    show_default=True,
    help="Maximum number of casefiles to run.",
)
@click.option(
    "--tolerance",
    default=0.1,
    show_default=True,
    help="Max allowed absolute error for MW quantities.",
)
@click.option(
    "--obj-tolerance",
    default=0.05,
    show_default=True,
    help="Max allowed relative error for objective function value.",
)
@click.option(
    "--energy-price-tolerance",
    default=1.0,
    show_default=True,
    help="Max allowed absolute error for energy price ($/MWh).",
)
@click.option(
    "--output-dir", default="data", show_default=True, help="Root directory for artefacts."
)
@click.option(
    "--pin-trader-targets",
    is_flag=True,
    help="Pin trader energy targets to NEMDE's published values, then report which "
    "constraints are violated -- the primary diagnostic for localising a misformulation.",
)
@click.option(
    "--pin-fcas-targets",
    is_flag=True,
    help="Pin FCAS targets to NEMDE's published values. Combine with --pin-trader-targets "
    "to pin everything, then unpin progressively to isolate a constraint.",
)
@click.option(
    "--disable-constraint",
    "disable_constraints",
    multiple=True,
    metavar="NAME",
    help="Deactivate a constraint block by name, e.g. C_FCAS_JOINT_RAMPING_RAISE_"
    "BIDIRECTIONAL_GEN. Repeatable. Unknown names are an error, not a no-op.",
)
@click.option(
    "--no-tie-breaking", is_flag=True, help="Drop the price-tied energy tie-breaking constraints."
)
@click.option(
    "--solver-time-limit",
    default=SolveOptions.solver_time_limit,
    show_default=True,
    help="CBC time limit in seconds, per solve pass.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Log model construction and solve timings, and stream CBC's solver log.",
)
def main(
    pattern: str,
    max_casefiles: int,
    tolerance: float,
    obj_tolerance: float,
    energy_price_tolerance: float,
    output_dir: str,
    pin_trader_targets: bool,
    pin_fcas_targets: bool,
    disable_constraints: tuple[str, ...],
    no_tie_breaking: bool,
    solver_time_limit: int,
    verbose: bool,
):
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING, format="%(name)s: %(message)s"
    )

    options = SolveOptions(
        pin_trader_targets=pin_trader_targets,
        pin_fcas_targets=pin_fcas_targets,
        disable_constraints=disable_constraints,
        tie_breaking=not no_tie_breaking,
        solver_time_limit=solver_time_limit,
        solver_log=verbose,
    )

    git_sha = resolve_git_sha()
    file_service = LocalFileService(params={"output_dir": output_dir})

    relative_paths = sorted(p.replace(f"{output_dir}/", "") for p in glob.glob(pattern))[
        :max_casefiles
    ]

    if not relative_paths:
        click.echo(f"No casefiles matched: {pattern}", err=True)
        sys.exit(1)

    click.echo(
        f"\nRunning {len(relative_paths)} casefile(s)  git={git_sha[:7] or 'unknown'}  "
        f"tolerance={tolerance}  obj_tolerance={obj_tolerance:.0%}  "
        f"energy_price_tolerance={energy_price_tolerance}\n"
    )

    def sym(ok: bool) -> str:
        return click.style("✓", fg="green") if ok else click.style("✗", fg="red")

    results = []
    for relative_path in relative_paths:
        run_id = str(ULID())
        data = file_service.load_artefact(relative_path=relative_path)
        backtest = run_backtest(
            casefile=data,
            run_id=run_id,
            git_sha=git_sha,
            tolerance=tolerance,
            obj_rel_tolerance=obj_tolerance,
            energy_price_tolerance=energy_price_tolerance,
            options=options,
        )
        persist_backtest(backtest=backtest, file_service=file_service)
        result = backtest.result
        results.append(result)

        verdict = (
            click.style("PASS", fg="green") if result["passed"] else click.style("FAIL", fg="red")
        )
        click.echo(f"\n{result['casefile_id']}")
        click.echo(f"  Run ID:       {run_id}")
        click.echo(f"  Region:       {sym(result['region'])} {result['region_max_err']:.4f} MW")
        click.echo(
            f"  Energy Price: {sym(result['energy_price'])} "
            f"{result['energy_price_max_err']:.4f} $/MWh"
        )
        click.echo(f"  Trader:       {sym(result['trader'])} {result['trader_max_err']:.4f} MW")
        click.echo(
            f"  Interconnect: {sym(result['interconnect'])} {result['interconnect_max_err']:.4f} MW"
        )
        click.echo(f"  Objective:    {sym(result['objective'])} {result['obj_rel_diff']:.2%}")
        click.echo(f"  Result:       {verdict}")

    n_passed = sum(r["passed"] for r in results)
    click.echo(f"\nOverall: {n_passed}/{len(results)} passed\n")
    sys.exit(0 if n_passed == len(results) else 1)


@click.command()
@click.argument("pattern")
@click.option(
    "--max",
    "max_casefiles",
    default=10,
    show_default=True,
    help="Maximum number of casefiles to run.",
)
@click.option(
    "--output-dir", default="data", show_default=True, help="Root directory for artefacts."
)
@click.option(
    "--disable-constraint",
    "disable_constraints",
    multiple=True,
    metavar="NAME",
    help="Deactivate a constraint block by name. Repeatable. Unknown names are an error.",
)
@click.option(
    "--no-tie-breaking", is_flag=True, help="Drop the price-tied energy tie-breaking constraints."
)
@click.option(
    "--solver-time-limit",
    default=SolveOptions.solver_time_limit,
    show_default=True,
    help="CBC time limit in seconds, per solve pass.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Log model construction and solve timings, and stream CBC's solver log.",
)
def solve_command(
    pattern: str,
    max_casefiles: int,
    output_dir: str,
    disable_constraints: tuple[str, ...],
    no_tie_breaking: bool,
    solver_time_limit: int,
    verbose: bool,
):
    """Solve casefiles and write the solution plus an HTML view of it.

    The backtest command's counterpart for an edited casefile: it never reads
    NemSpdOutputs' published solution, so nothing here depends on the casefile
    still describing the dispatch interval NEMDE actually ran.
    """

    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING, format="%(name)s: %(message)s"
    )

    options = SolveOptions(
        disable_constraints=disable_constraints,
        tie_breaking=not no_tie_breaking,
        solver_time_limit=solver_time_limit,
        solver_log=verbose,
    )

    git_sha = resolve_git_sha()
    file_service = LocalFileService(params={"output_dir": output_dir})

    relative_paths = sorted(p.replace(f"{output_dir}/", "") for p in glob.glob(pattern))[
        :max_casefiles
    ]

    if not relative_paths:
        click.echo(f"No casefiles matched: {pattern}", err=True)
        sys.exit(1)

    click.echo(f"\nSolving {len(relative_paths)} casefile(s)  git={git_sha[:7] or 'unknown'}\n")

    for relative_path in relative_paths:
        run_id = str(ULID())
        casefile = file_service.load_artefact(relative_path=relative_path)

        solution = run_model(casefile=casefile, options=options)
        context = solution_context(casefile)
        html_report = build_solution_report(
            solution=solution, context=context, run_id=run_id, git_sha=git_sha
        )
        run_dir = persist_solution(
            solution=solution,
            html_report=html_report,
            casefile_id=context["case_id"],
            run_id=run_id,
            file_service=file_service,
            frames=solution_frames(solution, context),
        )

        period = solution["PeriodSolution"]
        click.echo(f"\n{context['case_id']}  {context['period_id']}")
        click.echo(f"  Run ID:       {run_id}")
        click.echo(f"  Termination:  {solution['SolverInfo']['termination_condition']}")
        click.echo(f"  Objective:    {period['@TotalObjective']:,.2f}")
        click.echo(
            "  Prices:       "
            + "  ".join(
                f"{r['@RegionID']}={r['@EnergyPrice']:,.2f}"
                for r in sorted(solution["RegionSolution"], key=lambda i: i["@RegionID"])
            )
        )
        click.echo(f"  Report:       {output_dir}/output/{run_dir}/solution_report.html")

    click.echo("")


if __name__ == "__main__":
    main()
