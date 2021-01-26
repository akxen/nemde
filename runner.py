import json

from nemde.core.run.run_model import run_model
from nemde.io.casefile import load_base_case
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

data = {
    'case_id': '20201101001',
    'run_mode': 'pricing',
}

data_json = json.dumps(data)
solution = run_model(data_json)
print(solution['PeriodSolution']['@TotalObjective'])

base = load_base_case(case_id='20201101001')
obj = float(base.get('NEMSPDCaseFile').get('NemSpdOutputs')
            .get('PeriodSolution').get('@TotalObjective'))
print(obj)
