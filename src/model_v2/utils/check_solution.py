"""Check NEMDE solution components"""

import os
import json
import random

import numpy as np
import pandas as pd

import lookup
import loaders
import data as calculations


def get_region_index(data) -> list:
    """Get list of all regions"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

    out = []
    for i in regions:
        out.append(i['@RegionID'])

    return list(set(out))


def get_trader_index(data) -> list:
    """Get trader index"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

    # Container for trader IDs
    out = []
    for i in traders:
        out.append(i['@TraderID'])

    return out


def get_interconnector_index(data) -> list:
    """Get interconnector index"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                       .get('Interconnector'))

    # Container for interconnector IDs
    out = []
    for i in interconnectors:
        out.append(i['@InterconnectorID'])

    return out


def get_mnsp_index(data) -> list:
    """Get MNSP index"""

    # All interconnectors
    interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                       .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

    # Container for MNSP IDs
    out = []
    for i in interconnectors:
        if i['@MNSP'] == '1':
            out.append(i['@InterconnectorID'])

    return out


def check_total_cleared_demand_calculation(data):
    """Check TotalClearedDemand = TotalGeneration"""

    # All traders
    traders = get_trader_index(data)

    total_generation = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        if trader_type == 'GENERATOR':
            total_generation += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    # All regions
    regions = get_region_index(data)

    total_cleared_demand = 0
    for i in regions:
        total_cleared_demand += lookup.get_region_solution_attribute(data, i, '@ClearedDemand', float)

    return total_generation - total_cleared_demand


def check_total_cleared_demand_calculation_sample(data_dir, n=5):
    """Compute difference between total cleared demand and total generation for random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}

    # Compute fixed demand for each interval
    for d, i in sample:
        # Case data in json format
        try:
            data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)
        except KeyError:
            continue

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Check difference between total cleared demand and total generation
        demand_minus_generation = check_total_cleared_demand_calculation(case_data)

        # Add date to keys
        demand_calculations = {(d, i):
            {
                'difference': demand_minus_generation,
                'abs_difference': abs(demand_minus_generation),
            }
        }

        # Append to main container
        out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def get_solution_region_mnsp_loss_estimate(data, region_id) -> float:
    """Get estimate of MNSP loss allocated to given region"""

    # All interconnectors
    mnsps = get_mnsp_index(data)

    total = 0
    for i in mnsps:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        if region_id not in [from_region, to_region]:
            continue

        # Initial MW flow
        flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float)

        to_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFExport', float)
        to_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFImport', float)

        from_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFImport', float)
        from_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFExport', float)

        # Initial loss estimate over interconnector
        loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)

        # FromRegion is exporting, ToRegion is importing
        if flow >= 0:
            if region_id == from_region:
                export_flow = abs(flow) + (loss_share * loss)
                mnsp_loss = export_flow * (1 - from_lf_export)

            elif region_id == to_region:
                # + ((1 - loss_share) * initial_loss_estimate) TODO: check why allocated loss doesn't need to be added
                import_flow = abs(flow)
                mnsp_loss = import_flow * (1 - to_lf_import)

            else:
                raise Exception('Unexpected region:', region_id)

        # FromRegion is importing, ToRegion is exporting
        else:
            if region_id == from_region:
                import_flow = abs(flow) - (loss_share * loss)
                mnsp_loss = import_flow * (1 - from_lf_import)

            elif region_id == to_region:
                export_flow = abs(flow) + ((1 - loss_share) * loss)
                mnsp_loss = export_flow * (1 - to_lf_export)

            else:
                raise Exception('Unexpected region:', region_id)

        # Not sure why, but seems need to multiply loss by -1 when considering positive flow
        if flow >= 0:
            total -= mnsp_loss
        else:
            total += mnsp_loss

    return total


def get_initial_region_mnsp_loss_estimate(data, region_id) -> float:
    """Get estimate of MNSP loss allocated to given region"""

    # All interconnectors
    mnsps = get_mnsp_index(data)

    total = 0
    for i in mnsps:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        if region_id not in [from_region, to_region]:
            continue

        # Initial MW flow
        flow = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)

        to_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFExport', float)
        to_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFImport', float)

        from_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFImport', float)
        from_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFExport', float)

        # Initial loss estimate over interconnector
        loss = calculations.get_interconnector_loss_estimate(data, i, flow)
        # loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)

        # FromRegion is exporting, ToRegion is importing
        if flow >= 0:
            if region_id == from_region:
                export_flow = abs(flow) + (loss_share * loss)
                mnsp_loss = export_flow * (1 - from_lf_export)

            elif region_id == to_region:
                # + ((1 - loss_share) * initial_loss_estimate) TODO: check why allocated loss doesn't need to be added
                import_flow = abs(flow)
                mnsp_loss = import_flow * (1 - to_lf_import)

            else:
                raise Exception('Unexpected region:', region_id)

        # FromRegion is importing, ToRegion is exporting
        else:
            if region_id == from_region:
                import_flow = abs(flow) - (loss_share * loss)
                mnsp_loss = import_flow * (1 - from_lf_import)

            elif region_id == to_region:
                export_flow = abs(flow) + ((1 - loss_share) * loss)
                mnsp_loss = export_flow * (1 - to_lf_export)

            else:
                raise Exception('Unexpected region:', region_id)

        # Not sure why, but seems need to multiply loss by -1 when considering positive flow
        if flow >= 0:
            total -= mnsp_loss
        else:
            total += mnsp_loss

    return total


