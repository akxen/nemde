"""Lookup attributes for individual trader / interconnector / region"""


def convert_to_list(list_or_dict):
    """Convert list to dict or return input list"""

    if isinstance(list_or_dict, dict):
        return [list_or_dict]
    elif isinstance(list_or_dict, list):
        return list_or_dict
    else:
        raise Exception('Unexpected type:', type(list_or_dict), list_or_dict)


def get_case_attribute(data, attribute, func):
    """Get case attribute"""

    return func(data['NEMSPDCaseFile']['NemSpdInputs']['Case'][attribute])


def get_region_collection_attribute(data, region_id, attribute, func):
    """Get region collection attribute"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    for i in regions:
        if i['@RegionID'] == region_id:
            return func(i[attribute])

    raise LookupError('Attribute not found:', region_id, attribute)


def get_region_collection_initial_condition_attribute(data, region_id, attribute, func):
    """Get region collection attribute"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    for i in regions:
        if i['@RegionID'] == region_id:
            for j in convert_to_list(i.get('RegionInitialConditionCollection').get('RegionInitialCondition')):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise LookupError('Attribute not found:', region_id, attribute)


def get_region_period_collection_attribute(data, region_id, attribute, func):
    """Get region period collection attribute"""

    # All regions
    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('RegionPeriodCollection').get('RegionPeriod'))

    for i in regions:
        if i['@RegionID'] == region_id:
            return func(i[attribute])

    raise LookupError('Attribute not found:', region_id, attribute)


def get_region_solution_attribute(data, region_id, attribute, func, intervention='1'):
    """Extract region solution attribute"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')
    for i in regions:
        if (i['@RegionID'] == region_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise LookupError('Attribute not found:', region_id, attribute)


def get_trader_collection_attribute(data, trader_id, attribute, func):
    """Get trader collection attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])

    raise LookupError('Attribute not found:', trader_id, attribute)


def get_trader_collection_initial_condition_attribute(data, trader_id, attribute, func):
    """Get trader initial condition attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in i.get('TraderInitialConditionCollection').get('TraderInitialCondition'):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise LookupError('Attribute not found:', trader_id, attribute)


def get_trader_period_collection_attribute(data, trader_id, attribute, func):
    """Get trader period collection attribute"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])

    raise LookupError('Attribute not found:', trader_id, attribute)


def get_trader_quantity_band_attribute(data, trader_id, trade_type, attribute, func):
    """Get trader quantity band attribute"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in convert_to_list(i.get('TradeCollection').get('Trade')):
                if j['@TradeType'] == trade_type:
                    return func(j[attribute])

    raise LookupError('Attribute not found:', trader_id, trade_type, attribute)


def get_trader_price_band_attribute(data, trader_id, trade_type, attribute, func):
    """Get trader price band attribute"""

    # All traders
    # NEMSPDCaseFile.NemSpdInputs.TraderCollection.Trader[0].TradePriceStructureCollection.TradePriceStructure.TradeTypePriceStructureCollection.TradeTypePriceStructure.@TradeType
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            price_bands = (i.get('TradePriceStructureCollection').get('TradePriceStructure')
                           .get('TradeTypePriceStructureCollection').get('TradeTypePriceStructure'))

            for j in convert_to_list(price_bands):
                if j['@TradeType'] == trade_type:
                    return func(j[attribute])

    raise LookupError('Attribute not found:', trader_id, trade_type, attribute)


def get_trader_solution_attribute(data, trader_id, attribute, func, intervention='1'):
    """Get trader solution attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    for i in traders:
        if (i['@TraderID'] == trader_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise LookupError('Attribute not found:', trader_id, attribute, intervention)


def get_interconnector_collection_attribute(data, interconnector_id, attribute, func):
    """Get interconnector collection attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i[attribute])

    raise LookupError('Attribute not found:', interconnector_id, attribute, func)


def get_interconnector_collection_initial_condition_attribute(data, interconnector_id, attribute, func):
    """Get interconnector initial condition attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            # Initial conditions
            initial_conditions = i.get('InterconnectorInitialConditionCollection').get('InterconnectorInitialCondition')
            for j in convert_to_list(initial_conditions):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise LookupError('Attribute not found:', interconnector_id, attribute, func)


def get_interconnector_period_collection_attribute(data, interconnector_id, attribute, func):
    """Get interconnector period collection attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i[attribute])

    raise LookupError('Attribute not found:', interconnector_id, attribute, func)


def get_interconnector_loss_model_attribute(data, interconnector_id, attribute, func):
    """Get interconnector loss model attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i.get('LossModelCollection').get('LossModel')[attribute])

    raise Exception('Attribute not found:', interconnector_id, attribute)


def get_interconnector_solution_attribute(data, interconnector_id, attribute, func, intervention='1'):
    """Get interconnector solution attribute"""

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

    for i in interconnectors:
        if (i['@InterconnectorID'] == interconnector_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise LookupError('Attribute not found:', interconnector_id, attribute, intervention)


def get_generic_constraint_solution_attribute(data, constraint_id, attribute, func, intervention='1'):
    """Get generic constraint solution attribute"""

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

    for i in constraints:
        if (i['@ConstraintID'] == constraint_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise LookupError('Attribute not found:', constraint_id, attribute, intervention)


def get_period_solution_attribute(data, attribute, func):
    """Get period solution attribute"""

    return func(data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('PeriodSolution')[attribute])


def get_trader_offer_index(data) -> list:
    """Get tuples describing all offers made by traders"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    # Trader offers
    out = []
    for i in traders:
        for j in convert_to_list(i.get('TradeCollection').get('Trade')):
            out.append((i.get('@TraderID'), j.get('@TradeType')))

    return out


def get_region_index(data) -> list:
    """Get list of all regions"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    out = []
    for i in regions:
        out.append(i['@RegionID'])

    return list(set(out))


def get_generic_constraint_index(data) -> list:
    """Get generic constraint index"""

    return [i['@ConstraintID'] for i in (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                                         .get('Period').get('GenericConstraintPeriodCollection')
                                         .get('GenericConstraintPeriod'))]


def get_intervention_status(data) -> str:
    """Check if intervention pricing run occurred - trying to model physical run if intervention occurred"""

    return '0' if get_case_attribute(data, '@Intervention', str) == 'False' else '1'
