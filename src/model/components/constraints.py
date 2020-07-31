"""Define constraints"""

import time

import pyomo.environ as pyo


def define_generic_constraints(m):
    """
    Construct generic constraints. Also include constraints linking pyo.Variables in objective function to pyo.Variables in
    Generic  pyo.Constraints.
    """

    def trader_variable_link_rule(m, i, j):
        """Link generic constraint trader pyo.Variables to objective function pyo.Variables"""

        return m.V_TRADER_TOTAL_OFFER[i, j] == m.V_GC_TRADER[i, j]

    # Link between total power output and quantity band output
    m.C_TRADER_VARIABLE_LINK = pyo.Constraint(m.S_GC_TRADER_VARS, rule=trader_variable_link_rule)

    def region_variable_link_rule(m, i, j):
        """Link total offer amount for each bid type to region pyo.Variables"""

        return (sum(m.V_TRADER_TOTAL_OFFER[q, r] for q, r in m.S_TRADER_OFFERS
                    # if (self.data.get_trader_period_attribute(q, 'RegionID') == i)
                    if (m.P_TRADER_REGION[q] == i)
                    and (r == j)) == m.V_GC_REGION[i, j])

    # Link between region pyo.Variables and the trader components constituting those pyo.Variables
    m.C_REGION_VARIABLE_LINK = pyo.Constraint(m.S_GC_REGION_VARS, rule=region_variable_link_rule)

    def mnsp_variable_link_rule(m, i):
        """Link generic constraint MNSP pyo.Variables to objective function pyo.Variables"""

        # From and to regions for a given MNSP
        # from_region = self.data.get_interconnector_period_attribute(i, 'FromRegion')
        from_region = m.P_INTERCONNECTOR_FROM_REGION[i]

        # to_region = self.data.get_interconnector_period_attribute(i, 'ToRegion')
        to_region = m.P_INTERCONNECTOR_TO_REGION[i]

        # TODO: Taking difference between 'to' and 'from' region. Think this is correct.
        return m.V_GC_INTERCONNECTOR[i] == m.V_MNSP_TOTAL_OFFER[i, to_region] - m.V_MNSP_TOTAL_OFFER[i, from_region]

    # Link between total power output and quantity band output
    m.C_MNSP_VARIABLE_LINK = pyo.Constraint(m.S_MNSPS, rule=mnsp_variable_link_rule)

    def generic_constraint_rule(m, c):
        """NEMDE Generic  pyo.Constraints"""

        # Type of generic constraint (LE, GE, EQ)
        # constraint_type = self.data.get_generic_constraint_attribute(c, 'Type')
        constraint_type = m.P_GENERIC_CONSTRAINT_TYPE[c]

        if constraint_type == 'LE':
            return m.E_LHS_TERMS[c] <= m.P_RHS[c] + m.V_CV[c]
        elif constraint_type == 'GE':
            return m.E_LHS_TERMS[c] + m.V_CV[c] >= m.P_RHS[c]
        elif constraint_type == 'EQ':
            return m.E_LHS_TERMS[c] + m.V_CV_LHS[c] == m.P_RHS[c] + m.V_CV_RHS[c]
        else:
            raise Exception(f'Unexpected constraint type: {constraint_type}')

    # Generic constraints
    m.C_GENERIC_CONSTRAINT = pyo.Constraint(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rule)

    return m


