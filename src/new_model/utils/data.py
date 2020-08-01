"""Convert case data into format that can be used to construct model instance"""

import os
import json


def convert_to_list(dict_or_list) -> list:
    """Convert a dict to list. Return input if list is given."""

    if isinstance(dict_or_list, dict):
        return [dict_or_list]
    elif isinstance(dict_or_list, list):
        return dict_or_list
    else:
        raise Exception(f'Unexpected type: {dict_or_list}')


def get_region_index(data) -> list:
    """Get NEM region index"""

    return [i['@RegionID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection')
                                     .get('Region'))]


def get_trader_index(data) -> list:
    """Get trader index"""

    return [i['@TraderID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                                     .get('Period').get('TraderPeriodCollection').get('TraderPeriod'))]


def get_trader_offer_index(data) -> list:
    """Get trader offer index"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade'))]


def get_generic_constraint_index(data) -> list:
    """Get generic constraint index"""

    return [i['@ConstraintID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                                         .get('Period').get('GenericConstraintPeriodCollection')
                                         .get('GenericConstraintPeriod'))]


def get_generic_constraint_trader_variable_index(data) -> list:
    """Get all trader variables within generic constraints"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for all trader variables
    trader_variables = []
    for i in constraints:
        lhs_factor_collection = i.get('LHSFactorCollection')

        # Continue if no LHS factors or no trader factors
        if (lhs_factor_collection is None) or (lhs_factor_collection.get('TraderFactor') is None):
            continue

        for j in convert_to_list(lhs_factor_collection.get('TraderFactor')):
            trader_variables.append((j['@TraderID'], j['@TradeType']))

    # Retain unique indices
    return list(set(trader_variables))


def get_generic_constraint_interconnector_variable_index(data) -> list:
    """Get all interconnector variables within generic constraints"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for all interconnector variables
    interconnector_variables = []
    for i in constraints:
        lhs_factor_collection = i.get('LHSFactorCollection')

        # Continue if no LHS factors or no interconnector factors
        if (lhs_factor_collection is None) or (lhs_factor_collection.get('InterconnectorFactor') is None):
            continue

        for j in convert_to_list(lhs_factor_collection.get('InterconnectorFactor')):
            interconnector_variables.append(j['@InterconnectorID'])

    # Retain unique indices
    return list(set(interconnector_variables))


def get_generic_constraint_region_variable_index(data) -> list:
    """Get generic constraint region variable indices"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for all region variables
    region_variables = []
    for i in constraints:
        lhs_factor_collection = i.get('LHSFactorCollection')

        # Continue if no LHS factors or no region factors
        if (lhs_factor_collection is None) or (lhs_factor_collection.get('RegionFactor') is None):
            continue

        for j in convert_to_list(lhs_factor_collection.get('RegionFactor')):
            region_variables.append((j['@RegionID'], j['@TradeType']))

    # Retain unique indices
    return list(set(region_variables))


def get_mnsp_index(data) -> list:
    """Get MNSP index"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Only retain MNSPs
    return [i['@InterconnectorID'] for i in interconnectors if i['@MNSP'] == '1']


def get_mnsp_offer_index(data) -> list:
    """Get MNSP offer index"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for offer index
    offer_index = []
    for i in interconnectors:
        # Non-MNSP interconnectors will not have the MNSPOfferCollection attribute
        if i.get('MNSPOfferCollection') is None:
            continue

        # Extract InterconnectorID and RegionID for each offer entry
        for j in i.get('MNSPOfferCollection').get('MNSPOffer'):
            offer_index.append((i['@InterconnectorID'], j['@RegionID']))

    return offer_index


def get_interconnector_index(data) -> list:
    """Get interconnector index"""

    return [i['@InterconnectorID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                                             .get('Period').get('InterconnectorPeriodCollection')
                                             .get('InterconnectorPeriod'))]


def get_trader_price_bands(data) -> dict:
    """Trader price bands"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Container for all price bands
    price_bands = {}
    for i in traders:
        # All trade types for a given trader
        trade_types = (i.get('TradePriceStructureCollection').get('TradePriceStructure')
                       .get('TradeTypePriceStructureCollection').get('TradeTypePriceStructure'))

        for j in convert_to_list(trade_types):
            # Price bands
            for k in range(1, 11):
                price_bands[(i['@TraderID'], j['@TradeType'], k)] = float(j.get(f'@PriceBand{k}'))

    return price_bands


def get_trader_quantity_bands(data):
    """Get trader quantity bands"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Container for quantity bands
    quantity_bands = {}
    for i in traders:
        for j in convert_to_list(i.get('TradeCollection').get('Trade')):
            # Quantity bands
            for k in range(1, 11):
                quantity_bands[(i['@TraderID'], j['@TradeType'], k)] = float(j[f'@BandAvail{k}'])

    return quantity_bands


def get_trader_max_available(data) -> dict:
    """Get trader max available"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Container for max available
    max_available = {}
    for i in traders:
        # UIGF for semi-dispatchable plant - Note: UIGF will override MaxAvail for semi-dispatchable plant
        uigf = i.get('@UIGF')

        for j in convert_to_list(i.get('TradeCollection').get('Trade')):
            # Use UIGF if trader is semi-dispatchable and an energy offer is provided
            if (j.get('@TradeType') in ['ENOF', 'LDOF']) and (uigf is not None):
                max_available[(i['@TraderID'], j['@TradeType'])] = float(uigf)

            # Else, use max available specified for the trade type
            else:
                max_available[(i['@TraderID'], j['@TradeType'])] = float(j['@MaxAvail'])

    return max_available


def get_trader_initial_condition_attributes(data, attribute) -> dict:
    """Get trader initial MW"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Container for initial MW data
    values = {}
    for i in traders:
        # Initial conditions
        for j in i.get('TraderInitialConditionCollection').get('TraderInitialCondition'):
            # Check matching attribute and extract value
            if j.get('@InitialConditionID') == attribute:
                values[i.get('@TraderID')] = float(j.get('@Value'))

    return values


def get_trader_agc_status(data) -> dict:
    """
    Get trader AGC status. Returns a dict with trader IDs as keys and a bool indicating the trader's AGC status.
    True -> AGC enable, False -> AGC not enabled.
    """

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Container for initial MW data
    values = {}
    for i in traders:
        # Initial conditions
        for j in i.get('TraderInitialConditionCollection').get('TraderInitialCondition'):
            # Check matching attribute and extract value
            if j.get('@InitialConditionID') == 'AGCStatus':
                if j.get('@Value') == '0':
                    values[i.get('@TraderID')] = False
                elif j.get('@Value') == '1':
                    values[i.get('@TraderID')] = True
                else:
                    raise Exception(f'Unexpected type: {i}')

    return values


def get_trader_regions(data) -> dict:
    """Get trader regions"""

    # NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.TraderPeriodCollection.TraderPeriod[0].@RegionID

    return {i['@TraderID']: i['@RegionID']
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))}


