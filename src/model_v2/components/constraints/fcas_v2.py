"""FCAS constraints"""

import time

import pyomo.environ as pyo


def get_slope(x1, x2, y1, y2):
    """Compute slope. Return None if slope is undefined"""

    try:
        return (y2 - y1) / (x2 - x1)
    except ZeroDivisionError:
        return None


def get_intercept(slope, x0, y0):
    """Get y-axis intercept given slope and point"""

    return y0 - (slope * x0)


def get_energy_offer_type(m, i):
    """Get energy offer type"""

    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        energy_offer_type = 'ENOF'
    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        energy_offer_type = 'LDOF'
    else:
        raise Exception('Unhandled case')

    if (i, energy_offer_type) in m.S_TRADER_OFFERS:
        return energy_offer_type
    else:
        return None


def fcas_available_rule(m, i, j):
    """Set FCAS to zero if conditions not met"""

    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check energy output in previous interval within enablement minutes (else trapped outside trapezium)
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return m.V_TRADER_TOTAL_OFFER[i, j] == 0
    else:
        return pyo.Constraint.Skip


def as_profile_1_rule(m, i, j):
    """Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # No energy offer so can skip constraint
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Get slope between enablement min and low breakpoint
    x1, y1 = m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)], 0
    x2, y2 = m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, j)], m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
    slope = get_slope(x1, x2, y1, y2)

    # Vertical line between high breakpoint and enablement max
    if slope is None:
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
                + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])

    # Slopped line so must compute y-intercept
    y_intercept = get_intercept(slope, x1, y1)

    return (m.V_TRADER_TOTAL_OFFER[i, j] <= (slope * m.V_TRADER_TOTAL_OFFER[i, energy_offer]) + y_intercept
            + m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j])


def as_profile_2_rule(m, i, j):
    """Top of FCAS trapezium"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Ensure FCAS is less than max FCAS available
    return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)] + m.V_CV_TRADER_FCAS_AS_PROFILE_2[i, j]


