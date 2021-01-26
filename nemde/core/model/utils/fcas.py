"""Check FCAS availability calculations - equations for generators (loads require modified formulation)"""

import os
import io
import json
from typing import Union

import zipfile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# try:
#     import lookup
#     import loaders
#     import data as data_handler
# except ModuleNotFoundError:
#     import utils.lookup as lookup
#     import utils.loaders as loaders
#     import utils.data as data_handler


def get_trader_fcas_trapezium(data, trader_id, trade_type) -> dict:
    """Get trader FCAS trapezium"""

    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    high_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@HighBreakpoint', float)
    low_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@LowBreakpoint', float)
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    trapezium = {
        'EnablementMin': enablement_min,
        'EnablementMax': enablement_max,
        'HighBreakpoint': high_breakpoint,
        'LowBreakpoint': low_breakpoint,
        'MaxAvail': max_avail,
    }

    return trapezium


def get_line_from_slope_and_x_intercept(slope, x_intercept) -> dict:
    """Define line by its slope and x-intercept"""

    # y-intercept - set to None if slope undefined
    try:
        y_intercept = -slope * x_intercept
    except TypeError:
        y_intercept = None

    return {'slope': slope, 'y_intercept': y_intercept, 'x_intercept': x_intercept}


def get_intersection(line_1, line_2) -> tuple or None:
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


def get_new_breakpoint(slope, x_intercept, max_available) -> float:
    """Compute new (lower/upper) breakpoint"""

    # Y-axis intercept
    try:
        y_intercept = -slope * x_intercept
        return (max_available - y_intercept) / slope

    # If line is vertical or horizontal, return original x-intercept
    except (TypeError, ZeroDivisionError):
        return x_intercept


def get_fcas_trapezium_scaling_parameters(data, trader_id) -> dict:
    """Get parameters used when scaling FCAS trapezium"""

    try:
        lmw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'LMW', float)
    except LookupError:
        lmw = None

    try:
        hmw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'HMW', float)
    except LookupError:
        hmw = None

    try:
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except LookupError:
        ramp_up = None

    try:
        ramp_dn = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except LookupError:
        ramp_dn = None

    try:
        uigf = lookup.get_trader_period_collection_attribute(data, trader_id, '@UIGF', float)
    except LookupError:
        uigf = None

    # Combine parameters into single dictionary
    parameters = {
        'LMW': lmw,
        'HMW': hmw,
        'agc_ramp_up': ramp_up,
        'agc_ramp_down': ramp_dn,
        'UIGF': uigf
    }

    return parameters


def get_scaled_trapezium_agc_enablement_limit_lhs(trapezium, agc_enablement_min) -> dict:
    """Scale FCAS trapezium based on lower AGC enablement limit"""

    # Copy input trapezium
    trap = dict(trapezium)

    # No scaling applied if AGC limit is 0 or absent (from docs)
    if (agc_enablement_min == 0) or (agc_enablement_min is None):
        return trap

    # Trapezium enablement min is more restrictive than the AGC lower limit - return the original trapezium
    if agc_enablement_min <= trap['EnablementMin']:
        return trap

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

    # LHS line with new EnablementMin
    lhs_line = get_line_from_slope_and_x_intercept(lhs_slope, agc_enablement_min)

    # RHS line with original EnablementMax
    rhs_line = get_line_from_slope_and_x_intercept(rhs_slope, trap['EnablementMax'])

    # Intersection between LHS and RHS lines
    intersection = get_intersection(lhs_line, rhs_line)

    # Update max available if required
    if (intersection is not None) and (intersection[1] < trap['MaxAvail']):
        trap['MaxAvail'] = max([0, intersection[1]])

    # New low breakpoint
    trap['LowBreakpoint'] = get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'], trap['MaxAvail'])

    # New high breakpoint
    trap['HighBreakpoint'] = get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'], trap['MaxAvail'])

    # Update enablement min
    trap['EnablementMin'] = agc_enablement_min

    return trap


def get_scaled_trapezium_agc_enablement_limit_rhs(trapezium, agc_enablement_max) -> dict:
    """Scale FCAS trapezium based on upper AGC enablement limit"""

    # Copy input trapezium
    trap = dict(trapezium)

    # No scaling applied if AGC limit is 0 or absent (from docs)
    if (agc_enablement_max == 0) or (agc_enablement_max is None):
        return trap

    # Trapezium enablement max is more restrictive than the AGC upper limit - return the original trapezium
    if agc_enablement_max >= trap['EnablementMax']:
        return trap

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

    # LHS line with original EnablementMin
    lhs_line = get_line_from_slope_and_x_intercept(lhs_slope, trap['EnablementMin'])

    # RHS line with new EnablementMax
    rhs_line = get_line_from_slope_and_x_intercept(rhs_slope, agc_enablement_max)

    # Intersection between LHS and RHS lines
    intersection = get_intersection(lhs_line, rhs_line)

    # Update max available if required
    if (intersection is not None) and (intersection[1] < trap['MaxAvail']):
        trap['MaxAvail'] = max([0, intersection[1]])

    # New low breakpoint
    trap['LowBreakpoint'] = get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'], trap['MaxAvail'])

    # New high breakpoint
    trap['HighBreakpoint'] = get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'], trap['MaxAvail'])

    # Update enablement min
    trap['EnablementMax'] = agc_enablement_max

    return trap


