"""
Run model with user specified inputs
"""

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
    data = user_data

    # Extract options
    options = data.get('options', {})

    # Cleaned options
    cleaned = {
        'casefile': data.get('casefile', None),
        'case_id': data.get('case_id', None),
        'patches': data.get('patches', []),
        'options': {
            'run_mode': options.get('run_mode', 'target'),
            'algorithm': options.get('algorithm', 'default'),
            'solution_format': options.get('solution_format', 'standard'),
            'return_casefile': options.get('return_casefile', False),
            'solution_elements': options.get('solution_elements', []),
            'label': options.get('label', None),
        }
    }

    has_casefile = cleaned['casefile'] is not None
    has_case_id = cleaned['case_id'] is not None
    has_patches = len(cleaned['patches']) > 0

    if has_casefile and (has_case_id or has_patches):
        msg = ("If 'casefile' is specified then 'case_id' and 'patches'",
               "should be omitted")
        raise CasefileOptionsError(msg)

    if cleaned.get('options').get('run_mode') not in ['target', 'pricing']:
        msg = "'run_mode' must be set to 'target' or 'pricing'"
        raise CasefileOptionsError(msg)

    if cleaned.get('options').get('solution_format') not in ['standard', 'validation']:
        msg = "'solution_format' must be either 'standard' or 'validation'"
        raise CasefileOptionsError(msg)

    if not isinstance(cleaned.get('options').get('return_casefile'), bool):
        msg = f"'return_casefile' must be either True or False: {cleaned.get('options').get('return_casefile')}"
        raise CasefileOptionsError(msg)

    if not isinstance(cleaned.get('options').get('solution_elements'), list):
        msg = "'solution_elements' must be a list"
        raise CasefileOptionsError(msg)

    label = cleaned.get('options').get('label')
    if (label is not None) and not isinstance(label, str):
        msg = "'label' must be string"
        raise CasefileOptionsError(msg)

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
    casefile = data.get('casefile')
    patches = data.get('patches')
    run_mode = data.get('options').get('run_mode')
    algorithm = data.get('options').get('algorithm')
    solution_format = data.get('options').get('solution_format')
    return_casefile = data.get('options').get('return_casefile')

    # Use user specified casefile
    if case_id is None:
        case_data = casefile

    # Use base casefile and apply user patches
    else:
        base_case = load_base_case(case_id=case_id)
        case_data = patch_casefile(casefile=base_case, updates=patches)

    # Construct serialized casefile and model object
    serialized_case = construct_case(data=case_data, mode=run_mode)

    # Construct and solve model
    model = construct_model(data=serialized_case)
    model, solver_info = solve_model(model=model, algorithm=algorithm)

    # Compare solution with NEMDE solution or run model and return solution
    if solution_format == 'standard':
        solution = get_solution(model=model)

    elif solution_format == 'validation':
        solution = get_solution_comparison(model=model)

    else:
        msg = "'solution_format' must be either 'standard' or 'validation'"
        raise CasefileOptionsError(msg)

    if return_casefile:
        output = {
            'input': case_data,
            'output': solution,
            # 'solver': solver_info,
        }
        return output

    else:
        output = {
            'output': solution,
            # 'solver': solver_info,
        }

        return output
