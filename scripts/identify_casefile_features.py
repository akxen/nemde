"""
Identify casefiles that satisfy given conditions
"""

import os
import calendar
import itertools

import pandas as pd

import context
from nemde.io.casefile import load_base_case
from nemde.core.casefile import lookup
from setup_variables import setup_environment_variables


def check_intervention_status(casefile):
    """Check if intervention status is 'True'"""

    print("Identifying casefiles with intervention status = 'True'")

    case_id = lookup.get_case_attribute(
        data=casefile, attribute='@CaseID', func=str)

    intervention_status = lookup.get_case_attribute(
        data=casefile, attribute='@Intervention', func=str)

    if intervention_status == 'True':
        print(case_id, intervention_status)


def check_trader_current_mode_one(casefile):
    """Idenfity casefiles with at least one trader having @CurrentMode = 1"""

    # Get case ID
    case_id = lookup.get_case_attribute(data=casefile, attribute='@CaseID', func=str)

    # All traders
    traders = lookup.get_trader_index(data=casefile)

    for i in traders:
        try:
            current_mode = lookup.get_trader_collection_attribute(
                data=casefile, trader_id=i, attribute='@CurrentMode', func=str)
        except KeyError:
            continue

        if current_mode == '1':
            print(case_id, i)


def check_trader_current_mode_two(casefile):
    """Idenfity casefiles with at least one trader having @CurrentMode = 2"""

    # Get case ID
    case_id = lookup.get_case_attribute(data=casefile, attribute='@CaseID', func=str)

    # All traders
    traders = lookup.get_trader_index(data=casefile)

    for i in traders:
        try:
            current_mode = lookup.get_trader_collection_attribute(
                data=casefile, trader_id=i, attribute='@CurrentMode', func=str)
        except KeyError:
            continue

        if current_mode == '2':
            print(case_id, i)


def fast_start_unit_starts_up(casefile, intervention):
    """Check if a fast start unit starts up for a given dispatch interval"""

    # Get all traders
    traders = lookup.get_trader_index(data=casefile)

    # Flag indicating if at least one fast start unit starts up
    for i in traders:
        try:
            current_mode = lookup.get_trader_collection_attribute(
                data=casefile, trader_id=i, attribute='@CurrentMode', func=str)
        except KeyError:
            continue

        # Energy target
        energy_target = lookup.get_trader_solution_attribute(
            data=casefile, trader_id=i, attribute='@EnergyTarget',
            intervention=intervention, func=float)

        if (current_mode == '0') and (energy_target > 0.005):
            return True

    # No fast start units starting up identified
    return False


def identify_fast_start_unit_startup_casefiles(year, month):
    """
    Check if a fast start unit started up during a given interval. Model
    does not currently support multi-run approach required when modelling
    fast start unit startup intervals.
    """

    days_in_month = calendar.monthrange(year, month)[-1]

    out = []
    for index, (day, interval) in enumerate(itertools.product(range(1, days_in_month + 1), range(1, 289))):
        case_id = f'{year}{month:02}{day:02}{interval:03}'

        if index % 50 == 0:
            print(index, case_id)

        # Load casefile and extract intervention status
        casefile = load_base_case(case_id=case_id)

        entry = {
            'case_id': case_id,
            'intervention': 0,
            'startup_flag': fast_start_unit_starts_up(casefile=casefile, intervention='0')
        }

        out.append(entry)

        # Check if an intervention pricing period
        if casefile['NEMSPDCaseFile']['NemSpdInputs']['Case']['@Intervention'] == 'True':
            entry = {
                'case_id': case_id,
                'intervention': 1,
                'startup_flag': fast_start_unit_starts_up(casefile=casefile, intervention='1')
            }

            out.append(entry)

    # Convert to DataFrame and save as CSV
    path = os.path.join(os.path.dirname(__file__), os.path.pardir, 'casefiles',
                        'features', f'{year}{month:02}_startup.csv')

    pd.DataFrame(out).sort_values(
        by=['case_id', 'intervention']).to_csv(path, index=False)


def identify_casefiles(year, month, function):
    """Check intervention status"""

    for index, (day, interval) in enumerate(itertools.product(range(1, 31), range(1, 289))):
        case_id = f'{year}{month:02}{day:02}{interval:03}'

        # Load casefile and extract intervention status
        casefile = load_base_case(case_id=case_id)
        function(casefile)


if __name__ == '__main__':
    setup_environment_variables()

    # Identify casefiles with intervention status = True
    # identify_casefiles(year=2020, month=11, function=check_intervention_status)

    # Identify casefiles having at least one trader with CurrentMode = 1
    # identify_casefiles(year=2020, month=11, function=check_trader_current_mode_one)

    # Identify casefiles having at least one trader with CurrentMode = 2
    # identify_casefiles(year=2020, month=11, function=check_trader_current_mode_two)

    # Identify casefiles where fast start units startup
    identify_fast_start_unit_startup_casefiles(year=2020, month=11)