def get_scaled_trapezium_agc_ramp_rate(trapezium, scada_ramp_rate) -> dict:
    """Get FCAS trapezium after scaled for AGC ramp rate"""

    # Return input trapezium if scada_ramp_rate is None or 0 (from docs)
    if (scada_ramp_rate == 0) or (scada_ramp_rate is None):
        return trapezium

    # Input FCAS trapezium
    trap = dict(trapezium)

    # Max available
    max_available = min([trap['MaxAvail'], scada_ramp_rate / 12])

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


def get_trader_fcas_trapezium_scaled(params) -> dict:
    """Get scaled FCAS trapezium"""

    # Unscaled FCAS trapezium
    trapezium = dict({
        'EnablementMin': params['enablement_min'],
        'EnablementMax': params['enablement_max'],
        'HighBreakpoint': params['high_breakpoint'],
        'LowBreakpoint': params['low_breakpoint'],
        'MaxAvail': params['max_avail'],
    })

    # Regulation and contingency FCAS offers
    regulation_offers = ['R5RE', 'L5RE']
    contingency_offers = ['L6SE', 'L60S', 'L5MI', 'R6SE', 'R60S', 'R5MI']

    # Trader type and semi dispatch status
    trader_id = params['trader_id']
    trade_type = params['trade_type']
    trader_type = params['trader_type']
    semi_dispatch = params['semi_dispatch']

    # UIGF scaling applied to contingency offers for semi-dispatchable plant
    if (semi_dispatch == '1') and (trade_type in contingency_offers):
        return get_scaled_trapezium_agc_enablement_limit_rhs(trapezium, params['uigf'])

    # Scaling only applied to regulation offers (except UIGF scaling which also applies to contingency FCAS offers)
    elif trade_type in regulation_offers:
        # AGC enablement limits
        scaled_1 = get_scaled_trapezium_agc_enablement_limit_lhs(trapezium, params['lmw'])
        scaled_2 = get_scaled_trapezium_agc_enablement_limit_rhs(scaled_1, params['hmw'])

        # AGC ramp rate for generators (increasing generation increases frequency)
        if (trader_type == 'GENERATOR') and (trade_type == 'R5RE'):
            scaled_3 = get_scaled_trapezium_agc_ramp_rate(scaled_2, params['agc_ramp_up'])

        elif (trader_type == 'GENERATOR') and (trade_type == 'L5RE'):
            scaled_3 = get_scaled_trapezium_agc_ramp_rate(scaled_2, params['agc_ramp_dn'])

        # AGC ramp rate for loads (increasing load decreases frequency)
        elif (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (trade_type == 'R5RE'):
            scaled_3 = get_scaled_trapezium_agc_ramp_rate(scaled_2, params['agc_ramp_dn'])

        elif (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (trade_type == 'L5RE'):
            scaled_3 = get_scaled_trapezium_agc_ramp_rate(scaled_2, params['agc_ramp_up'])

        else:
            raise Exception(f'Unexpected trade type: {trader_id} {trade_type}')

        # Scale by UIGF - same procedure as scaling for AGC enablement max
        scaled_4 = get_scaled_trapezium_agc_enablement_limit_rhs(scaled_3, params['uigf'])

        return scaled_4

    # No scaling applied to contingency FCAS trapezia submitted by scheduled plant
    else:
        return trapezium


def get_trader_fcas_availability_max_quantity_condition(params) -> bool:
    """At least one quantity band must have positive value"""

    # Quantity greater than 0 for at least one quantity band for the given service
    max_quantity = max(params['quantity_bands'].values())

    return max_quantity > 0


def get_trader_fcas_availability_enablement_min_condition(params) -> bool:
    """Energy offer must be greater than enablement min. If no energy offer return True."""

    # Get scaled FCAS trapezium
    trapezium = get_trader_fcas_trapezium_scaled(params)

    # Semi-dispatch flag
    semi_dispatch = params['semi_dispatch']

    # Get max available for trader's energy offer
    if semi_dispatch == '1':
        energy_max_avail = params['uigf']
    else:
        # This may be None if the unit doesn't have an energy offer
        energy_max_avail = params['energy_max_avail']

    return energy_max_avail >= trapezium['EnablementMin'] if energy_max_avail is not None else True


def get_trader_fcas_availability_agc_status_condition(params) -> bool:
    """Get FCAS availability AGC status condition. AGC must be enabled for regulation FCAS."""

    # Check AGC status if presented with a regulating FCAS offer
    if params['trade_type'] in ['L5RE', 'R5RE']:
        # AGC is active='1', AGC is inactive='0'
        return True if params['agc_status'] == '1' else False

    # Return True if a presented with a contingency FCAS offer (AGC doesn't need to be enabled)
    else:
        return True


def get_trader_fcas_availability_status(params) -> bool:
    """Get trader FCAS availability status"""

    # Scaled FCAS trapezium
    trapezium = get_trader_fcas_trapezium_scaled(params)

    # Initial MW # TODO: may need to change if considering intervention pricing
    initial_mw = params['initial_mw']

    # Max availability condition
    cond_1 = trapezium['MaxAvail'] > 0

    # At least one quantity band for the service must have positive value
    cond_2 = get_trader_fcas_availability_max_quantity_condition(params)

    # Energy offer must be greater than service enablement min
    cond_3 = get_trader_fcas_availability_enablement_min_condition(params)

    # Enablement max must be greater than 0
    cond_4 = trapezium['EnablementMax'] >= 0

    # Unit must be operating between enablement min and enablement max
    cond_5 = trapezium['EnablementMin'] <= initial_mw <= trapezium['EnablementMax']

    # AGC status
    cond_6 = get_trader_fcas_availability_agc_status_condition(params)

    # All conditions must be satisfied if FCAS is available
    fcas_status = all([cond_1, cond_2, cond_3, cond_4, cond_5, cond_6])

    return fcas_status


def get_generator_effective_regulation_raise_max_available(data, trader_id) -> float:
    """Get effective R5RE max available"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@MaxAvail', float)

    try:
        # AGC ramp up rate - divide by 12 to get ramp rate over dispatch interval
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float)
    except LookupError:
        ramp_up = None

    # No scaling applied if SCADA ramp rate = 0 or absent
    return max_avail if ((ramp_up is None) or (ramp_up == 0)) else min([max_avail, ramp_up / 12])


def get_generator_effective_regulation_lower_max_available(data, trader_id) -> float:
    """Get effective L5RE max available"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'L5RE', '@MaxAvail', float)

    # AGC ramp down rate - divide by 12 to get ramp rate over dispatch interval
    try:
        ramp_down = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except LookupError:
        ramp_down = None

    return max_avail if ((ramp_down is None) or (ramp_down == 0)) else min([max_avail, ramp_down / 12])


def get_effective_enablement_max(data, trader_id, trade_type) -> float:
    """Get effective enablement max - only for R5RE and L5RE offers"""

    assert trade_type in ['L5RE', 'R5RE'], f'Unexpected trade type: {trade_type}'

    # Offer enablement max
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)

    # Upper AGC limit
    try:
        agc_up_limit = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'HMW', float)
    except LookupError:
        agc_up_limit = None

    # UIGF from semi-dispatchable plant
    try:
        uigf = lookup.get_trader_period_collection_attribute(data, trader_id, '@UIGF', float)
    except LookupError:
        uigf = None

    # Terms used to determine effective enablement max
    terms = [enablement_max, agc_up_limit, uigf]

    return min([i for i in terms if i is not None])


