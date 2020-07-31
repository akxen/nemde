"""Parse NEMDE case file"""

import os
import json
from collections import OrderedDict

try:
    from .utils.loader import load_dispatch_interval_json
    from .utils.convert import str_to_float
except ImportError:
    from utils.loader import load_dispatch_interval_json
    from utils.convert import str_to_float


def parse_trader_initial_condition_collection(trader_data):
    """Extract initial condition information from trader data element"""

    # All initial conditions
    initial_conditions = trader_data.get('TraderInitialConditionCollection').get('TraderInitialCondition')

    # Extracted trader initial conditions
    parsed_initial_conditions = {i.get('InitialConditionID'): str_to_float(i.get('Value')) for i in initial_conditions}

    return parsed_initial_conditions


def parse_trader_price_structure_collection(trader_data):
    """Extract price bands"""

    # Extract price info
    price_info = (trader_data.get('TradePriceStructureCollection').get('TradePriceStructure')
                  .get('TradeTypePriceStructureCollection').get('TradeTypePriceStructure'))

    if isinstance(price_info, list):
        return {j.get('TradeType'): {k: str_to_float(v) for k, v in j.items()} for j in price_info}

    elif isinstance(price_info, dict):
        return {price_info.get('TradeType'): {k: str_to_float(v) for k, v in price_info.items()}}

    else:
        raise Exception(f'Unexpected type: {price_info}')


def parse_trader_collection(data):
    """Parse NEMDE input - trader collection"""

    # Trader data
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Container for trader collection data
    trader_collection = {}

    for i in traders:
        # Extract ID
        trader_id = i.get('TraderID')

        # Initialise empty dictionary for parsed data
        trader_collection[trader_id] = {}

        # Extract data and parse keys according to specified rules
        for k, v in i.items():
            if k == 'TraderInitialConditionCollection':
                trader_collection[trader_id]['initial_conditions'] = parse_trader_initial_condition_collection(i)
            elif k == 'TradePriceStructureCollection':
                trader_collection[trader_id]['price_structure'] = parse_trader_price_structure_collection(i)
            else:
                trader_collection[trader_id][k] = str_to_float(v)

    return trader_collection


def parse_region_initial_condition_collection(region_data):
    """Parse initial condition information for a given region"""

    # All initial conditions
    initial_conditions = region_data.get('RegionInitialConditionCollection').get('RegionInitialCondition')

    # Extracted trader initial conditions
    parsed_initial_conditions = {i.get('InitialConditionID'): str_to_float(i.get('Value')) for i in initial_conditions}

    return parsed_initial_conditions


def parse_region_collection(data):
    """Parse region collection data"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    # Container for parsed data
    region_collection = {}

    for i in regions:
        # Extract ID
        region_id = i.get('RegionID')

        # Initialise empty dictionary for parsed data
        region_collection[region_id] = {}

        for k, v in i.items():
            if k == 'RegionInitialConditionCollection':
                region_collection[region_id]['initial_conditions'] = parse_region_initial_condition_collection(i)
            else:
                region_collection[region_id][k] = str_to_float(v)

    return region_collection


def parse_interconnector_initial_condition_collection(interconnector_data):
    """Parse interconnector initial condition information"""

    # All initial conditions
    initial_conditions = (interconnector_data.get('InterconnectorInitialConditionCollection')
                          .get('InterconnectorInitialCondition'))

    # Extracted trader initial conditions
    parsed_initial_conditions = {i.get('InitialConditionID'): str_to_float(i.get('Value')) for i in initial_conditions}

    return parsed_initial_conditions


def parse_interconnector_loss_model_segment_collection(loss_model_data):
    """Parse interconnector loss model segment collection"""

    # All loss models segments
    segments = loss_model_data.get('SegmentCollection').get('Segment')

    return OrderedDict({i: {k: str_to_float(v) for k, v in j.items()} for i, j in enumerate(segments)})


def parse_interconnector_loss_model_collection(interconnector_data):
    """Parse interconnector loss model collection"""

    # Loss model for a given interconnector
    loss_model = interconnector_data.get('LossModelCollection').get('LossModel')

    # Container for parsed loss model data
    parsed_loss_model = {}

    for k, v in loss_model.items():
        if k == 'SegmentCollection':
            parsed_loss_model['segment_collection'] = parse_interconnector_loss_model_segment_collection(loss_model)
        else:
            parsed_loss_model[k] = str_to_float(v)

    return parsed_loss_model


def parse_interconnector_price_structure(interconnector_data):
    """Parse MNSP price structure data"""

    price_structure = (interconnector_data.get('MNSPPriceStructureCollection').get('MNSPPriceStructure')
                       .get('MNSPRegionPriceStructureCollection').get('MNSPRegionPriceStructure'))

    parsed = {i.get('RegionID'): {k: str_to_float(v) for k, v in i.items()} for i in price_structure}

    return parsed


def parse_interconnector_collection(data):
    """Parse interconnector collection information"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for parsed interconnector data
    parsed = {}

    for i in interconnectors:
        # Interconnector ID
        interconnector_id = i.get('InterconnectorID')

        # Container for interconnector data
        parsed[interconnector_id] = {}

        for k, v in i.items():
            if k == 'InterconnectorInitialConditionCollection':
                parsed[interconnector_id]['initial_conditions'] = parse_interconnector_initial_condition_collection(i)
            elif k == 'LossModelCollection':
                parsed[interconnector_id]['loss_model'] = parse_interconnector_loss_model_collection(i)
            elif k == 'MNSPPriceStructureCollection':
                parsed[interconnector_id]['price_structure'] = parse_interconnector_price_structure(i)
            else:
                parsed[interconnector_id][k] = str_to_float(v)

    return parsed


