"""Process data to be used in model"""

import os
import json
import time

try:
    import context
    import case
except ModuleNotFoundError:
    pass

import loaders
from lookup import convert_to_list


def get_region_index(data) -> list:
    """Get region index"""

    return list(data['Data']['Regions'].keys())


def get_trader_index(data) -> list:
    """Get trader index"""

    return list(data['Data']['Traders'].keys())


def get_trader_semi_dispatch_index(data) -> list:
    """Get semi-dispatch index"""

    return [k for k, v in data['Data']['Traders'].items() if v['Info']['SemiDispatch'] == '1']


def get_trader_offer_index(data) -> list:
    """Get trader offer index"""

    return [(i, k) for i, j in data['Data']['Traders'].items() for k in j['PriceBands'].keys()]


def get_trader_energy_offer_index(data) -> list:
    """Get trader energy offer index"""

    return [(i, k) for i, j in data['Data']['Traders'].items() for k in j['PriceBands'].keys() if k in ['ENOF', 'LDOF']]


def get_trader_fcas_offer_index(data) -> list:
    """Get trader FCAS offer index"""

    # FCAS offer types
    trade_types = ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']

    return [(i, k) for i, j in data['Data']['Traders'].items() for k in j['PriceBands'].keys() if k in trade_types]


def get_trader_fast_start_index(data) -> list:
    """Get fast start traders"""

    return [k for k, v in data['Data']['Traders'].items()
            if (v['Info'].get('FastStart') is not None) and (v['Info'].get('FastStart') == '1')]


def reorder_tuple(input_tuple) -> tuple:
    """Sort tuples alphabetically"""

    if input_tuple[0][0] > input_tuple[1][0]:
        return tuple((input_tuple[1], input_tuple[0]))
    else:
        return tuple((input_tuple[0], input_tuple[1]))


def get_trader_price_tied_bands(data) -> list:
    """Get price-tied generators"""

    # Price and quantity bands
    price_bands = get_trader_price_bands(data)
    quantity_bands = get_trader_quantity_bands(data)

    # Generator energy offer price bands
    filtered_price_bands = {k: v for k, v in price_bands.items() if k[1] == 'ENOF'}

    # Trader region
    trader_region = get_trader_info_attribute(data, 'RegionID', str)

    # Container for price tied bands
    price_tied = []

    # For each price band
    for i, j in filtered_price_bands.items():
        # Compare it to every other price band
        for m, n in filtered_price_bands.items():
            # Price bands must be in same region (also ignore the input trader - will of course match)
            if (m == i) or (trader_region[i[0]] != trader_region[m[0]]):
                continue

            # Check if price difference less than threshold - append to container if so
            if abs(j - n) < 1e-6:
                if (quantity_bands[m[0], m[1], m[2]] != 0) and (quantity_bands[i[0], i[1], i[2]] != 0):
                    price_tied.append((i, m))

    # Re-order tuples, get unique price-tied combinations, and sort alphabetically
    price_tied_reordered = [reorder_tuple(i) for i in price_tied]
    price_tied_unique = list(set(price_tied_reordered))
    price_tied_unique.sort()

    # Flatten to produce one tuple for a given pair of price-tied generators
    price_tied_flattened = [(i[0][0], i[0][1], i[0][2], i[1][0], i[1][1], i[1][2]) for i in price_tied_unique]

    return price_tied_flattened


def get_generic_constraint_index(data) -> list:
    """Get generic constraint index"""

    return list(data['Data']['GenericConstraints'].keys())


def get_generic_constraint_trader_variable_index(data) -> list:
    """Get generic constraint trader variable index"""

    return list(set([(k['TraderID'], k['TradeType']) for i, j in data['Data']['GenericConstraints'].items()
                     for k in j['LHSTerms']['TraderFactor']]))


def get_generic_constraint_interconnector_variable_index(data) -> list:
    """Get generic constraint interconnector variable index"""

    return list(set([k['InterconnectorID'] for i, j in data['Data']['GenericConstraints'].items()
                     for k in j['LHSTerms']['InterconnectorFactor']]))


