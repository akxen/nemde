"""Utilities to parse FCAS offers"""


def get_line_from_slope_and_x_intercept(slope, x_intercept):
    """Define line by its slope and x-intercept"""

    # y-intercept - set to None if slope undefined
    try:
        y_intercept = -slope * x_intercept
    except TypeError:
        y_intercept = None

    return {'slope': slope, 'y_intercept': y_intercept, 'x_intercept': x_intercept}


def get_intersection(line_1, line_2):
    """Get point of intersection between two lines"""

    # Case 0 - both lines are horizontal
    if (line_1['slope'] == 0) and (line_2['slope'] == 0):
        return None

    # Case 1 - both slopes are defined
    if (line_1['slope'] is not None) and (line_2['slope'] is not None):
        x = (line_2['y_intercept'] - line_1['y_intercept']) / (line_1['slope'] - line_2['slope'])
        y = (line_1['slope'] * x) + line_1['y_intercept']
        return x, y

    # Case 2 - line 1's slope is undefined, line 2's slope is defined
    elif (line_1['slope'] is None) and (line_2['slope'] is not None):
        x = line_1['x_intercept']
        y = (line_2['slope'] * x) + line_2['y_intercept']
        return x, y

    # Case 3 - line 1's slope is defined, line 2's slope is undefined
    elif (line_1['slope'] is not None) and (line_2['slope'] is None):
        x = line_2['x_intercept']
        y = (line_1['slope'] * x) + line_1['y_intercept']
        return x, y

    # Case 4 - both lines have undefined slopes - lines are either coincident or never intersect
    elif (line_1['slope'] is None) and (line_2['slope'] is None):
        return None

    else:
        raise Exception('Unhandled case')


def get_new_breakpoint(slope, x_intercept, max_available):
    """Compute new (lower/upper) breakpoint"""

    # Y-axis intercept
    try:
        y_intercept = -slope * x_intercept
        return (max_available - y_intercept) / slope

    # If line is vertical or horizontal, return original x-intercept
    except (TypeError, ZeroDivisionError):
        return x_intercept


def get_fcas_trapezium_offer(trader_id, trade_type):
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


def get_scaled_fcas_trapezium_agc_enablement_limits_lhs(trader_id, trapezium):
    """Compute scaled FCAS trapezium - taking into account minimum AGC enablement limit"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    # AGC enablement limits
    try:
        agc_enablement_min = data.get_trader_initial_condition_attribute(trader_id, 'LMW')
    except:
        agc_enablement_min = None

    if (agc_enablement_min is not None) and (agc_enablement_min > trap['enablement_min']):
        # Compute slope between enablement min and lower breakpoint
        try:
            lhs_slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
        except ZeroDivisionError:
            lhs_slope = None

        # Compute slope between high breakpoint and enablement max
        try:
            rhs_slope = - trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
        except ZeroDivisionError:
            rhs_slope = None

        # LHS line with new min enablement limit
        lhs_line = get_line_from_slope_and_x_intercept(lhs_slope, agc_enablement_min)

        # RHS line (original)
        rhs_line = get_line_from_slope_and_x_intercept(rhs_slope, trap['enablement_max'])

        # Intersection between LHS and RHS lines
        intersection = get_intersection(lhs_line, rhs_line)

        # Update max available if required
        if intersection[1] < trap['max_available']:
            trap['max_available'] = intersection[1]

        # New low breakpoint
        trap['low_breakpoint'] = get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'], trap['max_available'])

        # New high breakpoint
        trap['high_breakpoint'] = get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'], trap['max_available'])

        # Update enablement min
        trap['enablement_min'] = agc_enablement_min

    return trap


def get_scaled_fcas_trapezium_agc_enablement_limits_rhs(trader_id, trapezium):
    """Compute scaled FCAS trapezium - taking into account minimum AGC enablement limit"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    # AGC enablement limits
    try:
        agc_enablement_max = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')
    except:
        agc_enablement_max = None

    if (agc_enablement_max is not None) and (agc_enablement_max < trap['enablement_max']):
        # Compute slope between enablement min and lower breakpoint
        try:
            lhs_slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
        except ZeroDivisionError:
            lhs_slope = None

        # Compute slope between high breakpoint and enablement max
        try:
            rhs_slope = - trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
        except ZeroDivisionError:
            rhs_slope = None

        # LHS line (original)
        lhs_line = get_line_from_slope_and_x_intercept(lhs_slope, trap['enablement_min'])

        # RHS line with new min enablement limit
        rhs_line = get_line_from_slope_and_x_intercept(rhs_slope, agc_enablement_max)

        # Intersection between LHS and RHS lines
        intersection = get_intersection(lhs_line, rhs_line)

        # Update max available if required
        if (intersection is not None) and (intersection[1] < trap['max_available']):
            trap['max_available'] = intersection[1]

        # New low breakpoint
        trap['low_breakpoint'] = get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'], trap['max_available'])

        # New high breakpoint
        trap['high_breakpoint'] = get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'], trap['max_available'])

        # Update enablement min
        trap['enablement_max'] = agc_enablement_max

    return trap


