"""
Common utility functions used when parsing casefiles
"""


def convert_to_list(list_or_dict):
    """Convert list to dict or return input list"""

    if isinstance(list_or_dict, dict):
        return [list_or_dict]
    elif isinstance(list_or_dict, list):
        return list_or_dict
    else:
        raise TypeError(f'Input should be a list or dict. Received {type(list_or_dict)}')
