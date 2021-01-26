import json

from nemde.core.run.run_model import run_model
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()

data = {'case_id': '20201101001'}
data_json = json.dumps(data)
solution = run_model(data_json)
print(solution)
