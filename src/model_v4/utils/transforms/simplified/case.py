"""Reformat NEMDE case file into a simplified format"""

import os
import json
import time

# import context

import loaders
from lookup import convert_to_list, get_intervention_status


def parse_case_attributes(data) -> dict:
    """Parse case data"""

    # Keys which should remain strings within the output dictionary
    str_keys = ['@CaseID', '@CaseType', '@Intervention', '@SwitchRunInitialStatus', '@UIGF_ATime', '@UseSOS2LossModel']

    return {k.replace('@', ''): v if k in str_keys else float(v)
            for k, v in data['NEMSPDCaseFile']['NemSpdInputs']['Case'].items()}


def get_trader_collection_data(data, trader_id) -> dict:
    """Get trader collection information"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            return i

    raise LookupError('Attribute not found:', trader_id)


def get_trader_period_data(data, trader_id) -> dict:
    """Get trader period information"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            return i

    raise LookupError('Attribute not found:', trader_id)


def get_interconnector_collection_data(data, interconnector_id) -> dict:
    """Get interconnector collection information"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return i

    raise LookupError('Attribute not found:', interconnector_id)


def get_interconnector_period_data(data, interconnector_id) -> dict:
    """Get interconnector period information"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return i

    raise LookupError('Attribute not found:', interconnector_id)


def get_region_collection_data(data, region_id) -> dict:
    """Get region collection data"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    for i in regions:
        if i['@RegionID'] == region_id:
            return i

    raise LookupError('Attribute not found:', region_id)


def get_region_period_data(data, region_id) -> dict:
    """Get region period data"""

    # All regions
    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('RegionPeriodCollection').get('RegionPeriod'))

    for i in regions:
        if i['@RegionID'] == region_id:
            return i

    raise LookupError('Attribute not found:', region_id)


def get_generic_constraint_collection_data(data, constraint_id) -> dict:
    """Get Generic Constraint collection data"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    for i in constraints:
        if i['@ConstraintID'] == constraint_id:
            return i

    raise LookupError('Attribute not found:', constraint_id)


def get_generic_constraint_period_data(data, constraint_id) -> dict:
    """Get Generic Constraint collection data"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('GenericConstraintPeriodCollection').get('GenericConstraintPeriod'))

    for i in constraints:
        if i['@ConstraintID'] == constraint_id:
            return i

    raise LookupError('Attribute not found:', constraint_id)


def get_generic_constraint_solution_data(data, constraint_id, intervention):
    """Generic constraint solution data"""

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

    for i in constraints:
        if (i['@ConstraintID'] == constraint_id) and (i['@Intervention'] == intervention):
            return i

    raise LookupError('Attribute not found:', constraint_id)


def parse_trader(data, trader_id) -> dict:
    """Parse trader data"""

    # Trader collection information
    collection = get_trader_collection_data(data, trader_id)
    period = get_trader_period_data(data, trader_id)

    collection_str_keys = ['@TraderID', '@TraderType', '@FastStart', '@CurrentMode', '@WhatIfCurrentMode',
                           '@SemiDispatch', '@Forecast_Origin', '@Forecast_Offer_DateTime']

    collection_attributes = {k.replace('@', ''): v if k in collection_str_keys else float(v)
                             for k, v in collection.items() if k.startswith('@')}

    period_str_keys = ['@TraderID', '@RegionID', '@TradePriceStructureID']

    period_attributes = {k.replace('@', ''): v if k in period_str_keys else float(v)
                         for k, v in period.items() if k.startswith('@')}

    # Trader info
    info = {**collection_attributes, **period_attributes}

    # Trader initial conditions
    initial_condition_str_keys = ['AGCStatus']
    initial_conditions = {
        i['@InitialConditionID']: i['@Value'] if i['@InitialConditionID'] in initial_condition_str_keys
        else float(i['@Value']) for i in collection['TraderInitialConditionCollection']['TraderInitialCondition']}

    # Trader price bands
    price_band_trade_types = convert_to_list(collection.get('TradePriceStructureCollection').get('TradePriceStructure')
                                             .get('TradeTypePriceStructureCollection').get('TradeTypePriceStructure'))

    price_band_str_keys = ['@TradeType', '@Offer_SettlementDate', '@Offer_EffectiveDate', '@Offer_VersionNo']
    price_bands = {i['@TradeType']: {k.replace('@', ''): v if k in price_band_str_keys else float(v)
                                     for k, v in i.items()} for i in price_band_trade_types}

    # Trader quantity bands
    quantity_band_trade_types = convert_to_list(period.get('TradeCollection').get('Trade'))
    quantity_band_str_keys = ['@TradeType']

    quantity_bands = {i['@TradeType']: {k.replace('@', ''): v if k in quantity_band_str_keys else float(v)
                                        for k, v in i.items()} for i in quantity_band_trade_types}

    # Combine trader output information
    out = {
        'Info': info,
        'InitialConditions': initial_conditions,
        'PriceBands': price_bands,
        'QuantityBands': quantity_bands
    }

    return out


def parse_traders(data) -> dict:
    """Parse all trader data"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Container for output
    out = {}

    for i in traders:
        out[i['@TraderID']] = parse_trader(data, i['@TraderID'])

    return out


