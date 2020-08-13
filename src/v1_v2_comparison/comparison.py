"""Compare slow (working) and fast (not working) model solutions"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))

import model_v1.model

import model_v2.model
import model_v2.utils.loaders
import model_v2.utils.data


def run_slow_model():
    """Run slow (working model)"""

    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to construct and run NEMDE approximate model
    nemde = model_v1.model.NEMDEModel(data_directory, output_directory)

    # Load MMSDM data for given interval
    nemde.mmsdm_data.load_interval(2019, 10)

    # Object used to interrogate NEMDE solution
    analysis = model_v1.model.NEMDESolution(data_directory)
    analysis.data.load_interval(2019, 10, 10, 1)
    analysis.fcas.data.load_interval(2019, 10, 10, 1)

    # Construct model for given trading interval
    mod = nemde.construct_model(2019, 10, 10, 1)

    # Solve model
    mod, status = nemde.solve_model(mod)

    return mod, status


def run_fast_model():
    """Run fast model"""

    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # NEMDE model object
    nemde = model_v2.model.NEMDEModel()

    # Case data in json format
    case_data_json = model_v2.utils.loaders.load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Parse case data
    case_data = model_v2.utils.data.parse_case_data_json(case_data_json)

    # Construct model
    mod = nemde.construct_model(case_data)

    # Solve model
    mod, status = nemde.solve_model(mod)

    return mod, status


if __name__ == '__main__':
    # Slow and fast models
    # m_s, s_s = run_slow_model()
    m_f, s_f = run_fast_model()
    # pass
