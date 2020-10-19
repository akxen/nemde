"""Process data to be used in model"""

import os
import json
import time

import context

import case
import loaders
from lookup import convert_to_list, get_intervention_status


def parse_case_data_json(data, intervention) -> dict:
    """
    Parse json data

    Parameters
    ----------
    data : json
        NEM case file in JSON format

    intervention : str
        Intervention status

    Returns
    -------
    case_data : dict
        Dictionary containing case data to be read into model
    """

    # Convert to dictionary
    data_dict = json.loads(data)

    case_data = {
        'S_REGIONS': get_region_index(data_dict),
        'S_TRADERS': get_trader_index(data_dict),
        'S_TRADERS_SEMI_DISPATCH': get_trader_semi_dispatch_index(data_dict),
        'S_TRADER_OFFERS': get_trader_offer_index(data_dict),
        'S_TRADER_ENERGY_OFFERS': get_trader_energy_offer_index(data_dict),
        'S_TRADER_FCAS_OFFERS': get_trader_fcas_offer_index(data_dict),
        'S_TRADER_FAST_START': get_trader_fast_start_index(data_dict),
        'S_TRADER_PRICE_TIED': get_price_tied_bands(data_dict),
        'S_GENERIC_CONSTRAINTS': get_generic_constraint_index(data_dict),
        'S_GC_TRADER_VARS': get_generic_constraint_trader_variable_index(data_dict),
        'S_GC_INTERCONNECTOR_VARS': get_generic_constraint_interconnector_variable_index(data_dict),
        'S_GC_REGION_VARS': get_generic_constraint_region_variable_index(data_dict),
        'S_MNSPS': get_mnsp_index(data_dict),
        'S_MNSP_OFFERS': get_mnsp_offer_index(data_dict),
        'S_INTERCONNECTORS': get_interconnector_index(data_dict),
        'S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS': get_interconnector_loss_model_breakpoint_index(data_dict),
        'S_INTERCONNECTOR_LOSS_MODEL_INTERVALS': get_interconnector_loss_model_interval_index(data_dict),
        'P_CASE_ID': get_case_attribute(data_dict, '@CaseID', str),
        'P_INTERVENTION_STATUS': intervention,
        'P_TRADER_PRICE_BAND': get_trader_price_bands(data_dict),
        'P_TRADER_QUANTITY_BAND': get_trader_quantity_bands(data_dict),
        'P_TRADER_MAX_AVAILABLE': get_trader_period_trade_attribute(data_dict, '@MaxAvail', float),
        'P_TRADER_UIGF': get_trader_period_attribute(data_dict, '@UIGF', float),
        'P_TRADER_INITIAL_MW': get_trader_initial_condition_attribute(data_dict, 'InitialMW', float),
        'P_TRADER_WHAT_IF_INITIAL_MW': get_trader_initial_condition_attribute(data_dict, 'WhatIfInitialMW', float),
        'P_TRADER_HMW': get_trader_initial_condition_attribute(data_dict, 'HMW', float),
        'P_TRADER_LMW': get_trader_initial_condition_attribute(data_dict, 'LMW', float),
        'P_TRADER_AGC_STATUS': get_trader_initial_condition_attribute(data_dict, 'AGCStatus', str),
        'P_TRADER_SEMI_DISPATCH_STATUS': get_trader_collection_attribute(data_dict, '@SemiDispatch', str),
        'P_TRADER_REGION': get_trader_period_attribute(data_dict, '@RegionID', str),
        'P_TRADER_PERIOD_RAMP_UP_RATE': get_trader_period_trade_attribute(data_dict, '@RampUpRate', float),
        'P_TRADER_PERIOD_RAMP_DOWN_RATE': get_trader_period_trade_attribute(data_dict, '@RampDnRate', float),
        'P_TRADER_TYPE': get_trader_collection_attribute(data_dict, '@TraderType', str),
        'P_TRADER_SCADA_RAMP_UP_RATE': get_trader_initial_condition_attribute(data_dict, 'SCADARampUpRate', float),
        'P_TRADER_SCADA_RAMP_DOWN_RATE': get_trader_initial_condition_attribute(data_dict, 'SCADARampDnRate', float),
        'P_TRADER_MIN_LOADING_MW': get_trader_fast_start_attribute(data_dict, '@MinLoadingMW', float),
        'P_TRADER_CURRENT_MODE': get_trader_fast_start_attribute(data_dict, '@CurrentMode', str),
        'P_TRADER_CURRENT_MODE_TIME': get_trader_fast_start_attribute(data_dict, '@CurrentModeTime', float),
        'P_TRADER_T1': get_trader_fast_start_attribute(data_dict, '@T1', float),
        'P_TRADER_T2': get_trader_fast_start_attribute(data_dict, '@T2', float),
        'P_TRADER_T3': get_trader_fast_start_attribute(data_dict, '@T3', float),
        'P_TRADER_T4': get_trader_fast_start_attribute(data_dict, '@T4', float),
        'P_INTERCONNECTOR_INITIAL_MW': get_interconnector_collection_attribute(data_dict, 'InitialMW', float),
        'P_INTERCONNECTOR_TO_REGION': get_interconnector_period_collection_attribute(data_dict, '@ToRegion', str),
        'P_INTERCONNECTOR_FROM_REGION': get_interconnector_period_collection_attribute(data_dict, '@FromRegion', str),
        'P_INTERCONNECTOR_LOWER_LIMIT': get_interconnector_period_collection_attribute(data_dict, '@LowerLimit', float),
        'P_INTERCONNECTOR_UPPER_LIMIT': get_interconnector_period_collection_attribute(data_dict, '@UpperLimit', float),
        'P_INTERCONNECTOR_MNSP_STATUS': get_interconnector_period_collection_attribute(data_dict, '@MNSP', str),
        'P_INTERCONNECTOR_LOSS_SHARE': get_interconnector_loss_model_attribute(data_dict, '@LossShare', float),
        'P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X': get_interconnector_loss_model_breakpoints_x(data_dict),
        'P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y': get_interconnector_loss_model_breakpoints_y(data_dict),
        'P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE': get_interconnector_initial_loss_estimate(data_dict),
        'P_MNSP_PRICE_BAND': get_mnsp_price_bands(data_dict),
        'P_MNSP_QUANTITY_BAND': get_mnsp_quantity_bands(data_dict),
        'P_MNSP_MAX_AVAILABLE': get_mnsp_quantity_band_attribute(data_dict, '@MaxAvail', float),
        'P_MNSP_TO_REGION_LF': get_mnsp_period_collection_attribute(data_dict, '@ToRegionLF', float),
        'P_MNSP_TO_REGION_LF_EXPORT': get_mnsp_period_collection_attribute(data_dict, '@ToRegionLFExport', float),
        'P_MNSP_TO_REGION_LF_IMPORT': get_mnsp_period_collection_attribute(data_dict, '@ToRegionLFImport', float),
        'P_MNSP_FROM_REGION_LF': get_mnsp_period_collection_attribute(data_dict, '@FromRegionLF', float),
        'P_MNSP_FROM_REGION_LF_EXPORT': get_mnsp_period_collection_attribute(data_dict, '@FromRegionLFExport', float),
        'P_MNSP_FROM_REGION_LF_IMPORT': get_mnsp_period_collection_attribute(data_dict, '@FromRegionLFImport', float),
        'P_MNSP_LOSS_PRICE': get_case_attribute(data_dict, '@MNSPLossesPrice', float),
        'P_MNSP_RAMP_UP_RATE': get_mnsp_quantity_band_attribute(data_dict, '@RampUpRate', float),
        'P_MNSP_RAMP_DOWN_RATE': get_mnsp_quantity_band_attribute(data_dict, '@RampDnRate', float),
        'P_MNSP_REGION_LOSS_INDICATOR': get_mnsp_region_loss_indicator(data_dict),
        'P_REGION_INITIAL_DEMAND': get_region_initial_condition_attribute(data_dict, 'InitialDemand', float),
        'P_REGION_ADE': get_region_initial_condition_attribute(data_dict, 'ADE', float),
        'P_REGION_DF': get_region_period_collection_attribute(data_dict, '@DF', float),
        'P_GC_RHS': get_generic_constraint_rhs(data_dict, intervention),
        'P_GC_TYPE': get_generic_constraint_collection_attribute(data_dict, '@Type', str),
        'P_CVF_GC': get_generic_constraint_collection_attribute(data_dict, '@ViolationPrice', float),
        'P_CVF_VOLL': get_case_attribute(data_dict, '@VoLL', float),
        'P_CVF_ENERGY_DEFICIT_PRICE': get_case_attribute(data_dict, '@EnergyDeficitPrice', float),
        'P_CVF_ENERGY_SURPLUS_PRICE': get_case_attribute(data_dict, '@EnergySurplusPrice', float),
        'P_CVF_UIGF_SURPLUS_PRICE': get_case_attribute(data_dict, '@UIGFSurplusPrice', float),
        'P_CVF_RAMP_RATE_PRICE': get_case_attribute(data_dict, '@RampRatePrice', float),
        'P_CVF_CAPACITY_PRICE': get_case_attribute(data_dict, '@CapacityPrice', float),
        'P_CVF_OFFER_PRICE': get_case_attribute(data_dict, '@OfferPrice', float),
        'P_CVF_MNSP_OFFER_PRICE': get_case_attribute(data_dict, '@MNSPOfferPrice', float),
        'P_CVF_MNSP_RAMP_RATE_PRICE': get_case_attribute(data_dict, '@MNSPRampRatePrice', float),
        'P_CVF_MNSP_CAPACITY_PRICE': get_case_attribute(data_dict, '@MNSPCapacityPrice', float),
        'P_CVF_AS_PROFILE_PRICE': get_case_attribute(data_dict, '@ASProfilePrice', float),
        'P_CVF_AS_MAX_AVAIL_PRICE': get_case_attribute(data_dict, '@ASMaxAvailPrice', float),
        'P_CVF_AS_ENABLEMENT_MIN_PRICE': get_case_attribute(data_dict, '@ASEnablementMinPrice', float),
        'P_CVF_AS_ENABLEMENT_MAX_PRICE': get_case_attribute(data_dict, '@ASEnablementMaxPrice', float),
        'P_CVF_INTERCONNECTOR_PRICE': get_case_attribute(data_dict, '@InterconnectorPrice', float),
        'P_CVF_FAST_START_PRICE': get_case_attribute(data_dict, '@FastStartPrice', float),
        'P_CVF_GENERIC_CONSTRAINT_PRICE': get_case_attribute(data_dict, '@GenericConstraintPrice', float),
        'P_CVF_SATISFACTORY_NETWORK_PRICE': get_case_attribute(data_dict, '@Satisfactory_Network_Price', float),
        'P_TIE_BREAK_PRICE': get_case_attribute(data_dict, '@TieBreakPrice', float),
        'preprocessed': {
            'GC_LHS_TERMS': get_generic_constraint_lhs_terms(data_dict),
            'FCAS_TRAPEZIUM': get_trader_fcas_trapezium(data_dict),
            'FCAS_AVAILABILITY_STATUS': get_trader_fcas_availability_status(data_dict)
        },
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

    t0 = time.time()
    intervention_status = get_intervention_status(cdata, 'physical')
    out_case = case.construct_case(cdata, intervention_status)
    print(time.time() - t0)
