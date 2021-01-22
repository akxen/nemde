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


def get_intervention_status(data, mode) -> str:
    """Check if intervention pricing run occurred - trying to model physical run if intervention occurred"""

    if (get_case_attribute(data, '@Intervention', str) == 'False') and (mode == 'physical'):
        return '0'
    elif (get_case_attribute(data, '@Intervention', str) == 'False') and (mode == 'pricing'):
        return '0'
    elif (get_case_attribute(data, '@Intervention', str) == 'True') and (mode == 'physical'):
        return '1'
    elif (get_case_attribute(data, '@Intervention', str) == 'True') and (mode == 'pricing'):
        return '0'
    else:
        raise Exception('Unhandled case:', mode)