def get_effective_enablement_min(data, trader_id, trade_type) -> float:
    """Get effective enablement min - only for R5RE and L5RE offers"""

    assert trade_type in ['L5RE', 'R5RE'], f'Unexpected trade type: {trade_type}'

    # Offer enablement min
    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)

    # Upper AGC limit
    try:
        agc_down_limit = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'LMW', float)
    except LookupError:
        agc_down_limit = None

    # Terms used to compute effective enablement min
    terms = [enablement_min, agc_down_limit]

    return max([i for i in terms if i is not None])


def get_generator_joint_ramp_raise_max(data, trader_id) -> Union[float, None]:
    """Get generator max joint ramp raise"""

    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)

    # SCADARampUpRate may not exist - return None
    try:
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float)
    except LookupError:
        ramp_up = None

    return initial_mw + (ramp_up / 12) if ((ramp_up is not None) and (ramp_up != 0)) else None


def get_generator_joint_ramp_lower_min(data, trader_id) -> Union[float, None]:
    """Get generator min joint ramp lower"""

    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)

    try:
        ramp_down = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except LookupError:
        return None

    return initial_mw - (ramp_down / 12) if ((ramp_down is not None) and (ramp_down != 0)) else None


def get_upper_slope_coefficient(data, trader_id, trade_type) -> Union[float, None]:
    """Get upper slope coefficient"""

    # FCAS trapezium parameters
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    high_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@HighBreakpoint', float)
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    return None if max_avail == 0 else (enablement_max - high_breakpoint) / max_avail


def get_lower_slope_coefficient(data, trader_id, trade_type) -> Union[float, None]:
    """Get lower slope coefficient"""

    # FCAS trapezium parameters
    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    low_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@LowBreakpoint', float)
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    # If MaxAvail is 0 then lower slope coefficient is undefined - return None
    return None if max_avail == 0 else (low_breakpoint - enablement_min) / max_avail


def get_generator_regulation_raise_term_1(data, trader_id, intervention) -> Union[float, None]:
    """Get R5RE term 1 in FCAS availability calculation"""

    # Joint raise max
    joint_ramp_raise_max = get_generator_joint_ramp_raise_max(data, trader_id)

    # No scaling applied because SCADARampUpRate is missing or 0
    if joint_ramp_raise_max is None:
        return None

    # Energy target
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)

    return joint_ramp_raise_max - energy_target


