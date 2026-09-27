"""Runtime switches for construct_model()/run_model(), so debugging workflows like
pinning targets to NEMDE's published values or disabling a suspect constraint
block are flags rather than source edits.

Previously "pin the targets and look for violations" and "selectively comment out
constraints" both meant editing model.py, running, and remembering to revert --
a stateful loop that dirties the tree the snapshot tests compare against, and one
an agent cannot drive unattended.

Defaults reproduce the model exactly as it runs in production: every field's
default is the previously hard-coded behaviour, so `SolveOptions()` is a no-op
on the solution. `solver_log` is the one exception -- it defaults off where the
old code always streamed CBC's log -- because it affects only what is printed.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SolveOptions:
    # Pin E_TRADER_TARGET for energy offers to NEMDE's published @EnergyTarget.
    # The primary diagnostic for a misformulation: pin, solve, and read off which
    # constraints are violated to localise it.
    pin_trader_targets: bool = False

    # Same, for the ten FCAS trade types. Pinning energy alone is the usual
    # first step; unpin progressively from both to isolate a constraint.
    pin_fcas_targets: bool = False

    # Names of constraint blocks to deactivate after construction, e.g.
    # ("C_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_GEN",). A name that matches no
    # block on the model raises, rather than silently disabling nothing.
    disable_constraints: tuple[str, ...] = field(default_factory=tuple)

    # Tie-breaking between price-tied energy offers. Off makes degenerate
    # solutions non-reproducible but removes the tie-break cost from the
    # objective, which is occasionally useful when auditing objective terms.
    tie_breaking: bool = True

    # CBC time limit in seconds, per solve pass. A hit limit is now an error
    # (see run.SolveFailure), not a silently stale solution.
    solver_time_limit: int = 300

    # Stream CBC's own log to stdout. Off by default: every solve emits a few
    # hundred lines, which buries the API container's request log. The CLI's
    # --verbose turns it back on, and solve times are in SolverInfo regardless.
    solver_log: bool = False


def apply_constraint_overrides(m, options: SolveOptions) -> None:
    """Deactivate the constraint blocks named in options.disable_constraints."""

    for name in options.disable_constraints:
        component = m.component(name)
        if component is None:
            raise ValueError(
                f"Cannot disable unknown constraint block {name!r}. "
                "Names are the C_* attributes on the Pyomo model."
            )
        component.deactivate()
