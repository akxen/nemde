"""
Load casefile as XML, convert to JSON and save for inspection
"""

import json

import context
from nemde.io.casefile import load_base_case
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def save_casefile_as_json(case_id):
    """Load casefile as XML, convert to JSON and save"""

    base = load_base_case(case_id=case_id)
    with open(f'casefiles/{case_id}.json', 'w') as f:
        json.dump(base, f)


if __name__ == '__main__':
    save_casefile_as_json(case_id='20201128127')
