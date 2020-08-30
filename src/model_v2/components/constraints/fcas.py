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
    """Get energy offer type which depends on whether a trader is a generator or a load"""

    if m.P_TRADER_TYPE[i] == 'GENERATOR':
        return 'ENOF'
    elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
        return 'LDOF'
    else:
        raise Exception('Unhandled case')


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

    # Get slope between enablement min and low breakpoint
    x1, y1 = m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, j)], 0
    x2, y2 = m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, j)], m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
    slope = get_slope(x1, x2, y1, y2)

    # Energy offer type (ENOF or LDOF)
    energy_offer = get_energy_offer_type(m, i)

    # Vertical line
    if slope is None:
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
                + m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j])

    # Sloped line
    else:
        # Compute y-intercept
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
    """Constraint LHS component of FCAS trapeziums (line between enablement high breakpoint and enablement max)"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[(i, j)]:
        return pyo.Constraint.Skip

    # Get slope between enablement min and low breakpoint
    x1, y1 = m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, j)], m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
    x2, y2 = m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, j)], 0
    slope = get_slope(x1, x2, y1, y2)

    # Energy offer type (ENOF or LDOF)
    energy_offer = get_energy_offer_type(m, i)

    # Vertical line between high breakpoint and enablement max
    if slope is None:
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_FCAS_MAX_AVAILABLE[(i, j)]
                + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])

    # Sloped line
    else:
        # Compute y-intercept
        y_intercept = get_intercept(slope, x1, y1)

        # Constraint depends on energy offer
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= (slope * m.V_TRADER_TOTAL_OFFER[i, energy_offer]) + y_intercept
                + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])


def joint_ramp_raise_generator_rule(m, i, j):
    """
    Joint ramping raise constraint for regulating FCAS - generators

    From docs: "applied if a unit has an energy offer, is enabled for regulating services, and the AGC ramp up or
    down rate is greater than zero".

    Energy Dispatch Target + Raise Regulating FCAS Target <= Initial MW + SCADA Ramp Up Capability
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Only consider raise regulation FCAS offers
    if j != 'R5RE':
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Check if unit has an energy offer
    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, j]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampUpRate is MW/h)
    scada_ramp = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12

    # TODO: handle case where SCADA_RAMP_UP_RATE is missing
    if scada_ramp <= 0:
        return pyo.Constraint.Skip

    # Construct constraint depending on trader type
    return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
            <= m.P_TRADER_INITIAL_MW[i] + scada_ramp + m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR[i, j])


