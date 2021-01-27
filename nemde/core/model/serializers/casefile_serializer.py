"""
Convert case data into format that can be used to construct model instance
"""

from nemde.core.casefile.lookup import convert_to_list, get_intervention_status
from nemde.core.casefile.algorithms import get_parsed_interconnector_loss_model_segments


def find(path, data):
    """
    Extract element from nested dictionary given a path using dot notation

    Parameters
    ----------
    path : str
        Path to nested element using dot notation
        E.g. 'NEMSPDCaseFile.NemSpdInputs.RegionCollection.Region'

    data : dict
        Nested dictionary

    Returns
    -------
    output : list or int or str or float
        Value corresponding to path in nested dictionary
    """

    keys = path.split('.')
    output = data
    for key in keys:
        output = output[key]

    return output


def get_region_index(data) -> list:
    """Get NEM region index"""

    return [i['@RegionID'] for i in (data.get('NEMSPDCaseFile')
                                     .get('NemSpdInputs')
                                     .get('RegionCollection')
                                     .get('Region'))]


def get_trader_index(data) -> list:
    """Get trader index"""

    return [i['@TraderID'] for i in (data.get('NEMSPDCaseFile')
                                     .get('NemSpdInputs')
                                     .get('PeriodCollection')
                                     .get('Period')
                                     .get('TraderPeriodCollection')
                                     .get('TraderPeriod'))]


def get_trader_semi_dispatch_index(data) -> list:
    """Get index of semi-dispatchable plant"""

    return [i['@TraderID'] for i in data.get('NEMSPDCaseFile')
            .get('NemSpdInputs')
            .get('TraderCollection')
            .get('Trader')
            if i['@SemiDispatch'] == '1']


def get_trader_offer_index(data) -> list:
    """Get trader offer index"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade'))]


def get_trader_fcas_offer_index(data) -> list:
    """Get trader FCAS offers"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade'))
            if j['@TradeType'] not in ['ENOF', 'LDOF']]


def get_trader_energy_offer_index(data) -> list:
    """Get trader energy offers"""

    return [(i['@TraderID'], j['@TradeType'])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade'))
            if j['@TradeType'] in ['ENOF', 'LDOF']]


def get_trader_fast_start_index(data) -> list:
    """Get fast start units"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

    # Fast start unit IDs
    return [i['@TraderID'] for i in traders if i.get('@FastStart') == '1']


def get_generic_constraint_index(data) -> list:
    """Get generic constraint index"""

    return [i['@ConstraintID'] for i in (data.get('NEMSPDCaseFile')
                                         .get('NemSpdInputs')
                                         .get('PeriodCollection')
                                         .get('Period')
                                         .get('GenericConstraintPeriodCollection')
                                         .get('GenericConstraintPeriod'))]


def get_generic_constraint_trader_variable_index(data) -> list:
    """Get all trader variables within generic constraints"""

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for all trader variables
    trader_variables = []
    for i in constraints:
        collection = i.get('LHSFactorCollection')

        # Continue if no LHS factors or no trader factors
        if (collection is None) or (collection.get('TraderFactor') is None):
            continue

        for j in convert_to_list(collection.get('TraderFactor')):
            trader_variables.append((j['@TraderID'], j['@TradeType']))

    # Retain unique indices
    return list(set(trader_variables))


def get_generic_constraint_interconnector_variable_index(data) -> list:
    """Get all interconnector variables within generic constraints"""

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for all interconnector variables
    interconnector_variables = []
    for i in constraints:
        collection = i.get('LHSFactorCollection')

        # Continue if no LHS factors or no interconnector factors
        if (collection is None) or (collection.get('InterconnectorFactor') is None):
            continue

        for j in convert_to_list(collection.get('InterconnectorFactor')):
            interconnector_variables.append(j['@InterconnectorID'])

    # Retain unique indices
    return list(set(interconnector_variables))


def get_generic_constraint_region_variable_index(data) -> list:
    """Get generic constraint region variable indices"""

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # Container for all region variables
    region_variables = []
    for i in constraints:
        collection = i.get('LHSFactorCollection')

        # Continue if no LHS factors or no region factors
        if (collection is None) or (collection.get('RegionFactor') is None):
            continue

        for j in convert_to_list(collection.get('RegionFactor')):
            region_variables.append((j['@RegionID'], j['@TradeType']))

    # Retain unique indices
    return list(set(region_variables))


def get_mnsp_index(data) -> list:
    """Get MNSP index"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

    # Only retain MNSPs
    return [i['@InterconnectorID'] for i in interconnectors if i['@MNSP'] == '1']


