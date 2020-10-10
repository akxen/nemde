"""Convert case data into format that can be used to construct model instance"""

import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__)))

import fcas
import lookup
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


def get_region_index(data) -> list:
    """Get NEM region index"""

    return [i['@RegionID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection')
                                     .get('Region'))]


def get_trader_index(data) -> list:
    """Get trader index"""

    return [i['@TraderID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                                     .get('Period').get('TraderPeriodCollection').get('TraderPeriod'))]


def get_trader_semi_dispatch_index(data) -> list:
    """Get index of semi-dispatchable plant"""

    return [i['@TraderID'] for i in data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')
            if i['@SemiDispatch'] == '1']


def get_trader_offer_index(data) -> list:
    """Get trader offer index"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade'))]


def get_trader_fcas_offer_index(data) -> list:
    """Get trader FCAS offers"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade')) if j['@TradeType'] not in ['ENOF', 'LDOF']]


def get_trader_energy_offer_index(data) -> list:
    """Get trader energy offers"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade')) if j['@TradeType'] in ['ENOF', 'LDOF']]


def get_trader_fcas_available_offers_index(data) -> list:
    """Get available FCAS offers"""

    # All FCAS offers
    offers = get_trader_fcas_offer_index(data)

    # FCAS available
    available = fcas.get_trader_fcas_availability_status(data)

    # All available FCAS offers
    return [i for i in offers if available[i]]


def get_trader_fast_start_index(data) -> list:
    """Get fast start units"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Fast start unit IDs
    return [i['@TraderID'] for i in traders if i.get('@FastStart') == '1']


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


def get_interconnector_loss_model_breakpoint_index(data) -> list:
    """Get interconnector loss model breakpoint index"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for indices
    values = []
    for i in interconnectors:
        # Loss model segments
        segments = i.get('LossModelCollection').get('LossModel').get('SegmentCollection').get('Segment')
        for j in range(len(segments) + 1):
            # Append index to container
            values.append((i['@InterconnectorID'], j))

    return values


def get_interconnector_loss_model_interval_index(data) -> list:
    """Get interconnector loss model interval index"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for indices
    values = []
    for i in interconnectors:
        # Loss model segments
        segments = i.get('LossModelCollection').get('LossModel').get('SegmentCollection').get('Segment')
        for j in range(len(segments)):
            # Append index to container
            values.append((i['@InterconnectorID'], j))

    return values


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


def get_trader_quantity_bands(data) -> dict:
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


def get_trader_initial_condition_attribute(data, attribute, func) -> dict:
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
                values[i.get('@TraderID')] = func(j.get('@Value'))

    return values


def get_trader_period_attribute(data, attribute, func) -> dict:
    """Get trader period attribute"""

    return {i['@TraderID']: func(i[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod')) if i.get(attribute) is not None}


def get_trader_collection_attribute(data, attribute, func) -> dict:
    """Get trader collection attribute"""

    return {i['@TraderID']: func(i[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader'))}


def get_trader_period_trade_attribute(data, attribute, func) -> dict:
    """Get trader quantity band attribute"""

    return {(i['@TraderID'], j['@TradeType']): func(j[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade')) if j.get(attribute) is not None}


def get_trader_fcas_trapezium(data) -> dict:
    """Get FCAS trapeziums"""

    return {(i['@TraderID'], j['@TradeType']):
        {
            'EnablementMin': float(j['@EnablementMin']),
            'LowBreakpoint': float(j['@LowBreakpoint']),
            'HighBreakpoint': float(j['@HighBreakpoint']),
            'EnablementMax': float(j['@EnablementMax']),
            'MaxAvail': float(j['@MaxAvail']),
        }
        for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                  .get('TraderPeriodCollection').get('TraderPeriod'))
        for j in convert_to_list(i.get('TradeCollection').get('Trade'))
        if j['@TradeType'] in ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']}


def get_trader_fcas_availability_status(data) -> dict:
    """Get FCAS availability"""

    # All FCAS offers
    offers = get_trader_offer_index(data)

    # Container for FCAS availability
    fcas_status = {}
    for trader_id, trade_type in offers:
        # Only check availability for FCAS offers
        if trade_type in ['L5RE', 'L6SE', 'L60S', 'L5MI', 'R5RE', 'R6SE', 'R60S', 'R5MI']:
            # Get FCAS availability status
            fcas_status[(trader_id, trade_type)] = fcas.get_trader_fcas_availability_status(data, trader_id, trade_type)

    return fcas_status


def get_trader_fast_start_attribute(data, attribute, func) -> dict:
    """Get trader fast start attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Fast start traders
    fast_start_traders = get_trader_fast_start_index(data)

    return {i['@TraderID']: func(i[attribute]) for i in traders if i['@TraderID'] in fast_start_traders}


def get_interconnector_collection_attribute(data, attribute, func) -> dict:
    """Get interconnector collection attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for extract values
    values = {}
    for i in interconnectors:
        for j in i.get('InterconnectorInitialConditionCollection').get('InterconnectorInitialCondition'):
            if j['@InitialConditionID'] == attribute:
                values[i['@InterconnectorID']] = func(j['@Value'])

    return values


def get_interconnector_period_collection_attribute(data, attribute, func) -> dict:
    """
    Get interconnector period collection attribute

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    attribute : str
        Name of attribute to extract for each interconnector

    func : function
        Function used to parse attribute values e.g. float or str

    Returns
    -------
    values : dict
        Dictionary of extracted interconnector period collection attributes
    """

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for extracted values
    values = {}
    for i in interconnectors:
        values[i['@InterconnectorID']] = func(i[attribute])

    return values


def get_interconnector_loss_model_attribute(data, attribute, func) -> dict:
    """
    Get interconnector loss model attribute

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    attribute : str
        Name of attribute to extract

    func : function
        Function used to parse attribute values e.g. convert to float or string
    """

    return {i['@InterconnectorID']: func(i.get('LossModelCollection').get('LossModel')[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                      .get('Interconnector'))}


def get_interconnector_loss_model_segments(data, interconnector_id) -> list:
    """Get segments corresponding to interconnector loss model"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for loss model segments
    segments = []
    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            for segment in i.get('LossModelCollection').get('LossModel').get('SegmentCollection').get('Segment'):
                s = {j: int(k) if j == '@Limit' else float(k) for j, k in segment.items()}
                segments.append(s)

    return segments


def get_parsed_interconnector_loss_model_segments(data, interconnector_id) -> list:
    """Use breakpoints and segment factors to construct a new start-end representation for the MLF curve"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Loss lower limit
    loss_lower_limit = get_interconnector_loss_model_attribute(data, '@LossLowerLimit', float)

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            # Check loss model
            segments = get_interconnector_loss_model_segments(data, interconnector_id)

            # First segment
            start = -loss_lower_limit[interconnector_id]

            # Format segments with start, end, and factor
            new_segments = []
            for s in segments:
                segment = {'start': start, 'end': s['@Limit'], 'factor': s['@Factor']}
                start = s['@Limit']
                new_segments.append(segment)

            return new_segments


def get_interconnector_loss_estimate(data, interconnector_id, flow) -> float:
    """Estimate interconnector loss - numerically integrating loss model segments"""

    # Construct segments based on loss model
    segments = get_parsed_interconnector_loss_model_segments(data, interconnector_id)

    # Initialise total in
    total_area = 0
    for s in segments:
        if flow > 0:
            # Only want segments to right of origin
            if s['end'] <= 0:
                proportion = 0

            # Only want segments that are less than or equal to flow
            elif s['start'] > flow:
                proportion = 0

            # Take positive part of segment if segment crosses origin
            elif (s['start'] < 0) and (s['end'] > 0):
                # Part of segment that is positive
                positive_proportion = s['end'] / (s['end'] - s['start'])

                # Flow proportion (if flow close to zero)
                flow_proportion = flow / (s['end'] - s['start'])

                # Take min value
                proportion = min(positive_proportion, flow_proportion)

            # If flow within segment
            elif (flow >= s['start']) and (flow <= s['end']):
                # Segment proportion
                proportion = (flow - s['start']) / (s['end'] - s['start'])

            # Use full segment if flow greater than end of segment - use full segment
            elif flow > s['end']:
                proportion = 1

            else:
                raise Exception('Unhandled case')

            # Compute block area
            area = (s['end'] - s['start']) * s['factor'] * proportion

            # Update total area
            total_area += area

        # Flow is <= 0
        else:
            # Only want segments to left of origin
            if s['start'] >= 0:
                proportion = 0

            # Only want segments that are >= flow
            elif s['end'] < flow:
                proportion = 0

            # Take negative part of segment if segment crosses origin
            elif (s['start'] < 0) and (s['end'] > 0):
                # Part of segment that is negative
                negative_proportion = - s['start'] / (s['end'] - s['start'])

                # Flow proportion (if flow close to zero)
                flow_proportion = -flow / (s['end'] - s['start'])

                # Take min value
                proportion = min(negative_proportion, flow_proportion)

            # If flow within segment
            elif (flow >= s['start']) and (flow <= s['end']):
                # Segment proportion
                proportion = -1 * (flow - s['end']) / (s['end'] - s['start'])

            # Use full segment if flow less than start of segment - use full segment
            elif flow <= s['start']:
                proportion = 1

            else:
                raise Exception('Unhandled case')

            # Compute block area
            area = -1 * (s['end'] - s['start']) * s['factor'] * proportion

            # Update total area
            total_area += area

    return total_area


def get_interconnector_initial_loss_estimate(data) -> dict:
    """Get initial loss estimate for each interconnector"""

    # Initial MW for all interconnectors
    initial_mw = get_interconnector_collection_attribute(data, 'InitialMW', float)

    # Loss estimate
    loss_estimate = {}
    for i in get_interconnector_index(data):
        # Compute loss estimate for each interconnector
        loss_estimate[i] = get_interconnector_loss_estimate(data, i, initial_mw[i])

    return loss_estimate


def get_interconnector_loss_model_segment_attribute(data, attribute, func) -> dict:
    """Get interconnector loss model segment collection"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for values
    values = {}
    for i in interconnectors:
        for j, k in enumerate(i.get('LossModelCollection').get('LossModel').get('SegmentCollection').get('Segment')):
            # Extract loss model segment attribute
            values[(i['@InterconnectorID'], j)] = func(k[attribute])

    return values


def get_interconnector_loss_model_breakpoints_x(data) -> dict:
    """Get interconnector loss model breakpoints - x-coordinate (power output)"""

    # Get loss model segments
    limit = get_interconnector_loss_model_segment_attribute(data, '@Limit', float)
    lower_limit = get_interconnector_loss_model_attribute(data, '@LossLowerLimit', float)

    # Container for break point values - offset segment ID - first segment should be loss lower limit
    values = {(interconnector_id, segment_id + 1): v for (interconnector_id, segment_id), v in limit.items()}

    # Add loss lower limit with zero index (corresponds to first segment)
    for i in get_interconnector_index(data):
        values[(i, 0)] = -lower_limit[i]

    return values


def get_interconnector_loss_model_breakpoints_y(data) -> dict:
    """Get interconnector loss model breakpoints - y-coordinate (estimated loss)"""

    # Get loss model segments
    limit = get_interconnector_loss_model_segment_attribute(data, '@Limit', float)
    lower_limit = get_interconnector_loss_model_attribute(data, '@LossLowerLimit', float)

    # Container for break point values - offset segment ID - first segment should be loss lower limit
    values = {(interconnector_id, segment_id + 1): get_interconnector_loss_estimate(data, interconnector_id, v)
              for (interconnector_id, segment_id), v in limit.items()}

    # Add loss lower limit with zero index (corresponds to first segment)
    for i in get_interconnector_index(data):
        values[(i, 0)] = get_interconnector_loss_estimate(data, i, -lower_limit[i])

    return values


def get_interconnector_solution_attribute(data, attribute, func, intervention) -> dict:
    """
    Get interconnector solution attribute

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    attribute : str
        Name of attribute to extract

    func : function
        Function used to parse attribute values e.g. convert to float or string

    intervention : str
        Flag indicating inclusion of intervention constraints. 0=no intervention constraints, 1=includes intervention.
    """

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

    # Container for extracted attribute values
    values = {}
    for i in interconnectors:
        if i['@Intervention'] == intervention:
            values[i['@InterconnectorID']] = func(i[attribute])

    return values


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


def get_mnsp_quantity_band_attribute(data, attribute, func) -> dict:
    """Get MNSP max available"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for max available data
    max_available = {}
    for i in interconnectors:
        if i.get('MNSPOfferCollection') is None:
            continue

        for j in i.get('MNSPOfferCollection').get('MNSPOffer'):
            max_available[(i['@InterconnectorID'], j['@RegionID'])] = func(j[attribute])

    return max_available


def get_mnsp_period_collection_attribute(data, attribute, func) -> dict:
    """
    Get MNSP period collection attribute

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    attribute : str
        Name of attribute to extract

    func : function
        Function used to parse extracted attribute

    Returns
    -------
    values : dict
        MNSP period collection attribute
    """

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for extracted values
    values = {}
    for i in interconnectors:
        if i['@MNSP'] != '1':
            continue

        # Append to container
        values[i['@InterconnectorID']] = func(i[attribute])

    return values


def get_region_initial_condition_attribute(data, attribute, func) -> dict:
    """
    Get region initial condition attribute

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    attribute : str
        Name of attribute to extract

    func : function
        Function used to parse attribute value

    Returns
    -------
    values : dict
        Extract attribute values for each NEM region
    """

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    # Container for extracted values
    values = {}
    for i in regions:
        for j in i.get('RegionInitialConditionCollection').get('RegionInitialCondition'):
            if j['@InitialConditionID'] == attribute:
                values[i['@RegionID']] = func(j['@Value'])

    return values


def get_region_period_collection_attribute(data, attribute, func) -> dict:
    """Get region period collection attribute"""

    return {i['@RegionID']: func(i[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('RegionPeriodCollection').get('RegionPeriod'))}


def get_generic_constraint_rhs(data, intervention) -> dict:
    """
    Get generic constraint right-hand-side term

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    intervention : str
        Intervention flag - '0' -> no intervention constraints, '1' -> intervention constraints included

    Returns
    -------
    rhs : dict
        Dictionary with keys = ConstraintIDs, values = constraint RHS
    """

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

    # Container for constraint RHS terms
    rhs = {}
    for i in constraints:
        # Check intervention flag
        if i['@Intervention'] == intervention:
            rhs[i['@ConstraintID']] = float(i['@RHS'])

    return rhs


def get_generic_constraint_collection_attribute(data, attribute, func) -> dict:
    """
    Get generic constraint collection attribute

    Parameters
    ----------
    data : dict
        NEMDE case file data

    attribute : str
        Name of attribute to extract

    func : function
        Function used to parse attribute e.g. float, or str

    Returns
    -------
    values : dict
        Extracted generic constraint collection values
    """

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for extract values
    values = {}
    for i in constraints:
        # Skip constraints with missing LHS factors
        if i.get('LHSFactorCollection') is None:
            continue

        values[i['@ConstraintID']] = func(i[f'{attribute}'])

    return values


def parse_constraint(constraint_data):
    """Constraint data"""

    lhs = constraint_data.get('LHSFactorCollection')

    if lhs is None:
        return {}

    # Trader factors
    traders = {(i['@TraderID'], i['@TradeType']): float(i['@Factor'])
               for i in convert_to_list(lhs.get('TraderFactor', []))}

    # Interconnector factors
    interconnectors = {(i['@InterconnectorID']): float(i['@Factor'])
                       for i in convert_to_list(lhs.get('InterconnectorFactor', []))}

    # Region factors
    regions = {(i['@RegionID'], i['@TradeType']): float(i['@Factor'])
               for i in convert_to_list(lhs.get('RegionFactor', []))}

    # Combine constraint terms into single dictionary
    terms = {'traders': traders, 'interconnectors': interconnectors, 'regions': regions}

    return terms


def get_generic_constraint_lhs_terms(data) -> dict:
    """Generic constraint LHS terms"""

    # All constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    return {i.get('@ConstraintID'): parse_constraint(i) for i in constraints}


def get_case_attribute(data, attribute) -> float:
    """Extract case attribute"""

    return float(data.get('NEMSPDCaseFile').get('NemSpdInputs').get('Case')[attribute])


def get_trader_solution(data, intervention) -> dict:
    """Get trader solution"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@TraderID', '@PeriodID', '@Intervention', '@FSTargetMode', '@SemiDispatchCap']

    # Container for extracted values
    solutions = {}
    for i in traders:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@TraderID']] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_interconnector_solution(data, intervention) -> dict:
    """Get interconnector solution"""

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@InterconnectorID', '@PeriodID', '@Intervention', '@NPLExists']

    # Container for extracted interconnector solutions
    solutions = {}
    for i in interconnectors:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@InterconnectorID']] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_region_solution(data, intervention) -> dict:
    """Get region solution"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@RegionID', '@PeriodID', '@Intervention']

    # Container for extracted region solutions
    solutions = {}
    for i in regions:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@RegionID']] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_region_solution_attribute(data, attribute, func, intervention) -> dict:
    """Get given solution attribute for all regions"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')

    return {i['@RegionID']: func(i[attribute]) for i in regions if i['@Intervention'] == intervention}


def get_constraint_solution(data, intervention) -> dict:
    """Get constraint solution"""

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@ConstraintID', '@Version', '@PeriodID', '@Intervention']

    # Container for extracted region solutions
    solutions = {}
    for i in constraints:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@ConstraintID']] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_case_solution(data) -> dict:
    """Get case solution"""

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@SolverStatus', '@Terminal', '@InterventionStatus', '@SolverVersion', '@NPLStatus', '@OCD_Status',
                '@CaseSubType']

    return {k: str(v) if k in str_keys else float(v)
            for k, v in data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('CaseSolution').items()}


def get_period_solution(data, intervention) -> dict:
    """Get period solution"""

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@PeriodID', '@Intervention', '@SwitchRunBestStatus', '@SolverStatus', '@NPLStatus']

    return {k: str(v) if k in str_keys else float(v)
            for i in convert_to_list(data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('PeriodSolution'))
            for k, v in i.items() if i['@Intervention'] == intervention}


def reorder_tuple(input_tuple) -> tuple:
    """Sort tuples alphabetically"""

    if input_tuple[0][0] > input_tuple[1][0]:
        return tuple((input_tuple[1], input_tuple[0]))
    else:
        return tuple((input_tuple[0], input_tuple[1]))


def get_price_tied_bands(data):
    """Get price-tied generators"""

    # Price and quantity bands
    price_bands = get_trader_price_bands(data)
    quantity_bands = get_trader_quantity_bands(data)

    # Generator energy offer price bands
    filtered_price_bands = {k: v for k, v in price_bands.items() if k[1] == 'ENOF'}

    # Trader region
    trader_region = get_trader_period_attribute(data, '@RegionID', str)

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
            # # Can break early if price > input price band - monotonically increase prices
            # elif n > j:
            #     break

    # Re-order tuples, get unique price-tied combinations, and sort alphabetically
    price_tied_reordered = [reorder_tuple(i) for i in price_tied]
    price_tied_unique = list(set(price_tied_reordered))
    price_tied_unique.sort()

    # Flatten to produce one tuple for a given pair of price-tied generators
    price_tied_flattened = [(i[0][0], i[0][1], i[0][2], i[1][0], i[1][1], i[1][2]) for i in price_tied_unique]

    return price_tied_flattened


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
        'P_MNSP_LOSS_PRICE': get_case_attribute(data_dict, '@MNSPLossesPrice'),
        'P_MNSP_RAMP_UP_RATE': get_mnsp_quantity_band_attribute(data_dict, '@RampUpRate', float),
        'P_MNSP_RAMP_DOWN_RATE': get_mnsp_quantity_band_attribute(data_dict, '@RampDnRate', float),
        'P_REGION_INITIAL_DEMAND': get_region_initial_condition_attribute(data_dict, 'InitialDemand', float),
        'P_REGION_ADE': get_region_initial_condition_attribute(data_dict, 'ADE', float),
        'P_REGION_DF': get_region_period_collection_attribute(data_dict, '@DF', float),
        'P_GC_RHS': get_generic_constraint_rhs(data_dict, intervention),
        'P_GC_TYPE': get_generic_constraint_collection_attribute(data_dict, '@Type', str),
        'P_CVF_GC': get_generic_constraint_collection_attribute(data_dict, '@ViolationPrice', float),
        'P_CVF_VOLL': get_case_attribute(data_dict, '@VoLL'),
        'P_CVF_ENERGY_DEFICIT_PRICE': get_case_attribute(data_dict, '@EnergyDeficitPrice'),
        'P_CVF_ENERGY_SURPLUS_PRICE': get_case_attribute(data_dict, '@EnergySurplusPrice'),
        'P_CVF_UIGF_SURPLUS_PRICE': get_case_attribute(data_dict, '@UIGFSurplusPrice'),
        'P_CVF_RAMP_RATE_PRICE': get_case_attribute(data_dict, '@RampRatePrice'),
        'P_CVF_CAPACITY_PRICE': get_case_attribute(data_dict, '@CapacityPrice'),
        'P_CVF_OFFER_PRICE': get_case_attribute(data_dict, '@OfferPrice'),
        'P_CVF_MNSP_OFFER_PRICE': get_case_attribute(data_dict, '@MNSPOfferPrice'),
        'P_CVF_MNSP_RAMP_RATE_PRICE': get_case_attribute(data_dict, '@MNSPRampRatePrice'),
        'P_CVF_MNSP_CAPACITY_PRICE': get_case_attribute(data_dict, '@MNSPCapacityPrice'),
        'P_CVF_AS_PROFILE_PRICE': get_case_attribute(data_dict, '@ASProfilePrice'),
        'P_CVF_AS_MAX_AVAIL_PRICE': get_case_attribute(data_dict, '@ASMaxAvailPrice'),
        'P_CVF_AS_ENABLEMENT_MIN_PRICE': get_case_attribute(data_dict, '@ASEnablementMinPrice'),
        'P_CVF_AS_ENABLEMENT_MAX_PRICE': get_case_attribute(data_dict, '@ASEnablementMaxPrice'),
        'P_CVF_INTERCONNECTOR_PRICE': get_case_attribute(data_dict, '@InterconnectorPrice'),
        'P_CVF_FAST_START_PRICE': get_case_attribute(data_dict, '@FastStartPrice'),
        'P_CVF_GENERIC_CONSTRAINT_PRICE': get_case_attribute(data_dict, '@GenericConstraintPrice'),
        'P_CVF_SATISFACTORY_NETWORK_PRICE': get_case_attribute(data_dict, '@Satisfactory_Network_Price'),
        'P_TIE_BREAK_PRICE': get_case_attribute(data_dict, '@TieBreakPrice'),
        'preprocessed': {
            'GC_LHS_TERMS': get_generic_constraint_lhs_terms(data_dict),
            'FCAS_TRAPEZIUM': get_trader_fcas_trapezium(data_dict),
            'FCAS_AVAILABILITY_STATUS': get_trader_fcas_availability_status(data_dict)
        },
        'solution': {
            'traders': get_trader_solution(data_dict, intervention),
            'interconnectors': get_interconnector_solution(data_dict, intervention),
            'regions': get_region_solution(data_dict, intervention),
            'constraints': get_constraint_solution(data_dict, intervention),
            'case': get_case_solution(data_dict),
            'period': get_period_solution(data_dict, intervention),
        }
    }

    return case_data


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Case data in json format
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)
