"""Unit offer constraints"""

import pyomo.environ as pyo


def trader_ramp_up_rate_rule(m, i, j):
    """Ramp up rate limit for ENOF and LDOF offers"""

    # Only construct ramp-rate constraint for energy offers
    if (j != 'ENOF') and (j != 'LDOF'):
        return pyo.Constraint.Skip

    # Ramp rate
    ramp_limit = m.P_TRADER_PERIOD_RAMP_UP_RATE[(i, j)]

    # Initial MW
    initial_mw = m.P_TRADER_INITIAL_MW[i]

    return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw <= (ramp_limit / 12) + m.V_CV_TRADER_RAMP_UP[i]


def trader_ramp_down_rate_rule(m, i, j):
    """Ramp down rate limit for ENOF and LDOF offers"""

    # Only construct ramp-rate constraint for energy offers
    if (j != 'ENOF') and (j != 'LDOF'):
        return pyo.Constraint.Skip

    # Ramp rate
    ramp_limit = m.P_TRADER_PERIOD_RAMP_DOWN_RATE[(i, j)]

    # Initial MW
    initial_mw = m.P_TRADER_INITIAL_MW[i]

    return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw + m.V_CV_TRADER_RAMP_DOWN[i] >= - (ramp_limit / 12)


def define_unit_constraints(m):
    """Construct ramp rate constraints for units"""

    # Ramp up rate limit
    m.C_TRADER_RAMP_UP_RATE = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_up_rate_rule)

    # Ramp up rate limit
    m.C_TRADER_RAMP_DOWN_RATE = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_down_rate_rule)

    return m