def parse_interconnector(data, interconnector_id) -> dict:
    """Parse interconnector data"""

    # Interconnector information
    period = get_interconnector_period_data(data, interconnector_id)
    collection = get_interconnector_collection_data(data, interconnector_id)

    period_str_keys = ['@InterconnectorID', '@MNSP', '@LossModelID', '@FromRegion', '@ToRegion',
                       '@MNSPPriceStructureID']
    period_attributes = {k.replace('@', ''): v if k in period_str_keys else float(v)
                         for k, v in period.items() if k.startswith('@')}

    collection_str_keys = ['@InterconnectorID']
    collection_attributes = {k.replace('@', ''): v if k in collection_str_keys else float(v)
                             for k, v in collection.items() if k.startswith('@')}

    # Combine collection and period attributes to create info dictionary
    info = {**period_attributes, **collection_attributes}

    # Initial conditions
    initial_conditions = {i['@InitialConditionID']: float(i['@Value']) for i in
                          (collection.get('InterconnectorInitialConditionCollection')
                           .get('InterconnectorInitialCondition'))}

    # Loss model attributes
    loss_model_str_keys = ['@LossModelID']
    loss_model_attributes = {k.replace('@', ''): v if k in loss_model_str_keys else float(v)
                             for k, v in collection.get('LossModelCollection').get('LossModel').items()
                             if k.startswith('@')}

    # Loss model segments
    loss_model_segments = [{k.replace('@', ''): float(v) for k, v in i.items()}
                           for i in (collection.get('LossModelCollection').get('LossModel').get('SegmentCollection')
                                     .get('Segment'))]

    # Combine interconnector information
    out = {
        'Info': info,
        'InitialConditions': initial_conditions,
        'LossModel': {**loss_model_attributes, **{'Segment': loss_model_segments}}
    }

    # Regular interconnector (no market offer)
    if period['@MNSP'] == '0':
        return out

    # Also extract offer data if interconnector is a MNSP
    elif period['@MNSP'] == '1':
        offer = parse_mnsp_offer(data, interconnector_id)
        mnsp_out = {**out, **offer}
        return mnsp_out

    else:
        raise Exception('Unexpected MNSP key:', collection['@MNSP'])


def parse_mnsp_offer(data, interconnector_id) -> dict:
    """Parse MNSP offer data"""

    # Interconnector information
    period = get_interconnector_period_data(data, interconnector_id)
    collection = get_interconnector_collection_data(data, interconnector_id)

    # Price bands
    price_band_regions = (collection.get('MNSPPriceStructureCollection').get('MNSPPriceStructure')
                          .get('MNSPRegionPriceStructureCollection').get('MNSPRegionPriceStructure'))

    price_band_region_str_keys = ['@RegionID', '@Offer_SettlementDate', '@Offer_EffectiveDate', '@Offer_VersionNo',
                                  '@LinkID', '@ParticipantID']

    price_bands = {i['@RegionID']:
                       {k.replace('@', ''): v if k in price_band_region_str_keys else float(v) for k, v in i.items()}
                   for i in price_band_regions}

    # Quantity bands
    quantity_band_regions = period.get('MNSPOfferCollection').get('MNSPOffer')

    quantity_band_region_str_keys = ['@RegionID']

    quantity_bands = {i['@RegionID']:
                          {k.replace('@', ''): v if k in quantity_band_region_str_keys else float(v) for k, v in i.items()}
                      for i in quantity_band_regions}

    return {'PriceBands': price_bands, 'QuantityBands': quantity_bands}


