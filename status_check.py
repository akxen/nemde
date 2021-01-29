"""Check intervention status"""

import itertools

from nemde.io.casefile import load_base_case
from nemde.core.casefile import lookup
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

for index, (day, interval) in enumerate(itertools.product(range(1, 31), range(1, 289))):
    case_id = f'202011{day:02}{interval:03}'
    
    # print(index, case_id)
    if index % 10 == 0:
        print(index, case_id)

    case = load_base_case(case_id=case_id)
    intervention_status = lookup.get_case_attribute(
        data=case, attribute='@Intervention', func=str)

    if intervention_status == 'True':
        print(case_id, intervention_status)
