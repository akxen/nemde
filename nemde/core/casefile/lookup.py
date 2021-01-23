"""
Lookup attribute values in casefile dictionary
"""

from nemde.errors import CasefileLookupError, CasefileRunModeError
from nemde.core.casefile.utils import convert_to_list


def get_case_attribute(data, attribute, func):
    """Get case attribute"""

    try:
        return func(data['NEMSPDCaseFile']['NemSpdInputs']['Case'][attribute])
    except CasefileLookupError as e:
        return e


def get_region_collection_attribute(data, region_id, attribute, func):
    """Get region collection attribute"""

    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('RegionCollection').get('Region'))

    for i in regions:
        if i['@RegionID'] == region_id:
            return func(i[attribute])

    raise CasefileLookupError('Attribute not found:', region_id, attribute)


def get_region_collection_initial_condition_attribute(data, region_id, attribute, func):
    """Get region initial condition attribute"""

    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('RegionCollection').get('Region'))

    for i in regions:
        if i['@RegionID'] == region_id:
            initial_conditions = (i.get('RegionInitialConditionCollection')
                                  .get('RegionInitialCondition'))

            for j in convert_to_list(initial_conditions):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise CasefileLookupError('Attribute not found:', region_id, attribute)


def get_region_period_collection_attribute(data, region_id, attribute, func):
    """Get region period collection attribute"""

    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('PeriodCollection').get('Period')
               .get('RegionPeriodCollection').get('RegionPeriod'))

    for i in regions:
        if i['@RegionID'] == region_id:
            return func(i[attribute])

    raise CasefileLookupError('Attribute not found:', region_id, attribute)


def get_region_solution_attribute(data, region_id, attribute, func, intervention):
    """Extract region solution attribute"""

    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')

    for i in regions:
        if (i['@RegionID'] == region_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    message = f'Attribute not found: {region_id} {attribute} {intervention}'
    raise CasefileLookupError(message)


def get_trader_collection_attribute(data, trader_id, attribute, func):
    """Get trader collection attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])

    raise CasefileLookupError('Attribute not found:', trader_id, attribute)


def get_trader_collection_initial_condition_attribute(data, trader_id, attribute, func):
    """Get trader initial condition attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            initial_conditions = (i.get('TraderInitialConditionCollection')
                                  .get('TraderInitialCondition'))
            for j in convert_to_list(initial_conditions):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise CasefileLookupError('Attribute not found:', trader_id, attribute)


def get_trader_period_collection_attribute(data, trader_id, attribute, func):
    """Get trader period collection attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])

    raise CasefileLookupError('Attribute not found:', trader_id, attribute)


def get_trader_quantity_band_attribute(data, trader_id, trade_type, attribute, func):
    """Get trader quantity band attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in convert_to_list(i.get('TradeCollection').get('Trade')):
                if j['@TradeType'] == trade_type:
                    return func(j[attribute])

    message = f'Attribute not found: {trader_id} {trade_type} {attribute}'
    raise CasefileLookupError(message)


def get_trader_price_band_attribute(data, trader_id, trade_type, attribute, func):
    """Get trader price band attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('TraderCollection').get('Trader'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            price_bands = (i.get('TradePriceStructureCollection')
                           .get('TradePriceStructure')
                           .get('TradeTypePriceStructureCollection')
                           .get('TradeTypePriceStructure'))

            for j in convert_to_list(price_bands):
                if j['@TradeType'] == trade_type:
                    return func(j[attribute])

    message = f'Attribute not found: {trader_id} {trade_type} {attribute}'
    raise CasefileLookupError(message)


def get_trader_solution_attribute(data, trader_id, attribute, func, intervention):
    """Get trader solution attribute"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdOutputs')
               .get('TraderSolution'))

    for i in traders:
        trader_id_matches = i['@TraderID'] == trader_id
        intervention_flag_matches = i['@Intervention'] == intervention
        if trader_id_matches and intervention_flag_matches:
            return func(i[attribute])

    message = f'Attribute not found: {trader_id} {attribute} {intervention}'
    raise CasefileLookupError(message)


def get_interconnector_collection_attribute(data, interconnector_id, attribute, func):
    """Get interconnector collection attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection').get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i[attribute])

    message = f'Attribute not found: {interconnector_id} {attribute} {func}'
    raise CasefileLookupError(message)


def get_interconnector_collection_initial_condition_attribute(data, interconnector_id, attribute, func):
    """Get interconnector initial condition attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection').get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            initial_conditions = (i.get('InterconnectorInitialConditionCollection')
                                  .get('InterconnectorInitialCondition'))

            for j in convert_to_list(initial_conditions):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    message = f'Attribute not found: {interconnector_id} {attribute} {func}'
    raise CasefileLookupError(message)


