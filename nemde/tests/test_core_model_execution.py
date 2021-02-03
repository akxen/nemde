"""Test that model runs correctly"""

import os
import json
import time
import logging
import calendar

import pytest
import numpy as np

import context
from nemde.core.model.execution import run_model
from nemde.io.database import mysql
from nemde.io.casefile import load_base_case
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables(online=False)

logger = logging.getLogger(__name__)


def get_casefile_ids(year, month, n):
    """
    Get casefile IDs

    Parameters
    ----------
    year : int
        Sample year

    month : int
        Sample month

    n : int
        Number of casefiles to return

    Returns
    -------
    Shuffled list of casefile IDs
    """

    # Get days in specified month
    _, days_in_month = calendar.monthrange(year, month)

    # Seed random number generator for reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [f'{year}{month:02}{i:02}{j:03}'
                  for i in range(1, days_in_month + 1) for j in range(1, 289)]

    # Shuffle list to randomise sample (should be reproducible though because seed is set)
    np.random.shuffle(population)

    return population[:n]


@pytest.fixture(scope='module', params=get_casefile_ids(year=2020, month=11, n=20))
def case_id(request):
    return request.param


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


def test_run_model_validation(testrun_uid, case_id):
    """Run model for a sample of case IDs"""

    user_data = {
        'case_id': case_id,
        'run_mode': 'physical',
        'options': {
            'solution_format': 'validation'
        }
    }

    # Run model and return solution
    user_data_json = json.dumps(user_data)
    solution = run_model(user_data=user_data_json)

    # Entry to post to database
    entry = {
        'run_id': testrun_uid,
        'run_time': int(time.time()),
        'case_id': user_data['case_id'],
        'results': json.dumps(solution)
    }

    # Post entry to database
    mysql.post_entry(schema=os.environ['MYSQL_SCHEMA'], table='results', entry=entry)

    # Compute relative difference
    objective = [i for i in solution['PeriodSolution'] if i['key'] == '@TotalObjective'][0]
    absolute_difference = abs(objective['model'] - objective['actual'])
    relative_difference = absolute_difference / abs(objective['actual'])

    assert relative_difference <= 0.001