def parse_region_period_collection(data):
    """Parse region period collection data"""

    # All regions
    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('RegionPeriodCollection').get('RegionPeriod'))

    return {i.get('RegionID'): {k: str_to_float(v) for k, v in i.items()} for i in regions}


def parse_trader_period_trade_collection(trader_data):
    """Extract quantity band and other trader period information"""

    # All trades
    trades = trader_data.get('TradeCollection').get('Trade')

    if isinstance(trades, list):
        return {i.get('TradeType'): {k: str_to_float(v) for k, v in i.items()} for i in trades}
    elif isinstance(trades, dict):
        return {trades.get('TradeType'): {k: str_to_float(v) for k, v in trades.items()}}
    else:
        raise Exception(f'Unexpected type: {trades}')


def parse_trader_period_collection(data):
    """Parse trader period collection"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Container for parsed data
    parsed = {}

    for i in traders:
        # Extract trader ID
        trader_id = i.get('TraderID')

        # Initialise inner dictionary for parsed trade data
        parsed[trader_id] = {}

        for k, v in i.items():
            if k == 'TradeCollection':
                parsed[trader_id]['trader_period'] = parse_trader_period_trade_collection(i)
            else:
                parsed[trader_id][k] = v

    return parsed


def parse_interconnector_period_offer_collection(interconnector_data):
    """Parse MNSP period offer collection"""

    # All trades for a given MNSP interconnector
    trades = interconnector_data.get('MNSPOfferCollection').get('MNSPOffer')

    return {i.get('RegionID'): {k: str_to_float(v) for k, v in i.items()} for i in trades}


def parse_interconnector_period_collection(data):
    """Parse interconnector period collection data"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for parsed data
    parsed = {}

    for i in interconnectors:
        # Extract ID
        interconnector_id = i.get('InterconnectorID')

        # Initialise inner container for parsed data
        parsed[interconnector_id] = {}

        for k, v in i.items():
            # Handle MNSP offer collection
            if k == 'MNSPOfferCollection':
                parsed[interconnector_id]['offer_collection'] = parse_interconnector_period_offer_collection(i)

            # Don't attempt float conversion for these keys
            elif k in ['LossModelID']:
                parsed[interconnector_id][k] = v

            # Attempt to convert to float
            else:
                parsed[interconnector_id][k] = str_to_float(v)

    return parsed