def get_mnsp_offer_index(data) -> list:
    """Get MNSP offer index"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

    # Container for offer index
    offer_index = []
    for i in interconnectors:
        # Non-MNSP interconnectors do not have an MNSPOfferCollection attribute
        if i.get('MNSPOfferCollection') is None:
            continue

        # Extract InterconnectorID and RegionID for each offer entry
        for j in i.get('MNSPOfferCollection').get('MNSPOffer'):
            offer_index.append((i['@InterconnectorID'], j['@RegionID']))

    return offer_index


def get_interconnector_index(data) -> list:
    """Get interconnector index"""

    return [i['@InterconnectorID'] for i in (data.get('NEMSPDCaseFile')
                                             .get('NemSpdInputs')
                                             .get('PeriodCollection')
                                             .get('Period')
                                             .get('InterconnectorPeriodCollection')
                                             .get('InterconnectorPeriod'))]


def get_interconnector_loss_model_breakpoint_index(data) -> list:
    """Get interconnector loss model breakpoint index"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for indices
    values = []
    for i in interconnectors:
        # Loss model segments
        segments = i.get('LossModelCollection').get(
            'LossModel').get('SegmentCollection').get('Segment')
        for j in range(len(segments) + 1):
            # Append index to container
            values.append((i['@InterconnectorID'], j))

    return values


def get_interconnector_loss_model_interval_index(data) -> list:
    """Get interconnector loss model interval index"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for indices
    values = []
    for i in interconnectors:
        # Loss model segments
        segments = i.get('LossModelCollection').get(
            'LossModel').get('SegmentCollection').get('Segment')
        for j in range(len(segments)):
            # Append index to container
            values.append((i['@InterconnectorID'], j))

    return values


def get_trader_price_bands(data) -> dict:
    """Trader price bands"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

    # Container for all price bands
    price_bands = {}
    for i in traders:
        # All trade types for a given trader
        trade_types = (i.get('TradePriceStructureCollection')
                       .get('TradePriceStructure')
                       .get('TradeTypePriceStructureCollection')
                       .get('TradeTypePriceStructure'))

        for j in convert_to_list(trade_types):
            # Price bands
            for k in range(1, 11):
                key = (i['@TraderID'], j['@TradeType'], k)
                price_bands[key] = float(j.get(f'@PriceBand{k}'))

    return price_bands


def get_trader_quantity_bands(data) -> dict:
    """Get trader quantity bands"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Container for quantity bands
    quantity_bands = {}
    for i in traders:
        for j in convert_to_list(i.get('TradeCollection').get('Trade')):
            # Quantity bands
            for k in range(1, 11):
                key = (i['@TraderID'], j['@TradeType'], k)
                quantity_bands[key] = float(j[f'@BandAvail{k}'])

    return quantity_bands


def get_trader_initial_condition_attribute(data, attribute, func) -> dict:
    """Get trader initial MW"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

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
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            if i.get(attribute) is not None}


def get_trader_collection_attribute(data, attribute, func) -> dict:
    """Get trader collection attribute"""

    return {i['@TraderID']: func(i[attribute]) for i in (data.get('NEMSPDCaseFile')
                                                         .get('NemSpdInputs')
                                                         .get('TraderCollection')
                                                         .get('Trader'))}


def get_trader_period_trade_attribute(data, attribute, func) -> dict:
    """Get trader quantity band attribute"""

    return {(i['@TraderID'], j['@TradeType']): func(j[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('PeriodCollection').get('Period')
                      .get('TraderPeriodCollection').get('TraderPeriod'))
            for j in convert_to_list(i.get('TradeCollection').get('Trade'))
            if j.get(attribute) is not None}


def get_trader_fast_start_attribute(data, attribute, func) -> dict:
    """Get trader fast start attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

    # Fast start traders
    fast_start_traders = get_trader_fast_start_index(data)

    return {i['@TraderID']: func(i.get(attribute))
            if i.get(attribute) is not None else i.get(attribute)
            for i in traders if i['@TraderID'] in fast_start_traders}


def get_interconnector_collection_attribute(data, attribute, func) -> dict:
    """Get interconnector collection attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for extract values
    values = {}
    for i in interconnectors:
        initial_conditions = (i.get('InterconnectorInitialConditionCollection')
                              .get('InterconnectorInitialCondition'))

        for j in initial_conditions:
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

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

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
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('InterconnectorCollection').get('Interconnector'))}