def define_offer_constraints(m):
    """Ensure trader and MNSP bids don't exceed their specified bid bands"""

    def trader_total_offer_rule(m, i, j):
        """Link quantity band offers to total offer made by trader for each offer type"""

        return m.V_TRADER_TOTAL_OFFER[i, j] == sum(m.V_TRADER_OFFER[i, j, k] for k in m.S_BANDS)

    # Linking individual quantity band offers to total amount offered by trader
    m.C_TRADER_TOTAL_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_total_offer_rule)

    def trader_offer_rule(m, i, j, k):
        """Band output must be non-negative and less than the max offered amount for that band"""

        return m.V_TRADER_OFFER[i, j, k] <= m.P_TRADER_QUANTITY_BAND[i, j, k] + m.V_CV_TRADER_OFFER[i, j, k]

    # Bounds on quantity band pyo.Variables for traders
    m.C_TRADER_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_rule)

    def trader_capacity_rule(m, i, j):
        """Constrain max available output"""

        return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_CAPACITY[i, j]

    # Ensure dispatch is constrained by max available offer amount
    m.C_TRADER_CAPACITY = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_capacity_rule)

    def mnsp_total_offer_rule(m, i, j):
        """Link quantity band offers to total offer made by MNSP for each offer type"""

        return m.V_MNSP_TOTAL_OFFER[i, j] == sum(m.V_MNSP_OFFER[i, j, k] for k in m.S_BANDS)

    # Linking individual quantity band offers to total amount offered by MNSP
    m.C_MNSP_TOTAL_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_total_offer_rule)

    def mnsp_offer_rule(m, i, j, k):
        """Band output must be non-negative and less than the max offered amount for that band"""

        return m.V_MNSP_OFFER[i, j, k] <= m.P_MNSP_QUANTITY_BAND[i, j, k] + m.V_CV_MNSP_OFFER[i, j, k]

    # Bounds on quantity band pyo.Variables for MNSPs
    m.C_MNSP_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_rule)

    def mnsp_capacity_rule(m, i, j):
        """Constrain max available output"""

        return m.V_MNSP_TOTAL_OFFER[i, j] <= m.P_MNSP_MAX_AVAILABLE[i, j] + m.V_CV_MNSP_CAPACITY[i, j]

    # Ensure dispatch is constrained by max available offer amount
    m.C_MNSP_CAPACITY = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_capacity_rule)

    return m


def define_unit_constraints(m):
    """Construct ramp rate constraints for units"""

    def trader_ramp_up_rate_rule(m, i, j):
        """Ramp up rate limit for ENOF and LDOF offers"""

        # Only construct ramp-rate constraint for energy offers
        if (j != 'ENOF') and (j != 'LDOF'):
            return pyo.Constraint.Skip

        # Ramp rate
        # ramp_limit = self.data.get_trader_quantity_band_attribute(i, j, 'RampUpRate')
        ramp_limit = m.P_TRADER_RAMP_UP_RATE[i]

        # Initial MW
        # initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')
        initial_mw = m.P_TRADER_INITIAL_MW[i]

        return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw <= (ramp_limit / 12) + m.V_CV_TRADER_RAMP_UP[i]

    # Ramp up rate limit
    m.C_TRADER_RAMP_UP_RATE = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_up_rate_rule)

    def trader_ramp_down_rate_rule(m, i, j):
        """Ramp down rate limit for ENOF and LDOF offers"""

        # Only construct ramp-rate constraint for energy offers
        if (j != 'ENOF') and (j != 'LDOF'):
            return pyo.Constraint.Skip

        # Ramp rate
        # ramp_limit = self.data.get_trader_quantity_band_attribute(i, j, 'RampDnRate')
        ramp_limit = m.P_TRADER_RAMP_DOWN_RATE[i]

        # Initial MW
        # initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')
        initial_mw = m.P_TRADER_INITIAL_MW[i]

        return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw + m.V_CV_TRADER_RAMP_DOWN[i] >= - (ramp_limit / 12)

    # Ramp up rate limit
    m.C_TRADER_RAMP_DOWN_RATE = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_down_rate_rule)

    return m


def define_region_constraints(m):
    """Define power balance constraint for each region, and constrain flows on interconnectors"""

    def power_balance_rule(m, r):
        """Power balance for each region"""

        return (m.E_REGION_GENERATION[r]
                ==
                m.E_REGION_DEMAND[r]
                + m.E_REGION_LOAD[r]
                + m.E_REGION_NET_EXPORT_FLOW[r]
                )

    # Power balance in each region
    m.C_POWER_BALANCE = pyo.Constraint(m.S_REGIONS, rule=power_balance_rule)

    return m


