"""Cost function expressions"""

import pyomo.environ as pyo


def trader_cost_function_rule(m, i, j):
    """Total cost associated with each offer"""

    # Scaling factor depending on participant type. Generator (+1), load (-1)
    if j == 'LDOF':
        factor = -1
    else:
        factor = 1

    return factor * sum(m.P_TRADER_PRICE_BAND[i, j, b] * m.V_TRADER_OFFER[i, j, b] for b in m.S_BANDS)


def mnsp_cost_function_rule(m, i, j):
    """MNSP cost function"""

    return sum(m.P_MNSP_PRICE_BAND[i, j, b] * m.V_MNSP_OFFER[i, j, b] for b in m.S_BANDS)


def define_cost_function_expressions(m):
    """Define expressions relating to trader and MNSP cost functions"""

    # Trader cost functions
    m.E_TRADER_COST_FUNCTION = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_cost_function_rule)

    # MNSP cost functions
    m.E_MNSP_COST_FUNCTION = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_cost_function_rule)

    return m