def get_generator_regulation_raise_term_2(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get R5RE term 2 in FCAS availability calculation"""

    # Map between FCAS keys
    fcas_map = {
        'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target',
        'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target'
    }

    # FCAS availability
    fcas_availability = get_trader_fcas_availability_status(data, trader_id, trade_type)

    # No constraint constructed if contingency FCAS unavailable
    if not fcas_availability:
        return None

    # Parameters
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)
    fcas_target = lookup.get_trader_solution_attribute(data, trader_id, fcas_map[trade_type], float, intervention)

    return enablement_max - energy_target - (upper_slope_coefficient * fcas_target)


def get_generator_regulation_raise_term_3(data, trader_id, intervention) -> Union[float, None]:
    """Get R5RE term 3 in FCAS availability calculation"""

    # Parameters
    enablement_max = get_effective_enablement_max(data, trader_id, 'R5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R5RE')

    # Ignore limit if slope coefficient = 0
    if upper_slope_coefficient == 0:
        return None

    return 0 if (upper_slope_coefficient is None) else (enablement_max - energy_target) / upper_slope_coefficient


def get_generator_regulation_raise_term_4(data, trader_id, intervention) -> Union[float, None]:
    """Get R5RE term 4 in FCAS availability calculation"""

    # Term parameters
    enablement_min = get_effective_enablement_min(data, trader_id, 'R5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'R5RE')

    # Ignore limit if slope coefficient = 0
    if lower_slope_coefficient == 0:
        return None

    return 0 if (lower_slope_coefficient is None) else (energy_target - enablement_min) / lower_slope_coefficient


def get_generator_regulation_raise_term_5(data, trader_id) -> float:
    """Get R5RE term 5 in FCAS availability calculation"""

    # Effective max available
    max_avail = get_generator_effective_regulation_raise_max_available(data, trader_id)

    return max_avail


def get_generator_regulation_raise_availability(data, trader_id, intervention) -> float:
    """Get raise regulation availability"""

    # Check if service is available
    fcas_status = get_trader_fcas_availability_status(data, trader_id, 'R5RE')

    # Return 0 if service is unavailable
    if not fcas_status:
        return 0

    # All trader offers
    offers = lookup.get_trader_offer_index(data)

    # Terms
    term_1 = get_generator_regulation_raise_term_1(data, trader_id, intervention)

    # Container for contingency FCAS terms
    contingency_fcas_terms = []
    for i in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # Check if contingency offer made by generator
        if (trader_id, i) in offers:
            contingency_fcas_terms.append(get_generator_regulation_raise_term_2(data, trader_id, i, intervention))

    term_3 = get_generator_regulation_raise_term_3(data, trader_id, intervention)
    term_4 = get_generator_regulation_raise_term_4(data, trader_id, intervention)
    term_5 = get_generator_regulation_raise_term_5(data, trader_id)

    # All terms
    terms = [term_1, term_3, term_4, term_5] + contingency_fcas_terms

    # Compute minimum of all terms - yields FCAS availability
    max_available = min([i for i in terms if i is not None])

    return max([0, max_available])


def get_generator_regulation_lower_term_1(data, trader_id, intervention) -> Union[float, None]:
    """Get L5RE term 1 in FCAS availability calculation"""

    # Joint lower min term
    joint_ramp_lower_min = get_generator_joint_ramp_lower_min(data, trader_id)

    # No scaling applied because SCADARampDnRate is missing or 0
    if joint_ramp_lower_min is None:
        return None

    # Energy target
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)

    return energy_target - joint_ramp_lower_min


def get_generator_regulation_lower_term_2(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get L5RE term 2 in FCAS availability calculation"""

    # Map between FCAS keys
    fcas_map = {
        'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target',
        'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target'
    }

    # FCAS availability
    fcas_availability = get_trader_fcas_availability_status(data, trader_id, trade_type)

    # No constraint constructed if contingency FCAS unavailable
    if not fcas_availability:
        return None

    # Parameters
    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)
    fcas_target = lookup.get_trader_solution_attribute(data, trader_id, fcas_map[trade_type], float, intervention)

    return energy_target - (lower_slope_coefficient * fcas_target) - enablement_min


def get_generator_regulation_lower_term_3(data, trader_id, intervention) -> Union[float, None]:
    """Get L5RE term 3 in FCAS availability calculation"""

    # Parameters
    enablement_max = get_effective_enablement_max(data, trader_id, 'L5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'L5RE')

    # Ignore limit if slope coefficient = 0
    if upper_slope_coefficient == 0:
        return None

    return 0 if (upper_slope_coefficient is None) else (enablement_max - energy_target) / upper_slope_coefficient


def get_generator_regulation_lower_term_4(data, trader_id, intervention) -> Union[float, None]:
    """Get L5RE term 4 in FCAS availability calculation"""

    # Term parameters
    enablement_min = get_effective_enablement_min(data, trader_id, 'L5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L5RE')

    # Ignore limit if slope coefficient = 0
    if lower_slope_coefficient == 0:
        return None

    return 0 if (lower_slope_coefficient is None) else (energy_target - enablement_min) / lower_slope_coefficient


def get_generator_regulation_lower_term_5(data, trader_id) -> float:
    """Get L5RE term 5 in FCAS availability calculation"""

    # Effective max available
    max_avail = get_generator_effective_regulation_lower_max_available(data, trader_id)

    return max_avail


def get_generator_regulation_lower_availability(data, trader_id, intervention) -> float:
    """Get lower regulation availability"""

    # Check if service is available
    fcas_status = get_trader_fcas_availability_status(data, trader_id, 'L5RE')

    # Return 0 if service is unavailable
    if not fcas_status:
        return 0

    # All trader offers
    offers = lookup.get_trader_offer_index(data)

    # Terms
    term_1 = get_generator_regulation_lower_term_1(data, trader_id, intervention)

    # Container for contingency FCAS terms
    contingency_fcas_terms = []
    for i in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # Check if contingency offer made by generator
        if (trader_id, i) in offers:
            contingency_fcas_terms.append(get_generator_regulation_lower_term_2(data, trader_id, i, intervention))

    term_3 = get_generator_regulation_lower_term_3(data, trader_id, intervention)
    term_4 = get_generator_regulation_lower_term_4(data, trader_id, intervention)
    term_5 = get_generator_regulation_lower_term_5(data, trader_id)

    # All terms
    terms = [term_1, term_3, term_4, term_5] + contingency_fcas_terms

    # Compute minimum of all terms - yields FCAS availability
    max_available = min([i for i in terms if i is not None])

    return max([0, max_available])


def get_generator_contingency_fcas_availability_term_1(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get generator contingency FCAS term 1"""

    # Parameters
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)

    if upper_slope_coefficient == 0:
        return None

    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    reg_target = lookup.get_trader_solution_attribute(data, trader_id, '@R5RegTarget', float, intervention)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)

    # Only have UIGF for semi-dispatchable plant
    try:
        uigf = lookup.get_trader_period_collection_attribute(data, trader_id, '@UIGF', float)
    except LookupError:
        uigf = None

    effective_enablement_max = min([i for i in [enablement_max, uigf] if i is not None])

    return (effective_enablement_max - reg_target - energy_target) / upper_slope_coefficient


def get_generator_contingency_fcas_availability_term_2(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get generator contingency FCAS term 2"""

    # Parameters
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)

    if lower_slope_coefficient == 0:
        return None

    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    reg_target = lookup.get_trader_solution_attribute(data, trader_id, '@L5RegTarget', float, intervention)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)

    return (energy_target - reg_target - enablement_min) / lower_slope_coefficient