def get_generic_constraint_region_variable_index(data) -> list:
    """Get generic constraint region variable index"""

    return list(set([(k['RegionID'], k['TradeType']) for i, j in data['Data']['GenericConstraints'].items()
                     for k in j['LHSTerms']['RegionFactor']]))


def get_mnsp_index(data) -> list:
    """Get MNSP index"""

    return [i for i, j in data['Data']['Interconnectors'].items() if j['Info']['MNSP'] == '1']


def get_mnsp_offer_index(data) -> list:
    """Get MNSP offer index"""

    return [(i, k) for i, j in data['Data']['Interconnectors'].items() if j['Info']['MNSP'] == '1'
            for k in j['PriceBands'].keys()]


def get_interconnector_index(data) -> list:
    """Get interconnector index"""

    return list(data['Data']['Interconnectors'].keys())


def get_interconnector_loss_model_breakpoint_index(data) -> list:
    """Get interconnector loss model breakpoints"""

    # Container for indices
    values = []
    for i, j in data['Data']['Interconnectors'].items():
        # Loss model segments
        segments = j['LossModel']['Segment']
        for k in range(len(segments) + 1):
            # Append index to container
            values.append((i, k))

    return values


def get_interconnector_loss_model_interval_index(data) -> list:
    """Get interconnector loss model interval index"""

    # Container for indices
    values = []
    for i, j in data['Data']['Interconnectors'].items():
        # Loss model segments
        segments = j['LossModel']['Segment']
        for k in range(len(segments)):
            # Append index to container
            values.append((i, k))

    return values


def get_trader_price_bands(data) -> dict:
    """Get trader price bands"""

    return {(i, k, b): v[f'PriceBand{b}'] for i, j in data['Data']['Traders'].items()
            for k, v in j['PriceBands'].items() for b in range(1, 11)}


def get_trader_quantity_bands(data) -> dict:
    """Get trader quantity bands"""

    return {(i, k, b): v[f'BandAvail{b}'] for i, j in data['Data']['Traders'].items()
            for k, v in j['QuantityBands'].items() for b in range(1, 11)}


def get_trader_quantity_band_attribute(data, attribute, func) -> dict:
    """Get trader quantity band attribute"""

    return {(i, k): func(v[attribute]) for i, j in data['Data']['Traders'].items()
            for k, v in j['QuantityBands'].items() if v.get(attribute) is not None}


def get_trader_info_attribute(data, attribute, func) -> dict:
    """Get trader info attribute"""

    return {i: func(j['Info'][attribute]) for i, j in data['Data']['Traders'].items()
            if j['Info'].get(attribute) is not None}


def get_trader_initial_condition_attribute(data, attribute, func) -> dict:
    """Get trader initial condition attribute"""

    return {i: func(j['InitialConditions'][attribute]) for i, j in data['Data']['Traders'].items()
            if j['InitialConditions'].get(attribute) is not None}


def get_trader_fcas_trapezium(data) -> dict:
    """Get FCAS trapeziums"""

    # FCAS offer trade types
    fcas_offers = ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']

    return {(i, k): {
        'EnablementMin': v['EnablementMin'],
        'LowBreakpoint': v['LowBreakpoint'],
        'HighBreakpoint': v['HighBreakpoint'],
        'EnablementMax': v['EnablementMax'],
        'MaxAvail': v['MaxAvail'],
    }
        for i, j in data['Data']['Traders'].items() for k, v in j['QuantityBands'].items() if k in fcas_offers}


def get_interconnector_initial_condition_attribute(data, attribute, func) -> dict:
    """Get interconnector initial condition attribute"""

    return {i: func(j['InitialConditions'][attribute]) for i, j in data['Data']['Interconnectors'].items()
            if j['InitialConditions'].get(attribute) is not None}


def get_interconnector_info_attribute(data, attribute, func) -> dict:
    """Get interconnector info attribute"""

    return {i: func(j['Info'][attribute]) for i, j in data['Data']['Interconnectors'].items()
            if j['Info'].get(attribute) is not None}


