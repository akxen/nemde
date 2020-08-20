"""Use a functions to construct FCAS expressions"""

import pyomo.environ as pyo


def get_effective_rreg_fcas_max_avail(m, i):
    """Get effective R5RE max available"""

    # Max available
    max_avail = m.P_TRADER_FCAS_MAX_AVAILABLE[(i, 'R5RE')]

    # Divide by 12 to get ramp rate of 5min dispatch interval
    agc_ramp_rate = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12


    return min(max_avail, agc_ramp_rate)


def get_effective_rreg_enablement_max(m, i):
    """Get effective R5RE enablement max"""

    return min(m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, 'R5RE')], m.P_TRADER_HMW[i])


def get_effective_rreg_enablement_min(m, i):
    """Get effective R5RE enablement min"""

    return max(m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, 'R5RE')], m.P_TRADER_LMW[i])


def get_effective_lreg_fcas_max_avail(m, i):
    """Get effective L5RE max available"""

    # Max available
    max_avail = m.P_TRADER_FCAS_MAX_AVAILABLE[(i, 'L5RE')]

    # Divide by 12 to get ramp rate of 5min dispatch interval # TODO: docs say ramp up, but I think should be ramp down
    agc_ramp_rate = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12

    return min(max_avail, agc_ramp_rate)


def get_effective_lreg_enablement_max(m, i):
    """Get effective L5RE enablement max"""

    return min(m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, 'L5RE')], m.P_TRADER_HMW[i])


def get_effective_lreg_enablement_min(m, i):
    """Get effective L5RE enablement min"""

    return max(m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, 'L5RE')], m.P_TRADER_LMW[i])


def get_joint_ramp_raise_max(m, i):
    """Get joint ramp raise max"""

    return m.P_TRADER_INITIAL_MW[i] + (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)


def get_joint_ramp_lower_min(m, i):
    """Get joint ramp lower_min"""

    return m.P_TRADER_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)


def get_slope_lower_coefficient(m, i, j):
    """Get lower slope coefficient"""

    try:
        return ((m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, j)] - m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
                / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])
    except ZeroDivisionError:
        return None


def get_slope_upper_coefficient(m, i, j):
    """Get upper slope coefficient"""

    try:
        return ((m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)])
                / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])
    except ZeroDivisionError:
        return None


def get_energy_offer_type(m, i):
    """Get energy offer type which depends on trader being a generator / load"""

    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        return 'ENOF'
    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        return 'LDOF'
    else:
        raise Exception('Unhandled case')


def fcas_availability_rule(m, i, j):
    """Fix unavailable FCAS to zero"""

    # Check if service is unavailable - fix to zero if True
    if (i, j) in m.S_TRADER_FCAS_UNAVAILABLE_OFFERS:
        return m.V_TRADER_TOTAL_OFFER[(i, j)] == 0
    else:
        return pyo.Constraint.Skip


def regulating_raise_constraint_1_rule(m, i, j):
    """Regulating raise is less than effective max available"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        # Effective max available - may be negative so set to 0 if required
        effective_max_available = max(0, get_effective_rreg_fcas_max_avail(m, i))
        return m.V_TRADER_TOTAL_OFFER[i, j] <= effective_max_available

    except ValueError:
        return pyo.Constraint.Skip


def regulating_raise_constraint_2_rule(m, i, j):
    """RHS FCAS trapezium slope"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    upper_slope_coefficient = get_slope_upper_coefficient(m, i, j)
    if (upper_slope_coefficient is None) or (upper_slope_coefficient == 0):
        return pyo.Constraint.Skip

    try:
        effective_enablement_max = get_effective_rreg_enablement_max(m, i)
    except ValueError:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j]
            <= (effective_enablement_max - m.V_TRADER_TOTAL_OFFER[i, energy_offer]) / upper_slope_coefficient)


def regulating_raise_constraint_3_rule(m, i, j):
    """LHS FCAS trapezium slope"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    lower_slope_coefficient = get_slope_lower_coefficient(m, i, j)
    if (lower_slope_coefficient is None) or (lower_slope_coefficient == 0):
        return pyo.Constraint.Skip

    try:
        effective_enablement_min = get_effective_rreg_enablement_min(m, i)
    except ValueError:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j]
            <= (m.V_TRADER_TOTAL_OFFER[i, energy_offer] - effective_enablement_min) / lower_slope_coefficient)


def regulating_raise_constraint_4_rule(m, i, j):
    """R6SE joint capacity constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for contingency service
    if (i, 'R6SE') not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        upper_slope_coefficient = get_slope_upper_coefficient(m, i, 'R6SE')
    except KeyError:
        return pyo.Constraint.Skip

    if upper_slope_coefficient is None:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, 'R6SE']
            - m.V_TRADER_TOTAL_OFFER[i, energy_offer]
            - (upper_slope_coefficient * m.V_TRADER_TOTAL_OFFER[i, 'R6SE'])
            + 0.001)


