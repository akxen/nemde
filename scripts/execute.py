import json
import time

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.execution import run_model
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

start = time.time()

data = {
    'case_id': '20201110153',
    'run_mode': 'physical',
    'options': {
        'solution_format': 'validation',
        'algorithm': 'dispatch_only'
    }
}

data_json = json.dumps(data)
solution = run_model(data_json)

# print(solution['PeriodSolution']['@TotalObjective'])

# base = load_base_case(case_id='20201101001')
# obj = float(base.get('NEMSPDCaseFile').get('NemSpdOutputs')
#             .get('PeriodSolution').get('@TotalObjective'))
# print(obj)
print('Finished', time.time() - start)
# print(solution['RegionSolution'])
print([abs(i['model'] - i['actual']) for i in solution['PeriodSolution'] if i['key'] == '@TotalObjective'])