def get_interconnector_loss_model_segments(data, interconnector_id) -> list:
    """Get segments corresponding to interconnector loss model"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for loss model segments
    segments = []
    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            loss_model_segments = (i.get('LossModelCollection')
                                   .get('LossModel').get('SegmentCollection')
                                   .get('Segment'))

            for segment in loss_model_segments:
                s = {j: int(k) if j == '@Limit' else float(k) for j, k in segment.items()}
                segments.append(s)

    return segments


def get_interconnector_loss_model_segment_attribute(data, attribute, func) -> dict:
    """Get interconnector loss model segment collection"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection').get('Interconnector'))

    # Container for values
    values = {}
    for i in interconnectors:
        segment_attributes = (i.get('LossModelCollection').get('LossModel')
                              .get('SegmentCollection').get('Segment'))

        for j, k in enumerate(segment_attributes):
            # Extract loss model segment attribute
            values[(i['@InterconnectorID'], j)] = func(k[attribute])

    return values


def get_standardised_interconnector_loss_model_segments(data) -> dict:
    """Use breakpoints and segment factors to construct a new start-end representation for the MLF curve"""

    return {i: get_parsed_interconnector_loss_model_segments(data, i)
            for i in get_interconnector_index(data)}


def get_mnsp_price_bands(data) -> dict:
    """Get MNSP price bands"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for price band information
    price_bands = {}
    for i in interconnectors:
        if i.get('MNSPPriceStructureCollection') is None:
            continue

        # MNSP price structure
        price_structure = (i.get('MNSPPriceStructureCollection')
                           .get('MNSPPriceStructure')
                           .get('MNSPRegionPriceStructureCollection')
                           .get('MNSPRegionPriceStructure'))

        for j in price_structure:
            for k in range(1, 11):
                key = (i['@InterconnectorID'], j['@RegionID'], k)
                price_bands[key] = float(j[f'@PriceBand{k}'])

    return price_bands


def get_mnsp_quantity_bands(data) -> dict:
    """Get MNSP quantity bands"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

    # Container for quantity band information
    quantity_bands = {}
    for i in interconnectors:
        if i.get('MNSPOfferCollection') is None:
            continue

        # MNSP offers
        offers = i.get('MNSPOfferCollection').get('MNSPOffer')
        for j in offers:
            for k in range(1, 11):
                key = (i['@InterconnectorID'], j['@RegionID'], k)
                quantity_bands[key] = float(j[f'@BandAvail{k}'])

    return quantity_bands


def get_mnsp_offer_attribute(data, attribute) -> dict:
    """MNSP offer attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

    # Container for MNSP offer attributes
    values = {}
    for i in interconnectors:
        if i.get('MNSPOfferCollection') is None:
            continue

        # MNSP offers
        offers = i.get('MNSPOfferCollection').get('MNSPOffer')
        for j in offers:
            for k in range(1, 11):
                key = (i['@InterconnectorID'], j['@RegionID'], k)
                values[key] = float(j[f'@{attribute}'])

    return values


def get_mnsp_quantity_band_attribute(data, attribute, func) -> dict:
    """Get MNSP max available"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

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

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

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

    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('RegionCollection').get('Region'))

    # Container for extracted values
    values = {}
    for i in regions:
        initial_conditions = (i.get('RegionInitialConditionCollection')
                              .get('RegionInitialCondition'))

        for j in initial_conditions:
            if j['@InitialConditionID'] == attribute:
                values[i['@RegionID']] = func(j['@Value'])

    return values


def get_region_period_collection_attribute(data, attribute, func) -> dict:
    """Get region period collection attribute"""

    return {i['@RegionID']: func(i[attribute])
            for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                      .get('PeriodCollection').get('Period')
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

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdOutputs')
                   .get('ConstraintSolution'))

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

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
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
    """
    Generic constraint LHS terms - if no LHS terms then constraint is skipped
    """

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    return {i.get('@ConstraintID'): parse_constraint(i) for i in constraints
            if i.get('LHSFactorCollection') is not None}