def parse_interconnectors(data) -> dict:
    """Parse all interconnectors"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for output
    out = {}
    for i in interconnectors:
        out[i['@InterconnectorID']] = parse_interconnector(data, i['@InterconnectorID'])

    return out


def parse_region(data, region_id) -> dict:
    """Parse region data"""

    # Region information
    period = get_region_period_data(data, region_id)
    collection = get_region_collection_data(data, region_id)

    region_str_keys = ['@RegionID']
    period_attributes = {k.replace('@', ''): v if k in region_str_keys else float(v)
                         for k, v in period.items() if k.startswith('@')}

    collection_attributes = {k.replace('@', ''): v if k in region_str_keys else float(v)
                             for k, v in collection.items() if k.startswith('@')}

    # Region attributes
    region_attributes = {**period_attributes, **collection_attributes}

    # Initial conditions
    initial_conditions = {i['@InitialConditionID']: float(i['@Value'])
                          for i in collection.get('RegionInitialConditionCollection').get('RegionInitialCondition')}

    # Output
    out = {
        'Info': region_attributes,
        'InitialConditions': initial_conditions
    }

    return out


def parse_regions(data) -> dict:
    """Parse all regions"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    # Container for output
    out = {}
    for i in regions:
        out[i['@RegionID']] = parse_region(data, i['@RegionID'])

    return out


def parse_generic_constraint(data, constraint_id, intervention) -> dict:
    """Parse generic constraint"""

    # Extract data
    period = get_generic_constraint_period_data(data, constraint_id)
    collection = get_generic_constraint_collection_data(data, constraint_id)
    solution = get_generic_constraint_solution_data(data, constraint_id, intervention)

    # Collection attributes
    collection_str_keys = ['@ConstraintID', '@VersionNo', '@EffectiveDate', '@Version', '@Type', '@Force_SCADA']
    collection_attributes = {k.replace('@', ''): v if k in collection_str_keys else float(v)
                             for k, v in collection.items() if k.startswith('@')}

    # Period attributes
    period_attributes = {k.replace('@', ''): v for k, v in period.items()}

    # Combine attributes into single dictionary
    attribute_keys = ['ConstraintID', 'Type', 'ViolationPrice', 'Intervention']
    attributes = {k: v for k, v in {**collection_attributes, **period_attributes}.items() if k in attribute_keys}

    # Add RHS - based on solution
    attributes['RHS'] = float(solution['@RHS'])

    # LHS terms
    trader_factors = [
        {k.replace('@', ''): float(v) if k == '@Factor' else v for k, v in i.items()}
        for i in convert_to_list(collection.get('LHSFactorCollection').get('TraderFactor', []))]

    interconnector_factors = [
        {k.replace('@', ''): float(v) if k == '@Factor' else v for k, v in i.items()}
        for i in convert_to_list(collection.get('LHSFactorCollection').get('InterconnectorFactor', []))]

    region_factors = [
        {k.replace('@', ''): float(v) if k == '@Factor' else v for k, v in i.items()}
        for i in convert_to_list(collection.get('LHSFactorCollection').get('RegionFactor', []))]

    lhs_terms = {
        'TraderFactor': trader_factors, 'InterconnectorFactor': interconnector_factors, 'RegionFactor': region_factors
    }

    # Constraint track
    track = {k.replace('@', ''): v
             for k, v in collection.get('s:ConstraintTrkCollection', {}).get('ConstraintTrkItem', {}).items()}

    # Output
    out = {
        'Info': attributes,
        # 'Track': track,
        'LHSTerms': lhs_terms,
    }

    return out


def parse_generic_constraints(data, intervention) -> dict:
    """Parse all generic constraints"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('GenericConstraintPeriodCollection').get('GenericConstraintPeriod'))

    # Container for output
    out = {}
    for i in constraints:
        out[i['@ConstraintID']] = parse_generic_constraint(data, i['@ConstraintID'], intervention)

    return out


def construct_case(data, intervention) -> dict:
    """Construct case"""

    # Parse case attributes
    case_attributes = parse_case_attributes(data)

    case = {
        'CaseID': case_attributes['CaseID'],
        'Data': {
            'Case': case_attributes,
            'Traders': parse_traders(data),
            'Interconnectors': parse_interconnectors(data),
            'Regions': parse_regions(data),
            'GenericConstraints': parse_generic_constraints(data, intervention)
        }
    }

    return case


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
    out_case = construct_case(cdata, intervention_status)
    print(time.time() - t0)

    # with open('cdata.json', 'w') as f:
    #     json.dump(out_case, f)
