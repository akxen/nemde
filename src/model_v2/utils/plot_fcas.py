"""Plot FCAS solution"""

import os
import json
import math

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


def get_trader_initial_condition(data, trader_id, attribute):
    """Get trader initial condition"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in i.get('TraderInitialConditionCollection').get('TraderInitialCondition'):
                if j['@InitialConditionID'] == attribute:
                    return float(j['@Value'])


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


def get_slope(x1, y1, x2, y2):
    """Get slope between two coordinates"""

    try:
        return (y2 - y1) / (x2 - x1)
    except ZeroDivisionError:
        return math.inf


def get_new_low_breakpoint(enablement_min, slope):
    """Get new low breakpoint"""
    pass


def get_intersection(x_intercept_1, m_1, x_intercept_2, m_2):
    """Get intersection"""

    if m_1 is math.inf:
        return

    return ()


def scale_fcas_trapezium_agc_enablement_min_lhs(trapezium, agc_enablement_min):
    """FCAS trapezium scaled by AGC enablement min"""

    # No scaling applied if AGC enablement min is None (from FCAS docs)
    if agc_enablement_min is None:
        return trapezium

    # AGC enablement min does not influence trapezium
    if agc_enablement_min < trapezium['EnablementMin']:
        return trapezium

    # Get slope
    x1, y1 = trapezium['EnablementMin'], 0
    x2, y2 = trapezium['LowBreakpoint'], trapezium['MaxAvail']
    slope = get_slope(x1, y1, x2, y2)

    # Vertical line
    if slope is math.inf:
        trapezium['EnablementMin'] = agc_enablement_min
        trapezium['LowBreakpoint'] = agc_enablement_min

    # Non-vertical line
    else:
        trapezium['EnablementMin'] = agc_enablement_min
        trapezium['LowBreakpoint'] = get_new_low_breakpoint(trapezium['EnablementMin'], slope)




def get_fcas_trapezium_scaled(trader_id, trade_type):
    """Get scaled FCAS trapezium"""
    pass


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


def plot_joint_capacity_constraint_lhs():
    """
    Plot joint capacity constraint LHS

    Energy Dispatch Target + Upper Slope Coeff x Contingency FCAS Target
    + [Raise Regulation FCAS enablement status] x Raise Regulating FCAS Target <= EnablementMax6
    """
    pass


def plot_joint_capacity_constraint_rhs():
    """
    Plot joint capacity constraint RHS

    Energy Dispatch Target − Lower Slope Coeff x Contingency FCAS Target
    − [Lower Regulation FCAS enablment status] x Lower Regulating FCAS Target >= EnablementMin7
    """
    pass


def plot_energy_regulating_fcas_constraint_lhs():
    """
    Plot joint energy and regulating FCAS constraint LHS

    Energy Dispatch Target + Upper Slope Coeff x Regulating FCAS Target <= EnablementMax8
    """
    pass


def plot_energy_regulating_fcas_constraint_rhs():
    """
    Plot joint energy and regulating FCAS constraint RHS

    Energy Dispatch Target − Lower Slope Coeff x Regulating FCAS Target >= EnablementMin9
    """
    pass


def plot_fcas_constraints(data, trader_id, trade_type):
    """Plot FCAS trapezium and constraints for a given trader and trade type"""

    fig, ax = plt.subplots()

    # Get FCAS trapezium
    unscaled = get_fcas_trapezium(data, trader_id, trade_type)

    # Scaled FCAS trapezium - R5RE and L5RE only offers for which trapezium is scaled
    # scaled = get_fcas_trapezium_scaled(data, trader_id, trade_type)
    ax = plot_trapezium(unscaled, ax, color='red')
    # ax = plot_trapezium(scaled, ax, style={'color': 'blue'})

    initial_mw = get_trader_initial_condition(data, trader_id, 'InitialMW')
    scada_ramp_up = get_trader_initial_condition(data, trader_id, 'SCADARampUpRate') / 12
    scada_ramp_down = get_trader_initial_condition(data, trader_id, 'SCADARampDnRate') / 12
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
    trap = get_fcas_trapezium(cdata, 'BW01', 'R5RE')
    plot_fcas_constraints(cdata, 'BW01', 'R5RE')
    plt.show()
