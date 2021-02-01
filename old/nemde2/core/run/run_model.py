"""Supply model with user inputs and run mode options. Return solution"""

import json

from nemde.io.database.mysql import load_dispatch_interval_json
from nemde.core.casefile.update import update_casefile_json
from nemde.core.casefile.serializers.json import casefile_serializer
from nemde.core.model.model import construct_model
from nemde.core.solution.algorithms import solve_model
from nemde.core.solution.serializers import get_solution


def run_model(user_data):
    """
    Run model with user options

    Parameters
    ----------
    user_data : dict
        Dictionary containing user supplied information

        user_data = {
            "case_id": "20210101001",
            "case_data": {},  # optional
            "options": {
                "intervention_status": 1, # 0 (optional default=1)
                "algorithm": "dispatch_only",  # "prices" (default="dispatch_only")
                "solution_format": "standard", # "validation" (default="standard")
        }
    """

    # TODO: check options and parameters - raise exceptions if conditions fail
    case_id = user_data.get('case_id')
    user_case_data = user_data.get('case_data', {})

    # Extract options and set defaults
    options = user_data.get('options', {})
    intervention_status = options.get('intervention_status', '1')
    algorithm = options.get('algorithm', 'dispatch_only')
    solution_format = options.get('solution_format', 'standard')

    # Get data corresponding to casefile and update with user specified data
    base_case = load_dispatch_interval_json(case_id)
    case = update_casefile_json(base_case=base_case, update=user_case_data)

    # Construct serialized casefile and model object
    serialized_case = casefile_serializer.construct_case(data=case)
    model = construct_model(serialized_case)

    # Solve model and extract solution
    model = solve_model(model, intervention_status, algorithm)
    solution = get_solution(model, solution_format)

    # Convert to solution dict to json
    solution_json = json.dumps(solution)

    return solution_json