def check_total_fixed_demand_calculation(data):
    """Check: TotalFixedDemand + Losses = TotalClearedDemand"""

    # All regions
    regions = get_region_index(data)

    # Total fixed demand
    total_fixed_demand = 0
    for i in regions:
        total_fixed_demand += lookup.get_region_solution_attribute(data, i, '@FixedDemand', float)

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    # Total interconnector
    total_interconnector_loss = 0
    for i in interconnectors:
        total_interconnector_loss += lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)

    # All regions
    regions = get_region_index(data)
    total_mnsp_loss = 0
    for i in regions:
        total_mnsp_loss += get_solution_region_mnsp_loss_estimate(data, i)

    # Total cleared demand
    total_cleared_demand = 0
    for i in regions:
        total_cleared_demand += lookup.get_region_solution_attribute(data, i, '@ClearedDemand', float)

    # All traders
    traders = get_trader_index(data)

    # Total scheduled demand
    total_scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)

        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch == '0'):
            total_scheduled_load += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    # TODO: check why sometimes total_mnsp_loss should be positive and other times negative
    return total_fixed_demand + total_interconnector_loss - total_mnsp_loss + total_scheduled_load - total_cleared_demand


def check_total_fixed_demand_calculation_sample(data_dir, n=5):
    """Check fixed demand calculation based on NEMDE solution for a random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}

    # Compute fixed demand for each interval
    for d, i in sample:
        # Case data in json format
        try:
            data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)
        except KeyError:
            continue

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Check difference between total cleared demand and total generation
        difference = check_total_fixed_demand_calculation(case_data)

        # Add date to keys
        demand_calculations = {(d, i):
            {
                'difference': difference,
                'abs_difference': abs(difference),
            }
        }

        # Append to main container
        out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def check_region_net_export_calculation(data, region_id):
    """Check net export calculation for a given region"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    # Flow over interconnectors
    interconnector_export = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float)

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            interconnector_export += flow

        # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            interconnector_export -= flow

        else:
            pass

    # Allocated interconnector losses
    region_interconnector_loss = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)
        mnsp_status = lookup.get_interconnector_period_collection_attribute(data, i, '@MNSP', str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float)
        loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP TODO: this conditional logic may be problematic - check
            if mnsp_status == '1':
                if flow >= 0:
                    region_interconnector_loss += loss
                else:
                    continue
            else:
                region_interconnector_loss += loss * loss_share

        # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                if flow < 0:
                    region_interconnector_loss += loss
                else:
                    continue
            else:
                region_interconnector_loss += loss * (1 - loss_share)

        else:
            pass

    # MNSP loss estimate
    mnsp_loss = get_solution_region_mnsp_loss_estimate(data, region_id)

    # Net export from solution
    net_export = lookup.get_region_solution_attribute(data, region_id, '@NetExport', float)

    return interconnector_export + region_interconnector_loss - mnsp_loss - net_export


