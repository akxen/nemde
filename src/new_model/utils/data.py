"""Convert case data into format that can be used to construct model instance"""

import os
import json


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


def get_trader_semi_dispatch_status(data) -> dict:
    """Get trader semi-dispatch status"""

    return {i['@TraderID']: i['@SemiDispatch']
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader'))}


def get_trader_regions(data) -> dict:
    """Get trader regions"""

    return {i['@TraderID']: i['@RegionID']
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))}


def get_trader_period_ramp_rate(data, attribute, func) -> dict:
    """Get trader period ramp rate"""

    return {(i['@TraderID'], j['@TradeType']): func(j[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade')) if j['@TradeType'] in ['ENOF', 'LDOF']}


def get_trader_fcas_offer_attribute(data, attribute, func) -> dict:
    """Get trader FCAS offer attribute"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.TraderPeriodCollection.TraderPeriod[3].TradeCollection.Trade[1].@MaxAvail
    # Container for values
    return {(i['@TraderID'], j['@TradeType']): func(j[attribute])
            for i in traders for j in convert_to_list(i.get('TradeCollection').get('Trade'))
            if j['@TradeType'] in ['L6SE', 'L60S', 'L5MI', 'L5RE', 'R6SE', 'R60S', 'R5MI', 'R5RE']}


def get_trader_fcas_trapezium_offer(data) -> dict:
    """Get FCAS trapeziums"""
    pass


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


def get_interconnector_loss_model_segments(data, interconnector_id):
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


def get_parsed_interconnector_loss_model_segments(data, interconnector_id):
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


def get_interconnector_loss_estimate(data, interconnector_id, flow):
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


def get_interconnector_solution_attribute(data, attribute, func, intervention=0) -> dict:
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

    intervention : int (default=0)
        Flag to indicate whether an intervention pricing period. 0=no intervention, 1=intervention.
    """

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

    # Container for extracted attribute values
    values = {}
    for i in interconnectors:
        if i['@Intervention'] == f'{intervention}':
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


def get_mnsp_max_available(data) -> dict:
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
            max_available[(i['@InterconnectorID'], j['@RegionID'])] = float(j['@MaxAvail'])

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


def get_generic_constraint_rhs(data, intervention=0) -> dict:
    """
    Get generic constraint right-hand-side term

    Parameters
    ----------
    data : dict
        NEMDE case file dictionary

    intervention : int (default=0)
        Intervention flag - 0 -> no intervention, 1 -> intervention pricing period

    Returns
    -------
    rhs : dict
        Dictionary with keys = ConstraintIDs, values = constraint RHS
    """
    # TODO: can check if GenericConstraintCollection has RHS information

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

    # Container for constraint RHS terms
    rhs = {}
    for i in constraints:
        # Check intervention flag
        if i['@Intervention'] == f'{intervention}':
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
        'S_TRADER_FCAS_OFFERS': get_trader_fcas_offer_index(data_dict),
        'S_TRADER_ENERGY_OFFERS': get_trader_energy_offer_index(data_dict),
        'S_GENERIC_CONSTRAINTS': get_generic_constraint_index(data_dict),
        'S_GC_TRADER_VARS': get_generic_constraint_trader_variable_index(data_dict),
        'S_GC_INTERCONNECTOR_VARS': get_generic_constraint_interconnector_variable_index(data_dict),
        'S_GC_REGION_VARS': get_generic_constraint_region_variable_index(data_dict),
        'S_MNSPS': get_mnsp_index(data_dict),
        'S_MNSP_OFFERS': get_mnsp_offer_index(data_dict),
        'S_INTERCONNECTORS': get_interconnector_index(data_dict),
        'P_TRADER_PRICE_BAND': get_trader_price_bands(data_dict),
        'P_TRADER_QUANTITY_BAND': get_trader_quantity_bands(data_dict),
        'P_TRADER_MAX_AVAILABLE': get_trader_max_available(data_dict),
        'P_TRADER_INITIAL_MW': get_trader_initial_condition_attributes(data_dict, 'InitialMW'),
        'P_TRADER_HMW': get_trader_initial_condition_attributes(data_dict, 'HMW'),
        'P_TRADER_LMW': get_trader_initial_condition_attributes(data_dict, 'LMW'),
        'P_TRADER_AGC_STATUS': get_trader_agc_status(data_dict),
        'P_TRADER_SEMI_DISPATCH_STATUS': get_trader_semi_dispatch_status(data_dict),
        'P_TRADER_REGION': get_trader_regions(data_dict),
        'P_TRADER_PERIOD_RAMP_UP_RATE': get_trader_period_ramp_rate(data_dict, '@RampUpRate', float),
        'P_TRADER_PERIOD_RAMP_DOWN_RATE': get_trader_period_ramp_rate(data_dict, '@RampDnRate', float),
        'P_TRADER_FCAS_ENABLEMENT_MIN': get_trader_fcas_offer_attribute(data_dict, '@EnablementMin', float),
        'P_TRADER_FCAS_LOW_BREAKPOINT': get_trader_fcas_offer_attribute(data_dict, '@LowBreakpoint', float),
        'P_TRADER_FCAS_HIGH_BREAKPOINT': get_trader_fcas_offer_attribute(data_dict, '@HighBreakpoint', float),
        'P_TRADER_FCAS_ENABLEMENT_MAX': get_trader_fcas_offer_attribute(data_dict, '@EnablementMax', float),
        'P_TRADER_FCAS_MAX_AVAILABLE': get_trader_fcas_offer_attribute(data_dict, '@MaxAvail', float),
        'P_INTERCONNECTOR_INITIAL_MW': get_interconnector_collection_attribute(data_dict, 'InitialMW', float),
        'P_INTERCONNECTOR_TO_REGION': get_interconnector_period_collection_attribute(data_dict, '@ToRegion', str),
        'P_INTERCONNECTOR_FROM_REGION': get_interconnector_period_collection_attribute(data_dict, '@FromRegion', str),
        'P_INTERCONNECTOR_LOWER_LIMIT': get_interconnector_period_collection_attribute(data_dict, '@LowerLimit', float),
        'P_INTERCONNECTOR_UPPER_LIMIT': get_interconnector_period_collection_attribute(data_dict, '@UpperLimit', float),
        'P_INTERCONNECTOR_MNSP_STATUS': get_interconnector_period_collection_attribute(data_dict, '@MNSP', str),
        'P_INTERCONNECTOR_LOSS_SHARE': get_interconnector_loss_model_attribute(data_dict, '@LossShare', float),
        'P_INTERCONNECTOR_LOSS_LOWER_LIMIT': get_interconnector_loss_model_attribute(data_dict, '@LossLowerLimit',
                                                                                     float),
        'P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE': get_interconnector_initial_loss_estimate(data_dict),
        'P_INTERCONNECTOR_SOLUTION_LOSS': get_interconnector_solution_attribute(data_dict, '@Losses', float),
        'P_MNSP_PRICE_BAND': get_mnsp_price_bands(data_dict),
        'P_MNSP_QUANTITY_BAND': get_mnsp_quantity_bands(data_dict),
        'P_MNSP_MAX_AVAILABLE': get_mnsp_max_available(data_dict),
        'P_MNSP_TO_REGION_LF': get_mnsp_period_collection_attribute(data_dict, '@ToRegionLF', float),
        'P_MNSP_FROM_REGION_LF': get_mnsp_period_collection_attribute(data_dict, '@FromRegionLF', float),
        'P_MNSP_LOSS_PRICE': get_case_attribute(data_dict, '@MNSPLossesPrice'),
        'P_REGION_INITIAL_DEMAND': get_region_initial_condition_attribute(data_dict, 'InitialDemand', float),
        'P_REGION_ADE': get_region_initial_condition_attribute(data_dict, 'ADE', float),
        'P_REGION_DF': get_region_period_collection_attribute(data_dict, '@DF', float),
        'P_GC_RHS': get_generic_constraint_rhs(data_dict),
        'P_GC_TYPE': get_generic_constraint_collection_attribute(data_dict, '@Type', str),
        'P_CVF_GC': get_generic_constraint_collection_attribute(data_dict, '@ViolationPrice', float),
        'P_CVF_VOLL': get_case_attribute(data_dict, '@VoLL'),
        'P_CVF_ENERGY_DEFICIT_PRICE': get_case_attribute(data_dict, '@EnergyDeficitPrice'),
        'P_CVF_ENERGY_SURPLUS_PRICE': get_case_attribute(data_dict, '@EnergySurplusPrice'),
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
        'parameters': {'GC_LHS_TERMS': get_generic_constraint_lhs_terms(data_dict)}
    }

    return case_data


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')
