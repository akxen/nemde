"""
Algorithms used to solve model
"""

import time

import pyomo.environ as pyo


def solve_model(model, algorithm=None):
    """Solve model"""

    # Setup solver
    options = {
        'sec': 60,  # time limit for each solve
    }

    opt = pyo.SolverFactory('cbc', solver_io='lp')

    # Solve model
    t0 = time.time()

    # First pass - MILP
    status_1 = opt.solve(model, tee=True, options=options, keepfiles=False)

    # Fix all integer variables
    for i in model.V_MNSP_FLOW_DIRECTION.keys():
        model.V_MNSP_FLOW_DIRECTION[i].fix()

    for i in model.V_LOSS_Y.keys():
        model.V_LOSS_Y[i].fix()

    # Resolve with integer variables fixed
    status_2 = opt.solve(model, tee=True, options=options, keepfiles=False)
    print('Finished MILP solve:', time.time() - t0)

    return model


def solve_model_dispatch(model, algorithm=None):
    """Solve model - only considers dispatch solution"""

    # Setup solver
    solver_options = {
        'sec': 60,  # time limit for each solve
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


def solve_model_fast_start(model, algorithm=None):
    """
    First solve model without fast start inflexibility constraints to check
    if units will come online. Change CurrentMode accordingly and resolve with
    fast-start unit constraints.
    Note: There is problem with CBC that makes it difficult to deactivate
    a constraint block (e.g. model.C_TRADER_INFLEXIBILITY_PROFILE) and then
    solve the model. Cannot implement this feature for now.
    """

    solver_options = {}
    opt = pyo.SolverFactory('cbc', solver_io='lp')

    # Deactivate inflexibility profiles constraints in first pass
    model.C_TRADER_INFLEXIBILITY_PROFILE.deactivate()
    first_pass = opt.solve(model, tee=True, options=solver_options, keepfiles=False)

    # Check if dispatch > 0 for any fast start units
    starting = [i for i, j in model.S_TRADER_ENERGY_OFFERS
                if (i in model.S_TRADER_FAST_START)
                and (model.V_TRADER_TOTAL_OFFER[i, j].value > 0.1)
                and (model.P_TRADER_CURRENT_MODE[i].value == '0')]

    # Set CurrentMode=1 and CurrentModeTime=0 for generators starting up
    for i in starting:
        model.P_TRADER_CURRENT_MODE[i] = '1'
        model.P_TRADER_CURRENT_MODE_TIME[i] = 0.0

    # Re-activate fast start constraints and re-solve
    model.C_TRADER_INFLEXIBILITY_PROFILE.reconstruct()
    model.C_TRADER_INFLEXIBILITY_PROFILE.activate()
    second_pass = opt.solve(model, tee=True, options=solver_options, keepfiles=False)

    return model
