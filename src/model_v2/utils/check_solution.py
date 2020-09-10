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


def get_initial_region_interconnector_loss(data, region_id) -> float:
    """Get initial loss allocated to each region"""

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
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)

        # loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)
        loss = calculations.get_interconnector_loss_estimate(data, i, initial_mw)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        # TODO: Using InitialMW seems best model for now - real NEMDE does 2 runs. Perhaps second run identifies flow
        #  direction has changed and updates loss factor

        # MNSP losses applied to sending end - based on InitialMW
        if mnsp_status == '1':
            if initial_mw >= 0:
                mnsp_loss_share = 1
            else:
                mnsp_loss_share = 0

        # # MNSP losses applied to sending end - based on solution flow
        # if mnsp_status == '1':
        #     if flow >= 0:
        #         mnsp_loss_share = 1
        #     else:
        #         mnsp_loss_share = 0

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                region_interconnector_loss += loss * mnsp_loss_share
            else:
                region_interconnector_loss += loss * loss_share

        # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                region_interconnector_loss += loss * (1 - mnsp_loss_share)
            else:
                region_interconnector_loss += loss * (1 - loss_share)

        else:
            pass

    return region_interconnector_loss


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


def get_initial_region_scheduled_load(data, region_id) -> float:
    """Get scheduled load in a given region - based NEMDE InitialMW values"""

    # All traders
    traders = get_trader_index(data)

    scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        trader_region = lookup.get_trader_period_collection_attribute(data, i, '@RegionID', str)

        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch == '0') and (trader_region == region_id):
            scheduled_load += lookup.get_trader_collection_initial_condition_attribute(data, i, 'InitialMW', float)

    return scheduled_load


def get_solution_region_interconnector_loss(data, region_id) -> float:
    """Get loss allocated to each region"""

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
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)

        # TODO: Using InitialMW seems best model for now - real NEMDE does 2 runs. Perhaps second run identifies flow
        #  direction has changed and updates loss factor

        # MNSP losses applied to sending end - based on InitialMW
        if mnsp_status == '1':
            if initial_mw >= 0:
                mnsp_loss_share = 1
            else:
                mnsp_loss_share = 0

        # # MNSP losses applied to sending end - based on solution flow
        # if mnsp_status == '1':
        #     if flow >= 0:
        #         mnsp_loss_share = 1
        #     else:
        #         mnsp_loss_share = 0

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                region_interconnector_loss += loss * mnsp_loss_share
            else:
                region_interconnector_loss += loss * loss_share

        # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                region_interconnector_loss += loss * (1 - mnsp_loss_share)
            else:
                region_interconnector_loss += loss * (1 - loss_share)

        else:
            pass

    return region_interconnector_loss


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


def get_solution_region_net_interconnector_export(data, region_id) -> float:
    """Get net export over interconnectors for a given region - based on NEMDE solution"""

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

    return interconnector_export


def get_solution_region_scheduled_load(data, region_id) -> float:
    """Get scheduled load in a given region - based on NEMDE solution"""

    # All traders
    traders = get_trader_index(data)

    scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        trader_region = lookup.get_trader_period_collection_attribute(data, i, '@RegionID', str)

        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch == '0') and (trader_region == region_id):
            scheduled_load += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return scheduled_load


def check_total_cleared_demand_calculation(data) -> float:
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


def check_total_fixed_demand_calculation(data) -> float:
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


def check_total_calculation_sample(data_dir, func, n=5):
    """Get calculation for a random sample of dispatch intervals"""

    print('Checking:', func.__name__)

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

    # Max absolute difference
    max_abs_difference = 0
    max_abs_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'{i + 1}/{len(sample)}')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Check difference between total cleared demand and total generation
        difference = func(case_data)

        # Add date to keys
        demand_calculations = {(day, interval):
            {
                'difference': difference,
                'abs_difference': abs(difference),
            }
        }

        if abs(difference) > max_abs_difference:
            max_abs_difference = abs(difference)
            max_abs_difference_interval = (day, interval)

        # Periodically print max abs difference and the corresponding interval
        if (i + 1) % 10 == 0:
            print('Max absolute difference:', max_abs_difference_interval, max_abs_difference)

        # Append to main container
        out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def check_region_cleared_demand_calculation(data, region_id) -> float:
    """Check region cleared demand calculation"""

    # Fixed demand from NEMDE solution
    fixed_demand = lookup.get_region_solution_attribute(data, region_id, '@FixedDemand', float)

    # Loss allocated to region based on interconnector flow
    region_interconnector_loss = get_solution_region_interconnector_loss(data, region_id)

    # Total scheduled load
    total_scheduled_load = get_solution_region_scheduled_load(data, region_id)

    # MNSP loss estimate
    mnsp_loss = get_solution_region_mnsp_loss_estimate(data, region_id)

    # Cleared demand from NEMDE solution
    cleared_demand = lookup.get_region_solution_attribute(data, region_id, '@ClearedDemand', float)

    return fixed_demand + region_interconnector_loss + total_scheduled_load - mnsp_loss - cleared_demand


