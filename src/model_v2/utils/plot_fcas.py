"""Plot FCAS solution"""

import os
import json
import math
from functools import wraps

import xmltodict

import matplotlib.pyplot as plt

from loaders import load_dispatch_interval_json


def convert_to_list(dict_or_list) -> list:
    """Convert a dict to list. Return input if list is given."""

    if isinstance(dict_or_list, dict):
        return [dict_or_list]
    elif isinstance(dict_or_list, list):
        return dict_or_list
    elif dict_or_list is None:
        return []
    else:
        raise Exception(f'Unexpected type: {dict_or_list}')


def get_trader_initial_condition(data, trader_id, attribute, func):
    """Get trader initial condition"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in i.get('TraderInitialConditionCollection').get('TraderInitialCondition'):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])


def get_trader_collection_attribute(data, trader_id, attribute, func):
    """Get trader collection attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])


def get_trader_period_attribute(data, trader_id, attribute, func):
    """Get trader period attribute"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])


def get_trader_quantity_band_attribute(data, trader_id, trade_type, attribute, func):
    """Get trader quantity band attribute"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in convert_to_list(i.get('TradeCollection').get('Trade')):
                if j['@TradeType'] == trade_type:
                    return func(j[attribute])


def get_trader_quantity_bands(data, trader_id, trade_type):
    """Get trader quantity bands"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in convert_to_list(i.get('TradeCollection').get('Trade')):
                if j['@TradeType'] == trade_type:
                    return {f'BandAvail{k}': float(j[f'@BandAvail{k}']) for k in range(1, 11)}


def get_trader_solution_attribute(data, trader_id, attribute, intervention='0'):
    """Get trader solution attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    for i in traders:
        if (i['@TraderID'] == trader_id) and (i['@Intervention'] == intervention):
            return float(i[attribute])