def as_profile_3_rule(m, i, j):
    """Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # No energy offer so can skip constraint
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Get slope between enablement min and low breakpoint
    x1, y1 = m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)], m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
    x2, y2 = m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)], 0
    slope = get_slope(x1, x2, y1, y2)

    # Vertical line between high breakpoint and enablement max
    if slope is None:
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
                + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])

    # Line is sloped so compute y-intercept
    y_intercept = get_intercept(slope, x1, y1)

    # Constraint for generators - depends on energy offer
    return (m.V_TRADER_TOTAL_OFFER[i, j] <= (slope * m.V_TRADER_TOTAL_OFFER[i, energy_offer]) + y_intercept
            + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])


def joint_ramp_up_rule(m, i, j):
    """Joint ramping constraint for regulating FCAS"""

    # Only consider raise regulation FCAS offers
    if not (j == 'R5RE'):
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampUpRate is MW/h)
    scada_ramp = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12

    # Skip constraint if ramp rate 0 or missing
    if scada_ramp <= 0:
        return pyo.Constraint.Skip

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # # Construct constraint depending on trader type
    # if m.P_TRADER_TYPE[i] in ['GENERATOR']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
    #             <= m.P_TRADER_INITIAL_MW[i] + scada_ramp + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])
    #
    # elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
    #             <= m.P_TRADER_INITIAL_MW[i] + scada_ramp + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])
    #
    # else:
    #     raise Exception(f'Unexpected trader type: {m.P_TRADER_TYPE[i]}')
    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
                <= m.P_TRADER_INITIAL_MW[i] + scada_ramp + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])
    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
                <= m.P_TRADER_INITIAL_MW[i] + scada_ramp + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])
    else:
        raise Exception('Unhandled case')


def joint_ramp_down_rule(m, i, j):
    """Joint ramping constraint for regulating FCAS"""

    # Only consider lower regulation FCAS offers
    if not (j == 'L5RE'):
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampDnRate is MW/h)
    scada_ramp = m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12

    # No constraint if SCADA ramp rate <= 0
    if scada_ramp <= 0:
        return pyo.Constraint.Skip

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # # Construct constraint based on trader type - differs for generators and loads
    # if m.P_TRADER_TYPE[i] in ['GENERATOR']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
    #             + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j] >= m.P_TRADER_INITIAL_MW[i] - scada_ramp)
    #
    # elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
    #             + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j] >= m.P_TRADER_INITIAL_MW[i] - scada_ramp)
    #
    # else:
    #     raise Exception(f'Unexpected trader type: {m.P_TRADER_TYPE[i]}')
    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] - m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
                + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j] >= m.P_TRADER_INITIAL_MW[i] - scada_ramp)

    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] - m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
                + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j] >= m.P_TRADER_INITIAL_MW[i] - scada_ramp)

    else:
        raise Exception('Unhandled case')


def joint_capacity_up_rule(m, i, j):
    """Joint capacity constraint for raise regulation services and contingency FCAS"""

    # Only consider contingency FCAS offers
    if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Skip constraint if no energy offer (see docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Check if raise regulation FCAS available for unit
    if ((i, 'R5RE') in m.S_TRADER_OFFERS) and ((i, 'R5RE') in m.S_TRADER_FCAS_AVAILABLE_OFFERS):
        raise_available = m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
    else:
        raise_available = 0

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])

    # if m.P_TRADER_TYPE[i] in ['GENERATOR']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             + (raise_available * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
    #             <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])
    #
    # elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             + (raise_available * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
    #             <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])
    #
    # else:
    #     raise Exception(f'Unexpected trader type: {m.P_TRADER_TYPE[i]}')

    if m.P_TRADER_TYPE[i] in ['GENERATOR']:
        return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
                + raise_available
                <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])

    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
                + raise_available
                <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])


def joint_capacity_down_rule(m, i, j):
    """Joint capacity constraint for lower regulation services and contingency FCAS"""

    # Only consider contingency FCAS offers
    if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Skip constraint if no energy offer (see docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Check if raise regulation FCAS available for unit
    if ((i, 'L5RE') in m.S_TRADER_OFFERS) and ((i, 'L5RE') in m.S_TRADER_FCAS_AVAILABLE_OFFERS):
        lower_available = m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
    else:
        lower_available = 0

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, j)] - m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])

    # # Construct constraint depending on generator type - differs for generators and loads
    # if m.P_TRADER_TYPE[i] in ['GENERATOR']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             - (lower_available * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
    #             + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j] >= m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
    #
    # elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             - (lower_available * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
    #             + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j] >= m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
    # else:
    #     raise Exception(f'Unexpected trader type: {m.P_TRADER_TYPE[i]}')
    return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j]) - lower_available
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j])


def energy_regulating_up_rule(m, i, j):
    """
    Joint energy and regulating FCAS constraints

    Energy Dispatch Target + Upper Slope Coeff x Regulating FCAS Target <= EnablementMax8
    """

    # Only consider contingency FCAS offers
    if j not in ['R5RE', 'L5RE']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # No energy offer so can skip constraint (from docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])

    # # Construct constraint depending on generator type - differs for generators and loads
    # if m.P_TRADER_TYPE[i] in ['GENERATOR']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)])
    #
    # elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)])
    # else:
    #     raise Exception(f'Unexpected trader type: {m.P_TRADER_TYPE[i]}')

    return (m.V_TRADER_TOTAL_OFFER[(i, energy_offer)] + (coefficient * m.V_TRADER_TOTAL_OFFER[(i, j)])
            <= m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)])


def energy_regulating_down_rule(m, i, j):
    """
    Joint energy and regulating FCAS constraints

    Energy Dispatch Target - Lower Slope Coeff x Regulating FCAS Target >= EnablementMin
    """

    # Only consider contingency FCAS offers
    if j not in ['R5RE', 'L5RE']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Energy offer
    energy_offer = get_energy_offer_type(m, i)

    # No energy offer so can skip constraint (from docs)
    if energy_offer is None:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, j)] - m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)])

    # # Construct constraint depending on generator type - differs for generators and loads
    # if m.P_TRADER_TYPE[i] in ['GENERATOR']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             >= m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
    #
    # elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
    #     return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
    #             >= m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])
    #
    # else:
    #     raise Exception(f'Unexpected trader type: {m.P_TRADER_TYPE[i]}')
    return (m.V_TRADER_TOTAL_OFFER[(i, energy_offer)] - (coefficient * m.V_TRADER_TOTAL_OFFER[(i, j)])
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)])


def define_fcas_constraints(m):
    """FCAS constraints"""

    # Start timer
    t0 = time.time()

    # FCAS availability
    m.C_FCAS_AVAILABILITY_RULE = pyo.Constraint(m.S_TRADER_OFFERS, rule=fcas_available_rule)
    print('Finished constructing C_FCAS_AVAILABILITY_RULE:', time.time() - t0)

    # AS profile constraint - between enablement min and low breakpoint
    m.C_AS_PROFILE_1 = pyo.Constraint(m.S_TRADER_OFFERS, rule=as_profile_1_rule)
    print('Finished constructing C_AS_PROFILE_1:', time.time() - t0)

    # AS profile constraint - between enablement min and low breakpoint
    m.C_AS_PROFILE_2 = pyo.Constraint(m.S_TRADER_OFFERS, rule=as_profile_2_rule)
    print('Finished constructing C_AS_PROFILE_2:', time.time() - t0)

    # AS profile constraint - between enablement min and low breakpoint
    m.C_AS_PROFILE_3 = pyo.Constraint(m.S_TRADER_OFFERS, rule=as_profile_3_rule)
    print('Finished constructing C_AS_PROFILE_3:', time.time() - t0)

    # Joint ramp up constraint
    m.C_JOINT_RAMP_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_up_rule)
    print('Finished constructing C_JOINT_RAMP_UP:', time.time() - t0)

    # Joint ramp up constraint
    m.C_JOINT_RAMP_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_down_rule)
    print('Finished constructing C_JOINT_RAMP_DOWN:', time.time() - t0)

    # Joint capacity constraint up
    m.C_JOINT_CAPACITY_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_capacity_up_rule)
    print('Finished constructing C_JOINT_CAPACITY_UP:', time.time() - t0)

    # Joint capacity constraint down
    m.C_JOINT_CAPACITY_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_capacity_down_rule)
    print('Finished constructing C_JOINT_CAPACITY_DOWN:', time.time() - t0)

    # Joint energy and regulating FCAS constraint
    m.C_JOINT_REGULATING_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=energy_regulating_up_rule)
    print('Finished constructing C_JOINT_REGULATING_UP:', time.time() - t0)

    # Joint energy and regulating FCAS constraint
    m.C_JOINT_REGULATING_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=energy_regulating_down_rule)
    print('Finished constructing C_JOINT_REGULATING_DOWN:', time.time() - t0)

    return m