def parse_generic_constraint_period_collection(data):
    """Parse generic constraint period collection data"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('GenericConstraintPeriodCollection').get('GenericConstraintPeriod'))

    return constraints


def parse_constraint_solution(data):
    """Parse constraint solution"""

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

    # Container for parsed constraints
    parsed = []

    for i in constraints:
        parsed.append({k: str_to_float(v) if k in ['RHS', 'MarginalValue', 'Deficit'] else v for k, v in i.items()})

    return parsed


def parse_case_attributes(data):
    """Parse case attributes"""

    return {k: str_to_float(v) for k, v in data.get('NEMSPDCaseFile').get('NemSpdInputs').get('Case').items()}


def parse_generic_constraint_trader_terms(constraint_data):
    """Parse generic constraint trader terms"""

    # All trader factor terms for a given constraint
    terms = constraint_data.get('LHSFactorCollection').get('TraderFactor')

    # Return empty dictionary if no terms
    if terms is None:
        return {}

    # Container for parsed trader terms
    parsed = {}
    if isinstance(terms, dict):
        parsed[(terms.get('TraderID'), terms.get('TradeType'))] = float(terms.get('Factor'))
    elif isinstance(terms, list):
        for i in terms:
            parsed[(i.get('TraderID'), i.get('TradeType'))] = float(i.get('Factor'))
    else:
        raise Exception(f'Unexpected type: {constraint_data}')

    return parsed


def parse_generic_constraint_interconnector_terms(constraint_data):
    """Parse generic constraint interconnector terms"""

    # All interconnector factor terms for a given constraint
    terms = constraint_data.get('LHSFactorCollection').get('InterconnectorFactor')

    # Return empty dictionary if no terms
    if terms is None:
        return {}

    # Container for parsed interconnector terms
    parsed = {}
    if isinstance(terms, dict):
        parsed[(terms.get('InterconnectorID'))] = float(terms.get('Factor'))
    elif isinstance(terms, list):
        for i in terms:
            parsed[(i.get('InterconnectorID'))] = float(i.get('Factor'))
    else:
        raise Exception(f'Unexpected type: {constraint_data}')

    return parsed


def parse_generic_constraint_region_terms(constraint_data):
    """Parse generic constraint region terms"""

    # All region factor terms for a given constraint
    terms = constraint_data.get('LHSFactorCollection').get('RegionFactor')

    # Return empty dictionary if no terms
    if terms is None:
        return {}

    # Container for parsed region terms
    parsed = {}
    if isinstance(terms, dict):
        parsed[(terms.get('RegionID'), terms.get('TradeType'))] = float(terms.get('Factor'))
    elif isinstance(terms, list):
        for i in terms:
            parsed[(i.get('RegionID'), i.get('TradeType'))] = float(i.get('Factor'))
    else:
        raise Exception(f'Unexpected type: {constraint_data}')

    return parsed


def parse_generic_constraint_collection(data):
    """Parse generic constraint collection data"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Parsed dictionary
    lhs_terms = {}

    # Dictionaries containing parsed data
    trader_factors = {}
    interconnector_factors = {}
    region_factors = {}

    for i in constraints:
        if i.get('LHSFactorCollection') is None:
            continue

        # Extract terms for traders, interconnectors, and regions
        trader_factors = {**trader_factors, **parse_generic_constraint_trader_terms(i)}
        interconnector_factors = {**interconnector_factors, **parse_generic_constraint_interconnector_terms(i)}
        region_factors = {**region_factors, **parse_generic_constraint_region_terms(i)}

        # Combine terms into a single dictionary
        terms = {'traders': trader_factors, 'interconnectors': interconnector_factors, 'regions': region_factors}
        lhs_terms[i.get('ConstraintID')] = terms

    parsed = {'constraints': constraints, 'lhs_terms': lhs_terms}

    return parsed


def parse_data(data):
    """Parse model data and extract selected components"""

    # Container for parsed data
    parsed = {
        'trader_collection': parse_trader_collection(data),
        'region_collection': parse_region_collection(data),
        'interconnector_collection': parse_interconnector_collection(data),
        'generic_constraint_collection': parse_generic_constraint_collection(data),
        'trader_period_collection': parse_trader_period_collection(data),
        'region_period_collection': parse_region_period_collection(data),
        'interconnector_period_collection': parse_interconnector_period_collection(data),
        'generic_constraint_period_collection': parse_generic_constraint_period_collection(data),
        'constraint_solution': parse_constraint_solution(data),
        'case_attributes': parse_case_attributes(data),
    }

    return parsed


if __name__ == '__main__':
    # Data directory
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Object used to get case data
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Convert to dictionary
    cdata = json.loads(case_data_json)

    import time

    t0 = time.time()
    trader_collection_parsed = parse_trader_collection(cdata)
    region_collection_parsed = parse_region_collection(cdata)
    interconnector_collection_parsed = parse_interconnector_collection(cdata)
    generic_constraint_collection_parsed = parse_generic_constraint_collection(cdata)
    region_period_collection_parsed = parse_region_period_collection(cdata)
    trader_period_collection_parsed = parse_trader_period_collection(cdata)
    interconnector_period_collection_parsed = parse_interconnector_period_collection(cdata)
    generic_constraint_period_collection_parsed = parse_generic_constraint_period_collection(cdata)
    h = parse_generic_constraint_collection(cdata)
    print(time.time() - t0)

    parsed_data = parse_data(cdata)


    # with open('cdata.json', 'w') as f:
    #     json.dump(parsed_data, f)