def check_region_net_export_calculation_sample(data_dir, n=5):
    """Check net export calculation based on NEMDE solution for a random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}
    # Compute fixed demand for each interval
    for d, i in sample:
        # Case data in json format
        try:
            data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)
        except KeyError:
            continue

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # All regions
        regions = get_region_index(case_data)

        # Check net export calculation for each region
        for j in regions:
            # Check difference between total cleared demand and total generation
            difference = check_region_net_export_calculation(case_data, j)

            # Add date to keys
            demand_calculations = {(d, i, j): {'difference': difference, 'abs_difference': abs(difference)}}

            # Append to main container
            out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def check_region_cleared_demand_calculation(data, region_id):
    """Check region cleared demand calculation"""

    # Fixed demand from NEMDE solution
    fixed_demand = lookup.get_region_solution_attribute(data, region_id, '@FixedDemand', float)

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    # Allocated interconnector losses
    region_interconnector_loss = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)
        mnsp_status = lookup.get_interconnector_period_collection_attribute(data, i, '@MNSP', str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float)
        loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP TODO: this conditional logic may be problematic - check
            if mnsp_status == '1':
                if flow >= 0:
                    region_interconnector_loss += loss
                else:
                    continue
            else:
                region_interconnector_loss += loss * loss_share

        # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                if flow < 0:
                    region_interconnector_loss += loss
                else:
                    continue
            else:
                region_interconnector_loss += loss * (1 - loss_share)

        else:
            pass

    # All traders
    traders = get_trader_index(data)

    total_scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        trader_region = lookup.get_trader_period_collection_attribute(data, i, '@RegionID', str)

        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch == '0') and (trader_region == region_id):
            total_scheduled_load += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    # MNSP loss estimate
    mnsp_loss = get_solution_region_mnsp_loss_estimate(data, region_id)

    # Cleared demand from NEMDE solution
    cleared_demand = lookup.get_region_solution_attribute(data, region_id, '@ClearedDemand', float)

    return fixed_demand + region_interconnector_loss + total_scheduled_load - mnsp_loss - cleared_demand


def check_region_cleared_demand_calculation_sample(data_dir, n=5):
    """Check cleared demand calculation based on NEMDE solution for a random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}
    # Compute fixed demand for each interval
    for d, i in sample:
        # Case data in json format
        try:
            data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)
        except KeyError:
            continue

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # All regions
        regions = get_region_index(case_data)

        # Check net export calculation for each region
        for j in regions:
            # Check difference between calculated region cleared demand and cleared demand from NEMDE solution
            difference = check_region_cleared_demand_calculation(case_data, j)

            # Add date to keys
            demand_calculations = {(d, i, j): {'difference': difference, 'abs_difference': abs(difference)}}

            # Append to main container
            out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def check_region_fixed_demand_calculation(data, region_id):
    """Check region fixed demand calculation"""

    # Fixed demand calculation terms
    demand = lookup.get_region_collection_initial_condition_attribute(data, region_id, 'InitialDemand', float)
    ade = lookup.get_region_collection_initial_condition_attribute(data, region_id, 'ADE', float)
    delta_forecast = lookup.get_region_period_collection_attribute(data, region_id, '@DF', float)

    # All traders
    traders = get_trader_index(data)

    total_scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        trader_region = lookup.get_trader_period_collection_attribute(data, i, '@RegionID', str)

        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch == '0') and (trader_region == region_id):
            total_scheduled_load += lookup.get_trader_collection_initial_condition_attribute(data, i, 'InitialMW', float)

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    # Allocated interconnector losses
    region_interconnector_loss = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)
        mnsp_status = lookup.get_interconnector_period_collection_attribute(data, i, '@MNSP', str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        flow = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)
        loss = calculations.get_interconnector_loss_estimate(data, i, flow)
        # loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP TODO: this conditional logic may be problematic - check
            if mnsp_status == '1':
                if flow >= 0:
                    region_interconnector_loss += loss
                else:
                    continue
            else:
                region_interconnector_loss += loss * loss_share

        # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                if flow < 0:
                    region_interconnector_loss += loss
                else:
                    continue
            else:
                region_interconnector_loss += loss * (1 - loss_share)

        else:
            pass

    # MNSP loss estimate
    mnsp_loss = get_initial_region_mnsp_loss_estimate(data, region_id)

    # Compute fixed demand
    fixed_demand = lookup.get_region_solution_attribute(data, region_id, '@FixedDemand', float)

    return demand - total_scheduled_load + ade + delta_forecast - region_interconnector_loss + mnsp_loss - fixed_demand


def check_region_fixed_demand_calculation_sample(data_dir, n=5):
    """Check fixed demand calculation based on NEMDE solution for a random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}
    # Compute fixed demand for each interval
    for d, i in sample:
        # Case data in json format
        try:
            data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)
        except KeyError:
            continue

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # All regions
        regions = get_region_index(case_data)

        # Check net export calculation for each region
        for j in regions:
            # Check difference between calculated region fixed demand and fixed demand from NEMDE solution
            difference = check_region_fixed_demand_calculation(case_data, j)

            # Add date to keys
            demand_calculations = {(d, i, j): {'difference': difference, 'abs_difference': abs(difference)}}

            # Append to main container
            out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_directory, 2019, 10, 22, 159)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    c1, c1_df, c1_max_diff = check_total_cleared_demand_calculation_sample(data_directory, n=1000)
    c2, c2_df, c2_max_diff = check_total_fixed_demand_calculation_sample(data_directory, n=1000)
    c3, c3_df, c3_max_diff = check_region_net_export_calculation_sample(data_directory, n=1000)
    c4, c4_df, c4_max_diff = check_region_cleared_demand_calculation_sample(data_directory, n=1000)
    c5, c5_df, c5_max_diff = check_region_fixed_demand_calculation_sample(data_directory, n=1000)

    # c5 = check_region_fixed_demand_calculation(cdata, 'SA1')
