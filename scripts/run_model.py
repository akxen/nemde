import os
import json
import time

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.execution import run_model
from setup_variables import setup_environment_variables


def load_custom_casefile(case_id):
    """Load custom case file"""

    casefiles_dir = os.path.join(
        os.path.dirname(__file__),
        os.path.pardir,
        'casefiles',
        'extracted')

    with open(os.path.join(casefiles_dir, case_id), 'r') as f:
        casefile = json.load(f)

    return casefile


def get_case_inputs(case_id):
    """Get case file data"""

    data = {
        'case_id': case_id,
        'options': {
            'solution_format': 'validation',
        }
    }

    return data


def get_custom_case_inputs(case_id):
    """Get case inputs from extracted JSON file"""

    casefile = load_custom_casefile(case_id=case_id)
    data = {
        'casefile': casefile,
    }

    return data


def run_case(data):
    """Run case"""

    start = time.time()
    solution = run_model(data)
    print('Finished', time.time() - start)
    print([abs(i['model'] - i['actual'])
           for i in solution['output']['PeriodSolution']
           if i['key'] == '@TotalObjective'])

    return solution


if __name__ == '__main__':
    setup_environment_variables('offline-host.env')

    case_id = '20210405178'
    data = get_case_inputs(case_id=case_id)
    solution = run_case(data=data)

    a = 10
