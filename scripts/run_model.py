import json
import time

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.execution import run_model
from setup_variables import setup_environment_variables
setup_environment_variables('offline-host.env')

start = time.time()

case_id = '20201104193'
data = {
    'case_id': case_id,
    'run_mode': 'physical',
    'options': {
        'solution_format': 'validation',
        'algorithm': 'default'
    }
}

data_json = json.dumps(data)
solution = run_model(data_json)

print('Finished', time.time() - start)
print([abs(i['model'] - i['actual']) for i in solution['PeriodSolution'] if i['key'] == '@TotalObjective'])
