"""
Run model with user specified inputs
"""

import json

from nemde.io.casefile import load_base_case
from nemde.errors import CasefileOptionsError
from nemde.core.casefile.updater import patch_casefile
from nemde.core.model.serializers import casefile_serializer
from nemde.core.model.serializers import solution_serializer
from nemde.core.model.preprocessing import get_preprocessed_serialized_casefile
from nemde.core.model.constructor import construct_model
from nemde.core.model.algorithms import solve_model


def clean_user_input(user_data):
    """Parse user data and set defaults if option not specified"""

    # Load user data as json
    data = json.loads(user_data)

    # Extract options
    options = data.get('options', {})

    # TODO check parameters and raise exceptions if values not allowed

    # TODO check if user case data is in JSON format - if not convert to JSON

    # Place cleaned data
    cleaned = {
        'case_data': data.get('case_data', None),
        'case_id': data.get('case_id', None),
        'patches': data.get('patches', []),
        'options': {
            'intervention': options.get('intervention', '0'),
            'algorithm': options.get('algorithm', 'dispatch_only'),
            'solution_format': options.get('solution_format', 'standard')
        }
    }

    has_case_data = cleaned['case_data'] is not None
    has_case_id = cleaned['case_id'] is not None
    has_patches = len(cleaned['patches']) > 0

    if has_case_data and (has_case_id or has_patches):
        description = ("If 'case_data' is specified then 'case_id' and",
                       "'patches' should be omitted")
        raise CasefileOptionsError("Case options conflict", description)

    return cleaned


def run_model(user_data):
    """
    Run model with user options

    Parameters
    ----------
    user_data : dict
        Dictionary containing user supplied information
    """

    # Clean user input and set defaults
    data = clean_user_input(user_data)

    # Extract model options
    case_id = data.get('case_id')
    user_case_data = data.get('case_data')
    user_patches = data.get('patches')
    algorithm = data.get('options').get('algorithm')
    intervention = data.get('options').get('intervention')
    solution_format = data.get('options').get('solution_format')

    # Use user specified casefile
    if case_id is None:
        case_data = user_case_data

    # Use use base casefile and apply user patches
    else:
        base_case = load_base_case(case_id=case_id)
        case_data = patch_casefile(casefile=base_case, updates=user_patches)

    # Construct serialized casefile and model object
    serialized_case = casefile_serializer.construct_case(
        data=case_data, intervention=intervention)

    # Apply preprocessing to serialized casefile
    preprocessed_case = get_preprocessed_serialized_casefile(data=serialized_case)

    # Construct model
    model = construct_model(data=preprocessed_case)

    # Solve model and extract solution
    model = solve_model(model=model, intervention=intervention, algorithm=algorithm)
    solution = solution_serializer.serialize_model_solution(model=model, format=solution_format)

    return solution
