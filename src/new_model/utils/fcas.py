"""Utilities to parse FCAS offers"""


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


def get_fcas_availability(self, trader_id, trade_type):
    """Check FCAS availability"""

    # FCAS trapezium
    if trade_type in ['R5RE', 'L5RE']:
        trapezium = get_scaled_fcas_trapezium(trader_id, trade_type)
    else:
        trapezium = get_fcas_trapezium_offer(trader_id, trade_type)

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