def get_generator_contingency_fcas_availability_term_3(data, trader_id, trade_type) -> float:
    """Get generator contingency FCAS term 3"""

    return lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)


def get_generator_contingency_fcas_availability(data, trader_id, trade_type, intervention) -> float:
    """Get FCAS availability for contingency raise service"""

    # Check if service is available
    fcas_status = get_trader_fcas_availability_status(data, trader_id, trade_type)

    # Return 0 if service is unavailable
    if not fcas_status:
        return 0

    # Terms
    term_1 = get_generator_contingency_fcas_availability_term_1(data, trader_id, trade_type, intervention)
    term_2 = get_generator_contingency_fcas_availability_term_2(data, trader_id, trade_type, intervention)
    term_3 = get_generator_contingency_fcas_availability_term_3(data, trader_id, trade_type)

    # All terms in a single list
    terms = [term_1, term_2, term_3]

    # Compute max available
    max_available = min([i for i in terms if i is not None])

    # Ensure max available >= 0
    return max([0, max_available])


def get_load_regulation_raise_term_1(data, trader_id, intervention) -> Union[float, None]:
    """Get R5RE term 1 in FCAS availability calculation - loads"""

    # Parameters
    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)

    try:
        ramp_down = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except LookupError:
        ramp_down = None

    # No scaling applied because SCADARampDnRate is missing or 0
    return energy_target - initial_mw + (ramp_down / 12) if ((ramp_down is not None) and (ramp_down != 0)) else None


def get_load_regulation_raise_term_2(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get R5RE term 2 in FCAS availability calculation - loads"""

    # Map between FCAS keys
    fcas_map = {
        'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target',
        'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target'
    }

    # FCAS availability
    fcas_availability = get_trader_fcas_availability_status(data, trader_id, trade_type)

    # No constraint constructed if contingency FCAS unavailable
    if not fcas_availability:
        return None

    # Parameters
    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)
    fcas_target = lookup.get_trader_solution_attribute(data, trader_id, fcas_map[trade_type], float, intervention)

    return energy_target - (lower_slope_coefficient * fcas_target) - enablement_min


def get_load_regulation_raise_term_3(data, trader_id, intervention) -> Union[float, None]:
    """Get R5RE term 3 in FCAS availability calculation - loads"""

    # Parameters
    enablement_max = get_effective_enablement_max(data, trader_id, 'R5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R5RE')

    # Ignore limit if slope coefficient = 0
    if upper_slope_coefficient == 0:
        return None

    return 0 if (upper_slope_coefficient is None) else (enablement_max - energy_target) / upper_slope_coefficient


def get_load_regulation_raise_term_4(data, trader_id, intervention) -> Union[float, None]:
    """Get R5RE term 4 in FCAS availability calculation - loads"""

    # Term parameters
    enablement_min = get_effective_enablement_min(data, trader_id, 'R5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'R5RE')

    # Ignore limit if slope coefficient = 0
    if lower_slope_coefficient == 0:
        return None

    return 0 if (lower_slope_coefficient is None) else (energy_target - enablement_min) / lower_slope_coefficient


def get_load_regulation_raise_term_5(data, trader_id) -> float:
    """Get R5RE term 5 in FCAS availability calculation - loads"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@MaxAvail', float)

    try:
        # AGC ramp up rate - divide by 12 to get ramp rate over dispatch interval
        ramp_down = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except LookupError:
        ramp_down = None

    # No scaling applied if SCADA ramp rate = 0 or absent
    return max_avail if ((ramp_down is None) or (ramp_down == 0)) else min([max_avail, ramp_down / 12])


def get_load_regulation_raise_availability(data, trader_id, intervention) -> float:
    """Get R5RE term FCAS availability"""

    # Check if service is available
    fcas_status = get_trader_fcas_availability_status(data, trader_id, 'R5RE')

    # Return 0 if service is unavailable
    if not fcas_status:
        return 0

    # All trader offers
    offers = lookup.get_trader_offer_index(data)

    # Terms
    term_1 = get_load_regulation_raise_term_1(data, trader_id, intervention)

    # Container for contingency FCAS terms
    contingency_fcas_terms = []
    for i in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # Check if contingency offer made by generator
        if (trader_id, i) in offers:
            contingency_fcas_terms.append(get_load_regulation_raise_term_2(data, trader_id, i, intervention))

    term_3 = get_load_regulation_raise_term_3(data, trader_id, intervention)
    term_4 = get_load_regulation_raise_term_4(data, trader_id, intervention)
    term_5 = get_load_regulation_raise_term_5(data, trader_id)

    # All terms
    terms = [term_1, term_3, term_4, term_5] + contingency_fcas_terms

    # Compute minimum of all terms - yields FCAS availability
    max_available = min([i for i in terms if i is not None])

    return max([0, max_available])


def get_load_regulation_lower_term_1(data, trader_id, intervention) -> Union[float, None]:
    """Get L5RE term 1 in FCAS availability calculation - loads"""

    # Parameters
    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)

    try:
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float)
    except LookupError:
        ramp_up = None

    # No scaling applied because SCADARampDnRate is missing or 0
    return initial_mw + (ramp_up / 12) - energy_target if ((ramp_up is not None) and (ramp_up != 0)) else None