def regulating_raise_constraint_5_rule(m, i, j):
    """R60S joint capacity constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for contingency service
    if (i, 'R60S') not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        upper_slope_coefficient = get_slope_upper_coefficient(m, i, 'R60S')
    except KeyError:
        return pyo.Constraint.Skip

    if upper_slope_coefficient is None:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, 'R60S']
            - m.V_TRADER_TOTAL_OFFER[i, energy_offer]
            - (upper_slope_coefficient * m.V_TRADER_TOTAL_OFFER[i, 'R60S'])
            + 0.001)


def regulating_raise_constraint_6_rule(m, i, j):
    """R5MI joint capacity constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for contingency service
    if (i, 'R5MI') not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        upper_slope_coefficient = get_slope_upper_coefficient(m, i, 'R5MI')
    except KeyError:
        return pyo.Constraint.Skip

    if upper_slope_coefficient is None:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, 'R5MI']
            - m.V_TRADER_TOTAL_OFFER[i, energy_offer]
            - (upper_slope_coefficient * m.V_TRADER_TOTAL_OFFER[i, 'R5MI'])
            + 0.001)


def regulating_raise_constraint_7_rule(m, i, j):
    """Joint energy ramp constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for regulating service
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        joint_ramp_raise_max = get_joint_ramp_raise_max(m, i)
    except ValueError:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return m.V_TRADER_TOTAL_OFFER[i, j] <= joint_ramp_raise_max - m.V_TRADER_TOTAL_OFFER[i, energy_offer] + 0.001


def regulating_lower_constraint_1_rule(m, i, j):
    """Regulating lower is less than effective max available"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        # Effective max available - may be negative so set to 0 if required
        effective_max_available = max(0, get_effective_lreg_fcas_max_avail(m, i))
        return m.V_TRADER_TOTAL_OFFER[i, j] <= effective_max_available

    except ValueError:
        return pyo.Constraint.Skip


def regulating_lower_constraint_2_rule(m, i, j):
    """RHS FCAS trapezium slope"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    upper_slope_coefficient = get_slope_upper_coefficient(m, i, j)
    if (upper_slope_coefficient is None) or (upper_slope_coefficient == 0):
        return pyo.Constraint.Skip

    try:
        effective_enablement_max = get_effective_lreg_enablement_max(m, i)
    except ValueError:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j]
            <= (effective_enablement_max - m.V_TRADER_TOTAL_OFFER[i, energy_offer]) / upper_slope_coefficient)


def regulating_lower_constraint_3_rule(m, i, j):
    """LHS FCAS trapezium slope"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    lower_slope_coefficient = get_slope_lower_coefficient(m, i, j)
    if (lower_slope_coefficient is None) or (lower_slope_coefficient == 0):
        return pyo.Constraint.Skip

    try:
        effective_enablement_min = get_effective_lreg_enablement_min(m, i)
    except ValueError:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j]
            <= (m.V_TRADER_TOTAL_OFFER[i, energy_offer] - effective_enablement_min) / lower_slope_coefficient)


def regulating_lower_constraint_4_rule(m, i, j):
    """L6SE joint capacity constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for contingency service
    if (i, 'L6SE') not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        lower_slope_coefficient = get_slope_lower_coefficient(m, i, 'L6SE')
    except KeyError:
        return pyo.Constraint.Skip

    if lower_slope_coefficient is None:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.V_TRADER_TOTAL_OFFER[i, energy_offer]
            - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, 'L6SE']
            - (lower_slope_coefficient * m.V_TRADER_TOTAL_OFFER[i, 'L6SE']))


def regulating_lower_constraint_5_rule(m, i, j):
    """L60S joint capacity constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for contingency service
    if (i, 'L60S') not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        lower_slope_coefficient = get_slope_lower_coefficient(m, i, 'L60S')
    except KeyError:
        return pyo.Constraint.Skip

    if lower_slope_coefficient is None:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.V_TRADER_TOTAL_OFFER[i, energy_offer]
            - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, 'L60S']
            - (lower_slope_coefficient * m.V_TRADER_TOTAL_OFFER[i, 'L60S']))


def regulating_lower_constraint_6_rule(m, i, j):
    """L5MI joint capacity constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for contingency service
    if (i, 'L5MI') not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        lower_slope_coefficient = get_slope_lower_coefficient(m, i, 'L5MI')
    except KeyError:
        return pyo.Constraint.Skip

    if lower_slope_coefficient is None:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.V_TRADER_TOTAL_OFFER[i, energy_offer]
            - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, 'L5MI']
            - (lower_slope_coefficient * m.V_TRADER_TOTAL_OFFER[i, 'L5MI']))


def regulating_lower_constraint_7_rule(m, i, j):
    """Joint energy ramp constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Check availability for regulating service
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    try:
        joint_ramp_lower_min = get_joint_ramp_lower_min(m, i)
    except ValueError:
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    return m.V_TRADER_TOTAL_OFFER[i, j] <= m.V_TRADER_TOTAL_OFFER[i, energy_offer] - joint_ramp_lower_min


