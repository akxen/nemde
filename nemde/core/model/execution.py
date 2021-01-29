"""
Run model with user specified inputs
"""

import json

from nemde.io.casefile import load_base_case
from nemde.errors import CasefileOptionsError
from nemde.core.casefile.updater import patch_casefile
from nemde.core.model.serializers.casefile_serializer import construct_case
from nemde.core.model.serializers.solution_serializer import get_solution
from nemde.core.model.serializers.solution_serializer import get_solution_comparison
from nemde.core.model.constructor import construct_model
from nemde.core.model.algorithms import solve_model


def clean_user_input(user_data):
    """Parse user data and set defaults if option not specified"""

    # Load user data as json
    data = json.loads(user_data)

    # Extract options
    options = data.get('options', {})

    # Cleaned options
    cleaned = {
        'case_data': data.get('case_data', None),
        'case_id': data.get('case_id', None),
        'patches': data.get('patches', []),
        'run_mode': options.get('run_mode', 'physical'),
        'options': {
            'algorithm': options.get('algorithm', 'dispatch_only'),
            'solution_format': options.get('solution_format', 'standard'),
        }
    }

    has_case_data = cleaned['case_data'] is not None
    has_case_id = cleaned['case_id'] is not None
    has_patches = len(cleaned['patches']) > 0

    if has_case_data and (has_case_id or has_patches):
        message = ("If 'case_data' is specified then 'case_id' and 'patches'",
                   "should be omitted")
        raise CasefileOptionsError(message)

    if cleaned.get('run_mode') not in ['physical', 'pricing']:
        message = "'run_mode' must be set to 'physical' or 'pricing'"
        raise CasefileOptionsError(message)

    if cleaned.get('options').get('solution_format') not in ['standard', 'validation']:
        message = "'solution_format' must be either 'standard' or 'validation'"
        raise CasefileOptionsError(message)

    return cleaned


def run_model(user_data):
    """
    Run model with user options

    Parameters
    ----------
    user_data : dict
        Dictionary containing user supplied information
    
    Returns
    -------
    Model solution
    """

    # Clean user input and set defaults
    data = clean_user_input(user_data)

    # Extract model options
    case_id = data.get('case_id')
    user_case_data = data.get('case_data')
    user_patches = data.get('patches')
    run_mode = data.get('run_mode')
    algorithm = data.get('options').get('algorithm')
    solution_format = data.get('options').get('solution_format')

    # Use user specified casefile
    if case_id is None:
        case_data = user_case_data

    # Use use base casefile and apply user patches
    else:
        base_case = load_base_case(case_id=case_id)
        case_data = patch_casefile(casefile=base_case, updates=user_patches)

    # Construct serialized casefile and model object
    serialized_case = construct_case(data=case_data, mode=run_mode)

    # Construct and solve model
    model = construct_model(data=serialized_case)
    model = solve_model(model=model, algorithm=algorithm)

    # Compare solution with NEMDE solution or run model and return solution
    if solution_format == 'standard':
        return get_solution(model=model)

    elif solution_format == 'validation':
        return get_solution_comparison(model=model)

    else:
        message = "'solution_format' must be either 'standard' or 'validation'"
        raise CasefileOptionsError(message)