def get_case_attribute(data, attribute, func):
    """Extract case attribute"""

    return func(data.get('NEMSPDCaseFile').get('NemSpdInputs').get('Case')[attribute])


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
    price_tied_flattened = [(i[0][0], i[0][1], i[0][2], i[1][0],
                             i[1][1], i[1][2]) for i in price_tied_unique]

    return price_tied_flattened


def get_mnsp_region_loss_indicator(data) -> dict:
    """Get region loss indicator. =1 if from region and InitialMW >= 0, or if ToRegion and InitialMW < 0, else =0"""

    # MNSP and region index
    mnsp_index = data['S_MNSPS']
    region_index = data['S_REGIONS']

    # MNSP attributes # TODO: this needs to change if intervention pricing case is considered
    initial_mw = data['P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW']
    to_region = data['P_INTERCONNECTOR_TO_REGION']
    from_region = data['P_INTERCONNECTOR_FROM_REGION']

    # Container for output
    out = {}
    for i in mnsp_index:

        for j in region_index:
            # Loss applied to FromRegion
            if (j == from_region[i]) and (initial_mw[i] >= 0):
                out[(i, j)] = 1

            # Loss applied to ToRegion
            elif (j == to_region[i]) and (initial_mw[i] < 0):
                out[(i, j)] = 1

            else:
                out[(i, j)] = 0

    return out


