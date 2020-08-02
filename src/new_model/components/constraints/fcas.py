"""FCAS constraints"""

import time

import pyomo.environ as pyo


def fcas_available_rule(m, i, j):
    """Set FCAS to zero if conditions not met"""

    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check energy output in previous interval within enablement minutes (else trapped outside trapezium)
    if not fcas_availability[(i, j)]:
        # Set FCAS to 0 if unavailable
        return m.V_TRADER_TOTAL_OFFER[i, j] == 0
    else:
        return pyo.Constraint.Skip


def as_profile_1_rule(m, i, j):
    """Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    if j in ['R5RE', 'L5RE']:
        trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)
    else:
        trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

    # Get slope between enablement min and low breakpoint
    x1, y1 = trapezium['enablement_min'], 0
    x2, y2 = trapezium['low_breakpoint'], trapezium['max_available']
    slope = self.get_slope(x1, x2, y1, y2)

    if slope is not None:
        y_intercept = self.get_intercept(slope, x1, y1)
        try:
            return (m.V_TRADER_TOTAL_OFFER[i, j] <= slope * m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + y_intercept
                    + m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j]
                    )

        except KeyError:
            return (m.V_TRADER_TOTAL_OFFER[i, j] <= slope * m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + y_intercept
                    + m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j]
                    )

    else:
        # TODO: need to consider if vertical line
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= trapezium['max_available']
                + m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j])


def as_profile_2_rule(m, i, j):
    """Top of FCAS trapezium"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    if j in ['R5RE', 'L5RE']:
        trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)
    else:
        trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

    # Ensure FCAS is less than max FCAS available
    return m.V_TRADER_TOTAL_OFFER[i, j] <= trapezium['max_available'] + m.V_CV_TRADER_FCAS_AS_PROFILE_2[i, j]


