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


def get_scaled_fcas_trapezium_agc_enablement_limits_lhs(trapezium, agc_enablement_min):
    """Compute scaled FCAS trapezium - taking into account minimum AGC enablement limit"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    if (agc_enablement_min is not None) and (agc_enablement_min > trap['EnablementMin']):
        # Compute slope between enablement min and lower breakpoint
        try:
            lhs_slope = trap['MaxAvail'] / (trap['LowBreakpoint'] - trap['EnablementMin'])
        except ZeroDivisionError:
            lhs_slope = None

        # Compute slope between high breakpoint and enablement max
        try:
            rhs_slope = - trap['MaxAvail'] / (trap['EnablementMax'] - trap['HighBreakpoint'])
        except ZeroDivisionError:
            rhs_slope = None

        # LHS line with new min enablement limit
        lhs_line = get_line_from_slope_and_x_intercept(lhs_slope, agc_enablement_min)

        # RHS line (original)
        rhs_line = get_line_from_slope_and_x_intercept(rhs_slope, trap['EnablementMax'])

        # Intersection between LHS and RHS lines
        intersection_x, intersection_y = get_intersection(lhs_line, rhs_line)

        # Update max available if required
        if intersection_y < trap['MaxAvail']:
            trap['MaxAvail'] = intersection_y

        # New low breakpoint
        trap['LowBreakpoint'] = get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'], trap['MaxAvail'])

        # New high breakpoint
        trap['HighBreakpoint'] = get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'], trap['MaxAvail'])

        # Update enablement min
        trap['EnablementMin'] = agc_enablement_min

    return trap


def get_scaled_fcas_trapezium_agc_enablement_limits_rhs(trapezium, agc_enablement_max):
    """Compute scaled FCAS trapezium - taking into account minimum AGC enablement limit"""

    # Input FCAS trapezium
    trap = dict(trapezium)

    if (agc_enablement_max is not None) and (agc_enablement_max < trap['EnablementMax']):
        # Compute slope between enablement min and lower breakpoint
        try:
            lhs_slope = trap['MaxAvail'] / (trap['LowBreakpoint'] - trap['EnablementMin'])
        except ZeroDivisionError:
            lhs_slope = None

        # Compute slope between high breakpoint and enablement max
        try:
            rhs_slope = - trap['MaxAvail'] / (trap['EnablementMax'] - trap['HighBreakpoint'])
        except ZeroDivisionError:
            rhs_slope = None

        # LHS line (original)
        lhs_line = get_line_from_slope_and_x_intercept(lhs_slope, trap['EnablementMin'])

        # RHS line with new min enablement limit
        rhs_line = get_line_from_slope_and_x_intercept(rhs_slope, agc_enablement_max)

        # Intersection between LHS and RHS lines
        intersection = get_intersection(lhs_line, rhs_line)

        # Update max available if required
        if (intersection is not None) and (intersection[1] < trap['MaxAvail']):
            trap['MaxAvail'] = intersection[1]

        # New low breakpoint
        trap['LowBreakpoint'] = get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'], trap['MaxAvail'])

        # New high breakpoint
        trap['HighBreakpoint'] = get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'], trap['MaxAvail'])

        # Update enablement min
        trap['EnablementMax'] = agc_enablement_max

    return trap

# def get_scaled_fcas_trapezium_agc_enablement_limits(trader_id, trapezium):
#     """Compute scaled FCAS trapezium - taking into account AGC enablement limits"""
#
#     # Input FCAS trapezium
#     trap = dict(trapezium)
#
#     # Scale trapezium LHS and RHS
#     trap = get_scaled_fcas_trapezium_agc_enablement_limits_lhs(trader_id, trap)
#     trap = get_scaled_fcas_trapezium_agc_enablement_limits_rhs(trader_id, trap)
#
#     return trap


# def get_scaled_fcas_trapezium_agc_ramp_rates(trader_id, trade_type, trapezium):
#     """FCAS trapezium taking into account AGC ramp rates"""
#
#     # Input FCAS trapezium
#     trap = dict(trapezium)
#
#     # AGC up and down ramp rates
#     if trade_type == 'R5RE':
#         try:
#             agc_ramp = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate')
#         except:
#             return trap
#     elif trade_type == 'L5RE':
#         try:
#             agc_ramp = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampDnRate')
#         except:
#             return trap
#     else:
#         raise Exception(f'Unexpected trade type: {trade_type}')
#
#     # Max available
#     max_available = min(trap['MaxAvail'], agc_ramp / 12)
#
#     if max_available < trap['MaxAvail']:
#         # Low breakpoint calculation
#         try:
#             slope = trap['MaxAvail'] / (trap['LowBreakpoint'] - trap['EnablementMin'])
#             trap['LowBreakpoint'] = get_new_breakpoint(slope, trap['EnablementMin'], max_available)
#         except ZeroDivisionError:
#             pass
#
#         # High breakpoint calculation
#         try:
#             slope = -trap['MaxAvail'] / (trap['EnablementMax'] - trap['HighBreakpoint'])
#             trap['HighBreakpoint'] = get_new_breakpoint(slope, trap['EnablementMax'], max_available)
#         except ZeroDivisionError:
#             pass
#
#     # Update max available
#     trap['MaxAvail'] = max_available
#
#     return trap


def get_scaled_fcas_trapezium_agc_ramp_rate(trapezium, scada_ramp_rate):
    """
    FCAS trapezium taking into account AGC ramp rates
    Note: must use SCADARampUpRate for R5RE and SCADARampDnRate for L5RE
    """

    # Return input trapezium if scada_ramp_rate is None
    if scada_ramp_rate is None:
        return trapezium

    # Input FCAS trapezium
    trap = dict(trapezium)

    # Max available
    max_available = min(trap['MaxAvail'], scada_ramp_rate / 12)

    if max_available < trap['MaxAvail']:
        # Low breakpoint calculation
        try:
            slope = trap['MaxAvail'] / (trap['LowBreakpoint'] - trap['EnablementMin'])
            trap['LowBreakpoint'] = get_new_breakpoint(slope, trap['EnablementMin'], max_available)
        except ZeroDivisionError:
            pass

        # High breakpoint calculation
        try:
            slope = -trap['MaxAvail'] / (trap['EnablementMax'] - trap['HighBreakpoint'])
            trap['HighBreakpoint'] = get_new_breakpoint(slope, trap['EnablementMax'], max_available)
        except ZeroDivisionError:
            pass

    # Update max available
    trap['MaxAvail'] = max_available

    return trap


def get_scaled_fcas_trapezium_uigf(trapezium, uigf):
    """Trapezium scaling for semi-scheduled units"""

    # UIGF is not None for semi-scheduled units
    if uigf is None:
        return trapezium

    # Input FCAS trapezium
    trap = dict(trapezium)

    if uigf < trap['EnablementMax']:
        # High breakpoint calculation
        try:
            slope = -trap['MaxAvail'] / (trap['EnablementMax'] - trap['HighBreakpoint'])
            trap['HighBreakpoint'] = get_new_breakpoint(slope, trap['EnablementMax'], uigf)
        except ZeroDivisionError:
            pass

        # Update enablement max
        trap['EnablementMax'] = uigf

    return trap
#
#
# def get_scaled_fcas_trapezium(trader_id, trade_type):
#     """Get scaled FCAS trapezium"""
#
#     # Get unscaled FCAS offer
#     trapezium_1 = dict(get_fcas_trapezium_offer(trader_id, trade_type))
#
#     assert trade_type in ['R5RE', 'L5RE'], Exception(f'{trade_type}: can only scale regulating FCAS trapeziums')
#
#     # Only scale regulating FCAS offers
#     trapezium_2 = get_scaled_fcas_trapezium_agc_enablement_limits(trader_id, trapezium_1)
#     trapezium_3 = get_scaled_fcas_trapezium_agc_ramp_rates(trader_id, trade_type, trapezium_2)
#     trapezium_4 = get_scaled_fcas_trapezium_uigf(trader_id, trapezium_3)
#
#     return trapezium_4


def get_fcas_availability(trapezium, trade_type, max_quantity, initial_mw, agc_status, energy_max_avail):
    """Check FCAS availability"""

    # Max availability must be greater than 0
    cond_1 = trapezium['MaxAvail'] > 0

    # Quantity greater than 0 for at least one quantity band for the given service
    cond_2 = max_quantity > 0

    # Try and use specified FCAS condition, but if energy offer doesn't exist, then set cond_3=True by default
    if energy_max_avail is None:
        cond_3 = True
    else:
        cond_3 = energy_max_avail >= trapezium['EnablementMin']

    # FCAS enablement max >= 0
    cond_4 = trapezium['EnablementMax'] >= 0

    # Initial MW within enablement min and max
    cond_5 = trapezium['EnablementMin'] <= initial_mw <= trapezium['EnablementMax']

    # AGC is activate for regulating FCAS
    if trade_type in ['R5RE', 'L5RE']:
        if agc_status == '1':
            cond_6 = True
        else:
            cond_6 = False
    else:
        # Set cond_6 to True if non-regulating FCAS offer
        cond_6 = True

    # All conditions must be true in order for FCAS to be enabled
    return all([cond_1, cond_2, cond_3, cond_4, cond_5, cond_6])