def get_load_regulation_lower_term_2(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get L5RE term 2 in FCAS availability calculation - loads"""

    # Map between FCAS keys
    fcas_map = {
        'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target',
        'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target'
    }

    # FCAS availability
    fcas_availability = get_trader_fcas_availability_status(data, trader_id, trade_type)

    # No constraint constructed if contingency FCAS unavailable
    if not fcas_availability:
        return None

    # Parameters
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)
    fcas_target = lookup.get_trader_solution_attribute(data, trader_id, fcas_map[trade_type], float, intervention)

    return enablement_max - energy_target - (upper_slope_coefficient * fcas_target)


def get_load_regulation_lower_term_3(data, trader_id, intervention) -> Union[float, None]:
    """Get L5RE term 3 in FCAS availability calculation - loads"""

    # Parameters
    enablement_max = get_effective_enablement_max(data, trader_id, 'L5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'L5RE')

    # Ignore limit if slope coefficient = 0
    if upper_slope_coefficient == 0:
        return None

    return 0 if (upper_slope_coefficient is None) else (enablement_max - energy_target) / upper_slope_coefficient


def get_load_regulation_lower_term_4(data, trader_id, intervention) -> Union[float, None]:
    """Get L5RE term 4 in FCAS availability calculation - loads"""

    # Parameters
    enablement_min = get_effective_enablement_min(data, trader_id, 'L5RE')
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L5RE')

    # Ignore limit if slope coefficient = 0
    if lower_slope_coefficient == 0:
        return None

    return 0 if (lower_slope_coefficient is None) else (energy_target - enablement_min) / lower_slope_coefficient


def get_load_regulation_lower_term_5(data, trader_id) -> float:
    """Get L5RE term 5 in FCAS availability calculation - loads"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'L5RE', '@MaxAvail', float)

    try:
        # AGC ramp up rate - divide by 12 to get ramp rate over dispatch interval
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float)
    except LookupError:
        ramp_up = None

    # No scaling applied if SCADA ramp rate = 0 or absent
    return max_avail if ((ramp_up is None) or (ramp_up == 0)) else min([max_avail, ramp_up / 12])


def get_load_regulation_lower_availability(data, trader_id, intervention) -> float:
    """
    Get FCAS availability for lower regulation service - loads

    Investigate if there is a bug in AEMO calculations for load LOWERREGACTUALAVAILABILITY calculations.
    Availability reported by AEMO seems to overstate load LOWERREGAVAILABILITY - the following calculations
    seem to be do a better job.
    """

    # Check if service is available
    fcas_status = get_trader_fcas_availability_status(data, trader_id, 'L5RE')

    # Return 0 if service is unavailable
    if not fcas_status:
        return 0

    # All trader offers
    offers = lookup.get_trader_offer_index(data)

    # Terms
    term_1 = get_load_regulation_lower_term_1(data, trader_id, intervention)

    # Container for contingency FCAS terms
    contingency_fcas_terms = []
    for i in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # Check if contingency offer made by generator
        if (trader_id, i) in offers:
            contingency_fcas_terms.append(get_load_regulation_lower_term_2(data, trader_id, i, intervention))

    term_3 = get_load_regulation_lower_term_3(data, trader_id, intervention)
    term_4 = get_load_regulation_lower_term_4(data, trader_id, intervention)
    term_5 = get_load_regulation_lower_term_5(data, trader_id)

    # All terms
    terms = [term_1, term_3, term_4, term_5] + contingency_fcas_terms

    # Compute minimum of all terms - yields FCAS availability
    max_available = min([i for i in terms if i is not None])

    return max([0, max_available])


