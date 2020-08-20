"""Construct FCAS constraints based on description in FCAS model docs"""

import math

import pyomo.environ as pyo


def fcas_common_unavailability_rule(m, i, j):
    """Unavailable FCAS targets fixed to 0"""

    return m.V_TRADER_TOTAL_OFFER[(i, j)] == 0


def define_common_fcas_constraints(m):
    """Define FCAS constraints common to all offer types"""

    # Unavailable FCAS types fixed have targets fixed to 0
    m.C_FCAS_AVAILABILITY = pyo.Constraint(m.S_TRADER_FCAS_UNAVAILABLE_OFFERS, rule=fcas_common_unavailability_rule)

    return m


def get_max_available(m, i, j):
    """Get max available - scaling applied for semi-scheduled generators"""

    # Use UIGF for semi-scheduled generators TODO: check if this needs to be scaled for semi-scheduled units
    if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '1':
        return min(m.P_TRADER_UIGF[i], m.P_TRADER_MAX_AVAILABLE[(i, j)])
    else:
        return m.P_TRADER_MAX_AVAILABLE[(i, j)]


def get_raise_reg_effective_max_avail(m, i, j):
    """Compute effective max available for raise regulation offers"""

    # Return None if AGC ramp up rate missing
    if i not in m.P_TRADER_SCADA_RAMP_UP_RATE.keys():
        return None

    # AGC ramp-rate - must divide by 12 to get effective ramp rate over 5min dispatch interval
    agc_ramp_rate = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12

    # Offer max available
    max_available = get_max_available(m, i, j)

    # Effective max available
    effective_max_available = min(max_available, agc_ramp_rate)

    return effective_max_available


def get_lower_reg_effective_max_avail(m, i, j):
    """Compute effective max available for lower regulation offers"""

    # Return None if AGC ramp up rate missing TODO: docs say ramp up rate should be used (think should be ramp down)
    if i not in m.P_TRADER_SCADA_RAMP_DOWN_RATE.keys():
        return None

    # AGC ramp-rate - must divide by 12 to get effective ramp rate over 5min dispatch interval
    agc_ramp_rate = m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12

    # Offer max available - ramp down so UIGF will have no impact - unit's ability to ramp down (possibly to zero)
    effective_max_available = min(m.P_TRADER_MAX_AVAILABLE[(i, j)], agc_ramp_rate)

    return effective_max_available


def get_energy_offer_type(m, i):
    """Get energy offer type for a given generator. Return None if no energy offer."""

    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        energy_offer = 'ENOF'
    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        energy_offer = 'LDOF'
    else:
        raise Exception('Unhandled case')

    # Return None if trader does not have an energy offer
    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return None

    else:
        return energy_offer


def get_raise_reg_effective_enablement_max(m, i, j):
    """Get raise regulation enablement max"""

    return min(m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)], m.P_TRADER_HMW[i])


def get_lower_reg_effective_enablement_max(m, i, j):
    """Get lower regulation enablement max"""

    return min(m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)], m.P_TRADER_HMW[i])


def get_raise_reg_effective_enablement_min(m, i, j):
    """Get raise regulation enablement min"""

    return max(m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)], m.P_TRADER_LMW[i])


def get_contingency_effective_enablement_max(m, i, j):
    """Get contingency enablement max - need to consider UIGF for semi-scheduled plant"""

    # Contingency enablement is scaled for semi-scheduled units
    if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '1':
        return min(m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)], m.P_TRADER_UIGF[i])
    else:
        return m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)]


def get_slope_upper_coefficient(m, i, j):
    """Get upper slope coefficient"""

    # Max available
    max_avail = get_max_available(m, i, j)

    try:
        return (m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)]) / max_avail
    except ZeroDivisionError:
        return math.inf


def get_slope_lower_coefficient(m, i, j):
    """Get upper slope coefficient"""

    # Max available
    max_avail = get_max_available(m, i, j)

    if max_avail == 0:
        return (m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, j)] - m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)]) / max_avail
    else:
        return math.inf


def fcas_raise_reg_trapezium_1_rule(m, i, j):
    """Scale FCAS trapezium max available"""

    # Effective max available
    effective_max_available = get_raise_reg_effective_max_avail(m, i, j)

    # No constraint if AGC ramp rate missing or equals 0
    if (effective_max_available is None) or (effective_max_available == 0):
        return pyo.Constraint.Skip

    return m.V_TRADER_TOTAL_OFFER[(i, j)] <= effective_max_available