def define_interconnector_constraints(m):
    """Define power flow limits on interconnectors"""

    def interconnector_forward_flow_rule(m, i):
        """Constrain forward power flow over interconnector"""

        # return (m.V_GC_INTERCONNECTOR[i] <= self.data.get_interconnector_period_attribute(i, 'UpperLimit')
        #         + m.V_CV_INTERCONNECTOR_FORWARD[i])

        return m.V_GC_INTERCONNECTOR[i] <= m.P_INTERCONNECTOR_UPPER_LIMIT[i] + m.V_CV_INTERCONNECTOR_FORWARD[i]

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_FORWARD_FLOW = pyo.Constraint(m.S_INTERCONNECTORS, rule=interconnector_forward_flow_rule)

    def interconnector_reverse_flow_rule(m, i):
        """Constrain reverse power flow over interconnector"""

        # return (m.V_GC_INTERCONNECTOR[i] + m.V_CV_INTERCONNECTOR_REVERSE[i]
        #         >= - self.data.get_interconnector_period_attribute(i, 'LowerLimit'))

        return m.V_GC_INTERCONNECTOR[i] + m.V_CV_INTERCONNECTOR_REVERSE[i] >= - m.P_INTERCONNECTOR_LOWER_LIMIT[i]

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_REVERSE_FLOW = pyo.Constraint(m.S_INTERCONNECTORS, rule=interconnector_reverse_flow_rule)

    def from_node_connection_point_balance_rule(m, i):
        """Power balance at from node connection point"""

        # # Loss share applied to from node connection point
        # loss_share = self.data.get_interconnector_loss_model_attribute(i, 'LossShare')
        #
        # return m.V_FLOW_FROM_CP[i] - (loss_share * m.V_LOSS[i]) - m.V_GC_INTERCONNECTOR[i] == 0

        return m.V_FLOW_FROM_CP[i] - (m.P_INTERCONNECTOR_LOSS_SHARE[i] * m.V_LOSS[i]) - m.V_GC_INTERCONNECTOR[i] == 0

    # From node connection point power balance
    m.C_FROM_NODE_CP_POWER_BALANCE = pyo.Constraint(m.S_INTERCONNECTORS,
                                                    rule=from_node_connection_point_balance_rule)

    def to_node_connection_point_balance_rule(m, i):
        """Power balance at to node connection point"""

        # Loss share applied to from node connection point
        # loss_share = 1 - self.data.get_interconnector_loss_model_attribute(i, 'LossShare')
        loss_share = 1 - m.P_INTERCONNECTOR_LOSS_SHARE[i]

        return m.V_GC_INTERCONNECTOR[i] - (loss_share * m.V_LOSS[i]) - m.V_FLOW_TO_CP[i] == 0

    # To node connection point power balance
    m.C_TO_NODE_CP_POWER_BALANCE = pyo.Constraint(m.S_INTERCONNECTORS, rule=to_node_connection_point_balance_rule)

    return m


def get_fcas_trapezium_offer(self, trader_id, trade_type):
    """Get FCAS trapezium offer for a given trader and trade type"""

    # Trapezium information
    enablement_min = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMin')
    enablement_max = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMax')
    low_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'LowBreakpoint')
    high_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'HighBreakpoint')
    max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

    # Store FCAS trapezium information in a dictionary
    trapezium = {'enablement_min': enablement_min, 'enablement_max': enablement_max, 'max_available': max_available,
                 'low_breakpoint': low_breakpoint, 'high_breakpoint': high_breakpoint}

    return trapezium


def get_fcas_trapezium_scaled_enablement_min(self, trader_id, trapezium):
    """Scale enablement min for regulating service"""

    # Get AGC enablement min
    try:
        agc_min = self.data.get_trader_initial_condition_attribute(trader_id, 'LMW')

    # No scaling applied if AGC enablement min not specified (from FCAS docs)
    except AssertionError:
        return trapezium

    # Difference between AGC enablement and offer enablement min
    offset = agc_min - trapezium['enablement_min']

    # If AGC min is more restrictive update the enablement and lower breakpoint
    if offset > 0:
        trapezium['low_breakpoint'] = trapezium['low_breakpoint'] + offset
        trapezium['enablement_min'] = agc_min

    return trapezium