def contingency_raise_constraint_1_rule(m, i, j):
    """R6SE max available constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]


def contingency_raise_constraint_2_rule(m, i, j):
    """R6SE RHS constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    upper_slope_coefficient = get_slope_upper_coefficient(m, i, j)

    if (upper_slope_coefficient is None) or (upper_slope_coefficient == 0):
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    return (m.V_TRADER_TOTAL_OFFER[i, j] <=
            (m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j] - m.V_TRADER_TOTAL_OFFER[i, energy_offer]) / upper_slope_coefficient)


def contingency_raise_constraint_3_rule(m, i, j):
    """R6SE LHS constraint"""

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    lower_slope_coefficient = get_slope_lower_coefficient(m, i, j)

    if (lower_slope_coefficient is None) or (lower_slope_coefficient == 0):
        return pyo.Constraint.Skip

    energy_offer = get_energy_offer_type(m, i)

    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    return (m.V_TRADER_TOTAL_OFFER[i, j] <=
            (m.V_TRADER_TOTAL_OFFER[i, energy_offer] - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j]) / lower_slope_coefficient)


def contingency_raise_constraint_4_rule(m, i, j):
    """
    Joint capacity constraint

    Note: created for units with an energy offer and enabled for contingency service
    """

    # Check if a generator
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Contingency service is unavailable
    if (i, j) not in m.S_TRADER_FCAS_AVAILABLE_OFFERS:
        return pyo.Constraint.Skip

    # Get energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # No energy offer specified for the unit
    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Upper slope coefficient
    upper_slope_coefficient = get_slope_upper_coefficient(m, i, j)

    if (upper_slope_coefficient is None) or (upper_slope_coefficient == 0):
        return pyo.Constraint.Skip

    # Raise regulation
    if (i, 'R5RE') not in m.S_TRADER_OFFERS:
        raise_reg = 0
    else:
        raise_reg = m.V_TRADER_TOTAL_OFFER[i, 'R5RE']

    return (m.V_TRADER_TOTAL_OFFER[i, j]
            <= ((m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j]
                - m.V_TRADER_TOTAL_OFFER[i, energy_offer]
                - raise_reg) / upper_slope_coefficient)
            + 0.001)


def define_fcas_constraints(m):
    """Define FCAS constraints"""

    # Regulating raise constraints
    m.C_FCAS_R5RE_1 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_1_rule)
    m.C_FCAS_R5RE_2 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_2_rule)
    m.C_FCAS_R5RE_3 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_3_rule)
    m.C_FCAS_R5RE_4 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_4_rule)
    m.C_FCAS_R5RE_5 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_5_rule)
    m.C_FCAS_R5RE_6 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_6_rule)
    m.C_FCAS_R5RE_7 = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=regulating_raise_constraint_7_rule)

    # # Regulating lower constraints
    # m.C_FCAS_L5RE_1 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_1_rule)
    # m.C_FCAS_L5RE_2 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_2_rule)
    # m.C_FCAS_L5RE_3 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_3_rule)
    # m.C_FCAS_L5RE_4 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_4_rule)
    # m.C_FCAS_L5RE_5 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_5_rule)
    # m.C_FCAS_L5RE_6 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_6_rule)
    # m.C_FCAS_L5RE_7 = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=regulating_lower_constraint_7_rule)

    # Contingency FCAS raise constraints
    # m.C_FCAS_R6SE_1 = pyo.Constraint(m.S_TRADER_FCAS_R6SE_OFFERS, rule=contingency_raise_constraint_1_rule)
    # m.C_FCAS_R6SE_2 = pyo.Constraint(m.S_TRADER_FCAS_R6SE_OFFERS, rule=contingency_raise_constraint_2_rule)
    # m.C_FCAS_R6SE_3 = pyo.Constraint(m.S_TRADER_FCAS_R6SE_OFFERS, rule=contingency_raise_constraint_3_rule)
    m.C_FCAS_R6SE_4 = pyo.Constraint(m.S_TRADER_FCAS_R6SE_OFFERS, rule=contingency_raise_constraint_4_rule)

    m.C_FCAS_R60S_4 = pyo.Constraint(m.S_TRADER_FCAS_R60S_OFFERS, rule=contingency_raise_constraint_4_rule)

    m.C_FCAS_R5MI_4 = pyo.Constraint(m.S_TRADER_FCAS_R5MI_OFFERS, rule=contingency_raise_constraint_4_rule)

    return m