def get_interconnector_loss_model_attribute(data, attribute, func) -> dict:
    """Get interconnector loss model attribute"""

    return {i: func(j['LossModel'][attribute]) for i, j in data['Data']['Interconnectors'].items()
            if j['LossModel'].get(attribute) is not None}


def get_interconnector_loss_model_segment_attribute(data, attribute, func) -> dict:
    """Get interconnector loss model segment collection"""

    # Container for values
    values = {}
    for i, j in data['Data']['Interconnectors'].items():
        for k, v in enumerate(j['LossModel']['Segment']):
            # Extract loss model segment attribute
            values[(i, k)] = func(v[attribute])

    return values


def get_standardised_interconnector_loss_model_segments(data) -> dict:
    """Use breakpoints and segment factors to construct a new start-end representation for the MLF curve"""

    # Container for output
    out = {}
    for interconnector_id, params in data['Data']['Interconnectors'].items():
        # Check loss model
        segments = params['LossModel']['Segment']

        # First segment
        start = -params['LossModel']['LossLowerLimit']

        # Format segments with start, end, and factor
        new_segments = []
        for s in segments:
            segment = {'start': start, 'end': s['Limit'], 'factor': s['Factor']}
            start = s['Limit']
            new_segments.append(segment)

        # Append new segments to container
        out[interconnector_id] = new_segments

    return out


def get_mnsp_price_bands(data) -> dict:
    """Get MNSP price bands"""

    return {(i, k, b): v[f'PriceBand{b}'] for i, j in data['Data']['Interconnectors'].items()
            if j['Info']['MNSP'] == '1'
            for k, v in j['PriceBands'].items() for b in range(1, 11)}


def get_mnsp_quantity_bands(data) -> dict:
    """Get MNSP quantity bands"""

    return {(i, k, b): v[f'BandAvail{b}'] for i, j in data['Data']['Interconnectors'].items()
            if j['Info']['MNSP'] == '1'
            for k, v in j['QuantityBands'].items() for b in range(1, 11)}


def get_mnsp_quantity_band_attribute(data, attribute, func) -> dict:
    """Get MNSP quantity band attribute"""

    return {(i, k): func(v[attribute]) for i, j in data['Data']['Interconnectors'].items() if j['Info']['MNSP'] == '1'
            for k, v in j['QuantityBands'].items()}


def get_mnsp_info_attribute(data, attribute, func) -> dict:
    """Get MNSP info attribute"""

    return {i: func(j['Info'][attribute]) for i, j in data['Data']['Interconnectors'].items()
            if (j['Info']['MNSP'] == '1') and (j['Info'].get(attribute) is not None)}


def get_case_attribute(data, attribute, func):
    """Get case attribute"""

    return func(data['Data']['Case'][attribute])


def get_region_initial_condition_attribute(data, attribute, func):
    """Get region initial condition attribute"""

    return {i: func(j['InitialConditions'][attribute]) for i, j in data['Data']['Regions'].items()}


def get_region_info_attribute(data, attribute, func):
    """Get region info attribute"""

    return {i: func(j['Info'][attribute]) for i, j in data['Data']['Regions'].items()}


def get_generic_constraint_info_attribute(data, attribute, func):
    """Get generic constraint info attribute"""

    return {i: func(j['Info'][attribute]) for i, j in data['Data']['GenericConstraints'].items()}


def parse_constraint(constraint_data):
    """Constraint data"""

    # LHS terms
    lhs = constraint_data['LHSTerms']

    # Trader factors
    traders = {(i['TraderID'], i['TradeType']): float(i['Factor'])
               for i in convert_to_list(lhs.get('TraderFactor', []))}

    # Interconnector factors
    interconnectors = {(i['InterconnectorID']): float(i['Factor'])
                       for i in convert_to_list(lhs.get('InterconnectorFactor', []))}

    # Region factors
    regions = {(i['RegionID'], i['TradeType']): float(i['Factor'])
               for i in convert_to_list(lhs.get('RegionFactor', []))}

    # Combine constraint terms into single dictionary
    terms = {'traders': traders, 'interconnectors': interconnectors, 'regions': regions}

    return terms


