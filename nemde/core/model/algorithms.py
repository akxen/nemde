"""
Algorithms used to solve model
"""

import time

import pyomo.environ as pyo


def solve_model(model, intervention=None, algorithm=None):
    """Solve model"""

    # Setup solver
    solver_options = {
    }

    opt = pyo.SolverFactory('cbc', solver_io='lp')

    # Solve model
    t0 = time.time()

    print('Starting MILP solve:', time.time() - t0)
    solve_status_1 = opt.solve(
        model, tee=True, options=solver_options, keepfiles=False)
    print('Finished MILP solve:', time.time() - t0)
    print('Objective value - 1:', model.OBJECTIVE.expr())

    return model