def get_fcas_trapezium_scaled_enablement_max(self, trader_id, trapezium):
    """Scale enablement max for regulating service"""

    # Get AGC enablement max
    try:
        agc_max = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')

    # No scaling applied if AGC enablement min not specified (from FCAS docs)
    except AssertionError:
        return trapezium

    # Difference between AGC enablement and offer enablement min
    offset = trapezium['enablement_max'] - agc_max

    # If AGC min is more restrictive update the enablement and lower breakpoint
    if offset > 0:
        trapezium['high_breakpoint'] = trapezium['high_breakpoint'] - offset
        trapezium['enablement_max'] = agc_max

    return trapezium


def get_trapezium_lhs_slope(trapezium):
    """Get slope on LHS of trapezium. Return None if slope is undefined."""

    try:
        return trapezium['max_available'] / (trapezium['low_breakpoint'] - trapezium['enablement_min'])
    except ZeroDivisionError:
        return None


def get_trapezium_rhs_slope(trapezium):
    """Get slope on RHS of trapezium. Return None if slope is undefined."""

    try:
        return -trapezium['max_available'] / (trapezium['enablement_max'] - trapezium['high_breakpoint'])
    except ZeroDivisionError:
        return None


def get_fcas_trapezium_scaled_agc_max_available(self, trader_id, trade_type, trapezium):
    """Scale max availability using AGC ramp rates"""

    # Try and get AGC ramp rate. Set to 0 if not found (will not perform scaling if ramp rate missing or = 0)
    try:
        if trade_type == 'R5RE':
            ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate') / 12
        elif trade_type == 'L5RE':
            ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampDnRate') / 12
        else:
            raise Exception(f'Should only scale FCAS trapezium for L5RE and R5RE offers. Encountered: {trade_type}')

    except AssertionError:
        ramp_rate = 0

    # Return unscaled trapezium if AGC ramp rate = 0 or missing (from FCAS NEMDE docs)
    if ramp_rate == 0:
        return trapezium

    # Update max available if AGC ramp rate is more restrictive
    if ramp_rate < trapezium['max_available']:
        lhs_slope = self.get_trapezium_lhs_slope(trapezium)
        rhs_slope = self.get_trapezium_rhs_slope(trapezium)

        trapezium['max_available'] = ramp_rate

        if lhs_slope is not None:
            trapezium['low_breakpoint'] = trapezium['enablement_min'] + (ramp_rate / lhs_slope)

        if rhs_slope is not None:
            trapezium['high_breakpoint'] = trapezium['enablement_max'] - (ramp_rate / rhs_slope)

    return trapezium


def get_fcas_trapezium_scaled_uigf_max_available(self, trader_id, trapezium):
    """For semi-scheduled units, scale all FCAS max available offers by UIGF if UIGF more restrictive"""

    # Get UIGF value
    uigf = self.data.get_trader_period_attribute(trader_id, 'UIGF')

    # Slope on left side of trapezium (positive slope)
    lhs_slope = self.get_trapezium_lhs_slope(trapezium)
    rhs_slope = self.get_trapezium_rhs_slope(trapezium)

    # Offset between max available and UIGF
    offset = trapezium['max_available'] - uigf

    # Must restrict max available to UIGF if max available offer > UIGF. Adjust breakpoints accordingly.
    if offset > 0:
        trapezium['max_available'] = uigf

        if lhs_slope is not None:
            trapezium['low_breakpoint'] = trapezium['low_breakpoint'] - (lhs_slope * offset)

        if rhs_slope is not None:
            trapezium['high_breakpoint'] = trapezium['high_breakpoint'] - (rhs_slope * offset)

    return trapezium