def get_mnsp_price_bands(data) -> dict:
    """Get MNSP price bands"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for price band information
    price_bands = {}
    for i in interconnectors:
        if i.get('MNSPPriceStructureCollection') is None:
            continue

        # MNSP price structure
        price_structure = (i.get('MNSPPriceStructureCollection').get('MNSPPriceStructure')
                           .get('MNSPRegionPriceStructureCollection').get('MNSPRegionPriceStructure'))
        for j in price_structure:
            for k in range(1, 11):
                price_bands[(i['@InterconnectorID'], j['@RegionID'], k)] = float(j[f'@PriceBand{k}'])

    return price_bands


def get_mnsp_quantity_bands(data) -> dict:
    """Get MNSP quantity bands"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for quantity band information
    quantity_bands = {}
    for i in interconnectors:
        if i.get('MNSPOfferCollection') is None:
            continue

        # MNSP offers
        offers = i.get('MNSPOfferCollection').get('MNSPOffer')
        for j in offers:
            for k in range(1, 11):
                quantity_bands[(i['@InterconnectorID'], j['@RegionID'], k)] = float(j[f'@BandAvail{k}'])

    return quantity_bands


def get_mnsp_offer_attribute(data, attribute) -> dict:
    """MNSP offer attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for MNSP offer attributes
    values = {}
    for i in interconnectors:
        if i.get('MNSPOfferCollection') is None:
            continue

        # MNSP offers
        offers = i.get('MNSPOfferCollection').get('MNSPOffer')
        for j in offers:
            for k in range(1, 11):
                values[(i['@InterconnectorID'], j['@RegionID'], k)] = float(j[f'@{attribute}'])

    return values


def parse_case_data_json(data) -> dict:
    """
    Parse json data

    Parameters
    ----------
    data : json
        NEM case file in JSON format

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
        'S_TRADER_OFFERS': get_trader_offer_index(data_dict),
        'S_GENERIC_CONSTRAINTS': get_generic_constraint_index(data_dict),
        'S_GC_TRADER_VARS': get_generic_constraint_trader_variable_index(data_dict),
        'S_GC_INTERCONNECTOR_VARS': get_generic_constraint_interconnector_variable_index(data_dict),
        'S_GC_REGION_VARS': get_generic_constraint_region_variable_index(data_dict),
        'S_MNSPS': get_mnsp_index(data_dict),
        'S_MNSP_OFFERS': get_mnsp_offer_index(data_dict),
        'S_INTERCONNECTORS': get_interconnector_index(data_dict),
        'P_TRADER_PRICE_BANDS': get_trader_price_bands(data_dict),
        'P_TRADER_QUANTITY_BANDS': get_trader_quantity_bands(data_dict),
        'P_TRADER_MAX_AVAILABLE': get_trader_max_available(data_dict),
        'P_TRADER_INITIAL_MW': get_trader_initial_condition_attributes(data_dict, 'InitialMW'),
        'P_TRADER_HMW': get_trader_initial_condition_attributes(data_dict, 'HMW'),
        'P_TRADER_LMW': get_trader_initial_condition_attributes(data_dict, 'LMW'),
        'P_TRADER_AGC_STATUS': get_trader_agc_status(data_dict),
        'P_TRADER_REGIONS': get_trader_regions(data_dict),
        'P_MNSP_PRICE_BANDS': get_mnsp_price_bands(data_dict),
        'P_MNSP_QUANTITY_BANDS': get_mnsp_quantity_bands(data_dict),
        'P_MNSP_MAX_AVAILABLE': get_mnsp_max_available(data_dict),
    }

    return case_data


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')