def get_generic_constraint_lhs_terms(data) -> dict:
    """Generic constraint LHS terms"""

    return {i: parse_constraint(j) for i, j in data['Data']['GenericConstraints'].items()}


def get_intervention_status(data, mode):
    """Intervention status"""

    # Intervention flag
    intervention_flag = data['Data']['Case']['Intervention']

    if (intervention_flag == 'False') and (mode == 'physical'):
        return '0'
    elif (intervention_flag == 'False') and (mode == 'pricing'):
        return '0'
    elif (intervention_flag == 'True') and (mode == 'physical'):
        return '1'
    elif (intervention_flag == 'True') and (mode == 'pricing'):
        return '0'
    else:
        raise Exception('Unhandled case:', mode)


def parse_case_data(data, mode) -> dict:
    """
    Parse json data

    Parameters
    ----------
    data : dict
        NEM case file data

    mode : str
        Run mode. Either 'physical' or 'pricing'.

    Returns
    -------
    case_data : dict
        Dictionary containing case data to be read into model
    """

    # Intervention status
    intervention = get_intervention_status(data, mode)

    case_data = {
        'S_REGIONS': get_region_index(data),
        'S_TRADERS': get_trader_index(data),
        'S_TRADERS_SEMI_DISPATCH': get_trader_semi_dispatch_index(data),
        'S_TRADER_OFFERS': get_trader_offer_index(data),
        'S_TRADER_ENERGY_OFFERS': get_trader_energy_offer_index(data),
        'S_TRADER_FCAS_OFFERS': get_trader_fcas_offer_index(data),
        'S_TRADER_FAST_START': get_trader_fast_start_index(data),
        'S_GENERIC_CONSTRAINTS': get_generic_constraint_index(data),
        'S_GC_TRADER_VARS': get_generic_constraint_trader_variable_index(data),
        'S_GC_INTERCONNECTOR_VARS': get_generic_constraint_interconnector_variable_index(data),
        'S_GC_REGION_VARS': get_generic_constraint_region_variable_index(data),
        'S_MNSPS': get_mnsp_index(data),
        'S_MNSP_OFFERS': get_mnsp_offer_index(data),
        'S_INTERCONNECTORS': get_interconnector_index(data),
        'S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS': get_interconnector_loss_model_breakpoint_index(data),
        'S_INTERCONNECTOR_LOSS_MODEL_INTERVALS': get_interconnector_loss_model_interval_index(data),
        'P_CASE_ID': data['CaseID'],
        'P_INTERVENTION_STATUS': intervention,
        'P_TRADER_PRICE_BAND': get_trader_price_bands(data),
        'P_TRADER_QUANTITY_BAND': get_trader_quantity_bands(data),
        'P_TRADER_MAX_AVAIL': get_trader_quantity_band_attribute(data, 'MaxAvail', float),
        'P_TRADER_UIGF': get_trader_info_attribute(data, 'UIGF', float),
        'P_TRADER_INITIAL_MW': get_trader_initial_condition_attribute(data, 'InitialMW', float),
        'P_TRADER_WHAT_IF_INITIAL_MW': get_trader_initial_condition_attribute(data, 'WhatIfInitialMW', float),
        'P_TRADER_HMW': get_trader_initial_condition_attribute(data, 'HMW', float),
        'P_TRADER_LMW': get_trader_initial_condition_attribute(data, 'LMW', float),
        'P_TRADER_AGC_STATUS': get_trader_initial_condition_attribute(data, 'AGCStatus', str),
        'P_TRADER_SEMI_DISPATCH_STATUS': get_trader_info_attribute(data, 'SemiDispatch', str),
        'P_TRADER_REGION': get_trader_info_attribute(data, 'RegionID', str),
        'P_TRADER_PERIOD_RAMP_UP_RATE': get_trader_quantity_band_attribute(data, 'RampUpRate', float),
        'P_TRADER_PERIOD_RAMP_DN_RATE': get_trader_quantity_band_attribute(data, 'RampDnRate', float),
        'P_TRADER_TYPE': get_trader_info_attribute(data, 'TraderType', str),
        'P_TRADER_SCADA_RAMP_UP_RATE': get_trader_initial_condition_attribute(data, 'SCADARampUpRate', float),
        'P_TRADER_SCADA_RAMP_DN_RATE': get_trader_initial_condition_attribute(data, 'SCADARampDnRate', float),
        'P_TRADER_MIN_LOADING_MW': get_trader_info_attribute(data, 'MinLoadingMW', float),
        'P_TRADER_CURRENT_MODE': get_trader_info_attribute(data, 'CurrentMode', str),
        'P_TRADER_CURRENT_MODE_TIME': get_trader_info_attribute(data, 'CurrentModeTime', float),
        'P_TRADER_T1': get_trader_info_attribute(data, 'T1', float),
        'P_TRADER_T2': get_trader_info_attribute(data, 'T2', float),
        'P_TRADER_T3': get_trader_info_attribute(data, 'T3', float),
        'P_TRADER_T4': get_trader_info_attribute(data, 'T4', float),
        'P_TRADER_ENABLEMENT_MIN': get_trader_quantity_band_attribute(data, 'EnablementMin', float),
        'P_TRADER_LOW_BREAKPOINT': get_trader_quantity_band_attribute(data, 'LowBreakpoint', float),
        'P_TRADER_HIGH_BREAKPOINT': get_trader_quantity_band_attribute(data, 'HighBreakpoint', float),
        'P_TRADER_ENABLEMENT_MAX': get_trader_quantity_band_attribute(data, 'EnablementMax', float),
        'P_INTERCONNECTOR_INITIAL_MW': get_interconnector_initial_condition_attribute(data, 'InitialMW', float),
        'P_INTERCONNECTOR_TO_REGION': get_interconnector_info_attribute(data, 'ToRegion', str),
        'P_INTERCONNECTOR_FROM_REGION': get_interconnector_info_attribute(data, 'FromRegion', str),
        'P_INTERCONNECTOR_LOWER_LIMIT': get_interconnector_info_attribute(data, 'LowerLimit', float),
        'P_INTERCONNECTOR_UPPER_LIMIT': get_interconnector_info_attribute(data, 'UpperLimit', float),
        'P_INTERCONNECTOR_MNSP_STATUS': get_interconnector_info_attribute(data, 'MNSP', str),
        'P_INTERCONNECTOR_LOSS_SHARE': get_interconnector_loss_model_attribute(data, 'LossShare', float),
        'P_INTERCONNECTOR_LOSS_LOWER_LIMIT': get_interconnector_loss_model_attribute(data, 'LossLowerLimit', float),
        'P_INTERCONNECTOR_LOSS_SEGMENT_LIMIT': get_interconnector_loss_model_segment_attribute(data, 'Limit', float),
        'P_INTERCONNECTOR_LOSS_SEGMENT_FACTOR': get_interconnector_loss_model_segment_attribute(data, 'Factor', float),
        'P_MNSP_PRICE_BAND': get_mnsp_price_bands(data),
        'P_MNSP_QUANTITY_BAND': get_mnsp_quantity_bands(data),
        'P_MNSP_MAX_AVAILABLE': get_mnsp_quantity_band_attribute(data, 'MaxAvail', float),
        'P_MNSP_TO_REGION_LF': get_mnsp_info_attribute(data, 'ToRegionLF', float),
        'P_MNSP_TO_REGION_LF_EXPORT': get_mnsp_info_attribute(data, 'ToRegionLFExport', float),
        'P_MNSP_TO_REGION_LF_IMPORT': get_mnsp_info_attribute(data, 'ToRegionLFImport', float),
        'P_MNSP_FROM_REGION_LF': get_mnsp_info_attribute(data, 'FromRegionLF', float),
        'P_MNSP_FROM_REGION_LF_EXPORT': get_mnsp_info_attribute(data, 'FromRegionLFExport', float),
        'P_MNSP_FROM_REGION_LF_IMPORT': get_mnsp_info_attribute(data, 'FromRegionLFImport', float),
        'P_MNSP_LOSS_PRICE': get_case_attribute(data, 'MNSPLossesPrice', float),
        'P_MNSP_RAMP_UP_RATE': get_mnsp_quantity_band_attribute(data, 'RampUpRate', float),
        'P_MNSP_RAMP_DOWN_RATE': get_mnsp_quantity_band_attribute(data, 'RampDnRate', float),
        'P_REGION_INITIAL_DEMAND': get_region_initial_condition_attribute(data, 'InitialDemand', float),
        'P_REGION_ADE': get_region_initial_condition_attribute(data, 'ADE', float),
        'P_REGION_DF': get_region_info_attribute(data, 'DF', float),
        'P_GC_RHS': get_generic_constraint_info_attribute(data, 'RHS', float),
        'P_GC_TYPE': get_generic_constraint_info_attribute(data, 'Type', str),
        'P_CVF_GC': get_generic_constraint_info_attribute(data, 'ViolationPrice', float),
        'P_CVF_VOLL': get_case_attribute(data, 'VoLL', float),
        'P_CVF_ENERGY_DEFICIT_PRICE': get_case_attribute(data, 'EnergyDeficitPrice', float),
        'P_CVF_ENERGY_SURPLUS_PRICE': get_case_attribute(data, 'EnergySurplusPrice', float),
        'P_CVF_UIGF_SURPLUS_PRICE': get_case_attribute(data, 'UIGFSurplusPrice', float),
        'P_CVF_RAMP_RATE_PRICE': get_case_attribute(data, 'RampRatePrice', float),
        'P_CVF_CAPACITY_PRICE': get_case_attribute(data, 'CapacityPrice', float),
        'P_CVF_OFFER_PRICE': get_case_attribute(data, 'OfferPrice', float),
        'P_CVF_MNSP_OFFER_PRICE': get_case_attribute(data, 'MNSPOfferPrice', float),
        'P_CVF_MNSP_RAMP_RATE_PRICE': get_case_attribute(data, 'MNSPRampRatePrice', float),
        'P_CVF_MNSP_CAPACITY_PRICE': get_case_attribute(data, 'MNSPCapacityPrice', float),
        'P_CVF_AS_PROFILE_PRICE': get_case_attribute(data, 'ASProfilePrice', float),
        'P_CVF_AS_MAX_AVAIL_PRICE': get_case_attribute(data, 'ASMaxAvailPrice', float),
        'P_CVF_AS_ENABLEMENT_MIN_PRICE': get_case_attribute(data, 'ASEnablementMinPrice', float),
        'P_CVF_AS_ENABLEMENT_MAX_PRICE': get_case_attribute(data, 'ASEnablementMaxPrice', float),
        'P_CVF_INTERCONNECTOR_PRICE': get_case_attribute(data, 'InterconnectorPrice', float),
        'P_CVF_FAST_START_PRICE': get_case_attribute(data, 'FastStartPrice', float),
        'P_CVF_GENERIC_CONSTRAINT_PRICE': get_case_attribute(data, 'GenericConstraintPrice', float),
        'P_CVF_SATISFACTORY_NETWORK_PRICE': get_case_attribute(data, 'Satisfactory_Network_Price', float),
        'P_TIE_BREAK_PRICE': get_case_attribute(data, 'TieBreakPrice', float),
        'intermediate': {
            'generic_constraint_lhs_terms': get_generic_constraint_lhs_terms(data),
            'loss_model_segments': get_standardised_interconnector_loss_model_segments(data),
        }
    }

    return case_data


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, os.path.pardir, os.path.pardir,
                                  'nemweb', 'Reports', 'Data_Archive', 'NEMDE', 'zipped')

    di_year, di_month, di_day, di_interval = 2019, 10, 1, 18
    di_case_id = f'{di_year}{di_month:02}{di_day:02}{di_interval:03}'

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_directory, di_year, di_month, di_day, di_interval)
    cdata = json.loads(case_data_json)

    intervention_status = get_intervention_status(cdata, 'physical')
    formatted_case = case.construct_case(cdata, intervention_status)

    t0 = time.time()
    case = parse_case_data(formatted_case, intervention_status)
    print(time.time() - t0)