def get_scaled_fcas_trapezium(self, trader_id, trade_type):
    """
    Scale FCAS trapezium using AGC enablement min (if more restrictive than offer enablement min).

    Note: trapezium scaling only applied to contingency services
    """

    # Trapezium scaling only applied to regulation services
    assert trade_type in ['R5RE', 'L5RE']

    # Get FCAS trapezium offer information
    trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

    # Regulating services - AGC enablement min (return scaled trapezium)
    trapezium = self.get_fcas_trapezium_scaled_enablement_min(trader_id, trapezium)

    # Regulating services - AGC enablement max (return scaled trapezium)
    trapezium = self.get_fcas_trapezium_scaled_enablement_max(trader_id, trapezium)

    # Regulating services - AGC ramp rates (return scaled trapezium) - no scaling if AGC ramp rate is zero of absent
    trapezium = self.get_fcas_trapezium_scaled_agc_max_available(trader_id, trade_type, trapezium)

    # Regulating services - UIGF for FCAS from semi-scheduled units (effective max enablement if more restrictive)
    semi_dispatch = self.data.get_trader_attribute(trader_id, 'SemiDispatch')
    if semi_dispatch == 1:
        trapezium = self.get_fcas_trapezium_scaled_uigf_max_available(trader_id, trapezium)

    return trapezium


def check_fcas_max_availability(self, trader_id, trade_type):
    """Check if max availability amount is greater than 0"""

    # Scaled FCAS trapezium for regulation offers
    if trade_type in ['R5RE', 'L5RE']:
        trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)

    # No scaling applied to contingency offers
    else:
        trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

    return trapezium['max_available'] > 0


def check_fcas_positive_offer(self, trader_id, trade_type):
    """Check that at least one price band has capacity greater than 0"""

    # Quantities within each band for the offer type
    quantities = [self.data.get_trader_quantity_band_attribute(trader_id, trade_type, f'BandAvail{i}') for
                  i in range(1, 11)]

    # Check if at least one band has a capacity greater than 0
    return max(quantities) > 0


def check_fcas_energy_enablement_min(self, trader_id, trade_type):
    """Check that max energy available exceeds the enablement min"""

    # Scaled FCAS trapezium
    if trade_type in ['R5RE', 'L5RE']:
        trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)
    else:
        trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

    # Energy max availability
    max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

    return max_available >= trapezium['max_available']


def check_fcas_enablement_max(self, trader_id, trade_type):
    """Check FCAS max availability greater than or equal to 0"""

    # Scaled FCAS trapezium
    if trade_type in ['R5RE', 'L5RE']:
        trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)
    else:
        trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

    return trapezium['enablement_max'] >= 0


def check_fcas_initial_mw(self, trader_id, trade_type):
    """Check that initial MW is between the enablement max and min limits"""

    # Scaled FCAS trapezium
    if trade_type in ['R5RE', 'L5RE']:
        trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)
    else:
        trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

    # Initial MW
    initial_mw = self.data.get_trader_initial_condition_attribute(trader_id, 'InitialMW')

    return trapezium['enablement_min'] <= initial_mw <= trapezium['enablement_max']


def check_fcas_preconditions(self, trader_id, trade_type):
    """Check pre-conditions for FCAS. Only construct constraints if conditions met."""

    # Check that max FCAS availability for offer type is greater than 0
    cond_1 = self.check_fcas_max_availability(trader_id, trade_type)

    # Check that at least one offer price band contains a capacity greater than 0
    cond_2 = self.check_fcas_positive_offer(trader_id, trade_type)

    # Check that energy availability is greater than enablement min for offer type
    cond_3 = self.check_fcas_energy_enablement_min(trader_id, trade_type)

    # Check that FCAS enablement maximum is greater than or equal to 0
    cond_4 = self.check_fcas_enablement_max(trader_id, trade_type)

    # Check that unit initially operating between enablement min and max levels
    cond_5 = self.check_fcas_initial_mw(trader_id, trade_type)

    # Check FCAS preconditions. Note: doesn't include AGC status condition
    fcas_available = cond_1 and cond_2 and cond_3 and cond_4 and cond_5

    return fcas_available


def check_trader_has_energy_offer(self, trader_id, m):
    """Check if a unit has an energy offer"""

    # Get trader type
    trader_type = self.data.get_trader_attribute(trader_id, 'TraderType')

    if trader_type == 'GENERATOR':
        energy_key = 'ENOF'
    elif (trader_type == 'LOAD') or (trader_type == 'NORMALLY_ON_LOAD'):
        energy_key = 'LDOF'
    else:
        raise Exception(f'Unexpected trader type: {trader_type}')

    # Check if energy offer made by generator
    if (trader_id, energy_key) in m.S_TRADER_OFFERS:
        return True
    else:
        return False