def get_fcas_trapezium(data, trader_id, trade_type):
    """Get FCAS trapezium"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
        .get('TraderPeriodCollection')['TraderPeriod'])

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in convert_to_list(i['TradeCollection']['Trade']):
                if j['@TradeType'] == trade_type:
                    # Parse elements
                    str_keys = ['@TradeType']
                    trade = {k: str(v) if k in str_keys else float(v) for k, v in j.items()}

                    # FCAS trapezium
                    trapezium = {
                        'EnablementMin': trade['@EnablementMin'],
                        'LowBreakpoint': trade['@LowBreakpoint'],
                        'HighBreakpoint': trade['@HighBreakpoint'],
                        'EnablementMax': trade['@EnablementMax'],
                        'MaxAvail': trade['@MaxAvail'],
                    }

                    return trapezium


def get_line_from_points(x1, y1, x2, y2):
    """Get line from points"""

    # Compute slope. Slope is inf if line is vertical
    try:
        slope = (y2 - y1) / (x2 - x1)
    except ZeroDivisionError:
        slope = math.inf

    # Line is vertical
    if slope is math.inf:
        x_intercept = x1
        y_intercept = None

    # Line is horizontal
    elif slope == 0:
        x_intercept = None
        y_intercept = y1

    # Line is sloped
    else:
        y_intercept = y1 - (slope * x1)
        x_intercept = (y_intercept - y1) / slope

    return {'slope': slope, 'x_intercept': x_intercept, 'y_intercept': y_intercept}


def get_line_slope_and_point(slope, x1, y1):
    """Get description of line based on slope and x-intercept, and a point on that line"""

    # Line is vertical
    if slope is math.inf:
        y_intercept = None
        x_intercept = x1

    # Line is horizontal
    elif slope == 0:
        y_intercept = y1
        x_intercept = None

    # Line is sloped
    else:
        y_intercept = y1 - slope * x1
        x_intercept = (y_intercept - y1) / slope

    return {'slope': slope, 'x_intercept': x_intercept, 'y_intercept': y_intercept}


def get_intersection(line_1, line_2):
    """Get intersection between two lines"""

    # Both lines are vertical
    if (line_1['slope'] is math.inf) and (line_2['slope'] is math.inf):
        x_intersection = None
        y_intersection = None

    # Lines are parallel
    elif line_1['slope'] == line_2['slope']:
        x_intersection = None
        y_intersection = None

    # Line 1 is vertical, line 2 is non-vertical
    elif (line_1['slope'] is math.inf) and (line_2['slope'] is not math.inf):
        x_intersection = line_1['x_intercept']
        y_intersection = (line_2['slope'] * x_intersection) + line_2['y_intercept']

    # Line 1 is non-vertical, line 2 is vertical
    elif (line_1['slope'] is not math.inf) and (line_2['slope'] is math.inf):
        x_intersection = line_2['x_intercept']
        y_intersection = (line_1['slope'] * x_intersection) + line_1['y_intercept']

    # Both lines are sloped
    else:
        x_intersection = (line_2['y_intercept'] - line_1['y_intercept']) / (line_1['slope'] - line_2['slope'])
        y_intersection = (line_1['slope'] * x_intersection) + line_1['y_intercept']

    return {'x': x_intersection, 'y': y_intersection}


def get_scaled_fcas_trapezium_agc_enablement_min_lhs(trapezium, agc_enablement_min):
    """Get scaled FCAS trapezium - AGC enablement min"""

    # Copy input trapezium
    trap = dict(trapezium)

    # No scaling required if AGC enablement min lower than offer EnablementMin
    if agc_enablement_min < trap['EnablementMin']:
        return trap

    # Get trapezium lines
    lhs_line = get_line_from_points(trap['EnablementMin'], 0, trap['LowBreakpoint'], trap['MaxAvail'])
    rhs_line = get_line_from_points(trap['HighBreakpoint'], trap['MaxAvail'], trap['EnablementMax'], 0)
    max_line = get_line_from_points(trap['LowBreakpoint'], trap['MaxAvail'], trap['HighBreakpoint'], trap['MaxAvail'])

    # New LHS line - slope remains the same
    new_lhs_line = get_line_slope_and_point(lhs_line['slope'], agc_enablement_min, 0)

    # Intersection between LHS and RHS lines
    intersection_1 = get_intersection(new_lhs_line, rhs_line)

    # Intersection between LHS and horizontal max available line
    intersection_2 = get_intersection(new_lhs_line, max_line)

    # Both LHS and RHS lines are vertical - no intersection - only EnablementMin and LowBreakpoint need to be scaled
    if (intersection_1['x'] is None) and (intersection_1['y'] is None):
        trap['EnablementMin'] = agc_enablement_min
        trap['LowBreakpoint'] = agc_enablement_min

    # LHS line intersects with RHS line - point of intersection below max available. Need to scale HighBreakpoint.
    elif intersection_1['y'] < trap['MaxAvail']:
        trap['EnablementMin'] = agc_enablement_min
        trap['LowBreakpoint'] = intersection_1['x']
        trap['HighBreakpoint'] = intersection_1['x']
        trap['MaxAvail'] = intersection_1['y']

    # LHS line intersects with max available horizontal line
    else:
        trap['EnablementMin'] = agc_enablement_min
        trap['LowBreakpoint'] = intersection_2['x']

    return trap


def get_scaled_fcas_trapezium_agc_enablement_min_rhs(trapezium, agc_enablement_max):
    """Get scaled FCAS trapezium - AGC enablement max"""

    # Copy input trapezium
    trap = dict(trapezium)

    # No scaling required if AGC enablement max greater than offer EnablementMax
    if agc_enablement_max > trap['EnablementMax']:
        return trap

    # Get trapezium lines
    lhs_line = get_line_from_points(trap['EnablementMin'], 0, trap['LowBreakpoint'], trap['MaxAvail'])
    rhs_line = get_line_from_points(trap['HighBreakpoint'], trap['MaxAvail'], trap['EnablementMax'], 0)
    max_line = get_line_from_points(trap['LowBreakpoint'], trap['MaxAvail'], trap['HighBreakpoint'], trap['MaxAvail'])

    # New RHS line - slope remains the same
    new_rhs_line = get_line_slope_and_point(rhs_line['slope'], agc_enablement_max, 0)

    # Intersection between RHS and LHS lines
    intersection_1 = get_intersection(new_rhs_line, lhs_line)

    # Intersection between RHS and horizontal max available line
    intersection_2 = get_intersection(new_rhs_line, max_line)

    # Both LHS and RHS lines are vertical - no intersection - only EnablementMax and HighBreakpoint need to be scaled
    if (intersection_1['x'] is None) and (intersection_1['y'] is None):
        trap['EnablementMax'] = agc_enablement_max
        trap['HighBreakpoint'] = agc_enablement_max

    # LHS line intersects with RHS line - point of intersection below max available. Need to scale LowBreakpoint.
    elif intersection_1['y'] < trap['MaxAvail']:
        trap['EnablementMax'] = agc_enablement_max
        trap['LowBreakpoint'] = intersection_1['x']
        trap['HighBreakpoint'] = intersection_1['x']
        trap['MaxAvail'] = intersection_1['y']

    # LHS line intersects with max available horizontal line
    else:
        trap['EnablementMax'] = agc_enablement_max
        trap['HighBreakpoint'] = intersection_2['x']

    return trap


def get_scaled_fcas_trapezium_agc_ramp_rate(trapezium, scada_ramp_rate):
    """
    Scale for AGC ramp rate up

    From FCAS docs: 'If the AGC ramp rate is zero or absent, no scaling is applied.'
    """

    # Copy dictionary
    trap = dict(trapezium)

    # Return input if SCADA ramp rate missing
    if scada_ramp_rate is None:
        return trapezium

    # Ramping capability over 5 min dispatch interval
    ramp_rate_limit = scada_ramp_rate / 12

    # Ramp rate doesn't pose restriction - return input trapezium
    if ramp_rate_limit > trap['MaxAvail']:
        return trap

    # Get trapezium lines
    lhs_line = get_line_from_points(trap['EnablementMin'], 0, trap['LowBreakpoint'], trap['MaxAvail'])
    rhs_line = get_line_from_points(trap['HighBreakpoint'], trap['MaxAvail'], trap['EnablementMax'], 0)

    # Get intersection between LHS, RHS and max available lines
    lhs_intersection = get_intersection(lhs_line, {'slope': 0, 'x_intercept': None, 'y_intercept': ramp_rate_limit})
    rhs_intersection = get_intersection(rhs_line, {'slope': 0, 'x_intercept': None, 'y_intercept': ramp_rate_limit})

    # Scale by AGC ramp-rate limit
    trap['LowBreakpoint'] = lhs_intersection['x']
    trap['HighBreakpoint'] = rhs_intersection['x']
    trap['MaxAvail'] = ramp_rate_limit

    return trap


def get_scaled_fcas_trapezium_uigf(trapezium, uigf):
    """Scale by UIGF for semi-scheduled units"""

    # Copy trapezium
    trap = dict(trapezium)

    # No UIGF supplied (e.g. non semi-scheduled unit)
    if uigf is None:
        return trap

    # Scaling is essentially the same as a AGC enablement min scaling
    return get_scaled_fcas_trapezium_agc_enablement_min_rhs(trapezium, uigf)


def get_trapezium_data(data, trader_id):
    """Get auxiliary data used to scale FCAS trapezium"""

    # Parameters
    try:
        agc_enablement_min = get_trader_initial_condition(data, trader_id, 'LMW', float)
    except Exception as e:
        print(e)
        agc_enablement_min = None

    try:
        agc_enablement_max = get_trader_initial_condition(data, trader_id, 'HMW', float)
    except Exception as e:
        print(e)
        agc_enablement_max = None

    try:
        scada_ramp_rate_up = get_trader_initial_condition(data, trader_id, 'SCADARampUpRate', float)
    except Exception as e:
        print(e)
        scada_ramp_rate_up = None

    try:
        scada_ramp_rate_down = get_trader_initial_condition(data, trader_id, 'SCADARampDnRate', float)
    except Exception as e:
        print(e)
        scada_ramp_rate_down = None

    try:
        uigf = get_trader_period_attribute(data, trader_id, '@UIGF', float)
    except Exception as e:
        print(e)
        uigf = None

    # Combine trader data into single dictionary
    trader_data = {'agc_enablement_min': agc_enablement_min, 'agc_enablement_max': agc_enablement_max,
                   'scada_ramp_rate_up': scada_ramp_rate_up, 'scada_ramp_rate_down': scada_ramp_rate_down, 'uigf': uigf}

    return trader_data


def get_fcas_trapezium_scaled(data, trader_id, trade_type):
    """Get scaled FCAS trapezium"""

    # Unscaled trapezium
    unscaled = get_fcas_trapezium(data, trader_id, trade_type)

    # Semi-dispatch status
    semi_dispatch_status = get_trader_collection_attribute(data, trader_id, '@SemiDispatch', str)

    # Get auxiliary trader data to scale FCAS trapezium
    trader_data = get_trapezium_data(data, trader_id)

    # Parameters
    agc_enablement_min = trader_data['agc_enablement_min']
    agc_enablement_max = trader_data['agc_enablement_max']
    scada_ramp_rate_up = trader_data['scada_ramp_rate_up']
    scada_ramp_rate_down = trader_data['scada_ramp_rate_down']
    uigf = trader_data['uigf']

    # Scaling applied to regulation FCAS offers for all units
    if trade_type in ['L5RE', 'R5RE']:
        # Scaled for AGC enablement limits
        scaled_1 = get_scaled_fcas_trapezium_agc_enablement_min_lhs(unscaled, agc_enablement_min)
        scaled_2 = get_scaled_fcas_trapezium_agc_enablement_min_rhs(scaled_1, agc_enablement_max)

        # Scale for AGC ramp rates
        if trade_type == 'R5RE':
            scaled_3 = get_scaled_fcas_trapezium_agc_ramp_rate(scaled_2, scada_ramp_rate_up)
        elif trade_type == 'L5RE':
            scaled_3 = get_scaled_fcas_trapezium_agc_ramp_rate(scaled_2, scada_ramp_rate_down)
        else:
            raise Exception('Unhandled case')

        # UIGF - only applies for semi-scheduled units
        scaled_4 = get_scaled_fcas_trapezium_uigf(scaled_3, uigf)

        return scaled_4

    # Scale contingency offers if a semi-dispatchable generator
    elif semi_dispatch_status == '1':
        # Scale for UIGF
        scaled_1 = get_scaled_fcas_trapezium_uigf(unscaled, uigf)
        return scaled_1

    # No scaling applied to contingency services for dispatchable generators
    elif (semi_dispatch_status == '0') and (trade_type in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']):
        return unscaled

    else:
        raise Exception('Unhandled case')


def get_fcas_availability(data, trader_id, trade_type) -> bool:
    """Get FCAS availability"""

    # Get scaled FCAS trapezium
    trapezium = get_fcas_trapezium_scaled(data, trader_id, trade_type)

    # Max availability for service is > 0
    cond_1 = trapezium['MaxAvail'] > 0

    # At least one band has quantity greater than 0
    trader_quantity_bands = get_trader_quantity_bands(cdata, trader_id, trade_type)
    cond_2 = max(v for _, v in trader_quantity_bands.items()) > 0

    # Energy offer availability greater than enablement min
    trader_type = get_trader_collection_attribute(cdata, trader_id, '@TraderType', str)
    if trader_type in ['GENERATOR']:
        try:
            energy_offer_max_avail = get_trader_quantity_band_attribute(cdata, trader_id, 'ENOF', '@MaxAvail', float)
        except Exception as e:
            print(e)
            energy_offer_max_avail = None
    elif trader_type in ['LOAD', 'NORMALLY_ON_LOAD']:
        try:
            energy_offer_max_avail = get_trader_quantity_band_attribute(cdata, trader_id, 'LDOF', '@MaxAvail', float)
        except Exception as e:
            print(e)
            energy_offer_max_avail = None
    else:
        raise Exception('Unhandled case')

    # If no energy offer, then cond_3 True by default
    if energy_offer_max_avail is None:
        cond_3 = True
    # Energy max available > 0
    else:
        cond_3 = energy_offer_max_avail > 0

    # FCAS enablement max > 0
    cond_4 = trapezium['EnablementMax'] > 0

    # Initial MW within enablement min and enablement max
    initial_mw = get_trader_initial_condition(cdata, trader_id, 'InitialMW', float)
    cond_5 = trapezium['EnablementMin'] <= initial_mw <= trapezium['EnablementMax']

    # AGC status for regulating FCAS - set cond_6 to True
    if trader_type in ['L5RE', 'R5RE']:
        agc_status = get_trader_initial_condition(cdata, trader_id, 'AGCStatus', str)
        cond_6 = agc_status == '1'
    else:
        cond_6 = True

    # FCAS available if all conditions True
    fcas_available = all([cond_1, cond_2, cond_3, cond_4, cond_5, cond_6])

    return fcas_available


def plot_trapezium(trapezium, ax, **kwargs):
    """Plot trapezium"""

    x = [trapezium['EnablementMin'], trapezium['LowBreakpoint'], trapezium['HighBreakpoint'], trapezium['EnablementMax']]
    y = [0, trapezium['MaxAvail'], trapezium['MaxAvail'], 0]

    ax.plot(x, y, color=kwargs.get('color'))

    return ax


def plot_joint_ramping_constraint_rhs(ax, initial_mw, scada_ramp_up, max_avail, **kwargs):
    """
    Plot joint ramping constraint LHS

    Energy Dispatch Target + Raise Regulating FCAS Target <= Initial MW + SCADA Ramp Up Capability

    if SCADA Ramp Up Rate > 0
    SCADA Ramp Up Capability = SCADA Ramp Up Rate ∗ Time Period
    """

    y1 = -1
    x1 = -y1 + initial_mw + scada_ramp_up

    y2 = (max_avail * 1.1) + 1
    x2 = -y2 + initial_mw + scada_ramp_up

    x = [x1, x2]
    y = [y1, y2]

    ax.plot(x, y, color=kwargs.get('color'))

    return ax


def plot_joint_ramping_constraint_lhs(ax, initial_mw, scada_ramp_down, max_avail, **kwargs):
    """
    Plot joint ramping constraint RHS

    Energy Dispatch Target - Lower Regulating FCAS Target >= Initial MW - SCADA Ramp Down Capability

    if SCADA Ramp Down Rate > 0
    SCADA Ramp Down Capability = SCADA Ramp Down Rate ∗ Time Period
    """

    y1 = -1
    x1 = y1 + initial_mw - scada_ramp_down

    y2 = (max_avail * 1.1) + 1
    x2 = y2 + initial_mw - scada_ramp_down

    x = [x1, x2]
    y = [y1, y2]

    ax.plot(x, y, color=kwargs.get('color'))

    return ax


def plot_joint_capacity_constraint_lhs(ax, lower_reg_fcas_target, lower_reg_fcas_status, trapezium, **kwargs):
    """
    Plot joint capacity constraint RHS

    Energy Dispatch Target − Lower Slope Coeff x Contingency FCAS Target
    − [Lower Regulation FCAS enablment status] x Lower Regulating FCAS Target >= EnablementMin7
    """

    # Lower coefficient
    lower_coefficient = (trapezium['LowBreakpoint'] - trapezium['EnablementMin']) / trapezium['MaxAvail']

    y1 = -1
    x1 = trapezium['EnablementMin'] + (lower_coefficient * y1) + (lower_reg_fcas_status * lower_reg_fcas_target)

    y2 = (trapezium['MaxAvail'] * 1.1) + 1
    x2 = trapezium['EnablementMin'] + (lower_coefficient * y2) + (lower_reg_fcas_status * lower_reg_fcas_target)

    x = [x1, x2]
    y = [y1, y2]

    ax.plot(x, y, color=kwargs.get('color'))

    return ax


def plot_joint_capacity_constraint_rhs(ax, raise_reg_fcas_target, raise_reg_fcas_status, trapezium, **kwargs):
    """
    Plot joint capacity constraint LHS

    Energy Dispatch Target + Upper Slope Coeff x Contingency FCAS Target
    + [Raise Regulation FCAS enablement status] x Raise Regulating FCAS Target <= EnablementMax6
    """

    # Upper coefficient
    upper_coefficient = (trapezium['EnablementMax'] - trapezium['HighBreakpoint']) / trapezium['MaxAvail']

    y1 = -1
    x1 = trapezium['EnablementMax'] - (upper_coefficient * y1) - (raise_reg_fcas_status * raise_reg_fcas_target)

    y2 = (trapezium['MaxAvail'] * 1.1) + 1
    x2 = trapezium['EnablementMax'] - (upper_coefficient * y2) - (raise_reg_fcas_status * raise_reg_fcas_target)

    x = [x1, x2]
    y = [y1, y2]

    ax.plot(x, y, color=kwargs.get('color'))

    return ax


def plot_energy_regulating_fcas_constraint_lhs():
    """
    Plot joint energy and regulating FCAS constraint RHS

    Energy Dispatch Target − Lower Slope Coeff x Regulating FCAS Target >= EnablementMin9
    """
    pass


def plot_energy_regulating_fcas_constraint_rhs():
    """
    Plot joint energy and regulating FCAS constraint LHS

    Energy Dispatch Target + Upper Slope Coeff x Regulating FCAS Target <= EnablementMax8
    """
    pass


def plot_fcas_constraints(data, trader_id, trade_type):
    """Plot FCAS trapezium and constraints for a given trader and trade type"""

    fig, ax = plt.subplots()

    # Get FCAS trapezium
    unscaled = get_fcas_trapezium(data, trader_id, trade_type)

    # Scaled FCAS trapezium - R5RE and L5RE only offers for which trapezium is scaled
    scaled = get_fcas_trapezium_scaled(data, trader_id, trade_type)
    ax = plot_trapezium(unscaled, ax, color='red')
    ax = plot_trapezium(scaled, ax, color='blue')

    initial_mw = get_trader_initial_condition(data, trader_id, 'InitialMW', float)
    scada_ramp_up = get_trader_initial_condition(data, trader_id, 'SCADARampUpRate', float) / 12
    scada_ramp_down = get_trader_initial_condition(data, trader_id, 'SCADARampDnRate', float) / 12
    max_avail = unscaled['MaxAvail']

    # Mapping between trade type keys
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # FCAS and energy solution
    energy_solution = get_trader_solution_attribute(cdata, trader_id, '@EnergyTarget')
    fcas_solution = get_trader_solution_attribute(cdata, trader_id, key_map[trade_type])

    # Plot solution
    ax.scatter(x=[energy_solution], y=[fcas_solution], s=15, color='green')

    ax = plot_joint_ramping_constraint_rhs(ax, initial_mw, scada_ramp_up, max_avail, color='blue')
    ax = plot_joint_ramping_constraint_lhs(ax, initial_mw, scada_ramp_down, max_avail, color='blue')
    # ax = plot_joint_capacity_constraint_rhs(ax, enablement_max, high_breakpoint, max_avail, raise_reg_status)

    return fig, ax


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Case data in json format
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Trapezium
    # trap = get_fcas_trapezium(cdata, 'BW01', 'R5RE')
    # plot_fcas_constraints(cdata, 'GSTONE3', 'L5RE')
    # plt.show()

    trader_id, trade_type = 'GSTONE3', 'R6SE'
    # us = get_fcas_trapezium(cdata, trader_id, trade_type)
    sc = get_fcas_trapezium_scaled(cdata, trader_id, trade_type)

    fig, ax = plt.subplots()
    plot_trapezium(sc, ax)

    raise_reg_fcas_status = get_fcas_availability(cdata, trader_id, 'R5RE')
    raise_reg_fcas_target = get_trader_solution_attribute(cdata, trader_id, '@R5RegTarget')
    ax = plot_joint_capacity_constraint_rhs(ax, raise_reg_fcas_target, raise_reg_fcas_status, sc, color='green')

    lower_reg_fcas_status = get_fcas_availability(cdata, trader_id, 'L5RE')
    lower_reg_fcas_target = get_trader_solution_attribute(cdata, trader_id, '@L5RegTarget')
    ax = plot_joint_capacity_constraint_lhs(ax, lower_reg_fcas_target, lower_reg_fcas_status, sc, color='green')

    plt.show()
