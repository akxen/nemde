"""Compare slow (working) and fast (not working) model solutions"""

import os
import sys

import pandas as pd
import pyomo.environ as pyo

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

    return mod, status, nemde


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

    return mod, status, nemde


def compare_objectives(m_1, m_2):
    """Check objective values for both models"""

    return {'m_1_objective': pyo.value(m_1.OBJECTIVE), 'm_2_objective': pyo.value(m_2.OBJECTIVE)}


def check_sets(m_1, m_1_attribute, m_2, m_2_attribute):
    """Check if sets in two models contain the same elements"""

    check = set(m_1.__getattribute__(m_1_attribute)) == set(m_2.__getattribute__(m_2_attribute))
    assert check, f'Sets do not match: {m_1, m_1_attribute, m_2, m_2_attribute}'
    print(f'sets: {m_1_attribute} {m_2_attribute} - sets match')


def compare_sets(m_1, m_2):
    """Compare sets between two models"""

    check_sets(m_1, 'S_REGIONS', m_2, 'S_REGIONS')
    check_sets(m_1, 'S_TRADERS', m_2, 'S_TRADERS')
    check_sets(m_1, 'S_TRADER_OFFERS', m_2, 'S_TRADER_OFFERS')
    check_sets(m_1, 'S_GENERIC_CONSTRAINTS', m_2, 'S_GENERIC_CONSTRAINTS')
    check_sets(m_1, 'S_GC_TRADER_VARS', m_2, 'S_GC_TRADER_VARS')
    check_sets(m_1, 'S_GC_INTERCONNECTOR_VARS', m_2, 'S_GC_INTERCONNECTOR_VARS')
    check_sets(m_1, 'S_GC_REGION_VARS', m_2, 'S_GC_REGION_VARS')
    check_sets(m_1, 'S_BANDS', m_2, 'S_BANDS')
    check_sets(m_1, 'S_MNSPS', m_2, 'S_MNSPS')
    check_sets(m_1, 'S_MNSP_OFFERS', m_2, 'S_MNSP_OFFERS')
    check_sets(m_1, 'S_INTERCONNECTORS', m_2, 'S_INTERCONNECTORS')

    # Missing
    # S_TRADERS_SEMI_DISPATCH, S_TRADER_FCAS_OFFERS, S_TRADER_ENERGY_OFFERS, S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
    # S_INTERCONNECTOR_LOSS_MODEL_INTERVALS

    # # Semi-dispatchable traders
    # m.S_TRADERS_SEMI_DISPATCH = pyo.Set(initialize=data['S_TRADERS_SEMI_DISPATCH'])
    #
    # # Trader FCAS offers
    # m.S_TRADER_FCAS_OFFERS = pyo.Set(initialize=data['S_TRADER_FCAS_OFFERS'])
    #
    # # Trader energy offers
    # m.S_TRADER_ENERGY_OFFERS = pyo.Set(initialize=data['S_TRADER_ENERGY_OFFERS'])

    # # Interconnector loss model breakpoints
    # m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS = pyo.Set(initialize=data['S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS'])
    #
    # # Interconnector loss model intervals
    # m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS = pyo.Set(initialize=data['S_INTERCONNECTOR_LOSS_MODEL_INTERVALS'])


def get_parameters(m_1, m_1_attribute, m_2, m_2_attribute):
    """Compare model attributes"""

    # Check if model indices are the same
    check_index = set(m_1.__getattribute__(m_1_attribute).keys()) == set(m_2.__getattribute__(m_2_attribute).keys())
    assert check_index, f'Parameter indices do not match: {m_1_attribute} {m_2_attribute}'

    # Combine values into single dictionary
    out = {
        k:
            {
                'm_1': v.value,
                'm_2': m_2.__getattribute__(m_2_attribute)[k].value,
                'difference': v.value - m_2.__getattribute__(m_2_attribute)[k].value,
                'abs_difference': abs(v.value - m_2.__getattribute__(m_2_attribute)[k].value),
            }
        for k, v in m_1.__getattribute__(m_1_attribute).items()
    }

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False)

    return df


def check_parameters(m_1, m_1_attribute, m_2, m_2_attribute):
    """Check parameters match between models"""

    # Check if model indices are the same
    check_index = set(m_1.__getattribute__(m_1_attribute).keys()) == set(m_2.__getattribute__(m_2_attribute).keys())
    assert check_index, f'Parameter indices do not match: {m_1_attribute} {m_2_attribute}'

    match = [v == m_2.__getattribute__(m_2_attribute)[k] for k, v in m_1.__getattribute__(m_1_attribute).items()]
    assert all(match), f'All parameters do not match: {m_1_attribute} {m_2_attribute}'
    print(f'parameters: {m_1_attribute} {m_2_attribute} - parameters match')


