"""
Algorithms used to solve model
"""

import time

import pyomo.environ as pyo


def default_algorithm(model):
    """
    First solve model without fast start inflexibility constraints to check
    if units will come online. Change CurrentMode accordingly and resolve with
    fast-start unit constraints.

    Note: There is sometimes a problem with CBC that makes it difficult to
    deactivate a constraint block (e.g. model.C_TRADER_INFLEXIBILITY_PROFILE)
    and then solve the model. Running inside Docker container seems to fix
    this issue for now.
    """

    options = {
        'sec': 300
    }
    opt = pyo.SolverFactory('cbc', solver_io='lp')

    # Solve model with 'swammped' inflexibility profile constraints
    model.C_TRADER_INFLEXIBILITY_PROFILE.deactivate()
    solver_info_1 = opt.solve(model, tee=True, options=options, keepfiles=False)

    # Check if dispatch > 0 for any fast start units
    starting = [i for i, j in model.S_TRADER_ENERGY_OFFERS
                if (i in model.S_TRADER_FAST_START)
                and (model.V_TRADER_TOTAL_OFFER[i, j].value > 0.005)
                and (model.P_TRADER_CURRENT_MODE[i].value == 0)]

    # TODO: check if model can be returned when 'starting' is an empty list

    # Set CurrentMode=1 and CurrentModeTime=0 for generators starting up
    for i in starting:
        model.P_TRADER_CURRENT_MODE[i] = 1
        model.P_TRADER_CURRENT_MODE_TIME[i] = 0

    model.C_TRADER_RAMP_UP_RATE.reconstruct()
    model.C_TRADER_RAMP_DOWN_RATE.reconstruct()
    model.C_TRADER_INFLEXIBILITY_PROFILE.reconstruct()
    model.C_TRADER_INFLEXIBILITY_PROFILE.activate()
    solver_info_2 = opt.solve(model, tee=True, options=options, keepfiles=False)

    return model, solver_info_2


def dispatch_only_algorithm(model):
    """Solve model - only considers dispatch solution"""

    # Setup solver
    options = {
        'sec': 300,  # time limit for each solve
        'loglevel': 3
    }

    opt = pyo.SolverFactory('cbc', solver_io='lp')

    # Solve model
    t0 = time.time()

    print('Starting MILP solve:', time.time() - t0)
    solver_info = opt.solve(model, tee=True, options=options, keepfiles=False)
    print('Finished MILP solve:', time.time() - t0)
    print('Objective value - 1:', model.OBJECTIVE.expr())

    return model, solver_info


def solve_model(model, algorithm=None):
    """Solve model using specified algorithm"""

    if algorithm == 'default':
        return default_algorithm(model)
    elif algorithm == 'dispatch_only':
        return dispatch_only_algorithm(model)
    else:
        raise ValueError(f"Algorithm '{algorithm}' not recognised")
