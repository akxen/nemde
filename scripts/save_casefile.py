"""
Load casefile as XML, convert to JSON and save for inspection
"""

import os
import json

import context
from nemde.io.casefile import load_base_case_from_archive
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def save_casefile_as_json(case_id, data_dir):
    """Load casefile as XML, convert to JSON and save"""

    base = load_base_case_from_archive(case_id=case_id, data_dir=data_dir)
    with open(f'casefiles/extracted/{case_id}.json', 'w') as f:
        json.dump(base, f)


if __name__ == '__main__':
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, 'casefiles', 'zipped')
    save_casefile_as_json(case_id='20201104193', data_dir=data_directory)