def fcas_raise_reg_trapezium_2_rule(m, i, j):
    """Scale FCAS trapezium RHS"""

    # Get energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Unit does not have an energy offer - skip constraint (from docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Upper slope coefficient
    upper_slope_coefficient = get_slope_upper_coefficient(m, i, j)

    # Skip constraint if upper slope coefficient is 0 (from docs)
    if upper_slope_coefficient == 0:
        return pyo.Constraint.Skip

    # Effective enablement max
    effective_enablement_max = get_raise_reg_effective_enablement_max(m, i, j)

    return (m.V_TRADER_TOTAL_OFFER[(i, j)]
            <= (effective_enablement_max - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]) / upper_slope_coefficient)


def fcas_raise_reg_trapezium_3_rule(m, i, j):
    """Scale FCAS trapezium LHS"""

    # Get energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Unit does not have an energy offer - skip constraint (from docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Lower slope coefficient
    lower_slope_coefficient = get_slope_lower_coefficient(m, i, j)

    # Skip constraint if upper slope coefficient is 0 (from docs)
    if lower_slope_coefficient == 0:
        return pyo.Constraint.Skip

    # Effective enablement min
    effective_enablement_min = get_raise_reg_effective_enablement_min(m, i, j)

    return (m.V_TRADER_TOTAL_OFFER[(i, j)]
            <= (m.V_TRADER_TOTAL_OFFER[(i, energy_offer)] - effective_enablement_min) / lower_slope_coefficient)


def fcas_raise_reg_r6se_joint_capacity_rule(m, i, j):
    """Raise regulation joint capacity constraint - R6SE"""

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # Skip constraint if no contingency service
    if (i, 'R6SE') not in m.V_TRADER_TOTAL_OFFER.keys():
        return pyo.Constraint.Skip

    # Enablement max
    enablement_max = get_contingency_effective_enablement_max(m, i, 'R6SE')

    # Upper slope coefficient
    upper_slope_coefficient = get_slope_upper_coefficient(m, i, 'R6SE')

    # No capacity constraint so can skip
    if upper_slope_coefficient is math.inf:
        return pyo.Constraint.Skip
    else:
        return (m.V_TRADER_TOTAL_OFFER[(i, j)]
                <= enablement_max - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]
                - (upper_slope_coefficient * m.V_TRADER_TOTAL_OFFER[(i, 'R6SE')]))


def fcas_raise_reg_r60s_joint_capacity_rule(m, i, j):
    """Raise regulation joint capacity constraint - R60S"""

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # Skip constraint if no contingency service
    if (i, 'R60S') not in m.V_TRADER_TOTAL_OFFER.keys():
        return pyo.Constraint.Skip

    # Enablement max
    enablement_max = get_contingency_effective_enablement_max(m, i, 'R60S')

    # Upper slope coefficient
    upper_slope_coefficient = get_slope_upper_coefficient(m, i, 'R60S')

    # No capacity constraint so can skip
    if upper_slope_coefficient is math.inf:
        return pyo.Constraint.Skip
    else:
        return (m.V_TRADER_TOTAL_OFFER[(i, j)]
                <= enablement_max - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]
                - (upper_slope_coefficient * m.V_TRADER_TOTAL_OFFER[(i, 'R60S')]))


def fcas_raise_reg_r5mi_joint_capacity_rule(m, i, j):
    """Raise regulation joint capacity constraint - R5MI"""

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # Skip constraint if no contingency service
    if (i, 'R5MI') not in m.V_TRADER_TOTAL_OFFER.keys():
        return pyo.Constraint.Skip

    # Enablement max
    enablement_max = get_contingency_effective_enablement_max(m, i, 'R5MI')

    # Upper slope coefficient
    upper_slope_coefficient = get_slope_upper_coefficient(m, i, 'R5MI')

    # No capacity constraint so can skip
    if upper_slope_coefficient is math.inf:
        return pyo.Constraint.Skip
    else:
        return (m.V_TRADER_TOTAL_OFFER[(i, j)]
                <= enablement_max - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]
                - (upper_slope_coefficient * m.V_TRADER_TOTAL_OFFER[(i, 'R5MI')]))


def fcas_raise_reg_joint_ramp_rule(m, i, j):
    """Joint ramp raise constraint"""

    # Initial MW
    initial_mw = m.P_TRADER_INITIAL_MW[i]

    # AGC ramp rate
    agc_ramp_up = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Skip constraint if no energy offer
    if energy_offer is None:
        return pyo.Constraint.Skip
    else:
        return m.V_TRADER_TOTAL_OFFER[(i, j)] <= initial_mw + agc_ramp_up - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]


