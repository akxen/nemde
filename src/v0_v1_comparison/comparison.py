"""Compare slow (working) and fast (not working) model solutions"""

import os
import sys

import pandas as pd
import pyomo.environ as pyo

sys.path.append(os.path.join(os.path.dirname(__file__), os.path.pardir))

import model_v0.model
import model_v1.model


def run_m_1():
    """Run slow (working model)"""

    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to construct and run NEMDE approximate model
    nemde = model_v0.model.NEMDEModel(data_directory, output_directory)

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


def run_m_2():
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


def compare_objectives(m_1, m_2, n_1):
    """Check objective values for both models"""

    return {'m_1_objective': pyo.value(m_1.OBJECTIVE), 'm_2_objective': pyo.value(m_2.OBJECTIVE),
            'solution': n_1.data.get_period_solution_attribute('TotalObjective')}


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


def get_model_attributes(m_1, m_1_attribute, m_2, m_2_attribute):
    """Compare model attributes"""

    # Check if model indices are the same
    check_index = set(m_1.__getattribute__(m_1_attribute).keys()) == set(m_2.__getattribute__(m_2_attribute).keys())
    assert check_index, f'Parameter indices do not match: {m_1_attribute} {m_2_attribute}'

    # Combine values into single dictionary
    try:
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
    except AttributeError:
        out = {
            k:
                {
                    'm_1': v,
                    'm_2': m_2.__getattribute__(m_2_attribute)[k],
                    'difference': v - m_2.__getattribute__(m_2_attribute)[k],
                    'abs_difference': abs(v - m_2.__getattribute__(m_2_attribute)[k]),
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


def compare_fcas_trapeziums(m_1, m_2, n_1):
    """Compare FCAS trapeziums"""

    # FCAS trapeziums from first model (working model)
    fcas_1 = {
        k: n_1.fcas.get_scaled_fcas_trapezium(k[0], k[1])
        if k[1] in ['R5RE', 'L5RE'] else n_s.fcas.get_fcas_trapezium_offer(k[0], k[1])
        for k, _ in m_2.P_TRADER_FCAS_ENABLEMENT_MIN.items()
    }

    # FCAS trapeziums from second model
    fcas_2 = {
        k: {
            'enablement_min': m_2.P_TRADER_FCAS_ENABLEMENT_MIN[k],
            'low_breakpoint': m_2.P_TRADER_FCAS_LOW_BREAKPOINT[k],
            'high_breakpoint': m_2.P_TRADER_FCAS_HIGH_BREAKPOINT[k],
            'enablement_max': m_2.P_TRADER_FCAS_ENABLEMENT_MAX[k],
        }
        for k, v in m_2.P_TRADER_FCAS_ENABLEMENT_MIN.items()
    }

    # Difference between models
    difference = {
        k: {
            'enablement_min': abs(fcas_1[k]['enablement_min'] - fcas_2[k]['enablement_min']),
            'low_breakpoint': abs(fcas_1[k]['low_breakpoint'] - fcas_2[k]['low_breakpoint']),
            'high_breakpoint': abs(fcas_1[k]['high_breakpoint'] - fcas_2[k]['high_breakpoint']),
            'enablement_max': abs(fcas_1[k]['enablement_max'] - fcas_2[k]['enablement_max']),
        }
        for k, _ in fcas_2.items()
    }

    # Convert to DataFrame and identify offers for which trapeziums differ the most
    df = pd.DataFrame(difference).T.sum(axis=1).sort_values(ascending=False)

    return df


def compare_trader_solution(m_1, m_2, n_1):
    """Compare trader solutions"""

    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Solution
    solution = {k: {'solution': n_1.data.get_trader_solution_attribute(k[0], key_map[k[1]].replace('@', ''))}
                for k in m_2.S_TRADER_OFFERS}

    # Construct DataFrame
    df_solution = pd.DataFrame(solution).T
    model_output = get_model_attributes(m_1, 'V_TRADER_TOTAL_OFFER', m_2, 'V_TRADER_TOTAL_OFFER')

    # Combine model and observed values
    offers_solution = model_output.join(df_solution, how='left').sort_values(by='abs_difference', ascending=False)

    return offers_solution


def compare_interconnector_flow_solution(m_1, m_2, n_1):
    """Compare interconnector flow solutions"""

    # Combine into single dictionary
    out = {
        k: {
            'm_1': m_1.V_GC_INTERCONNECTOR[k].value,
            'm_2': m_2.V_GC_INTERCONNECTOR[k].value,
            'difference': m_1.V_GC_INTERCONNECTOR[k].value - m_2.V_GC_INTERCONNECTOR[k].value,
            'abs_difference': abs(m_1.V_GC_INTERCONNECTOR[k].value - m_2.V_GC_INTERCONNECTOR[k].value),
            'solution': n_1.data.get_interconnector_solution_attribute(k, 'Flow')
        }
        for k, v in m_1.V_GC_INTERCONNECTOR.items()
    }

    return pd.DataFrame(out).T


def compare_interconnector_loss_solution(m_1, m_2, n_1):
    """Compare interconnector loss solutions"""

    # Combine into single dictionary
    out = {
        k: {
            'm_1': m_1.V_LOSS[k].value,
            'm_2': m_2.V_LOSS[k].value,
            'difference': m_1.V_LOSS[k].value - m_2.V_LOSS[k].value,
            'abs_difference': abs(m_1.V_LOSS[k].value - m_2.V_LOSS[k].value),
            'solution': n_1.data.get_interconnector_solution_attribute(k, 'Losses')
        }
        for k, v in m_1.V_LOSS.items()
    }

    return pd.DataFrame(out).T


if __name__ == '__main__':
    # Slow and fast models
    m_s, s_s, n_s = run_m_1()
    m_f, s_f, n_f = run_m_2()

    # Check objective values
    objectives = compare_objectives(m_s, m_f, n_s)
    print(objectives)

    # Check sets and parameters
    # compare_sets(m_s, m_f)
    # compare_parameters(m_s, m_f)
    # c1 = compare_constraints(m_s, 'C_AS_PROFILE_1', m_f, 'C_AS_PROFILE_1')
    # c2 = compare_constraints(m_s, 'C_GENERIC_CONSTRAINT', m_f, 'C_GENERIC_CONSTRAINT')

    # Trader and interconnector solutions
    df_t = compare_trader_solution(m_s, m_f, n_s)
    df_i = compare_interconnector_flow_solution(m_s, m_f, n_s)
    df_l = compare_interconnector_loss_solution(m_s, m_f, n_s)
