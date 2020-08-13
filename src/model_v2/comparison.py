"""Compare slow (working) and fast (not working) model solutions"""

import os
import sys
import json
sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))

import model

sys.path.pop()

import model2
from utils.data import parse_case_data_json
from utils.loaders import load_dispatch_interval_json


def run_slow_model():
    """Run slow (working model)"""

    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to construct and run NEMDE approximate model
    nemde = model.NEMDEModel(data_directory, output_directory)

    # Load MMSDM data for given interval
    nemde.mmsdm_data.load_interval(2019, 10)

    # Object used to interrogate NEMDE solution
    analysis = model.NEMDESolution(data_directory)
    analysis.data.load_interval(2019, 10, 10, 1)
    analysis.fcas.data.load_interval(2019, 10, 10, 1)

    # Construct model for given trading interval
    model_s = nemde.construct_model(2019, 10, 10, 1)

    # Solve model
    model_s, status_s = nemde.solve_model(model_s)

    return model_s, status_s


if __name__ == '__main__':
    # Slow and fast models
    # m_s, s_s = run_slow_model()

    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # NEMDE model object
    nemde = model2.NEMDEModel()

    # Case data in json format
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # # Drop keys
    # for k in ['ConstraintScadaDataCollection', 'GenericEquationCollection']:
    #     cdata['NEMSPDCaseFile']['NemSpdInputs'].pop(k)
    # with open('example.json', 'w') as f:
    #     json.dump(cdata, f)

    case_data = parse_case_data_json(case_data_json)

    # Construct model
    nemde_model = nemde.construct_model(case_data)

    # Solve model
    nemde_model, status = nemde.solve_model(nemde_model)
