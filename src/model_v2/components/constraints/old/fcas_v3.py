"""Construct FCAS constraints based on description in FCAS model docs"""

import pyomo.environ as pyo


def fcas_common_unavailability_rule(m, i):
    """Unavailable FCAS targets fixed to 0"""

    return m.V_TRADER_TOTAL_OFFER[i] == 0


def fcas_common_max_available_rule(m, i, j):
    """Max available for given service"""

    # TODO: Considering UIGF for semi-scheduled units. Not sure if this is necessary (think it is).
    if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '1':
        max_available = min(m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)], m.P_TRADER_UIGF[i])
    else:
        max_available = m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]

    return m.V_TRADER_TOTAL_OFFER[(i, j)] <= max_available


def define_common_fcas_constraints(m):
    """Define FCAS constraints common to all offer types"""

    # Fix all unavailable FCAS targets to 0
    m = pyo.Constraint(m.S_TRADER_FCAS_UNAVAILABLE_OFFERS, rule=fcas_common_unavailability_rule)

    # Max available constraint
    # m = pyo.Constraint(m.S_TRADER_FCAS_OFFERS, rule=fcas_common_max_available_rule)

    return m


def fcas_raise_reg_trapezium_1_rule(m, i, j):
    """Scale FCAS trapezium max available"""

    # TODO: Considering UIGF for semi-scheduled units. Not sure if this is necessary (think it is).
    if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '1':
        max_available = min(m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)], m.P_TRADER_UIGF[i])
    else:
        max_available = m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]

    # Effective max available
    effective_max_available = min(max_available, m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)

    return m.V_TRADER_TOTAL_OFFER[(i, 'R5RE')] <= effective_max_available


def fcas_raise_reg_trapezium_2_rule(m, i, j):
    """Scale FCAS trapezium RHS"""

    # Effective enablement max
    enablement_max = min(m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)], m.P_TRADER_FCAS_HMW[i])

    # Energy offer
    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        energy_offer = 'ENOF'
    elif m.P_TRADER_TYPE in ['LOAD', 'NORMALLY_ON_LOAD']:
        energy_offer = 'LDOF'
    else:
        raise Exception('Unhandled case')

    # Upper slope coefficient
    upper_slope_coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)])
                               / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])

    return (m.V_TRADER_TOTAL_OFFER[(i, 'R5RE')]
            <= (enablement_max - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]) / upper_slope_coefficient)


def fcas_raise_reg_trapezium_3_rule(m, i, j):
    """Scale FCAS trapezium LHS"""

    # Effective enablement min
    effective_enablement_min = min(m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)], m.P_TRADER_FCAS_LMW[i])

    return m.V_TRADER_TOTAL_OFFER[(i, 'R5RE')] <= effective_enablement_min


def define_raise_regulation_constraints(m):
    """Raise regulation constraints"""

    # Effective max available
    m = pyo.Constraint(m.S_TRADER)


def define_fcas_constraints(m):
    """Define FCAS constraints"""

    # Constraints common to all offer types
    m = define_common_fcas_constraints(m)

    # Raise regulation constraints
    m = define_raise_regulation_constraints(m)

    return m