def get_load_contingency_fcas_availability_term_1(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get load contingency FCAS term 1"""

    # Parameters
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)

    if upper_slope_coefficient == 0:
        return None

    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    reg_target = lookup.get_trader_solution_attribute(data, trader_id, '@L5RegTarget', float, intervention)

    # Only have UIGF for semi-dispatchable plant
    try:
        uigf = lookup.get_trader_period_collection_attribute(data, trader_id, '@UIGF', float)
    except LookupError:
        uigf = None

    effective_enablement_max = min([i for i in [enablement_max, uigf] if i is not None])

    return (effective_enablement_max - energy_target - reg_target) / upper_slope_coefficient


def get_load_contingency_fcas_availability_term_2(data, trader_id, trade_type, intervention) -> Union[float, None]:
    """Get load contingency FCAS term 2"""

    # Parameters
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)

    if lower_slope_coefficient == 0:
        return None

    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float, intervention)
    reg_target = lookup.get_trader_solution_attribute(data, trader_id, '@R5RegTarget', float, intervention)

    return (energy_target - reg_target - enablement_min) / lower_slope_coefficient


def get_load_contingency_fcas_availability_term_3(data, trader_id, trade_type) -> float:
    """Get load contingency raise term 3"""

    return lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)


def get_load_contingency_fcas_availability(data, trader_id, trade_type, intervention) -> float:
    """Get FCAS availability for contingency raise service - loads"""

    # Check if service is available
    fcas_status = get_trader_fcas_availability_status(data, trader_id, trade_type)

    # Return 0 if service is unavailable
    if not fcas_status:
        return 0

    # Terms
    term_1 = get_load_contingency_fcas_availability_term_1(data, trader_id, trade_type, intervention)
    term_2 = get_load_contingency_fcas_availability_term_2(data, trader_id, trade_type, intervention)
    term_3 = get_load_contingency_fcas_availability_term_3(data, trader_id, trade_type)

    # All terms in a single list
    terms = [term_1, term_2, term_3]

    # Compute max available
    max_available = min([i for i in terms if i is not None])

    # Ensure max available >= 0
    return max([0, max_available])


def get_trader_fcas_availability(data, trader_id, trade_type, intervention) -> float:
    """Compute FCAS availability for a given trade type"""

    # Trader type
    trader_type = lookup.get_trader_collection_attribute(data, trader_id, '@TraderType', str)

    if trader_type == 'GENERATOR':
        if trade_type == 'R5RE':
            return get_generator_regulation_raise_availability(data, trader_id, intervention)
        elif trade_type == 'L5RE':
            return get_generator_regulation_lower_availability(data, trader_id, intervention)
        elif trade_type in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            return get_generator_contingency_fcas_availability(data, trader_id, trade_type, intervention)
        else:
            raise Exception(f'Unexpected trade type: {trader_id} {trade_type}')

    elif trader_type in ['LOAD', 'NORMALLY_ON_LOAD']:
        if trade_type == 'R5RE':
            return get_load_regulation_raise_availability(data, trader_id, intervention)
        elif trade_type == 'L5RE':
            return get_load_regulation_lower_availability(data, trader_id, intervention)
        elif trade_type in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            return get_load_contingency_fcas_availability(data, trader_id, trade_type, intervention)
        else:
            raise Exception(f'Unexpected trade type: {trader_id} {trade_type}')

    else:
        raise Exception(f'Unexpected trader type: {trader_id} {trader_type} {trader_type}')


def get_observed_trader_fcas_availability(data_dir, tmp_dir) -> pd.DataFrame:
    """Get FCAS availability reported in MMS"""

    with zipfile.ZipFile(os.path.join(data_dir, 'PUBLIC_DVD_DISPATCHLOAD_201910010000.zip')) as z1:
        with z1.open('PUBLIC_DVD_DISPATCHLOAD_201910010000.CSV') as z2:
            df = pd.read_csv(z2, skiprows=1).iloc[:-1]

    # Convert intervention flag and dispatch interval to string
    df['INTERVENTION'] = df['INTERVENTION'].astype(int).astype('str')
    df['DISPATCHINTERVAL'] = df['DISPATCHINTERVAL'].astype(int).astype('str')

    #  Convert to datetime
    df['SETTLEMENTDATE'] = pd.to_datetime(df['SETTLEMENTDATE'])

    # Set index
    df = df.set_index(['DISPATCHINTERVAL', 'DUID', 'INTERVENTION'])
    df = df.sort_index()

    # Save to
    df.to_pickle(os.path.join(tmp_dir, 'fcas_availability.pickle'))

    return df


def check_fcas_availability(data, observed, trade_type) -> pd.DataFrame:
    """Check FCAS availability with observed values"""

    # Case ID - corresponds to dispatch interval ID
    case_id = lookup.get_case_attribute(data, '@CaseID', str)

    # All trader FCAS offers
    trader_offers = lookup.get_trader_offer_index(data)

    # Check if a intervention pricing run occurred
    intervention_flag = lookup.get_case_attribute(data, '@Intervention', str)

    # TODO: Need to abstract intervention flag status
    # Intervention flag is '0' if no pricing run occurs. '1'=physical run, '0'=pricing run
    if intervention_flag == 'False':
        intervention = '0'
    else:
        intervention = '1'

    # Mapping between trade type and trader solution attribute
    solution_map = {
        'R5RE': '@R5RegTarget',
        'L5RE': '@L5RegTarget',
        'R6SE': '@R6Target',
        'R60S': '@R60Target',
        'R5MI': '@R5Target',
        'L6SE': '@L6Target',
        'L60S': '@L60Target',
        'L5MI': '@L5Target',
    }

    out = {}
    for i, j in trader_offers:
        if j == trade_type:
            out[(case_id, i, j)] = {
                'calculated': get_trader_fcas_availability(data, i, j, intervention),
                'calculated_status': get_trader_fcas_availability_status(data, i, j),
                'solution': lookup.get_trader_solution_attribute(data, i, solution_map[j], float, intervention),
            }

    # Calculated FCAS availability
    df_1 = pd.DataFrame(out).T.rename_axis(['DISPATCHINTERVAL', 'DUID', 'TRADETYPE'])

    # Mapping between trade types and calculated FCAS availability column names
    availability_map = {
        'R5RE': 'RAISEREGACTUALAVAILABILITY',
        'L5RE': 'LOWERREGACTUALAVAILABILITY',
        'R6SE': 'RAISE6SECACTUALAVAILABILITY',
        'R60S': 'RAISE60SECACTUALAVAILABILITY',
        'R5MI': 'RAISE5MINACTUALAVAILABILITY',
        'L6SE': 'LOWER6SECACTUALAVAILABILITY',
        'L60S': 'LOWER60SECACTUALAVAILABILITY',
        'L5MI': 'LOWER5MINACTUALAVAILABILITY',
    }

    flag_map = {
        'R5RE': 'RAISEREGFLAGS',
        'L5RE': 'LOWERREGFLAGS',
        'R6SE': 'RAISE6SECFLAGS',
        'R60S': 'RAISE60SECFLAGS',
        'R5MI': 'RAISE5MINFLAGS',
        'L6SE': 'LOWER6SECFLAGS',
        'L60S': 'LOWER60SECFLAGS',
        'L5MI': 'LOWER5MINFLAGS',
    }

    # Columns from observed FCAS target DataFrame to be retained
    columns = [availability_map[trade_type], flag_map[trade_type]]

    # Join calculated and observed values in single DataFrame
    df_2 = df_1.join(observed.loc[(case_id, slice(None), intervention), columns])

    # Compute difference
    df_2['difference'] = df_2['calculated'] - df_2[availability_map[trade_type]]
    df_2['abs_difference'] = df_2['difference'].abs()
    df_2 = df_2.sort_values(by='abs_difference', ascending=False)

    return df_2


def check_fcas_availability_sample(data_dir, observed, trade_type, n=5) -> pd.DataFrame:
    """Check FCAS availability for random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = []

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'{i + 1}/{len(sample)}: ({day}, {interval})')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        data = json.loads(data_json)

        # Dispatch interval
        dispatch_interval = f'{2019}{10:02}{day:02}{interval:03}'

        # Check FCAS availability for a given dispatch interval
        df = check_fcas_availability(data, observed, trade_type)

        # Append to main container
        out.append(df)

    # Concatenate results for all dispatch intervals
    df_c = pd.concat(out).sort_values(by='abs_difference', ascending=False)

    return df_c


