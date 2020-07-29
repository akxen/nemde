"""Parse NEMDE case file"""

import os
import json
from abc import ABC, abstractmethod

from utils.loader import load_dispatch_interval_json
from utils.convert import str_to_float


def parse_trader_initial_condition_collection(trader_data):
    """Extract initial condition information from trader data element"""

    # All initial conditions
    initial_conditions = trader_data.get('TraderInitialConditionCollection').get('TraderInitialCondition')

    # Extracted trader initial conditions
    parsed_initial_conditions = {i.get('InitialConditionID'): str_to_float(i.get('Value')) for i in initial_conditions}

    return parsed_initial_conditions


def parse_trader_price_structure_collection(trader_info):
    """Extract price bands"""

    # Extract price info
    price_info = (trader_info.get('TradePriceStructureCollection').get('TradePriceStructure')
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

    return {i: {k: str_to_float(v) for k, v in j.items()} for i, j in enumerate(segments)}


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
            elif k == 'MNSPPriceStructure':
                parsed[interconnector_id]['mnsp_price_structure'] = parse_interconnector_price_structure(i)
            else:
                print(v)
                parsed[interconnector_id][k] = str_to_float(v)

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

    trader_collection_parsed = parse_trader_collection(cdata)
    region_collection_parsed = parse_region_collection(cdata)
    interconnector_collection_parsed = parse_interconnector_collection(cdata)