def joint_ramp_lower_generator_rule(m, i, j):
    """
    Joint ramping lower constraint for regulating FCAS - generators

    From docs: "applied if a unit has an energy offer, is enabled for regulating services, and the AGC ramp up or
    down rate is greater than zero".

    Energy Dispatch Target − Lower Regulating FCAS Target >= Initial MW − SCADA Ramp Down Capability
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Only consider lower regulation FCAS offers
    if j != 'L5RE':
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Check if unit has an energy offer
    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, j]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampDnRate is MW/h)
    scada_ramp = m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12

    # No constraint if SCADA ramp rate <= 0
    if scada_ramp <= 0:
        return pyo.Constraint.Skip

    return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR[i, j] >= m.P_TRADER_INITIAL_MW[i] - scada_ramp)


def get_joint_capacity_raise_generator_constraint(trade_type):
    """Get rule for joint capacity constraint for given trade type"""

    def joint_capacity_raise_generator_rule(m, i, j):
        """
        Joint capacity constraint for raise regulation services and contingency FCAS

        From docs: "Joint capacity constraints are created for all units with an energy offer and which are enabled for a
        contingency service. One set of constraints is created for each contingency service (fast raise, slow raise,
        delayed raise, fast lower, slow lower, or delayed lower) for which the unit is enabled."

        Energy Dispatch Target + Upper Slope Coeff x Contingency FCAS Target
        + [Raise Regulation FCAS enablement status] x Raise Regulating FCAS Target <= EnablementMax
        """

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider energy offer
        if j != 'ENOF':
            return pyo.Constraint.Skip

        # Check if contingency FCAS offer exists for the unit
        if (i, trade_type) not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Check if contingency FCAS is available
        if not m.P_TRADER_FCAS_AVAILABILITY[i, trade_type]:
            return pyo.Constraint.Skip

        # Check if raise regulation FCAS available for unit
        try:
            raise_available = int(m.P_TRADER_FCAS_AVAILABILITY[i, 'R5RE']) * m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
        except KeyError:
            raise_available = 0

        # Slope coefficient
        coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[i, trade_type] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[i, trade_type])
                       / m.P_TRADER_FCAS_MAX_AVAILABLE[i, trade_type])

        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, trade_type])
                + raise_available
                <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, trade_type]
                + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_GENERATOR[i, trade_type])

    return joint_capacity_raise_generator_rule


def get_joint_capacity_lower_generator_constraint(trade_type):
    """Get rule for joint capacity constraint for given trade type"""

    def joint_capacity_lower_generator_rule(m, i, j):
        """
        Joint capacity constraint for lower regulation services and contingency FCAS

        From docs: "Joint capacity constraints are created for all units with an energy offer and which are enabled for a
        contingency service. One set of constraints is created for each contingency service (fast raise, slow raise,
        delayed raise, fast lower, slow lower, or delayed lower) for which the unit is enabled."

        Energy Dispatch Target − Lower Slope Coeff x Contingency FCAS Target
        − [Lower Regulation FCAS enablement status] x Lower Regulating FCAS Target >= EnablementMin
        """

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider energy offer
        if j != 'ENOF':
            return pyo.Constraint.Skip

        # Check if contingency FCAS offer exists for the unit
        if (i, trade_type) not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Check if contingency FCAS is available
        if not m.P_TRADER_FCAS_AVAILABILITY[i, trade_type]:
            return pyo.Constraint.Skip

        # Check if lower regulation FCAS available for unit
        try:
            lower_available = int(m.P_TRADER_FCAS_AVAILABILITY[i, 'L5RE']) * m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
        except KeyError:
            lower_available = 0

        # Slope coefficient
        coefficient = ((m.P_TRADER_FCAS_LOW_BREAKPOINT[i, trade_type] - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, trade_type])
                       / m.P_TRADER_FCAS_MAX_AVAILABLE[i, trade_type])

        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, trade_type])
                - lower_available
                + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_GENERATOR[i, trade_type]
                >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, trade_type])

    return joint_capacity_lower_generator_rule


def energy_regulating_raise_generator_rule(m, i, j):
    """
    Joint energy and regulating FCAS constraints

    From docs: "Energy and regulating FCAS capacity constraints are created for all units with an energy offer and
    which are enabled for regulating services."

    Energy Dispatch Target + Upper Slope Coeff x Regulating FCAS Target <= EnablementMax
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Only consider energy offer
    if j != 'ENOF':
        return pyo.Constraint.Skip

    # Check if regulating FCAS offer
    if (i, 'R5RE') not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, 'R5RE']:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, 'R5RE')] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, 'R5RE')])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, 'R5RE')])

    return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
            <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, 'R5RE']
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR[i, 'ENOF'])


