import json
import time

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.execution import run_model
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

start = time.time()

data = {
    'case_id': '20201121156',
    'run_mode': 'physical',
    'options': {
        'solution_format': 'validation',
        'algorithm': 'fast_start_units'
    }
}

data_json = json.dumps(data)
solution = run_model(data_json)

# print(solution['PeriodSolution']['@TotalObjective'])

# case_id = '20201121156'
# base = load_base_case(case_id=case_id)
# with open(f'casefiles/{case_id}.json', 'w') as f:
    # json.dump(base, f)
# obj = float(base.get('NEMSPDCaseFile').get('NemSpdOutputs')
#             .get('PeriodSolution').get('@TotalObjective'))
# print(obj)
print('Finished', time.time() - start)
# print(solution['RegionSolution'])
print([abs(i['model'] - i['actual']) for i in solution['PeriodSolution'] if i['key'] == '@TotalObjective'])