def as_profile_3_rule(m, i, j):
    """Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

    # Only consider FCAS offers - ignore energy offers
    if j in ['ENOF', 'LDOF']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    if j in ['R5RE', 'L5RE']:
        trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)
    else:
        trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

    # Get slope between enablement min and low breakpoint
    x1, y1 = trapezium['high_breakpoint'], trapezium['max_available']
    x2, y2 = trapezium['enablement_max'], 0
    slope = self.get_slope(x1, x2, y1, y2)

    if slope is not None:
        y_intercept = self.get_intercept(slope, x1, y1)
        try:
            return (m.V_TRADER_TOTAL_OFFER[i, j] <= slope * m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + y_intercept
                    + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])

        except KeyError:
            return (m.V_TRADER_TOTAL_OFFER[i, j] <= slope * m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + y_intercept
                    + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])

    else:
        # TODO: need to consider if vertical line
        return (m.V_TRADER_TOTAL_OFFER[i, j] <= trapezium['max_available']
                + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])


def joint_ramp_up_rule(m, i, j):
    """Joint ramping constraint for regulating FCAS"""

    # Only consider raise regulation FCAS offers
    if not (j == 'R5RE'):
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampUpRate is MW/h)
    scada_ramp = self.data.get_trader_initial_condition_attribute(i, 'SCADARampUpRate') / 12

    # TODO: Check what to do if no SCADARampUpRate
    if (not scada_ramp) or (scada_ramp <= 0):
        return pyo.Constraint.Skip

    # Initial MW
    initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + m.V_TRADER_TOTAL_OFFER[i, 'R5RE'] <= initial_mw + scada_ramp
                + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])

    # TODO: check structure of constraint when considering loads
    except:
        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + m.V_TRADER_TOTAL_OFFER[i, 'L5RE'] <= initial_mw + scada_ramp
                + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])


def joint_ramp_down_rule(m, i, j):
    """Joint ramping constraint for regulating FCAS"""

    # Only consider lower regulation FCAS offers
    if not (j == 'L5RE'):
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # SCADA ramp-up - divide by 12 to get max ramp over 5 minutes (assuming SCADARampDnRate is MW/h)
    scada_ramp = self.data.get_trader_initial_condition_attribute(i, 'SCADARampDnRate') / 12

    # TODO: Check what to do if no SCADARampUpRate
    if (not scada_ramp) or (scada_ramp <= 0):
        return pyo.Constraint.Skip

    # Initial MW
    initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
                + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j] >= initial_mw - scada_ramp)

    # TODO: check structure of constraint when considering loads
    except:
        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
                + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j] >= initial_mw - scada_ramp)


def joint_capacity_up_rule(m, i, j):
    """Joint capacity constraint for raise regulation services and contingency FCAS"""

    # Only consider contingency FCAS offers
    if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # if j not in ['R6SE', 'R60S', 'R5MI']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

    # Check if raise regulation FCAS available for unit
    try:
        raise_available = int(self.get_fcas_availability(i, 'R5RE'))
    except:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = (trapezium['enablement_max'] - trapezium['high_breakpoint']) / trapezium['max_available']

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                + (raise_available * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
                <= trapezium['enablement_max'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])
    except:
        pass

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                + (raise_available * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
                <= trapezium['enablement_max'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])

    except:
        return pyo.Constraint.Skip


def joint_capacity_down_rule(m, i, j):
    """Joint capacity constraint for lower regulation services and contingency FCAS"""

    # Only consider contingency FCAS offers
    if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # if j not in ['L6SE', 'L60S', 'L5MI']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

    # """Energy Dispatch Target − Lower Slope Coeff × Contingency FCAS Target
    # − [Lower Regulation FCAS enablment status] × Lower Regulating FCAS Target
    # ≥ EnablementMin7
    # """

    # Check if raise regulation FCAS available for unit
    # TODO: Check what needs to be done if raise regulating FCAS offer missing. Assuming no constraint.
    try:
        lower_available = int(self.get_fcas_availability(i, 'L5RE'))
    except:
        return pyo.Constraint.Skip

    # Slope coefficient
    coefficient = (trapezium['low_breakpoint'] - trapezium['enablement_min']) / trapezium['max_available']

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                - (lower_available * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
                + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j] >= trapezium['enablement_min'])
    except:
        pass

    # TODO: Check if LDOF should have positive or negative coefficient
    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                - (lower_available * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
                + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j] >= trapezium['enablement_min'])
    except:
        return pyo.Constraint.Skip


def energy_regulating_up_rule(m, i, j):
    """Joint energy and regulating FCAS constraints"""

    # Only consider contingency FCAS offers
    if j not in ['R5RE', 'L5RE']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)

    # Slope coefficient
    coefficient = (trapezium['enablement_max'] - trapezium['high_breakpoint']) / trapezium['max_available']

    # """Energy Dispatch Target + Upper Slope Coeff × Regulating FCAS Target ≤ EnablementMax8"""

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                <= trapezium['enablement_max'])
    except:
        pass

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                <= trapezium['enablement_max'])
    except:
        return pyo.Constraint.Skip


def energy_regulating_down_rule(m, i, j):
    """Joint energy and regulating FCAS constraints"""

    # Only consider contingency FCAS offers
    if j not in ['R5RE', 'L5RE']:
        return pyo.Constraint.Skip

    # Check FCAS is available
    if not fcas_availability[(i, j)]:
        return pyo.Constraint.Skip

    # Get FCAS trapezium
    trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)

    # Slope coefficient
    coefficient = (trapezium['low_breakpoint'] - trapezium['enablement_min']) / trapezium['max_available']

    # Energy Dispatch Target − Lower Slope Coeff × Regulating FCAS Target ≥ EnablementMin

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                >= trapezium['enablement_min'])
    except:
        pass

    try:
        return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                >= trapezium['enablement_min'])
    except:
        return pyo.Constraint.Skip


def define_fcas_constraints(self, m):
    """FCAS constraints"""

    # Get FCAS availability for each unit and offer type (run once and store result in dictionary)
    fcas_availability = {(i, j): self.get_fcas_availability(i, j) for i, j in m.S_TRADER_OFFERS
                         if j not in ['ENOF', 'LDOF']}

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