def energy_regulating_lower_generator_rule(m, i, j):
    """
    Joint energy and regulating FCAS constraints

    From docs: "Energy and regulating FCAS capacity constraints are created for all units with an energy offer and
    which are enabled for regulating services."

    Energy Dispatch Target - Lower Slope Coeff x Regulating FCAS Target >= EnablementMin9
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] != 'GENERATOR':
        return pyo.Constraint.Skip

    # Only consider energy offer
    if j != 'ENOF':
        return pyo.Constraint.Skip

    # Check if regulating FCAS offer
    if (i, 'L5RE') not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, 'L5RE']:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_LOW_BREAKPOINT[i, 'L5RE'] - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, 'L5RE'])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[i, 'L5RE'])

    return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR[i, 'ENOF']
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, 'L5RE'])


def joint_ramp_raise_load_rule(m, i, j):
    """
    Joint ramping raise constraint for regulating FCAS - loads

    From docs: "applied if a unit has an energy offer, is enabled for regulating services, and the AGC ramp up or
    down rate is greater than zero".

    (assumed constraint from scheduled loads doc)
    Energy Dispatch Target - Raise Regulating FCAS Target <= Initial MW - SCADA Ramp Down Capability

    Note: for loads frequency is increased by DECREASING load
    """

    # Only consider loads
    if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
        return pyo.Constraint.Skip

    # Only consider raise regulation FCAS offers
    if j != 'R5RE':
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Check if unit has an energy offer
    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, j]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampUpRate is MW/h)
    scada_ramp = m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12

    # TODO: handle case where SCADA_RAMP_UP_RATE is missing
    if scada_ramp <= 0:
        return pyo.Constraint.Skip

    # Construct constraint depending on trader type
    return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD[i, j] >= m.P_TRADER_INITIAL_MW[i] - scada_ramp)


def joint_ramp_lower_load_rule(m, i, j):
    """
    Joint ramping lower constraint for regulating FCAS - loads

    From docs: "applied if a unit has an energy offer, is enabled for regulating services, and the AGC ramp up or
    down rate is greater than zero".

    (assumed constraint from scheduled loads doc)
    Energy Dispatch Target − Lower Regulating FCAS Target >= Initial MW − SCADA Ramp Down Capability

    Note: for loads frequency is increased by DECREASING load
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
        return pyo.Constraint.Skip

    # Only consider lower regulation FCAS offers
    if j != 'L5RE':
        return pyo.Constraint.Skip

    # Energy offer type
    energy_offer = get_energy_offer_type(m, i)

    # Check if unit has an energy offer
    if (i, energy_offer) not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, j]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampDnRate is MW/h)
    scada_ramp = m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12

    # No constraint if SCADA ramp rate <= 0
    if scada_ramp <= 0:
        return pyo.Constraint.Skip

    return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
            - m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD[i, j] <= m.P_TRADER_INITIAL_MW[i] + scada_ramp)


def get_joint_capacity_raise_load_constraint(trade_type):
    """Get rule for joint capacity constraint for given trade type"""

    def joint_capacity_raise_load_rule(m, i, j):
        """
        Joint capacity constraint for raise regulation services and contingency FCAS

        From docs: "Joint capacity constraints are created for all units with an energy offer and which are enabled for a
        contingency service. One set of constraints is created for each contingency service (fast raise, slow raise,
        delayed raise, fast lower, slow lower, or delayed lower) for which the unit is enabled."

        Energy Dispatch Target - (Lower Slope Coeff x Contingency FCAS Target)
        - [Raise Regulation FCAS enablement status] x Raise Regulating FCAS Target >= EnablementMin

        Note: for loads frequency is increased by DECREASING load
        """

        # Only consider generators
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider energy offer
        if j != 'LDOF':
            return pyo.Constraint.Skip

        # Check if contingency FCAS offer exists for the unit
        if (i, trade_type) not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Check if contingency FCAS is available
        if not m.P_TRADER_FCAS_AVAILABILITY[i, trade_type]:
            return pyo.Constraint.Skip

        # Check if raise regulation FCAS available for unit
        try:
            raise_available = int(m.P_TRADER_FCAS_AVAILABILITY[i, 'R5RE']) * m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
        except KeyError:
            raise_available = 0

        # Slope coefficient
        coefficient = ((m.P_TRADER_FCAS_LOW_BREAKPOINT[i, trade_type] - m.P_TRADER_FCAS_ENABLEMENT_MIN[i, trade_type])
                       / m.P_TRADER_FCAS_MAX_AVAILABLE[i, trade_type])

        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, trade_type])
                - raise_available + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_LOAD[i, trade_type]
                >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, trade_type])

    return joint_capacity_raise_load_rule


def get_joint_capacity_lower_load_constraint(trade_type):
    """Get rule for joint capacity constraint for given trade type"""

    def joint_capacity_lower_load_rule(m, i, j):
        """
        Joint capacity constraint for lower regulation services and contingency FCAS

        From docs: "Joint capacity constraints are created for all units with an energy offer and which are enabled for a
        contingency service. One set of constraints is created for each contingency service (fast raise, slow raise,
        delayed raise, fast lower, slow lower, or delayed lower) for which the unit is enabled."

        Energy Dispatch Target - (Lower Slope Coeff x Contingency FCAS Target)
        - [Raise Regulation FCAS enablement status] x Raise Regulating FCAS Target >= EnablementMin

        Note: for loads frequency is increased by DECREASING load
        """

        # Only consider generators
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider energy offer
        if j != 'LDOF':
            return pyo.Constraint.Skip

        # Check if contingency FCAS offer exists for the unit
        if (i, trade_type) not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Check if contingency FCAS is available
        if not m.P_TRADER_FCAS_AVAILABILITY[i, trade_type]:
            return pyo.Constraint.Skip

        # Check if raise regulation FCAS available for unit
        try:
            lower_available = int(m.P_TRADER_FCAS_AVAILABILITY[i, 'L5RE']) * m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
        except KeyError:
            lower_available = 0

        # Slope coefficient
        coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[i, trade_type] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[i, trade_type])
                       / m.P_TRADER_FCAS_MAX_AVAILABLE[i, trade_type])

        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, trade_type])
                + lower_available - m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_LOAD[i, trade_type]
                <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, trade_type])

    return joint_capacity_lower_load_rule