def check_region_fixed_demand_calculation(data, region_id) -> float:
    """Check region fixed demand calculation"""

    # Fixed demand calculation terms
    demand = lookup.get_region_collection_initial_condition_attribute(data, region_id, 'InitialDemand', float)
    ade = lookup.get_region_collection_initial_condition_attribute(data, region_id, 'ADE', float)
    delta_forecast = lookup.get_region_period_collection_attribute(data, region_id, '@DF', float)

    # Total scheduled load at start of dispatch interval
    total_scheduled_load = get_initial_region_scheduled_load(data, region_id)

    # Region interconnector loss
    region_interconnector_loss = get_initial_region_interconnector_loss(data, region_id)

    # MNSP loss estimate
    mnsp_loss = get_initial_region_mnsp_loss_estimate(data, region_id)

    # Fixed demand from NEMDE solution
    fixed_demand = lookup.get_region_solution_attribute(data, region_id, '@FixedDemand', float)

    return demand - total_scheduled_load + ade + delta_forecast - region_interconnector_loss + mnsp_loss - fixed_demand


def check_region_net_export_calculation(data, region_id) -> float:
    """Check net export calculation for a given region"""

    # Net export over interconnectors connected to region
    interconnector_export = get_solution_region_net_interconnector_export(data, region_id)

    # Loss allocated to region due to interconnector flow
    region_interconnector_loss = get_solution_region_interconnector_loss(data, region_id)

    # MNSP loss estimate
    mnsp_loss = get_solution_region_mnsp_loss_estimate(data, region_id)

    # Net export from solution
    net_export = lookup.get_region_solution_attribute(data, region_id, '@NetExport', float)

    return interconnector_export + region_interconnector_loss - mnsp_loss - net_export


def check_region_calculation_sample(data_dir, func, n=5):
    """Check region calculations for a random sample of dispatch intervals"""

    print('Checking:', func.__name__)

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

    # Placeholder for max absolute difference observed
    max_abs_difference = 0
    max_abs_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'{i + 1}/{len(sample)}')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # All regions
        regions = get_region_index(case_data)

        # Check net export calculation for each region
        for j in regions:
            # Check difference between calculated region fixed demand and fixed demand from NEMDE solution
            difference = func(case_data, j)

            # Add date to keys
            demand_calculations = {(day, interval, j): {'difference': difference, 'abs_difference': abs(difference)}}

            if abs(difference) > max_abs_difference:
                max_abs_difference = abs(difference)
                max_abs_difference_interval = (day, interval, j)

            # Append to main container
            out = {**out, **demand_calculations}

        # Periodically print max absolute difference observed
        if (i + 1) % 10 == 0:
            print('Max absolute difference:', max_abs_difference_interval, max_abs_difference)

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
    case_data_json = loaders.load_dispatch_interval_json(data_directory, 2019, 10, 8, 6)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Check aggregate values for entire system
    c1, c1_df, c1_max = check_total_calculation_sample(data_directory, check_total_cleared_demand_calculation, n=10)
    c2, c2_df, c2_max = check_total_calculation_sample(data_directory, check_total_fixed_demand_calculation, n=10)

    # Check values for each region
    c3, c3_df, c3_max = check_region_calculation_sample(data_directory, check_region_net_export_calculation, n=10)
    c4, c4_df, c4_max = check_region_calculation_sample(data_directory, check_region_cleared_demand_calculation, n=10)
    c5, c5_df, c5_max = check_region_calculation_sample(data_directory, check_region_fixed_demand_calculation, n=10)