def compare_parameters(m_1, m_2):
    """Compare parameters between two models"""

    # Check price and quantity bands
    check_parameters(m_1, 'P_TRADER_PRICE_BAND', m_2, 'P_TRADER_PRICE_BAND')
    check_parameters(m_1, 'P_TRADER_QUANTITY_BAND', m_2, 'P_TRADER_QUANTITY_BAND')
    check_parameters(m_1, 'P_TRADER_INITIAL_MW', m_2, 'P_TRADER_INITIAL_MW')
    check_parameters(m_1, 'P_RHS', m_2, 'P_GC_RHS')


def compare_constraints(m_1, m_1_attribute, m_2, m_2_attribute):
    """Compare constraint sets"""

    # Check if model indices are the same
    check_index = set(m_1.__getattribute__(m_1_attribute).keys()) == set(m_2.__getattribute__(m_2_attribute).keys())
    assert check_index, 'Model indices do not match'

    # Combine values into single dictionary
    out = {
        k:
            {
                'm_1': pyo.value(v.body),
                'm_2': pyo.value(m_2.__getattribute__(m_2_attribute)[k].body),
                'difference': pyo.value(v.body) - pyo.value(m_2.__getattribute__(m_2_attribute)[k].body),
                'abs_difference': abs(pyo.value(v.body) - pyo.value(m_2.__getattribute__(m_2_attribute)[k].body)),
            }
        for k, v in m_1.__getattribute__(m_1_attribute).items()
    }

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False)

    return df


if __name__ == '__main__':
    # Slow and fast models
    m_s, s_s, n_s = run_slow_model()
    m_f, s_f, n_f = run_fast_model()

    # Check objective values
    objectives = compare_objectives(m_s, m_f)
    print(objectives)

    # Check sets and parameters
    # compare_sets(m_s, m_f)
    # compare_parameters(m_s, m_f)

    offers = get_parameters(m_s, 'V_TRADER_TOTAL_OFFER', m_f, 'V_TRADER_TOTAL_OFFER')

    set([k for k, v in m_s.C_FCAS_AVAILABILITY_RULE.items()]) == set(
        [k for k, v in m_f.C_FCAS_AVAILABILITY_RULE.items()])
    len(set([k for k, v in m_s.C_FCAS_AVAILABILITY_RULE.items()]))
    len(set([k for k, v in m_f.C_FCAS_AVAILABILITY_RULE.items()]))

    set([k for k, v in m_s.C_FCAS_AVAILABILITY_RULE.items()]).difference(
        set([k for k, v in m_f.C_FCAS_AVAILABILITY_RULE.items()]))

    set(k for k, v in m_s.C_AS_PROFILE_1.items()) == set(k for k, v in m_f.C_AS_PROFILE_1.items())

    c = compare_constraints(m_s, 'C_AS_PROFILE_1', m_f, 'C_AS_PROFILE_1')

    f_fcas = {
        k: {
            'enablement_min': m_f.P_TRADER_FCAS_ENABLEMENT_MIN[k],
            'low_breakpoint': m_f.P_TRADER_FCAS_LOW_BREAKPOINT[k],
            'high_breakpoint': m_f.P_TRADER_FCAS_HIGH_BREAKPOINT[k],
            'enablement_max': m_f.P_TRADER_FCAS_ENABLEMENT_MAX[k],
        }
        for k, v in m_f.P_TRADER_FCAS_ENABLEMENT_MIN.items()
    }

    s_fcas = {
        k: n_s.fcas.get_scaled_fcas_trapezium(k[0], k[1])
        if k[1] in ['R5RE', 'L5RE'] else n_s.fcas.get_fcas_trapezium_offer(k[0], k[1])
        for k, _ in m_f.P_TRADER_FCAS_ENABLEMENT_MIN.items()
    }

    d_fcas = {
        k: {
            'enablement_min': abs(f_fcas[k]['enablement_min'] - s_fcas[k]['enablement_min']),
            'low_breakpoint': abs(f_fcas[k]['low_breakpoint'] - s_fcas[k]['low_breakpoint']),
            'high_breakpoint': abs(f_fcas[k]['high_breakpoint'] - s_fcas[k]['high_breakpoint']),
            'enablement_max': abs(f_fcas[k]['enablement_max'] - s_fcas[k]['enablement_max']),
        }
        for k, _ in f_fcas.items()
    }

    df_d_fcas = pd.DataFrame(d_fcas).T.sum(axis=1).sort_values(ascending=False)
