"""
Identify casefiles that satisfy given conditions
"""

import itertools

import context
from nemde.io.casefile import load_base_case
from nemde.core.casefile import lookup
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables(online=False)


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


def identify_casefiles(year, month, function):
    """Check intervention status"""

    for index, (day, interval) in enumerate(itertools.product(range(1, 31), range(1, 289))):
        case_id = f'{year}{month:02}{day:02}{interval:03}'

        if index % 10 == 0:
            print(index, case_id)

        # Load casefile and extract intervention status
        casefile = load_base_case(case_id=case_id)
        function(casefile)


if __name__ == '__main__':
    # Identify casefiles with intervention status = True
    # identify_casefiles(year=2020, month=11, function=check_intervention_status)

    # Identify casefiles having at least one trader with CurrentMode = 1
    identify_casefiles(year=2020, month=11, function=check_trader_current_mode_one)