def get_interconnector_period_collection_attribute(data, interconnector_id, attribute, func):
    """Get interconnector period collection attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection')
                       .get('InterconnectorPeriod'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i[attribute])

    message = f'Attribute not found: {interconnector_id} {attribute} {func}'
    raise CasefileLookupError(message)


def get_interconnector_loss_model_attribute(data, interconnector_id, attribute, func):
    """Get interconnector loss model attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection').get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i.get('LossModelCollection').get('LossModel')[attribute])

    raise CasefileLookupError('Attribute not found:', interconnector_id, attribute)


def get_interconnector_loss_model_segments(data, interconnector_id) -> list:
    """Get segments corresponding to interconnector loss model"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection').get('Interconnector'))

    # Container for loss model segments
    output = []
    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            # Loss model segements for interconnector
            segments = (i.get('LossModelCollection').get('LossModel')
                        .get('SegmentCollection').get('Segment'))

            # Convert '@Factor' to float and '@Limit' to int (following casefile)
            for segment in segments:
                s = {j: int(k) if j == '@Limit' else float(k) for j, k in segment.items()}
                output.append(s)

    return output


def get_interconnector_solution_attribute(data, interconnector_id, attribute, func, intervention):
    """Get interconnector solution attribute"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdOutputs')
                       .get('InterconnectorSolution'))

    for i in interconnectors:
        interconnector_id_matches = i['@InterconnectorID'] == interconnector_id
        intervention_flag_matches = i['@Intervention'] == intervention

        if interconnector_id_matches and intervention_flag_matches:
            return func(i[attribute])

    message = f'Attribute not found: {interconnector_id} {attribute} {intervention}'
    raise CasefileLookupError(message)


def get_generic_constraint_collection_attribute(data, constraint_id, attribute, func):
    """Get generic constraint collection attribute"""

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    for i in constraints:
        if i['@ConstraintID'] == constraint_id:
            return func(i[attribute])

    message = f'Attribute not found: {constraint_id} {attribute}'
    raise CasefileLookupError(message)


def get_generic_constraint_trk_collection_attribute(data, constraint_id, attribute, func):
    """
    Get generic constraint trk collection attribute (inner key within
    generic constraint collection attribute)
    """

    # Trk collection for generic constraint
    trk_collection = get_generic_constraint_collection_attribute(
        data=data, constraint_id=constraint_id,
        attribute='s:ConstraintTrkCollection', func=dict)

    # Get items corresponding to the collection
    trk_items = trk_collection['ConstraintTrkItem']

    return func(trk_items[attribute])


def get_generic_constraint_solution_attribute(data, constraint_id, attribute, func, intervention):
    """Get generic constraint solution attribute"""

    constraints = (data.get('NEMSPDCaseFile').get('NemSpdOutputs')
                   .get('ConstraintSolution'))

    for i in constraints:
        contraint_id_matches = i['@ConstraintID'] == constraint_id
        intervention_flag_matches = i['@Intervention'] == intervention

        if contraint_id_matches and intervention_flag_matches:
            return func(i[attribute])

    message = f'Attribute not found: {constraint_id} {attribute} {intervention}'
    raise CasefileLookupError(message)


def get_period_solution_attribute(data, attribute, func, intervention):
    """Get period solution attribute"""

    period_solution = (data.get('NEMSPDCaseFile').get('NemSpdOutputs')
                       .get('PeriodSolution'))

    for i in convert_to_list(period_solution):
        if i['@Intervention'] == intervention:
            return func(i[attribute])

    raise CasefileLookupError('Attribute not found:', attribute, intervention)


def get_trader_index(data) -> list:
    """Get all trader IDs"""

    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    return [i['@TraderID'] for i in traders]


def get_interconnector_index(data) -> list:
    """Get interconnector index"""

    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                       .get('InterconnectorCollection').get('Interconnector'))

    return [i['@InterconnectorID'] for i in interconnectors]


def get_mnsp_index(data) -> list:
    """Get MNSP index"""

    mnsps = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
             .get('PeriodCollection').get('Period')
             .get('InterconnectorPeriodCollection')
             .get('InterconnectorPeriod'))

    return [i['@InterconnectorID'] for i in mnsps if i['@MNSP'] == '1']


def get_region_index(data) -> list:
    """Get list of all regions"""

    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
               .get('RegionCollection').get('Region'))

    return [i['@RegionID'] for i in regions]


def get_intervention_status(data, mode) -> str:
    """
    Check if intervention pricing run occurred - trying to model physical
    run if intervention occurred
    """

    # Intervention flag is str in casefile 'True' or 'False'
    intervention_flag = get_case_attribute(data, '@Intervention', str)

    if (intervention_flag == 'False') and (mode == 'physical'):
        return '0'
    elif (intervention_flag == 'False') and (mode == 'pricing'):
        return '0'
    elif (intervention_flag == 'True') and (mode == 'physical'):
        return '1'
    elif (intervention_flag == 'True') and (mode == 'pricing'):
        return '0'
    else:
        raise CasefileRunModeError('Unhandled case:', mode)