def energy_regulating_raise_load_rule(m, i, j):
    """
    Joint energy and regulating FCAS constraints - loads

    From docs: "Energy and regulating FCAS capacity constraints are created for all units with an energy offer and
    which are enabled for regulating services."

    (assumed constraint from scheduled loads doc)
    Energy Dispatch Target - (Lower Slope Coeff x Regulating FCAS Target) >= EnablementMin
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
        return pyo.Constraint.Skip

    # Only consider energy offer
    if j != 'LDOF':
        return pyo.Constraint.Skip

    # Check if regulating FCAS offer
    if (i, 'R5RE') not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, 'R5RE']:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_LOW_BREAKPOINT[(i, 'R5RE')] - m.P_TRADER_FCAS_ENABLEMENT_MIN[(i, 'R5RE')])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, 'R5RE')])

    return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD[i, 'LDOF']
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, 'R5RE'])


def energy_regulating_lower_load_rule(m, i, j):
    """
    Joint energy and regulating FCAS constraints - loads

    From docs: "Energy and regulating FCAS capacity constraints are created for all units with an energy offer and
    which are enabled for regulating services."

    (assumed constraint from scheduled loads doc)
    Energy Dispatch Target + Upper Slope Coeff x Regulating FCAS Target <= EnablementMax
    """

    # Only consider generators
    if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
        return pyo.Constraint.Skip

    # Only consider energy offer
    if j != 'LDOF':
        return pyo.Constraint.Skip

    # Check if regulating FCAS offer
    if (i, 'L5RE') not in m.S_TRADER_OFFERS:
        return pyo.Constraint.Skip

    # Check regulating FCAS is available
    if not m.P_TRADER_FCAS_AVAILABILITY[i, 'L5RE']:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = ((m.P_TRADER_FCAS_ENABLEMENT_MAX[(i, 'L5RE')] - m.P_TRADER_FCAS_HIGH_BREAKPOINT[(i, 'L5RE')])
                   / m.P_TRADER_FCAS_MAX_AVAILABLE[(i, 'L5RE')])

    return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
            - m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD[i, 'LDOF']
            <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, 'L5RE'])


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

    # Joint ramp raise constraint - generators
    m.C_JOINT_RAMP_RAISE_GENERATOR = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_raise_generator_rule)
    print('Finished constructing C_JOINT_RAMP_RAISE_GENERATOR:', time.time() - t0)

    # Joint ramp lower constraint - generators
    m.C_JOINT_RAMP_LOWER_GENERATOR = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_lower_generator_rule)
    print('Finished constructing C_JOINT_RAMP_LOWER_GENERATOR:', time.time() - t0)

    # Joint capacity raise - R6SE - generators
    m.C_JOINT_CAPACITY_RAISE_R6SE_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_raise_generator_constraint('R6SE'))
    print('Finished constructing C_JOINT_CAPACITY_RAISE_R6SE_GENERATOR:', time.time() - t0)

    # Joint capacity raise - R60S - generators
    m.C_JOINT_CAPACITY_RAISE_R60S_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_raise_generator_constraint('R60S'))
    print('Finished constructing C_JOINT_CAPACITY_RAISE_R60S_GENERATOR:', time.time() - t0)

    # Joint capacity raise - R5MI - generators
    m.C_JOINT_CAPACITY_RAISE_R5MI_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_raise_generator_constraint('R5MI'))
    print('Finished constructing C_JOINT_CAPACITY_RAISE_R5MI_GENERATOR:', time.time() - t0)

    # Joint capacity lower - L6SE - generators
    m.C_JOINT_CAPACITY_LOWER_L6SE_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_lower_generator_constraint('L6SE'))
    print('Finished constructing C_JOINT_CAPACITY_LOWER_L6SE_GENERATOR:', time.time() - t0)

    # Joint capacity lower - L60S - generators
    m.C_JOINT_CAPACITY_LOWER_L60S_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_lower_generator_constraint('L60S'))
    print('Finished constructing C_JOINT_CAPACITY_LOWER_L60S_GENERATOR:', time.time() - t0)

    # Joint capacity lower - L5MI - generators
    m.C_JOINT_CAPACITY_LOWER_L5MI_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_lower_generator_constraint('L5MI'))
    print('Finished constructing C_JOINT_CAPACITY_LOWER_L5MI_GENERATOR:', time.time() - t0)

    # Joint energy and regulating FCAS constraint - generators
    m.C_JOINT_REGULATING_RAISE_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=energy_regulating_raise_generator_rule)
    print('Finished constructing C_JOINT_REGULATING_RAISE_GENERATOR:', time.time() - t0)

    # Joint energy and regulating FCAS constraint - generators
    m.C_JOINT_REGULATING_LOWER_GENERATOR = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=energy_regulating_lower_generator_rule)
    print('Finished constructing C_JOINT_REGULATING_LOWER_GENERATOR:', time.time() - t0)

    # Joint ramp up constraint - loads
    m.C_JOINT_RAMP_RAISE_LOAD = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_raise_load_rule)
    print('Finished constructing C_JOINT_RAMP_RAISE_LOAD:', time.time() - t0)

    # Joint ramp lower constraint - loads
    m.C_JOINT_RAMP_LOWER_LOAD = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_lower_load_rule)
    print('Finished constructing C_JOINT_RAMP_LOWER_LOAD:', time.time() - t0)

    # Joint capacity raise - R6SE - loads
    m.C_JOINT_CAPACITY_RAISE_R6SE_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_raise_load_constraint('R6SE'))
    print('Finished constructing C_JOINT_CAPACITY_RAISE_R6SE_LOAD:', time.time() - t0)

    # Joint capacity raise - R60S - loads
    m.C_JOINT_CAPACITY_RAISE_R60S_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_raise_load_constraint('R60S'))
    print('Finished constructing C_JOINT_CAPACITY_RAISE_R60S_LOAD:', time.time() - t0)

    # Joint capacity raise - R60S - loads
    m.C_JOINT_CAPACITY_RAISE_R5MI_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_raise_load_constraint('R5MI'))
    print('Finished constructing C_JOINT_CAPACITY_RAISE_R5MI_LOAD:', time.time() - t0)

    # Joint capacity raise - L6SE - loads
    m.C_JOINT_CAPACITY_LOWER_L6SE_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_lower_load_constraint('L6SE'))
    print('Finished constructing C_JOINT_CAPACITY_LOWER_L6SE_LOAD:', time.time() - t0)

    # Joint capacity raise - L60S - loads
    m.C_JOINT_CAPACITY_LOWER_L60S_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_lower_load_constraint('L60S'))
    print('Finished constructing C_JOINT_CAPACITY_LOWER_L60S_LOAD:', time.time() - t0)

    # Joint capacity raise - L5MI - loads
    m.C_JOINT_CAPACITY_LOWER_L5MI_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=get_joint_capacity_lower_load_constraint('L5MI'))
    print('Finished constructing C_JOINT_CAPACITY_LOWER_L5MI_LOAD:', time.time() - t0)

    # Joint energy and regulating FCAS constraint - loads
    m.C_JOINT_REGULATING_RAISE_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=energy_regulating_raise_load_rule)
    print('Finished constructing C_JOINT_REGULATING_RAISE_LOAD:', time.time() - t0)

    # Joint energy and regulating FCAS constraint - loads
    m.C_JOINT_REGULATING_LOWER_LOAD = pyo.Constraint(
        m.S_TRADER_OFFERS, rule=energy_regulating_lower_load_rule)
    print('Finished constructing C_JOINT_REGULATING_RAISE_LOAD:', time.time() - t0)

    return m