def get_scaled_fcas_trapezium_agc_enablement_limits(trader_id, trapezium):
    """Compute scaled FCAS trapezium - taking into account AGC enablement limits"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    # Scale trapezium LHS and RHS
    trap = get_scaled_fcas_trapezium_agc_enablement_limits_lhs(trader_id, trap)
    trap = get_scaled_fcas_trapezium_agc_enablement_limits_rhs(trader_id, trap)

    return trap


def get_scaled_fcas_trapezium_agc_ramp_rates(trader_id, trade_type, trapezium):
    """FCAS trapezium taking into account AGC ramp rates"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    # AGC up and down ramp rates
    if trade_type == 'R5RE':
        try:
            agc_ramp = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate')
        except:
            return trap
    elif trade_type == 'L5RE':
        try:
            agc_ramp = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampDnRate')
        except:
            return trap
    else:
        raise Exception(f'Unexpected trade type: {trade_type}')

    # Max available
    max_available = min(trap['max_available'], agc_ramp / 12)

    if max_available < trap['max_available']:
        # Low breakpoint calculation
        try:
            slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
            trap['low_breakpoint'] = get_new_breakpoint(slope, trap['enablement_min'], max_available)
        except ZeroDivisionError:
            pass

        # High breakpoint calculation
        try:
            slope = -trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
            trap['high_breakpoint'] = get_new_breakpoint(slope, trap['enablement_max'], max_available)
        except ZeroDivisionError:
            pass

    # Update max available
    trap['max_available'] = max_available

    return trap


def get_scaled_fcas_trapezium_uigf(trader_id, trapezium):
    """Trapezium scaling for semi-scheduled units"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    # Try and get UIGF value if it exists for a given unit (only will exist for semi-scheduled units)
    try:
        uigf = self.data.get_trader_period_attribute(trader_id, 'UIGF')
    except TypeError:
        return trap

    if uigf < trap['enablement_max']:
        # High breakpoint calculation
        try:
            slope = -trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
            trap['high_breakpoint'] = get_new_breakpoint(slope, trap['enablement_max'], uigf)
        except ZeroDivisionError:
            pass

        # Update enablement max
        trap['enablement_max'] = uigf

    return trap


def get_scaled_fcas_trapezium(trader_id, trade_type):
    """Get scaled FCAS trapezium"""

    # Get unscaled FCAS offer
    trapezium_1 = dict(get_fcas_trapezium_offer(trader_id, trade_type))

    assert trade_type in ['R5RE', 'L5RE'], Exception(f'{trade_type}: can only scale regulating FCAS trapeziums')

    # Only scale regulating FCAS offers
    trapezium_2 = get_scaled_fcas_trapezium_agc_enablement_limits(trader_id, trapezium_1)
    trapezium_3 = get_scaled_fcas_trapezium_agc_ramp_rates(trader_id, trade_type, trapezium_2)
    trapezium_4 = get_scaled_fcas_trapezium_uigf(trader_id, trapezium_3)

    return trapezium_4