def get_slope(x1, x2, y1, y2):
    """Compute slope. Return None if slope is undefined"""

    try:
        return (y2 - y1) / (x2 - x1)
    except ZeroDivisionError:
        return None


def get_intercept(slope, x0, y0):
    """Get y-axis intercept given slope and point"""

    return y0 - (slope * x0)


def get_fcas_availability(self, trader_id, trade_type):
    """Check FCAS availability"""

    # FCAS trapezium
    if trade_type in ['R5RE', 'L5RE']:
        trapezium = self.fcas.get_scaled_fcas_trapezium(trader_id, trade_type)
    else:
        trapezium = self.fcas.get_fcas_trapezium_offer(trader_id, trade_type)

    # Max availability must be greater than 0
    cond_1 = trapezium['max_available'] > 0

    # Quantity greater than 0 for at least one quantity band for the given service
    cond_2 = (max([self.data.get_trader_quantity_band_attribute(trader_id, trade_type, f'BandAvail{i}')
                   for i in range(1, 11)])
              > 0)

    # TODO: Need to handle traders without energy offers
    # Try and get max available for energy offers
    try:
        max_avail = self.data.get_trader_quantity_band_attribute(trader_id, 'ENOF', 'MaxAvail')
    except AttributeError:
        pass

    # Try and get max available for load offers
    try:
        max_avail = self.data.get_trader_quantity_band_attribute(trader_id, 'LDOF', 'MaxAvail')
    except AttributeError:
        pass

    # Try and use specified FCAS condition, but if energy offer doesn't exist, then set cond_3=True by default
    try:
        cond_3 = max_avail >= trapezium['enablement_min']
    except NameError:
        cond_3 = True

    # cond_3 = max_avail >= trapezium['enablement_min']

    # FCAS enablement max >= 0
    cond_4 = trapezium['enablement_max'] >= 0

    # Initial MW within enablement min and max
    cond_5 = (trapezium['enablement_min']
              <= self.data.get_trader_initial_condition_attribute(trader_id, 'InitialMW')
              <= trapezium['enablement_max'])

    # AGC is activate for regulating FCAS
    if trade_type in ['R5RE', 'L5RE']:
        agc_status = self.data.get_trader_initial_condition_attribute(trader_id, 'AGCStatus')
        if agc_status == 1:
            cond_6 = True
        else:
            cond_6 = False
    else:
        # Set cond_6 to True if non-regulating FCAS offer
        cond_6 = True

    return all([cond_1, cond_2, cond_3, cond_4, cond_5, cond_6])