def check_trader_fcas_trapezium(data, trader_id, trade_type, show=False) -> None:
    """Check scaled and unscaled FCAS trapezia"""

    # Scaled and unscaled FCAS trapezia
    t_1 = get_trader_fcas_trapezium(data, trader_id, trade_type)
    t_2 = get_trader_fcas_trapezium_scaled(data, trader_id, trade_type)

    fig, ax = plt.subplots()
    x_1 = [t_1['EnablementMin'], t_1['LowBreakpoint'], t_1['HighBreakpoint'], t_1['EnablementMax']]
    y_1 = [0, t_1['MaxAvail'], t_1['MaxAvail'], 0]

    x_2 = [t_2['EnablementMin'], t_2['LowBreakpoint'], t_2['HighBreakpoint'], t_2['EnablementMax']]
    y_2 = [0, t_2['MaxAvail'], t_2['MaxAvail'], 0]

    ax.plot(x_1, y_1, color='b', alpha=0.8, linewidth=1, zorder=0)
    ax.plot(x_2, y_2, color='r', alpha=0.8, linewidth=1, zorder=10)
    ax.set_title(f'{trader_id} {trade_type}')

    filename = f"{trader_id.replace('#', '').replace('/', '')}-{trade_type}"
    print(filename)
    print(t_1)
    print(t_2)

    fig.savefig(f"plots/fcas_check/{filename}.png")

    if show:
        plt.show()
    else:
        plt.close()


def check_trader_fcas_trapezia(data) -> None:
    """Check scaled and unscaled FCAS trapezia for all FCAS offers"""

    offers = lookup.get_trader_offer_index(data)

    for i, j in offers:
        if j not in ['ENOF', 'LDOF']:
            check_trader_fcas_trapezium(data, i, j, show=False)


def check_fcas_availability_status(data):
    """Compare calculated and observed FCAS availability"""

    # All trader offers
    offers = lookup.get_trader_offer_index(data)

    # Map between trade types and keys used in NEMDE solution
    fcas_map = {
        'R6SE': '@R6Flags', 'R60S': '@R60Flags', 'R5MI': '@R5Flags', 'R5RE': '@R5RegFlags',
        'L6SE': '@L6Flags', 'L60S': '@L60Flags', 'L5MI': '@L5Flags', 'L5RE': '@L5RegFlags'
    }

    # Container for output
    out = {}
    for i, j in offers:
        # Only consider FCAS offers (i.e. not energy offers)
        if j not in ['ENOF', 'LDOF']:
            out[(i, j)] = {
                'calculated': int(get_trader_fcas_availability_status(data, i, j)),
                'observed': lookup.get_trader_solution_attribute(data, i, fcas_map[j], int)
            }

    # Convert to DataFrame
    df = pd.DataFrame(out).T

    def compare_availabilities(row):
        """Check calculated and observed FCAS availabilities"""

        # Calculated availability status - 1=available, 0=unavailable
        calculated_is_available = row['calculated'] == 1

        # Observed availability flag - (odd=available, even=unavailable) from MMSDM data model doc
        observed_is_available = row['calculated'] % 2 != 0

        return calculated_is_available == observed_is_available

    # Compare calculated and observed availabilities
    df['comparison'] = df.apply(compare_availabilities, axis=1)

    # Offers where a difference between calculated and observed values exists
    difference = df.loc[~df['comparison'], :].index.tolist()

    return out, df, difference


def check_fcas_availability_status_sample(data_dir, n=5):
    """Check FCAS availability for a random sample of dispatch intervals"""

    print('Checking FCAS availability status')

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}

    # Placeholder for max difference observed
    max_difference = 0
    max_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'{i + 1}/{len(sample)}: ({day}, {interval})')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Check FCAS availability for dispatch interval - find all generators for which a difference exists
        _, _, difference = check_fcas_availability_status(case_data)

        # Append to container
        out[(day, interval)] = difference

        # Update max difference
        if len(difference) > max_difference:
            max_difference = len(difference)
            max_difference_interval = (day, interval)

        # Periodically print max absolute difference observed
        if (i + 1) % 10 == 0:
            print('Max number of intervals with difference:', max_difference_interval, max_difference)

    # All intervals with a difference
    intervals_with_difference = {k: v for k, v in out.items() if len(v) > 0}

    return out, intervals_with_difference
