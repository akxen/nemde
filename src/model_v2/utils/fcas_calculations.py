"""Compute max availability for each service"""

import os
import json

import pandas as pd

import loaders


def convert_to_list(dict_or_list) -> list:
    """Convert dict to list"""

    if isinstance(dict_or_list, dict):
        return [dict_or_list]
    elif isinstance(dict_or_list, list):
        return dict_or_list
    else:
        raise Exception('Unexpected type:', dict_or_list)


def get_trader_initial_condition_attribute(data, trader_id, attribute, func):
    """Get trader initial condition"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in convert_to_list(i.get('TraderInitialConditionCollection').get('TraderInitialCondition')):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise Exception('No attribute found:', trader_id, attribute)


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

    raise Exception('No attribute found:', trader_id, trade_type, attribute)


def get_trader_solution_attribute(data, trader_id, attribute, func):
    """Get trader solution attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    for i in traders:
        if (i['@TraderID'] == trader_id) and (i['@Intervention'] == '0'):
            return func(i[attribute])

    raise Exception('No attribute found:', trader_id, attribute)


def get_effective_r5re_max_available(data, trader_id):
    """Get effective R5RE max available"""

    # Max available
    max_avail = get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@MaxAvail', float)

    # AGC ramp rate - need to divide by 12 to get ramp rate over 5 min interval
    agc_ramp_rate = get_trader_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float) / 12

    return min(max_avail, agc_ramp_rate)


def get_effective_r5re_enablement_max(data, trader_id):
    """Get effective R5RE enablement max"""

    # Enablement max
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@EnablementMax', float)

    # AGC upper limit
    agc_upper_limit = get_trader_initial_condition_attribute(data, trader_id, 'HMW', float)

    return min(enablement_max, agc_upper_limit)


def get_effective_r5re_enablement_min(data, trader_id):
    """Get effective R5RE enablement min"""

    # Enablement min
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@EnablementMin', float)

    # AGC lower limit
    agc_lower_limit = get_trader_initial_condition_attribute(data, trader_id, 'LMW', float)

    return max(enablement_min, agc_lower_limit)


def get_effective_l5re_max_available(data, trader_id):
    """Get effective L5RE max available"""

    # Max available
    max_avail = get_trader_quantity_band_attribute(data, trader_id, 'L5RE', '@MaxAvail', float)

    # AGC ramp rate - need to divide by 12 to get ramp rate over 5 min interval
    # - docs say ramp up rate but think down rate correct
    agc_ramp_rate = get_trader_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float) / 12

    return min(max_avail, agc_ramp_rate)


def get_effective_l5re_enablement_max(data, trader_id):
    """Get effective L5RE enablement max"""

    # Enablement max
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, 'L5RE', '@EnablementMax', float)

    # AGC upper limit
    agc_upper_limit = get_trader_initial_condition_attribute(data, trader_id, 'HMW', float)

    return min(enablement_max, agc_upper_limit)


def get_effective_l5re_enablement_min(data, trader_id):
    """Get effective L5RE enablement min"""

    # Enablement min
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, 'L5RE', '@EnablementMin', float)

    # AGC lower limit
    agc_lower_limit = get_trader_initial_condition_attribute(data, trader_id, 'LMW', float)

    return max(enablement_min, agc_lower_limit)


def get_joint_ramp_raise_max(data, trader_id):
    """Get joint ramp raise max term"""

    # Initial MW
    initial_mw = get_trader_initial_condition_attribute(data, trader_id, 'InitialMW', float)

    # AGC ramp rate - need to divide by 12 to get ramp rate over 5 min interval
    agc_ramp_rate = get_trader_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float) / 12

    return initial_mw + agc_ramp_rate


def get_joint_ramp_lower_min(data, trader_id):
    """Get joint ramp lower min term"""

    # Initial MW
    initial_mw = get_trader_initial_condition_attribute(data, trader_id, 'InitialMW', float)

    # AGC ramp rate - need to divide by 12 to get ramp rate over 5 min interval
    agc_ramp_rate = get_trader_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float) / 12

    return initial_mw - agc_ramp_rate


def get_lower_slope_coefficient(data, trader_id, trade_type):
    """Get lower slope coefficient"""

    low_breakpoint = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@LowBreakpoint', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    max_available = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    return (low_breakpoint - enablement_min) / max_available


