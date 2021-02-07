"""
Validate inferrred NEMDE calculations using casefile inputs and outputs
"""

import os
import numbers
import calendar

import pytest
import numpy as np

import context
from nemde.io.casefile import load_base_case
from nemde.analysis import calculations
from nemde.config.setup_variables import setup_environment_variables

setup_environment_variables()


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


# Get sample of casefile IDs for a given year and month
casefile_ids = get_casefile_ids(year=2020, month=11, n=1)


@pytest.fixture(scope='module', params=casefile_ids)
def casefile(request):
    return load_base_case(request.param)


@pytest.fixture(scope='module', params=['SA1', 'VIC1', 'TAS1', 'VIC1', 'NSW1', 'QLD1'])
def region_id(request):
    return request.param


def test_get_region_initial_interconnector_loss(casefile, region_id):
    initial_loss = calculations.get_region_initial_interconnector_loss(
        data=casefile, region_id=region_id)
    assert isinstance(initial_loss, numbers.Number)


def test_get_region_initial_mnsp_loss_estimate(casefile, region_id):
    initial_loss = calculations.get_region_initial_mnsp_loss_estimate(
        data=casefile, region_id=region_id)
    assert isinstance(initial_loss, numbers.Number)


def test_get_region_initial_scheduled_load(casefile, region_id):
    initial_load = calculations.get_region_initial_scheduled_load(
        data=casefile, region_id=region_id)

    assert isinstance(initial_load, numbers.Number)


def test_get_region_solution_interconnector_loss(casefile, region_id):
    solution_loss = calculations.get_region_solution_interconnector_loss(
        data=casefile, region_id=region_id, intervention='0')

    assert isinstance(solution_loss, numbers.Number)


def test_get_region_solution_mnsp_loss_estimate(casefile, region_id):
    solution_loss = calculations.get_region_solution_mnsp_loss_estimate(
        data=casefile, region_id=region_id, intervention='0')

    assert isinstance(solution_loss, numbers.Number)


def test_get_region_solution_net_interconnector_export(casefile, region_id):
    net_export = calculations.get_region_solution_net_interconnector_export(
        data=casefile, region_id=region_id, intervention='0')

    assert isinstance(net_export, numbers.Number)


def test_get_region_solution_scheduled_load(casefile, region_id):
    scheduled_load = calculations.get_region_solution_scheduled_load(
        data=casefile, region_id=region_id, intervention='0')

    assert isinstance(scheduled_load, numbers.Number)


def test_check_aggregate_cleared_demand(casefile):
    comparison = calculations.check_aggregate_cleared_demand(
        data=casefile, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_aggregate_fixed_demand(casefile):
    comparison = calculations.check_aggregate_fixed_demand(
        data=casefile, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_region_cleared_demand(casefile, region_id):
    comparison = calculations.check_region_cleared_demand(
        data=casefile, region_id=region_id, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_region_fixed_demand(casefile, region_id):
    comparison = calculations.check_region_fixed_demand(
        data=casefile, region_id=region_id, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_region_net_export(casefile, region_id):
    comparison = calculations.check_region_net_export(
        data=casefile, region_id=region_id, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_region_power_balance(casefile, region_id):
    comparison = calculations.check_region_power_balance(
        data=casefile, region_id=region_id, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_region_dispatched_generation(casefile, region_id):
    comparison = calculations.check_region_dispatched_generation(
        data=casefile, region_id=region_id, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_region_dispatched_load(casefile, region_id):
    comparison = calculations.check_region_dispatched_load(
        data=casefile, region_id=region_id, intervention='0')

    assert comparison['abs_difference'] < 0.1


def test_check_generic_constraint_ids_are_unique(casefile):
    """Check if generic constraint IDs are unique"""

    # Generic constraints
    constraints = (casefile.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    # All constraint IDs
    constraint_ids = [i['@ConstraintID'] for i in constraints]

    assert len(constraint_ids) == len(set(constraint_ids))


@pytest.mark.skip(reason='Dynamic RHS will cause inputs to differ from solution RHS')
def test_check_generic_constraint_rhs_calculation(casefile):
    """Check NEMDE input constraint RHS matches NEMDE solution RHS"""

    constraints = (casefile.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    for i in constraints:
        comparison = calculations.check_generic_constraint_rhs_calculation(
            data=casefile, constraint_id=i['@ConstraintID'], intervention='0')

        assert comparison['abs_difference'] < 0.1
