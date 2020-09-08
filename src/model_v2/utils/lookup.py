"""Lookup attributes for individual trader / interconnector / region"""


def convert_to_list(list_or_dict):
    """Convert list to dict or return input list"""

    if isinstance(list_or_dict, dict):
        return list(list_or_dict)
    elif isinstance(list_or_dict, list):
        return list_or_dict
    else:
        raise Exception('Unexpected type:', type(list_or_dict), list_or_dict)


def get_region_collection_attribute(data, region_id, attribute, func):
    """Get region collection attribute"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    for i in regions:
        if i['@RegionID'] == region_id:
            return func(i[attribute])

    raise Exception('Attribute not found:', region_id, attribute)


def get_region_collection_initial_condition_attribute(data, region_id, attribute, func):
    """Get region collection attribute"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    for i in regions:
        if i['@RegionID'] == region_id:
            for j in convert_to_list(i.get('RegionInitialConditionCollection').get('RegionInitialCondition')):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise Exception('Attribute not found:', region_id, attribute)


def get_region_period_collection_attribute(data, region_id, attribute, func):
    """Get region period collection attribute"""

    # All regions
    regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('RegionPeriodCollection').get('RegionPeriod'))

    for i in regions:
        if i['@RegionID'] == region_id:
            return func(i[attribute])

    raise Exception('Attribute not found:', region_id, attribute)


def get_region_solution_attribute(data, region_id, attribute, func, intervention='0'):
    """Extract region solution attribute"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')
    for i in regions:
        if (i['@RegionID'] == region_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise Exception('Attribute not found:', region_id, attribute)


def get_trader_collection_attribute(data, trader_id, attribute, func):
    """Get trader collection attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])

    raise Exception('Attribute not found:', trader_id, attribute)


def get_trader_collection_initial_condition_attribute(data, trader_id, attribute, func):
    """Get trader initial condition attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    for i in traders:
        if i['@TraderID'] == trader_id:
            for j in i.get('TraderInitialConditionCollection').get('TraderInitialCondition'):
                if j['@InitialConditionID'] == attribute:
                    return func(j['@Value'])

    raise Exception('Attribute not found:', trader_id, attribute)


def get_trader_period_collection_attribute(data, trader_id, attribute, func):
    """Get trader period collection attribute"""

    # All traders
    traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
               .get('TraderPeriodCollection').get('TraderPeriod'))

    for i in traders:
        if i['@TraderID'] == trader_id:
            return func(i[attribute])

    raise Exception('Attribute not found:', trader_id, attribute)


def get_trader_solution_attribute(data, trader_id, attribute, func, intervention='0'):
    """Get trader solution attribute"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    for i in traders:
        if (i['@TraderID'] == trader_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise Exception('Attribute not found:', trader_id, attribute, intervention)


def get_interconnector_collection_attribute(data, interconnector_id, attribute, func):
    """Get interconnector collection attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i[attribute])

    raise Exception('Attribute not found:', interconnector_id, attribute, func)


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

    raise Exception('Attribute not found:', interconnector_id, attribute, func)


def get_interconnector_period_collection_attribute(data, interconnector_id, attribute, func):
    """Get interconnector period collection attribute"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i[attribute])

    raise Exception('Attribute not found:', interconnector_id, attribute, func)


def get_interconnector_loss_model_attribute(data, interconnector_id, attribute, func):
    """Get interconnector loss model attribute"""

    # NEMSPDCaseFile.NemSpdInputs.InterconnectorCollection.Interconnector[0].LossModelCollection.LossModel.@LossShare
    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    for i in interconnectors:
        if i['@InterconnectorID'] == interconnector_id:
            return func(i.get('LossModelCollection').get('LossModel')[attribute])

    raise Exception('Attribute not found:', interconnector_id, attribute)


def get_interconnector_solution_attribute(data, interconnector_id, attribute, func, intervention='0'):
    """Get interconnector solution attribute"""

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

    for i in interconnectors:
        if (i['@InterconnectorID'] == interconnector_id) and (i['@Intervention'] == intervention):
            return func(i[attribute])

    raise Exception('Attribute not found:', interconnector_id, attribute, intervention)