def get_upper_slope_coefficient(data, trader_id, trade_type):
    """Get upper slope coefficient"""

    enablement_max = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    high_breakpoint = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@HighBreakpoint', float)
    max_available = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    return (enablement_max - high_breakpoint) / max_available


def get_r5re_term_1(data, trader_id):
    """Get effective max available"""

    return get_effective_r5re_max_available(data, trader_id)


def get_r5re_term_2(data, trader_id):
    """Get upper slope constraint"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)

    enablement_max = get_effective_r5re_enablement_max(data, trader_id)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R5RE')

    term = (enablement_max - energy_target) / upper_slope_coefficient

    return term


def get_r5re_term_3(data, trader_id):
    """Get lower slope constraint"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)

    enablement_min = get_effective_r5re_enablement_min(data, trader_id)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'R5RE')

    # Return None if slope coefficient is 0
    if lower_slope_coefficient == 0:
        return None

    # Compute term
    term = (energy_target - enablement_min) / lower_slope_coefficient

    return term


def get_r5re_term_4(data, trader_id):
    """Get R6SE limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    fcas_target = get_trader_solution_attribute(data, trader_id, '@R6Target', float)
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, 'R6SE', '@EnablementMax', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R6SE')

    return enablement_max - energy_target - (upper_slope_coefficient * fcas_target)


def get_r5re_term_5(data, trader_id):
    """Get R60S limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    fcas_target = get_trader_solution_attribute(data, trader_id, '@R60Target', float)
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, 'R60S', '@EnablementMax', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R60S')

    return enablement_max - energy_target - (upper_slope_coefficient * fcas_target)


def get_r5re_term_6(data, trader_id):
    """Get R5MI limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    fcas_target = get_trader_solution_attribute(data, trader_id, '@R5Target', float)
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, 'R5MI', '@EnablementMax', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R5MI')

    return enablement_max - energy_target - (upper_slope_coefficient * fcas_target)


def get_r5re_term_7(data, trader_id):
    """Ramping constraint"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    joint_ramp_raise_max = get_joint_ramp_raise_max(data, trader_id)

    return joint_ramp_raise_max - energy_target


def get_l5re_term_1(data, trader_id):
    """Get effective max available"""

    return get_effective_l5re_max_available(data, trader_id)


def get_l5re_term_2(data, trader_id):
    """Get upper slope constraint"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)

    enablement_max = get_effective_l5re_enablement_max(data, trader_id)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'L5RE')

    # Return None if upper slope coefficient 0
    if upper_slope_coefficient == 0:
        return None

    term = (enablement_max - energy_target) / upper_slope_coefficient

    return term


def get_l5re_term_3(data, trader_id):
    """Get lower slope constraint"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)

    enablement_min = get_effective_l5re_enablement_min(data, trader_id)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L5RE')

    # Return None if slope coefficient is 0
    if lower_slope_coefficient == 0:
        return None

    # Compute term
    term = (energy_target - enablement_min) / lower_slope_coefficient

    return term


