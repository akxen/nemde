"""Check intervention status"""

import itertools

from nemde.io.casefile import load_base_case
from nemde.core.casefile import lookup
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables(online=False)


def check_intervention_status(year, month):
    """Check intervention status"""

    for index, (day, interval) in enumerate(itertools.product(range(1, 31), range(1, 289))):
        case_id = f'{year}{month:02}{day:02}{interval:03}'

        if index % 10 == 0:
            print(index, case_id)

        # Load casefile and extract intervention status
        case = load_base_case(case_id=case_id)
        intervention_status = lookup.get_case_attribute(
            data=case, attribute='@Intervention', func=str)

        if intervention_status == 'True':
            print(case_id, intervention_status)


if __name__ == '__main__':
    # Check intervention status for a given year and month
    check_intervention_status(year=2020, month=11)