def construct_case(data, intervention) -> dict:
    """
    Parse json data

    Parameters
    ----------
    data : dict
        NEMDE casefile

    intervention : str
        NEMDE intervention flag. Either '1' or '0'.

    Returns
    -------
    case : dict
        Dictionary containing case data to be read into model
    """

    # Get intervention status
    # intervention = get_intervention_status(data=data, mode=mode)

    case = {
        'S_REGIONS': get_region_index(data),
        'S_TRADERS': get_trader_index(data),
        'S_TRADERS_SEMI_DISPATCH': get_trader_semi_dispatch_index(data),
        'S_TRADER_OFFERS': get_trader_offer_index(data),
        'S_TRADER_ENERGY_OFFERS': get_trader_energy_offer_index(data),
        'S_TRADER_FCAS_OFFERS': get_trader_fcas_offer_index(data),
        'S_TRADER_FAST_START': get_trader_fast_start_index(data),
        'S_TRADER_PRICE_TIED': get_price_tied_bands(data),
        'S_GENERIC_CONSTRAINTS': get_generic_constraint_index(data),
        'S_GC_TRADER_VARS': get_generic_constraint_trader_variable_index(data),
        'S_GC_INTERCONNECTOR_VARS': get_generic_constraint_interconnector_variable_index(data),
        'S_GC_REGION_VARS': get_generic_constraint_region_variable_index(data),
        'S_MNSPS': get_mnsp_index(data),
        'S_MNSP_OFFERS': get_mnsp_offer_index(data),
        'S_INTERCONNECTORS': get_interconnector_index(data),
        'S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS': get_interconnector_loss_model_breakpoint_index(data),
        'S_INTERCONNECTOR_LOSS_MODEL_INTERVALS': get_interconnector_loss_model_interval_index(data),
        'P_CASE_ID': get_case_attribute(data, '@CaseID', str),
        'P_INTERVENTION_STATUS': intervention,
        'P_TRADER_PRICE_BAND': get_trader_price_bands(data),
        'P_TRADER_QUANTITY_BAND': get_trader_quantity_bands(data),
        'P_TRADER_MAX_AVAIL': get_trader_period_trade_attribute(data, '@MaxAvail', float),
        'P_TRADER_UIGF': get_trader_period_attribute(data, '@UIGF', float),
        'P_TRADER_INITIAL_MW': get_trader_initial_condition_attribute(data, 'InitialMW', float),
        'P_TRADER_WHAT_IF_INITIAL_MW': get_trader_initial_condition_attribute(data, 'WhatIfInitialMW', float),
        'P_TRADER_HMW': get_trader_initial_condition_attribute(data, 'HMW', float),
        'P_TRADER_LMW': get_trader_initial_condition_attribute(data, 'LMW', float),
        'P_TRADER_AGC_STATUS': get_trader_initial_condition_attribute(data, 'AGCStatus', str),
        'P_TRADER_SEMI_DISPATCH_STATUS': get_trader_collection_attribute(data, '@SemiDispatch', str),
        'P_TRADER_REGION': get_trader_period_attribute(data, '@RegionID', str),
        'P_TRADER_PERIOD_RAMP_UP_RATE': get_trader_period_trade_attribute(data, '@RampUpRate', float),
        'P_TRADER_PERIOD_RAMP_DN_RATE': get_trader_period_trade_attribute(data, '@RampDnRate', float),
        'P_TRADER_TYPE': get_trader_collection_attribute(data, '@TraderType', str),
        'P_TRADER_SCADA_RAMP_UP_RATE': get_trader_initial_condition_attribute(data, 'SCADARampUpRate', float),
        'P_TRADER_SCADA_RAMP_DN_RATE': get_trader_initial_condition_attribute(data, 'SCADARampDnRate', float),
        'P_TRADER_MIN_LOADING_MW': get_trader_fast_start_attribute(data, '@MinLoadingMW', float),
        'P_TRADER_CURRENT_MODE': get_trader_fast_start_attribute(data, '@CurrentMode', str),
        'P_TRADER_CURRENT_MODE_TIME': get_trader_fast_start_attribute(data, '@CurrentModeTime', float),
        'P_TRADER_T1': get_trader_fast_start_attribute(data, '@T1', float),
        'P_TRADER_T2': get_trader_fast_start_attribute(data, '@T2', float),
        'P_TRADER_T3': get_trader_fast_start_attribute(data, '@T3', float),
        'P_TRADER_T4': get_trader_fast_start_attribute(data, '@T4', float),
        'P_TRADER_ENABLEMENT_MIN': get_trader_period_trade_attribute(data, '@EnablementMin', float),
        'P_TRADER_LOW_BREAKPOINT': get_trader_period_trade_attribute(data, '@LowBreakpoint', float),
        'P_TRADER_HIGH_BREAKPOINT': get_trader_period_trade_attribute(data, '@HighBreakpoint', float),
        'P_TRADER_ENABLEMENT_MAX': get_trader_period_trade_attribute(data, '@EnablementMax', float),
        'P_INTERCONNECTOR_INITIAL_MW': get_interconnector_collection_attribute(data, 'InitialMW', float),
        'P_INTERCONNECTOR_TO_REGION': get_interconnector_period_collection_attribute(data, '@ToRegion', str),
        'P_INTERCONNECTOR_FROM_REGION': get_interconnector_period_collection_attribute(data, '@FromRegion', str),
        'P_INTERCONNECTOR_LOWER_LIMIT': get_interconnector_period_collection_attribute(data, '@LowerLimit', float),
        'P_INTERCONNECTOR_UPPER_LIMIT': get_interconnector_period_collection_attribute(data, '@UpperLimit', float),
        'P_INTERCONNECTOR_MNSP_STATUS': get_interconnector_period_collection_attribute(data, '@MNSP', str),
        'P_INTERCONNECTOR_LOSS_SHARE': get_interconnector_loss_model_attribute(data, '@LossShare', float),
        'P_INTERCONNECTOR_LOSS_LOWER_LIMIT': get_interconnector_loss_model_attribute(data, '@LossLowerLimit', float),
        'P_INTERCONNECTOR_LOSS_SEGMENT_LIMIT': get_interconnector_loss_model_segment_attribute(data, '@Limit', float),
        'P_INTERCONNECTOR_LOSS_SEGMENT_FACTOR': get_interconnector_loss_model_segment_attribute(data, '@Factor', float),
        'P_MNSP_PRICE_BAND': get_mnsp_price_bands(data),
        'P_MNSP_QUANTITY_BAND': get_mnsp_quantity_bands(data),
        'P_MNSP_MAX_AVAILABLE': get_mnsp_quantity_band_attribute(data, '@MaxAvail', float),
        'P_MNSP_TO_REGION_LF': get_mnsp_period_collection_attribute(data, '@ToRegionLF', float),
        'P_MNSP_TO_REGION_LF_EXPORT': get_mnsp_period_collection_attribute(data, '@ToRegionLFExport', float),
        'P_MNSP_TO_REGION_LF_IMPORT': get_mnsp_period_collection_attribute(data, '@ToRegionLFImport', float),
        'P_MNSP_FROM_REGION_LF': get_mnsp_period_collection_attribute(data, '@FromRegionLF', float),
        'P_MNSP_FROM_REGION_LF_EXPORT': get_mnsp_period_collection_attribute(data, '@FromRegionLFExport', float),
        'P_MNSP_FROM_REGION_LF_IMPORT': get_mnsp_period_collection_attribute(data, '@FromRegionLFImport', float),
        'P_MNSP_LOSS_PRICE': get_case_attribute(data, '@MNSPLossesPrice', float),
        'P_MNSP_RAMP_UP_RATE': get_mnsp_quantity_band_attribute(data, '@RampUpRate', float),
        'P_MNSP_RAMP_DOWN_RATE': get_mnsp_quantity_band_attribute(data, '@RampDnRate', float),
        'P_REGION_INITIAL_DEMAND': get_region_initial_condition_attribute(data, 'InitialDemand', float),
        'P_REGION_ADE': get_region_initial_condition_attribute(data, 'ADE', float),
        'P_REGION_DF': get_region_period_collection_attribute(data, '@DF', float),
        'P_GC_RHS': get_generic_constraint_rhs(data, intervention),
        'P_GC_TYPE': get_generic_constraint_collection_attribute(data, '@Type', str),
        'P_CVF_GC': get_generic_constraint_collection_attribute(data, '@ViolationPrice', float),
        'P_CVF_VOLL': get_case_attribute(data, '@VoLL', float),
        'P_CVF_ENERGY_DEFICIT_PRICE': get_case_attribute(data, '@EnergyDeficitPrice', float),
        'P_CVF_ENERGY_SURPLUS_PRICE': get_case_attribute(data, '@EnergySurplusPrice', float),
        'P_CVF_UIGF_SURPLUS_PRICE': get_case_attribute(data, '@UIGFSurplusPrice', float),
        'P_CVF_RAMP_RATE_PRICE': get_case_attribute(data, '@RampRatePrice', float),
        'P_CVF_CAPACITY_PRICE': get_case_attribute(data, '@CapacityPrice', float),
        'P_CVF_OFFER_PRICE': get_case_attribute(data, '@OfferPrice', float),
        'P_CVF_MNSP_OFFER_PRICE': get_case_attribute(data, '@MNSPOfferPrice', float),
        'P_CVF_MNSP_RAMP_RATE_PRICE': get_case_attribute(data, '@MNSPRampRatePrice', float),
        'P_CVF_MNSP_CAPACITY_PRICE': get_case_attribute(data, '@MNSPCapacityPrice', float),
        'P_CVF_AS_PROFILE_PRICE': get_case_attribute(data, '@ASProfilePrice', float),
        'P_CVF_AS_MAX_AVAIL_PRICE': get_case_attribute(data, '@ASMaxAvailPrice', float),
        'P_CVF_AS_ENABLEMENT_MIN_PRICE': get_case_attribute(data, '@ASEnablementMinPrice', float),
        'P_CVF_AS_ENABLEMENT_MAX_PRICE': get_case_attribute(data, '@ASEnablementMaxPrice', float),
        'P_CVF_INTERCONNECTOR_PRICE': get_case_attribute(data, '@InterconnectorPrice', float),
        'P_CVF_FAST_START_PRICE': get_case_attribute(data, '@FastStartPrice', float),
        'P_CVF_GENERIC_CONSTRAINT_PRICE': get_case_attribute(data, '@GenericConstraintPrice', float),
        'P_CVF_SATISFACTORY_NETWORK_PRICE': get_case_attribute(data, '@Satisfactory_Network_Price', float),
        'P_TIE_BREAK_PRICE': get_case_attribute(data, '@TieBreakPrice', float),
        'intermediate': {
            'generic_constraint_lhs_terms': get_generic_constraint_lhs_terms(data),
            'loss_model_segments': get_standardised_interconnector_loss_model_segments(data),
        },
    }

    # Get intervention flag
    intervention_flag = get_case_attribute(data, '@Intervention', str)

    # Use 'What If' if an intervention pricing period and run mode is 'pricing'
    if (intervention_flag == 'True') and (intervention == '0'):
        effective_mw = {
            'P_TRADER_EFFECTIVE_INITIAL_MW': case['P_TRADER_WHAT_IF_INITIAL_MW'],
            'P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW': case['P_INTERCONNECTOR_WHAT_IF_INITIAL_MW'],
        }

    # Use InitialMW in all other cases
    else:
        effective_mw = {
            'P_TRADER_EFFECTIVE_INITIAL_MW': case['P_TRADER_INITIAL_MW'],
            'P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW': case['P_INTERCONNECTOR_INITIAL_MW'],
        }

    # Combine into final serialized case dictionary
    case_data = {**case, **effective_mw}

    return case_data
