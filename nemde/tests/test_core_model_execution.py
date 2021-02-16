"""Test that model runs correctly"""

import os
import uuid
import zlib
import json
import time
import logging
import calendar

import pytest
import numpy as np

import context
from nemde.io.database import mysql
from nemde.core.model.execution import run_model
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

logger = logging.getLogger(__name__)


def get_casefile_id_sample(year, month, n):
    """
    Get random sample of casefile IDs

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


def get_selected_casefile_ids():
    """Run tests for a given set of casefiles"""

    # # Cases where at least one trader has current mode = 1
    # case_ids = [
    #     '20201101017',
    #     '20201101126',
    #     '20201101127',
    #     '20201101134',
    #     '20201101135',
    #     '20201101161',
    #     '20201101164',
    #     '20201101165',
    #     '20201101169',
    # ]

    # # Cases where at least one trader has current mode = 2
    # case_ids = [
    #     '20201101076',
    #     '20201101136',
    #     '20201101159',
    #     '20201101160',
    #     '20201101160',
    #     '20201101161',
    #     '20201101165',
    #     '20201101166',
    #     '20201101167',
    #     '20201101171',
    #     '20201101172',
    #     '20201101173',
    # ]

    # # Cases where pass criterion should fail
    # case_ids = ['20201117113']

    # # Cases where fast start generator starts up
    # case_ids = [
    #     '20201117111',
    #     '20201127043',
    #     '20201121156',
    #     '20201116149',
    #     '20201106112',
    #     '20201118096',
    #     '20201118132',
    #     '20201130139',
    #     '20201105150',
    #     '20201129141',
    #     '20201125069',
    #     '20201127157',
    #     '20201104148',
    #     '20201130169',
    #     '20201113133',
    #     '20201121157',
    #     '20201122151',
    #     '20201124151',
    #     '20201123151',
    #     '20201129139',
    #     '20201111151',
    #     '20201103117',
    #     '20201119061',
    #     '20201119157',
    #     '20201119127',
    #     '20201130217',
    #     '20201123169',
    #     '20201129176',
    #     '20201114073',
    #     '20201128140',
    #     '20201119199',
    #     '20201115073',
    #     '20201122247',
    #     '20201101049',
    #     '20201113114',
    #     '20201115092',
    #     '20201111050'
    # ]

    # Cases with discrepancy
    case_ids = [
        '20201129176',
    ]

    return case_ids


def record_new_test_run(schema, case_ids):
    """Initialise and record a new run"""

    entry = {
        'group_id': uuid.uuid4().hex,
        'parameters': json.dumps({'case_ids': case_ids})
    }
    mysql.post_entry(schema=schema, table='test_run_info', entry=entry)

    return entry


def get_most_recent_test_run_info(schema):
    """
    Get most recent run info. Includes case IDs for which tests should be
    undertaken. Note that each time pytest starts a new testrun_uid is created.
    There may be instances where a test is interrupted and needs to resume
    midway. The 'parameters' field within the 'run_info' table contains the
    the case IDs for a given test run. All case IDs specified in order to
    complete the run. Therefore if a test run is interrupted several
    testrun_uids may be associated with a given 'group' run, which are
    identified by a 'group_id'.
    """

    sql = f"SELECT * FROM {schema}.test_run_info ORDER BY row_id DESC LIMIT 1"
    results = mysql.run_query(sql)

    if results:
        return results[0]
    else:
        return None


def get_test_run_info(schema, group_id):
    """Get run info"""

    sql = f"SELECT * FROM {schema}.test_run_info WHERE group_id='{group_id}'"
    results = mysql.run_query(sql)

    if results:
        return results[0]
    else:
        return None


def get_remaining_casefile_ids(schema, group_id):
    """Get remaining casefile IDs to test for a given test run"""

    # Latest goup info
    info = get_test_run_info(schema=schema, group_id=group_id)
    group_id = info['group_id']
    parameters = json.loads(info['parameters'])

    # Complete casefile IDs
    sql = f"SELECT case_id FROM {schema}.results WHERE group_id='{group_id}'"
    results = mysql.run_query(sql)
    completed = [i['case_id'] for i in results]

    # Remaining casefile IDs for which tests must be run
    remaining = list(set(parameters['case_ids']) - set(completed))
    remaining.sort()

    return remaining


@pytest.fixture
def prepare_new_run():
    """Prepare run"""
    case_ids = get_casefile_id_sample(year=2020, month=11, n=10000)
    record_new_test_run(schema=os.getenv('MYSQL_SCHEMA'), case_ids=case_ids)


@pytest.mark.prepare_new_test_run
def test_prepare(prepare_new_run):
    """Prepare test run"""
    assert True


def get_casefile_ids():
    """
    Get casefile IDs for test run. Will attempt to finish remaining
    cases for the latest test run.
    """

    schema = os.getenv('MYSQL_SCHEMA')

    info = get_most_recent_test_run_info(schema=schema)

    # If there are no test run records return an empty list
    if info is None:
        return []
    else:
        case_ids = get_remaining_casefile_ids(schema=schema, group_id=info['group_id'])
        return case_ids


# @pytest.fixture(scope='module', params=['20201101001', '20201101002'])
@pytest.fixture(scope='module', params=get_casefile_ids())
def case_id(request):
    return request.param


@pytest.fixture(scope='module')
def group_id():
    """Get test group ID"""

    info = get_most_recent_test_run_info(schema=os.getenv('MYSQL_SCHEMA'))

    return info['group_id']


@pytest.mark.validate
def test_validate_model(case_id, testrun_uid, group_id):
    """Run model for a sample of case IDs"""

    user_data = {
        'case_id': case_id,
        'run_mode': 'physical',
        'options': {
            'algorithm': 'default',
            'solution_format': 'validation'
        }
    }

    # Run model and return solution
    user_data_json = json.dumps(user_data)
    solution = run_model(user_data=user_data_json)

    # Compress results before saving
    results = zlib.compress(json.dumps(solution).encode('utf-8'))

    # Entry to post to database
    entry = {
        'run_id': testrun_uid,
        'group_id': group_id,
        'run_time': int(time.time()),
        'case_id': user_data['case_id'],
        'results': results
    }

    # Post entry to database
    mysql.post_entry(schema=os.environ['MYSQL_SCHEMA'], table='results', entry=entry)

    # Compute relative difference
    objective = [i for i in solution['PeriodSolution']
                 if i['key'] == '@TotalObjective'][0]
    absolute_difference = abs(objective['model'] - objective['actual'])
    relative_difference = absolute_difference / abs(objective['actual'])

    assert relative_difference <= 0.001