def get_l5re_term_4(data, trader_id):
    """Get R6SE limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    fcas_target = get_trader_solution_attribute(data, trader_id, '@L6Target', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, 'L6SE', '@EnablementMin', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L6SE')

    return energy_target - enablement_min - (lower_slope_coefficient * fcas_target)


def get_l5re_term_5(data, trader_id):
    """Get R60S limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    fcas_target = get_trader_solution_attribute(data, trader_id, '@L60Target', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, 'L60S', '@EnablementMin', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L60S')

    return energy_target - enablement_min - (lower_slope_coefficient * fcas_target)


def get_l5re_term_6(data, trader_id):
    """Get R5MI limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    fcas_target = get_trader_solution_attribute(data, trader_id, '@L5Target', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, 'L5MI', '@EnablementMin', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L5MI')

    return energy_target - enablement_min - (lower_slope_coefficient * fcas_target)


def get_l5re_term_7(data, trader_id):
    """Ramping constraint"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    joint_ramp_lower_min = get_joint_ramp_lower_min(data, trader_id)

    return energy_target - joint_ramp_lower_min


def get_regulating_raise_availability(data, trader_id):
    """Get regulating raise availability R5RE"""

    # Compute terms
    term_1 = get_r5re_term_1(data, trader_id)
    term_2 = get_r5re_term_2(data, trader_id)
    term_3 = get_r5re_term_3(data, trader_id)
    term_4 = get_r5re_term_4(data, trader_id)
    term_5 = get_r5re_term_5(data, trader_id)
    term_6 = get_r5re_term_6(data, trader_id)
    term_7 = get_r5re_term_7(data, trader_id)

    # All terms in a list
    terms = [term_1, term_2, term_3, term_4, term_5, term_6, term_7]

    # Most restrictive term
    min_term = min([i for i in terms if i is not None])

    # Combine terms into single dictionary
    out = {
        'term_1': term_1,
        'term_2': term_2,
        'term_3': term_3,
        'term_4': term_4,
        'term_5': term_5,
        'term_6': term_6,
        'term_7': term_7,
        'min': min_term,
        'min_term': [f'term_{i + 1}' for i, j in enumerate(terms) if j == min_term],
    }

    return out


def get_regulating_lower_availability(data, trader_id):
    """Get regulating lower availability L5RE"""

    # Compute terms
    term_1 = get_l5re_term_1(data, trader_id)
    term_2 = get_l5re_term_2(data, trader_id)
    term_3 = get_l5re_term_3(data, trader_id)
    term_4 = get_l5re_term_4(data, trader_id)
    term_5 = get_l5re_term_5(data, trader_id)
    term_6 = get_l5re_term_6(data, trader_id)
    term_7 = get_l5re_term_7(data, trader_id)

    # All terms in a list
    terms = [term_1, term_2, term_3, term_4, term_5, term_6, term_7]

    # Most restrictive term
    min_term = min([i for i in terms if i is not None])

    # Combine terms into single dictionary
    out = {
        'term_1': term_1,
        'term_2': term_2,
        'term_3': term_3,
        'term_4': term_4,
        'term_5': term_5,
        'term_6': term_6,
        'term_7': term_7,
        'min': min_term,
        'min_term': [f'term_{i + 1}' for i, j in enumerate(terms) if j == min_term],
    }

    return out


def get_contingency_raise_term_1(data, trader_id, trade_type):
    """FCAS service max availability"""

    # Assuming FCAS max available not scaled
    max_available = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    return max_available


def get_contingency_raise_term_2(data, trader_id, trade_type):
    """Get FCAS upper slope limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)

    # Return None if slope coefficient is 0
    if upper_slope_coefficient == 0:
        return None

    return (enablement_max - energy_target) / upper_slope_coefficient


def get_contingency_raise_term_3(data, trader_id, trade_type):
    """Get FCAS lower slope limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)

    # Return None if slope coefficient is 0
    if lower_slope_coefficient == 0:
        return None

    return (energy_target - enablement_min) / lower_slope_coefficient


def get_contingency_raise_term_4(data, trader_id, trade_type):
    """Get joint ramping constraint limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    regulation_target = get_trader_solution_attribute(data, trader_id, '@R5RegTarget', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)

    return (enablement_max - energy_target - regulation_target) / upper_slope_coefficient


def get_contingency_raise_service_availability(data, trader_id, trade_type):
    """Get FCAS contingency raise service max availability"""

    term_1 = get_contingency_raise_term_1(data, trader_id, trade_type)
    term_2 = get_contingency_raise_term_2(data, trader_id, trade_type)
    term_3 = get_contingency_raise_term_3(data, trader_id, trade_type)
    term_4 = get_contingency_raise_term_4(data, trader_id, trade_type)

    # All terms in a list
    terms = [term_1, term_2, term_3, term_4]

    # Most restrictive term
    min_term = min([i for i in terms if i is not None])

    # Combine terms into single dictionary
    out = {
        'term_1': term_1,
        'term_2': term_2,
        'term_3': term_3,
        'term_4': term_4,
        'min': min_term,
        'min_term': [f'term_{i + 1}' for i, j in enumerate(terms) if j == min_term],
    }

    return out


def get_contingency_lower_term_1(data, trader_id, trade_type):
    """FCAS service max availability"""

    # Assuming FCAS max available not scaled
    max_available = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    return max_available


def get_contingency_lower_term_2(data, trader_id, trade_type):
    """Get FCAS upper slope limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    enablement_max = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)

    # Return None if slope coefficient is 0
    if upper_slope_coefficient == 0:
        return None

    return (enablement_max - energy_target) / upper_slope_coefficient


