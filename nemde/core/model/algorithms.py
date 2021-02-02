"""
Algorithms used to solve model
"""

import time

import pyomo.environ as pyo


def solve_model(model, algorithm=None):
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


def solve_model_fast_start(model, algorithm=None):
    """
    First solve model without fast start inflexibility constraints to check
    if units will come online. Change CurrentMode accordingly and resolve with
    fast-start unit constraints
    """

    solver_options = {}
    opt = pyo.SolverFactory('cbc', solver_io='os')

    # Disable fast-start unit profile constraints and solve model
    print([i for i in model.C_TRADER_INFLEXIBILITY_PROFILE.keys()])
    keys = ['AGLHAL', 'AGLSOM', 'BARCALDN', 'BARRON-2', 'BBTHREE1', 'BBTHREE2',
            'BBTHREE3', 'BDL01', 'BDL02', 'BRAEMAR1', 'BRAEMAR2', 'BRAEMAR3',
            'BRAEMAR5', 'BRAEMAR6', 'CG1', 'CG2', 'CG3', 'CG4', 'DRYCGT1',
            'DRYCGT2', 'DRYCGT3', 'JLA01', 'JLA02', 'JLA03', 'JLA04', 'JLB01',
            'JLB02', 'JLB03', 'KAREEYA3', 'LADBROK1', 'LADBROK2', 'LNGS1', 'LNGS2',
            'MACKAYGT', 'MINTARO', 'MORTLK11', 'MORTLK12', 'MSTUART1', 'MSTUART2',
            'MSTUART3', 'POR01', 'POR03', 'PUMP1', 'PUMP2', 'QPS1', 'QPS2', 'QPS3',
            'QPS4', 'QPS5', 'ROMA_7', 'ROMA_8', 'SHGEN', 'SHPUMP', 'SNUG1', 'TVPP104',
            'URANQ11', 'URANQ12', 'URANQ13', 'URANQ14', 'VPGS1', 'VPGS2', 'VPGS3',
            'VPGS4', 'VPGS5', 'VPGS6', 'W/HOE#1', 'W/HOE#2', 'YABULU']
    print(len(keys))

    for i in keys[1:68]:
        print('deactivating', i, model.C_TRADER_INFLEXIBILITY_PROFILE[i].expr)
        model.C_TRADER_INFLEXIBILITY_PROFILE[i].deactivate()

    model.C_TRADER_INFLEXIBILITY_PROFILE[keys[0]].deactivate()
    first_pass = opt.solve(model, tee=True, options=solver_options,
                           keepfiles=True, logfile='/tmp/cbc_test.log')

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
