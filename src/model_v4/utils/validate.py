"""Functions used to validate model outputs"""

import os

import pandas as pd

import lookup
import solution


def check_region_fixed_demand(data, m, region_id, intervention):
    """Check fixed demand calculation"""

    # Container for output
    calculated = m.E_REGION_FIXED_DEMAND[region_id].expr()
    observed = lookup.get_region_solution_attribute(data, region_id, '@FixedDemand', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_net_export(data, m, region_id, intervention):
    """Check net export calculation"""

    # Container for output
    calculated = m.E_REGION_NET_EXPORT[region_id].expr()
    observed = lookup.get_region_solution_attribute(data, region_id, '@NetExport', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_dispatched_generation(data, m, region_id, intervention):
    """Check region dispatched generation"""

    # Container for output
    calculated = m.E_REGION_DISPATCHED_GENERATION[region_id].expr()
    observed = lookup.get_region_solution_attribute(data, region_id, '@DispatchedGeneration', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_dispatched_load(data, m, region_id, intervention):
    """Check region dispatched load"""

    # Container for output
    calculated = m.E_REGION_DISPATCHED_LOAD[region_id].expr()
    observed = lookup.get_region_solution_attribute(data, region_id, '@DispatchedLoad', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_interconnector_flow(data, m, interconnector_id, intervention):
    """Check interconnector flow calculation"""

    # Container for output
    calculated = m.V_GC_INTERCONNECTOR[interconnector_id].value
    observed = lookup.get_interconnector_solution_attribute(data, interconnector_id, '@Flow', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'interconnector_id': interconnector_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_interconnector_loss(data, m, interconnector_id, intervention):
    """Check interconnector loss calculation"""

    # Container for output
    calculated = m.V_LOSS[interconnector_id].value
    observed = lookup.get_interconnector_solution_attribute(data, interconnector_id, '@Losses', float,
                                                                  intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'interconnector_id': interconnector_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_trader_output(data, m, trader_id, trade_type, intervention):
    """Check trader output"""

    # Calculated and observed values
    calculated = m.V_TRADER_TOTAL_OFFER[trader_id, trade_type].value

    # Map between NEMDE output keys and keys used in solution dictionary
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Observed dispatch
    observed = lookup.get_trader_solution_attribute(data, trader_id, key_map[trade_type], float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'trader_id': trader_id,
        'trade_type': trade_type,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_price(data, m, region_id, intervention):
    """Check region energy price (exclude FCAS for now)"""

    # Extract energy price - use default value of -9999 if none available
    try:
        calculated = m.dual[m.C_POWER_BALANCE[region_id]]
    except KeyError:
        calculated = -9999

    # Observed energy price
    observed = lookup.get_region_solution_attribute(data, region_id, '@EnergyPrice', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_objective_value(data, m, intervention):
    """Check objective value calculation"""

    # Container for output
    calculated = m.OBJECTIVE.expr()
    observed = lookup.get_period_solution_attribute(data, '@TotalObjective', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'intervention_flag': intervention,
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_fast_start_error_condition(data, intervention):
    """Check if fast start unit is in CurrentMode=0 and has EnergyTarget > 0"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Mode 0 unit committed - initialise to False
    mode_0_committed = False

    for i in traders:
        trader_id = i['@TraderID']
        trade_type = '@EnergyTarget'
        energy_target = lookup.get_trader_solution_attribute(data, trader_id, trade_type, float, intervention)
        fast_start_threshold = lookup.get_case_attribute(data, '@FastStartThreshold', float)
        if (i.get('@CurrentMode') == '0') and (energy_target > fast_start_threshold):
            mode_0_committed = True

    return mode_0_committed


def check_mnsp_flow_inverts_condition(data, intervention):
    """Check if MNSP flow direction switches over dispatch interval"""

    # Flow switches - initialise to False
    mnsp_flow_switches = False

    for i in lookup.get_mnsp_index(data):
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)
        target_flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float, intervention)

        if ((initial_mw < 0) and (target_flow > 0)) or ((initial_mw > 0) and (target_flow < 0)):
            mnsp_flow_switches = True

    return mnsp_flow_switches


def check_price_tied_condition(data, solution, intervention, trade_type):
    """Price tied units may cause dispatch outcomes to vary from NEMDE solution"""

    # Get trader solution
    _, df = analysis.check_trader_solution(data, solution, intervention)

    # Units with a dispatch discrepancy
    try:
        units = df.loc[df.loc[:, 'abs_difference'] > 0.001, :].loc[(slice(None), trade_type), :]
    except KeyError:
        return 0, 0

    # Unique dispatch band prices
    unique_prices = units.loc[:, 'model_current_price'].unique()

    return units.shape[0], len(unique_prices)


def check_known_unhandled_cases(data, solution, intervention):
    """Run diagnostics to check if known unhandled cases are present"""

    # Number of generators with an EnergyTarget discrepancy and the number of unique prices corresponding to those units
    n_enof_discrepancy, n_enof_unique_current_prices = check_price_tied_condition(data, solution, intervention, 'ENOF')

    # MNSP output
    mnsp_initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, 'T-V-MNSP1',
                                                                                             'InitialMW', float)

    # Run diagnostics on case data to check if known issues associated with case
    output = {
        'case_id': lookup.get_case_attribute(data, '@CaseID', str),
        'fast_start_error': check_fast_start_error_condition(data, intervention),
        'mnsp_flow_inverts': check_mnsp_flow_inverts_condition(data, intervention),
        'n_enof_discrepancy': n_enof_discrepancy,
        'n_enof_unique_current_prices': n_enof_unique_current_prices,
        'mnsp_initial_mw': mnsp_initial_mw,
        'mnsp_target_flow': solution.get('interconnectors').get('T-V-MNSP1').get('Flow'),
    }

    return output


def get_dispatch_interval_sample(n, seed=10):
    """Get sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(seed)

    # Population of dispatch intervals for a given month TODO: take into days in month
    population = [(i, j) for i in range(1, 31) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Keys for all possible dispatch intervals
    all_keys = list(population_map.keys())

    # Shuffle keys to randomise sample (should be reproducible though because seed is set)
    np.random.shuffle(all_keys)

    # Sample of keys
    sample_keys = all_keys[:n]

    # Extract sample
    sample = [population_map[i] for i in sample_keys]

    return sample


def check_region_fixed_demand_calculation_sample(data_dir, intervention, n=5):
    """Check region fixed demand calculations for a random sample of dispatch intervals"""

    # Random sample of dispatch intervals (with seeded random number generator for reproducible results)
    sample = get_dispatch_interval_sample(n, seed=10)

    # Container for model output
    out = {}

    # Placeholder for max absolute difference observed
    max_abs_difference = 0
    max_abs_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'({day}, {interval}) {i + 1}/{len(sample)}')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Preprocessed case data
        processed_data = data.parse_case_data_json(data_json)

        # Construct model
        m = construct_model(processed_data, case_data)

        # All regions
        regions = lookup.get_region_index(case_data)

        for r in regions:
            # Check difference between calculated region fixed demand and fixed demand from NEMDE solution
            fixed_demand_info = check_region_fixed_demand(case_data, m, r, intervention)

            # Add to dictionary
            out[(day, interval, r)] = fixed_demand_info

            if fixed_demand_info['abs_difference'] > max_abs_difference:
                max_abs_difference = fixed_demand_info['abs_difference']
                max_abs_difference_interval = (day, interval, r)

        # Periodically print max absolute difference observed
        if (i + 1) % 10 == 0:
            print('Max absolute difference:', max_abs_difference_interval, max_abs_difference)

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    return df


def check_generic_constraint_rhs(data, m, constraint_id, intervention):
    """Check generic constraint RHS"""

    # Container for output
    calculated = m.P_GC_RHS[constraint_id]
    observed = lookup.get_generic_constraint_solution_attribute(data, constraint_id, '@RHS', float, intervention)

    out = {
        'calculated': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed)
    }

    return out


def check_generic_constraint_rhs_sample(data_dir, intervention, n=5):
    """Check generic constraint RHS for a random sample of dispatch intervals"""

    # Random sample of dispatch intervals (with seeded random number generator for reproducible results)
    sample = get_dispatch_interval_sample(n, seed=10)

    # Container for model output
    out = {}

    # Placeholder for max absolute difference observed
    max_abs_difference = 0
    max_abs_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'({day}, {interval}) {i + 1}/{len(sample)}')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Preprocessed case data
        processed_data = data.parse_case_data_json(data_json)

        # Construct model
        m = construct_model(processed_data, case_data)

        # All constraints
        constraints = lookup.get_generic_constraint_index(case_data)

        for j in constraints:
            # Check difference
            info = check_generic_constraint_rhs(case_data, m, j, intervention)

            # Add to dictionary
            out[(j, day, interval)] = info

            if info['abs_difference'] > max_abs_difference:
                max_abs_difference = info['abs_difference']
                max_abs_difference_interval = (j, day, interval)

        # Periodically print max absolute difference observed
        if (i + 1) % 10 == 0:
            print('Max absolute difference:', max_abs_difference_interval, max_abs_difference)

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    return df


def get_observed_fcas_availability(data_dir, tmp_dir):
    """Get FCAS availability reported in MMS"""

    with zipfile.ZipFile(os.path.join(data_dir, 'PUBLIC_DVD_DISPATCHLOAD_201910010000.zip')) as z1:
        with z1.open('PUBLIC_DVD_DISPATCHLOAD_201910010000.CSV') as z2:
            df = pd.read_csv(z2, skiprows=1).iloc[:-1]

    # Convert intervention flag and dispatch interval to string
    df['INTERVENTION'] = df['INTERVENTION'].astype(int).astype('str')
    df['DISPATCHINTERVAL'] = df['DISPATCHINTERVAL'].astype(int).astype('str')

    #  Convert to datetime
    df['SETTLEMENTDATE'] = pd.to_datetime(df['SETTLEMENTDATE'])

    # Set index
    df = df.set_index(['DISPATCHINTERVAL', 'DUID', 'INTERVENTION'])
    df = df.sort_index()

    # Save to
    df.to_pickle(os.path.join(tmp_dir, 'fcas_availability.pickle'))

    return df


def check_fcas_solution(data, output, intervention, case_id, sample_dir, tmp_dir, use_cache=True):
    """Check FCAS solution and compare availability with observed availability"""

    # Compare model and observed solutions
    comparison = solution.get_model_comparison(data, output)

    # Trader dispatch target
    df_trader_targets = solution.inspect_trader_solution(comparison)

    # Load observed FCAS data
    if use_cache:
        observed_fcas = pd.read_pickle(os.path.join(tmp_dir, 'fcas_availability.pickle'))
    else:
        observed_fcas = get_observed_fcas_availability(sample_dir, tmp_dir)

    # Column map
    column_map = {
        'RAISEREGAVAILABILITY': 'R5RE',
        'RAISE6SECACTUALAVAILABILITY': 'R6SE',
        'RAISE60SECACTUALAVAILABILITY': 'R60S',
        'RAISE5MINACTUALAVAILABILITY': 'R5MI',
        'LOWERREGACTUALAVAILABILITY': 'L5RE',
        'LOWER6SECACTUALAVAILABILITY': 'L6SE',
        'LOWER60SECACTUALAVAILABILITY': 'L60S',
        'LOWER5MINACTUALAVAILABILITY': 'L5MI',
    }

    # Augment DataFrame
    observed_fcas_formatted = (observed_fcas.loc[(case_id, slice(None), intervention), column_map.keys()]
                               .rename(columns=column_map).stack().to_frame('fcas_availability').droplevel([0, 2])
                               .rename_axis(['trader_id', 'trade_type']))

    # Combine trader solution with observed FCAS availability
    df_c = df_trader_targets.join(observed_fcas_formatted, how='left')

    # Difference between observed FCAS and available FCAS
    df_c['fcas_availability_difference'] = df_c['model'] - df_c['fcas_availability']
    df_c['fcas_availability_abs_difference'] = df_c['fcas_availability_difference'].abs()

    # Sort to largest difference is first - if difference is positive then model > actual available --> problem
    df_c = df_c.sort_values(by='fcas_availability_difference', ascending=False)

    return df_c


def check_constraint_violation(m):
    """Check constraint violation expressions"""

    # Penalty terms to print
    terms = ['E_CV_GC_PENALTY',
             'E_CV_GC_LHS_PENALTY',
             'E_CV_GC_RHS_PENALTY',
             'E_CV_TRADER_OFFER_PENALTY',
             'E_CV_TRADER_CAPACITY_PENALTY',
             'E_CV_TRADER_RAMP_UP_PENALTY',
             'E_CV_TRADER_RAMP_DOWN_PENALTY',
             'E_CV_TRADER_FCAS_JOINT_RAMPING_UP',
             'E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN',
             'E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS',
             'E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS',
             'E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS',
             'E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS',
             'E_CV_TRADER_FCAS_MAX_AVAILABLE',
             'E_CV_TRADER_INFLEXIBILITY_PROFILE',
             'E_CV_TRADER_INFLEXIBILITY_PROFILE_LHS',
             'E_CV_TRADER_INFLEXIBILITY_PROFILE_RHS',
             'E_CV_MNSP_OFFER_PENALTY',
             'E_CV_MNSP_CAPACITY_PENALTY',
             'E_CV_MNSP_RAMP_UP_PENALTY',
             'E_CV_MNSP_RAMP_DOWN_PENALTY',
             'E_CV_INTERCONNECTOR_FORWARD_PENALTY',
             'E_CV_INTERCONNECTOR_REVERSE_PENALTY']

    for i in terms:
        print(i, sum(m.__getattribute__(i)[j].expr() for j in m.__getattribute__(i).keys()))

