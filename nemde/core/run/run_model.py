"""
Run model with user specified inputs
"""

import json

from nemde.io.casefile import load_base_case
# from nemde.core.casefile.updater import update_casefile
from nemde.core.model.serializers import casefile_serializer
# from nemde.core.model.serializers import solution_serializer
# from nemde.core.model.preprocessing import preprocess_serialized_casefile
# from nemde.core.model.constructor import construct_model
# from nemde.core.model.algorithms import solve_model


def clean_user_input(user_data):
    """Parse user data and set defaults if option not specified"""

    # Load user data as json
    data = json.loads(user_data)

    # Extract options
    options = data.get('options', {})

    # TODO check parameters and raise exceptions if values not allowed

    # TODO check if user case data is in JSON format - if not convert to JSON

    # Place cleaned data
    cleaned_data = {
        'case_id': data.get('case_id', None),
        'case_data': data.get('case_data', {}),
        'options': {
            'intervention': options.get('intervention', '1'),
            'algorithm': options.get('algorithm', 'dispatch_only'),
            'solution_format': options.get('solution_format', 'standard')
        }
    }

    return cleaned_data


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
    algorithm = data.get('options').get('algorithm')
    intervention = data.get('options').get('intervention')
    solution_format = data.get('options').get('solution_format')

    # Get data corresponding to casefile
    if case_id is None:
        base_case = {}
    else:
        base_case = load_base_case(case_id=case_id)

    # # Update base case with case data specified by user
    # updated_case = update_casefile(base=base_case, update=user_case_data)

    # # Construct serialized casefile and model object
    # serialized_case = casefile_serializer.construct_case(data=updated_case)
    # print(serialized_case)

    # # Apply preprocessing to serialized casefile
    # preprocessed_case = preprocess_serialized_casefile(data=serialized_case)

    # # Construct model
    # model = construct_model(data=preprocessed_case)

    # # Solve model and extract solution
    # model = solve_model(model=model, intervention=intervention, algorithm=algorithm)
    # solution = solution_serializer(model=model, format=solution_format)

    # # Convert solution dict to json
    # solution_json = json.dumps(solution)

    # return solution_json