def define_raise_regulation_constraints(m):
    """Raise regulation constraints"""

    # Raise regulation constraints
    m.C_FCAS_RAISE_REG_MAX_AVAILABLE = pyo.Constraint(m.S_TRADER_FCAS_R5RE_OFFERS, rule=fcas_raise_reg_trapezium_1_rule)

    # FCAS trapezium RHS scaling
    m.C_FCAS_RAISE_REG_TRAPEZIUM_RHS = pyo.Constraint(
        m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_raise_reg_trapezium_2_rule)

    # FCAS trapezium LHS scaling
    m.C_FCAS_RAISE_REG_TRAPEZIUM_LHS = pyo.Constraint(
        m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_raise_reg_trapezium_3_rule)

    # Joint capacity constraints - R6SE
    m.C_FCAS_RAISE_REG_R6SE_JOINT_CAPACITY = pyo.Constraint(
        m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_raise_reg_r6se_joint_capacity_rule)

    # Joint capacity constraints - R60S
    m.C_FCAS_RAISE_REG_R60S_JOINT_CAPACITY = pyo.Constraint(
        m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_raise_reg_r60s_joint_capacity_rule)

    # Joint capacity constraints - R5MI
    m.C_FCAS_RAISE_REG_R5MI_JOINT_CAPACITY = pyo.Constraint(
        m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_raise_reg_r5mi_joint_capacity_rule)

    # Joint ramping constraints
    m.C_FCAS_RAISE_REG_JOINT_RAMP = pyo.Constraint(
        m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_raise_reg_joint_ramp_rule)

    return m


def fcas_lower_reg_trapezium_1_rule(m, i, j):
    """Scale FCAS trapezium max available"""

    # Effective max available
    effective_max_available = get_lower_reg_effective_max_avail(m, i, j)

    # No constraint if AGC ramp rate missing or equals 0
    if (effective_max_available is None) or (effective_max_available == 0):
        return pyo.Constraint.Skip

    return m.V_TRADER_TOTAL_OFFER[(i, j)] <= effective_max_available


def fcas_lower_reg_trapezium_2_rule(m, i, j):
    """Scale FCAS trapezium RHS"""

    # Get energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Unit does not have an energy offer - skip constraint (from docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Upper slope coefficient
    upper_slope_coefficient = get_slope_upper_coefficient(m, i, j)

    # Skip constraint if upper slope coefficient is 0 (from docs)
    if upper_slope_coefficient == 0:
        return pyo.Constraint.Skip

    # Effective enablement max
    effective_enablement_max = get_lower_reg_effective_enablement_max(m, i, j)

    return (m.V_TRADER_TOTAL_OFFER[(i, j)]
            <= (effective_enablement_max - m.V_TRADER_TOTAL_OFFER[(i, energy_offer)]) / upper_slope_coefficient)


def define_lower_regulation_constraints(m):
    """Lower regulation constraints"""

    # Lower regulation max available
    m.C_FCAS_LOWER_REG_MAX_AVAILABLE = pyo.Constraint(m.S_TRADER_FCAS_L5RE_OFFERS, rule=fcas_lower_reg_trapezium_1_rule)

    # FCAS trapezium RHS scaling
    m.C_FCAS_LOWER_REG_TRAPEZIUM_RHS = pyo.Constraint(
        m.S_TRADER_FCAS_L5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
        rule=fcas_lower_reg_trapezium_2_rule)

    # # FCAS trapezium LHS scaling
    # m.C_FCAS_RAISE_REG_TRAPEZIUM_LHS = pyo.Constraint(
    #     m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
    #     rule=fcas_raise_reg_trapezium_3_rule)
    #
    # # Joint capacity constraints - R6SE
    # m.C_FCAS_RAISE_REG_R6SE_JOINT_CAPACITY = pyo.Constraint(
    #     m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
    #     rule=fcas_raise_reg_r6se_joint_capacity_rule)
    #
    # # Joint capacity constraints - R60S
    # m.C_FCAS_RAISE_REG_R60S_JOINT_CAPACITY = pyo.Constraint(
    #     m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
    #     rule=fcas_raise_reg_r60s_joint_capacity_rule)
    #
    # # Joint capacity constraints - R5MI
    # m.C_FCAS_RAISE_REG_R5MI_JOINT_CAPACITY = pyo.Constraint(
    #     m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
    #     rule=fcas_raise_reg_r5mi_joint_capacity_rule)
    #
    # # Joint ramping constraints
    # m.C_FCAS_RAISE_REG_JOINT_RAMP = pyo.Constraint(
    #     m.S_TRADER_FCAS_R5RE_OFFERS.intersection(m.S_TRADER_FCAS_AVAILABLE_OFFERS),
    #     rule=fcas_raise_reg_joint_ramp_rule)

    return m


def define_fcas_constraints(m):
    """Define FCAS constraints"""

    # Constraints common to all FCAS offers
    m = define_common_fcas_constraints(m)

    # Raise regulation constraints
    # m = define_raise_regulation_constraints(m)

    # Lower regulation constraints
    # m = define_lower_regulation_constraints(m)

    return m