def get_contingency_lower_term_3(data, trader_id, trade_type):
    """Get FCAS lower slope limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)

    # Return None if slope coefficient is 0
    if lower_slope_coefficient == 0:
        return None

    return (energy_target - enablement_min) / lower_slope_coefficient


def get_contingency_lower_term_4(data, trader_id, trade_type):
    """Get joint ramping constraint limit"""

    energy_target = get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    enablement_min = get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    regulation_target = get_trader_solution_attribute(data, trader_id, '@L5RegTarget', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, trade_type)

    return (energy_target - enablement_min - regulation_target) / lower_slope_coefficient


def get_contingency_lower_service_availability(data, trader_id, trade_type):
    """Get FCAS contingency lower service max availability"""

    term_1 = get_contingency_lower_term_1(data, trader_id, trade_type)
    term_2 = get_contingency_lower_term_2(data, trader_id, trade_type)
    term_3 = get_contingency_lower_term_3(data, trader_id, trade_type)
    term_4 = get_contingency_lower_term_4(data, trader_id, trade_type)

    # All terms in a list
    terms = [term_1, term_2, term_3, term_4]

    # Most restrictive term
    min_term = min([i for i in terms if i is not None])

    # Combine terms into single dictionary
    out = {
        'term_1': term_1,
        'term_2': term_2,
        'term_3': term_3,
        'term_4': term_4,
        'min': min_term,
        'min_term': [f'term_{i + 1}' for i, j in enumerate(terms) if j == min_term],
    }

    return out


def get_trader_fcas_max_availability(data, trader_id):
    """Get max availability for each FCAS service"""

    try:
        r5re = get_regulating_raise_availability(data, trader_id)
    except:
        r5re = None

    try:
        l5re = get_regulating_lower_availability(data, trader_id)
    except:
        l5re = None

    try:
        r6se = get_contingency_raise_service_availability(data, trader_id, 'R6SE')
    except:
        r6se = None

    try:
        r60s = get_contingency_raise_service_availability(data, trader_id, 'R60S')
    except:
        r60s = None

    try:
        r5mi = get_contingency_raise_service_availability(data, trader_id, 'R5MI')
    except:
        r5mi = None

    try:
        l6se = get_contingency_raise_service_availability(data, trader_id, 'L6SE')
    except:
        l6se = None

    try:
        l60s = get_contingency_raise_service_availability(data, trader_id, 'L60S')
    except:
        l60s = None

    try:
        l5mi = get_contingency_raise_service_availability(data, trader_id, 'L5MI')
    except:
        l5mi = None

    # Dictionary containing FCAS availability
    out = {
        (trader_id, 'R5RE'): r5re,
        (trader_id, 'L5RE'): l5re,
        (trader_id, 'R6SE'): r6se,
        (trader_id, 'R60S'): r60s,
        (trader_id, 'R5MI'): r5mi,
        (trader_id, 'L6SE'): l6se,
        (trader_id, 'L60S'): l60s,
        (trader_id, 'L5MI'): l5mi
    }

    return out


def get_fcas_max_availability(data):
    """Get max FCAS availability for all generators"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Container for FCAS availability
    out = {}
    for i in traders:
        trader_fcas_availability = get_trader_fcas_max_availability(data, i['@TraderID'])
        out = {**out, **trader_fcas_availability}

    # Convert to DataFrame
    df = pd.DataFrame(out).T.dropna(how='all', axis=0)

    return out, df


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # a1 = get_regulating_raise_availability(cdata, 'BW01')
    # a2 = get_regulating_lower_availability(cdata, 'BW01')
    # a3 = get_contingency_raise_service_availability(cdata, 'BW01', 'R6SE')
    # a4 = get_contingency_raise_service_availability(cdata, 'BW01', 'R60S')
    # a5 = get_contingency_raise_service_availability(cdata, 'BW01', 'R5MI')
    # a6 = get_contingency_lower_service_availability(cdata, 'BW01', 'L6SE')
    # a7 = get_contingency_lower_service_availability(cdata, 'BW01', 'L60S')
    # a8 = get_contingency_lower_service_availability(cdata, 'BW01', 'L5MI')
    #
    # trader_id = 'BW01'

    max_fcas, df_max_fcas = get_fcas_max_availability(cdata)