def define_fcas_constraints(self, m):
    """FCAS constraints"""

    # Get FCAS availability for each unit and offer type (run once and store result in dictionary)
    fcas_availability = {(i, j): self.get_fcas_availability(i, j) for i, j in m.S_TRADER_OFFERS
                         if j not in ['ENOF', 'LDOF']}

    # Start timer
    t0 = time.time()

    def fcas_available_rule(m, i, j):
        """Set FCAS to zero if conditions not met"""

        if j in ['ENOF', 'LDOF']:
            return pyo.Constraint.Skip

        # Check energy output in previous interval within enablement minutes (else trapped outside trapezium)
        # if not self.get_fcas_availability(i, j):
        if not fcas_availability[(i, j)]:
            # Set FCAS to 0 if unavailable
            return m.V_TRADER_TOTAL_OFFER[i, j] == 0
        else:
            return pyo.Constraint.Skip

    # FCAS availability
    m.C_FCAS_AVAILABILITY_RULE = pyo.Constraint(m.S_TRADER_OFFERS, rule=fcas_available_rule)
    print('Finished constructing C_FCAS_AVAILABILITY_RULE:', time.time() - t0)

    def as_profile_1_rule(m, i, j):
        """ pyo.Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

        # Only consider FCAS offers - ignore energy offers
        if j in ['ENOF', 'LDOF']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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

    # AS profile constraint - between enablement min and low breakpoint
    m.C_AS_PROFILE_1 = pyo.Constraint(m.S_TRADER_OFFERS, rule=as_profile_1_rule)
    print('Finished constructing C_AS_PROFILE_1:', time.time() - t0)

    def as_profile_2_rule(m, i, j):
        """Top of FCAS trapezium"""

        # Only consider FCAS offers - ignore energy offers
        if j in ['ENOF', 'LDOF']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
        if not fcas_availability[(i, j)]:
            return pyo.Constraint.Skip

        # Get FCAS trapezium
        if j in ['R5RE', 'L5RE']:
            trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)
        else:
            trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

        # Ensure FCAS is less than max FCAS available
        return m.V_TRADER_TOTAL_OFFER[i, j] <= trapezium['max_available'] + m.V_CV_TRADER_FCAS_AS_PROFILE_2[i, j]

    # AS profile constraint - between enablement min and low breakpoint
    m.C_AS_PROFILE_2 = pyo.Constraint(m.S_TRADER_OFFERS, rule=as_profile_2_rule)
    print('Finished constructing C_AS_PROFILE_2:', time.time() - t0)

    def as_profile_3_rule(m, i, j):
        """ pyo.Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

        # Only consider FCAS offers - ignore energy offers
        if j in ['ENOF', 'LDOF']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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

    # AS profile constraint - between enablement min and low breakpoint
    m.C_AS_PROFILE_3 = pyo.Constraint(m.S_TRADER_OFFERS, rule=as_profile_3_rule)
    print('Finished constructing C_AS_PROFILE_3:', time.time() - t0)

    def joint_ramp_up_rule(m, i, j):
        """Joint ramping constraint for regulating FCAS"""

        # Only consider raise regulation FCAS offers
        if not (j == 'R5RE'):
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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

    # Joint ramp up constraint
    m.C_JOINT_RAMP_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_up_rule)
    print('Finished constructing C_JOINT_RAMP_UP:', time.time() - t0)

    def joint_ramp_down_rule(m, i, j):
        """Joint ramping constraint for regulating FCAS"""

        # Only consider lower regulation FCAS offers
        if not (j == 'L5RE'):
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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

    # Joint ramp up constraint
    m.C_JOINT_RAMP_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_ramp_down_rule)
    print('Finished constructing C_JOINT_RAMP_DOWN:', time.time() - t0)

    def joint_capacity_up_rule(m, i, j):
        """Joint capacity constraint for raise regulation services and contingency FCAS"""

        # Only consider contingency FCAS offers
        if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            # if j not in ['R6SE', 'R60S', 'R5MI']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
        if not fcas_availability[(i, j)]:
            return pyo.Constraint.Skip

        # Get FCAS trapezium
        trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

        # Check if raise regulation FCAS available for unit
        # TODO: Check what needs to be done if raise regulating FCAS offer missing. Assuming no constraint.
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

            # return  pyo.Constraint.Skip
        except:
            return pyo.Constraint.Skip

    # Joint capacity constraint up
    m.C_JOINT_CAPACITY_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_capacity_up_rule)
    print('Finished constructing C_JOINT_CAPACITY_UP:', time.time() - t0)

    def joint_capacity_down_rule(m, i, j):
        """Joint capacity constraint for lower regulation services and contingency FCAS"""

        # Only consider contingency FCAS offers
        if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            # if j not in ['L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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
            # return  pyo.Constraint.Skip
        except:
            return pyo.Constraint.Skip

    # Joint capacity constraint down
    m.C_JOINT_CAPACITY_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=joint_capacity_down_rule)
    print('Finished constructing C_JOINT_CAPACITY_DOWN:', time.time() - t0)

    def energy_regulating_up_rule(m, i, j):
        """Joint energy and regulating FCAS constraints"""

        # Only consider contingency FCAS offers
        if j not in ['R5RE', 'L5RE']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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

    # Joint energy and regulating FCAS constraint
    m.C_JOINT_REGULATING_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=energy_regulating_up_rule)
    print('Finished constructing C_JOINT_REGULATING_UP:', time.time() - t0)

    def energy_regulating_down_rule(m, i, j):
        """Joint energy and regulating FCAS constraints"""

        # Only consider contingency FCAS offers
        if j not in ['R5RE', 'L5RE']:
            return pyo.Constraint.Skip

        # Check FCAS is available
        # if not self.get_fcas_availability(i, j):
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

    # Joint energy and regulating FCAS constraint
    m.C_JOINT_REGULATING_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=energy_regulating_down_rule)
    print('Finished constructing C_JOINT_REGULATING_DOWN:', time.time() - t0)

    return m


