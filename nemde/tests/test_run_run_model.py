"""Test that model runs correctly"""

import json
import logging

import context
from nemde.core.run.run_model import run_model
from nemde.io.casefile import load_base_case
logger = logging.getLogger(__name__)


def test_run_model():
    """Test model runs correctly given user input"""

    user_data_dict = {
        'case_id': '20201101001',
        'run_mode': 'physical'
    }

    # Run model
    user_data_json = json.dumps(user_data_dict)
    solution = run_model(user_data=user_data_json)

    # Extract total objective obtained from model
    model_objective = solution['PeriodSolution']['@TotalObjective']

    # Check NEMDE solution for the corresponding dispatch interval
    base_case = load_base_case(case_id=user_data_dict['case_id'])
    nemde_objective = float(base_case.get('NEMSPDCaseFile')
                            .get('NemSpdOutputs').get('PeriodSolution')
                            .get('@TotalObjective'))

    # Normalised difference between model and observed objectives
    relative_difference = (model_objective - nemde_objective) / nemde_objective

    assert abs(relative_difference) <= 1e-3
