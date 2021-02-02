import json
import time

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.execution import run_model
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

start = time.time()


case_id = '20201129139'
data = {
    'case_id': case_id,
    'run_mode': 'physical',
    'options': {
        'solution_format': 'validation'
    }
}

data_json = json.dumps(data)
solution = run_model(data_json)

objective = [i for i in solution['PeriodSolution'] if i['key'] == '@TotalObjective'][0]

# obj = float(base.get('NEMSPDCaseFile').get('NemSpdOutputs')
# .get('PeriodSolution').get('@TotalObjective'))

print('Objective', objective)
print('Abs. difference', abs(objective['model'] - objective['actual']))
print('Finished', time.time() - start)
# print(solution['summary'])