def define_loss_model_constraints(m):
    """Interconnector loss model constraints"""

    def approximated_loss_rule(m, i):
        """Approximate interconnector loss"""

        return (m.V_LOSS[i] == sum(m.P_LOSS_MODEL_BREAKPOINTS_Y[i, j] * m.V_LOSS_LAMBDA[i, j]
                                   for j in m.S_INTERCONNECTOR_BREAKPOINTS[i])
                )

    # Approximate loss over interconnector
    m.C_APPROXIMATED_LOSS = pyo.Constraint(m.S_INTERCONNECTORS, rule=approximated_loss_rule)

    def sos2_condition_1_rule(m, i):
        """SOS2 condition 1"""

        return (m.V_GC_INTERCONNECTOR[i] == sum(m.P_LOSS_MODEL_BREAKPOINTS_X[i, j] * m.V_LOSS_LAMBDA[i, j]
                                                for j in m.S_INTERCONNECTOR_BREAKPOINTS[i]))

    # SOS2 condition 1
    m.C_SOS2_CONDITION_1 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_1_rule)

    def sos2_condition_2_rule(m, i):
        """SOS2 condition 2"""

        return sum(m.V_LOSS_LAMBDA[i, j] for j in m.S_INTERCONNECTOR_BREAKPOINTS[i]) == 1

    # SOS2 condition 2
    m.C_SOS2_CONDITION_2 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_2_rule)

    def sos2_condition_3_rule(m, i):
        """SOS2 condition 3"""

        return sum(m.V_LOSS_Y[i, j] for j in m.S_INTERCONNECTOR_INTERVALS[i]) == 1

    # SOS2 condition 3
    m.C_SOS2_CONDITION_3 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_3_rule)

    def sos2_condition_4_rule(m, i, j):
        """SOS2 condition 4"""

        end = max(m.S_INTERCONNECTOR_BREAKPOINTS[i])

        if (j >= 2) and (j <= end - 1):
            return (sum(m.V_LOSS_Y[i, z] for z in range(j + 1, end))
                    <= sum(m.V_LOSS_LAMBDA[i, z] for z in range(j + 1, end + 1)))
        else:
            return pyo.Constraint.Skip

    # SOS2 condition 4
    m.C_SOS2_CONDITION_4 = pyo.Constraint(m.S_BREAKPOINTS, rule=sos2_condition_4_rule)

    def sos2_condition_5_rule(m, i, j):
        """SOS2 condition 5"""

        end = max(m.S_INTERCONNECTOR_BREAKPOINTS[i])

        if (j >= 2) and (j <= end - 1):
            return (sum(m.V_LOSS_LAMBDA[i, z] for z in range(j + 1, end + 1))
                    <= sum(m.V_LOSS_Y[i, z] for z in range(j, end)))
        else:
            return pyo.Constraint.Skip

    # SOS2 condition 5
    m.C_SOS2_CONDITION_5 = pyo.Constraint(m.S_BREAKPOINTS, rule=sos2_condition_5_rule)

    def sos2_condition_6_rule(m, i, j):
        """SOS2 condition 6"""

        end = max(m.S_INTERCONNECTOR_BREAKPOINTS[i])

        if j == 1:
            return m.V_LOSS_LAMBDA[i, j] <= m.V_LOSS_Y[i, j]
            # return  pyo.Constraint.Skip
        elif j == end:
            return m.V_LOSS_LAMBDA[i, j] <= m.V_LOSS_Y[i, j - 1]
        else:
            return pyo.Constraint.Skip

    # SOS2 condition 6
    m.C_SOS2_CONDITION_6 = pyo.Constraint(m.S_BREAKPOINTS, rule=sos2_condition_6_rule)

    return m
