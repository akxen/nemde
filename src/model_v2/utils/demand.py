"""
Demand calculations

Observations:
TotalClearedDemand = TotalGeneration

TotalClearedDemand = TotalFixedDemand + TotalRegionLoss + TotalScheduledLoad + TotalInterconnectorLoss - TotalMNSPLoss

TotalFixedDemand = TotalInitialDemand - TotalInitialScheduledLoad + TotalInitialADE + TotalInitialDeltaForecast
                   - TotalInitialRegionLoss + TotalInitialMNSPLoss
"""


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


def get_initial_region_interconnector_loss_estimate(data, region_id) -> float:
    """Get estimate of interconnector losses allocated to given region"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)

        if region_id not in [from_region, to_region]:
            continue

        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)
        loss = calculations.get_interconnector_loss_estimate(data, i, initial_mw)
        mnsp_status = lookup.get_interconnector_period_collection_attribute(data, i, '@MNSP', str)

        # Loss applied to exporting region if an MNSP
        if mnsp_status == '1':
            if (initial_mw >= 0) and (region_id == from_region):
                total += loss
            elif (initial_mw < 0) and (region_id == to_region):
                total += loss
            else:
                continue

        # Loss shared if not an MNSP
        else:
            if region_id == from_region:
                total += loss * loss_share
            elif region_id == to_region:
                total += loss * (1 - loss_share)
            else:
                continue

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
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)

        to_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLF', float)
        from_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLF', float)

        to_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFExport', float)
        to_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFImport', float)

        from_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFImport', float)
        from_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFExport', float)

        # Initial loss estimate over interconnector
        initial_loss_estimate = calculations.get_interconnector_loss_estimate(data, i, initial_mw)

        # FromRegion is exporting, ToRegion is importing
        if initial_mw >= 0:
            if region_id == from_region:
                export_flow = abs(initial_mw) + (loss_share * initial_loss_estimate)
                mnsp_loss = export_flow * (1 - from_lf_export)

            elif region_id == to_region:
                # + ((1 - loss_share) * initial_loss_estimate) TODO: check why allocated loss doesn't need to be added
                import_flow = abs(initial_mw)
                mnsp_loss = import_flow * (1 - to_lf_import)

            else:
                raise Exception('Unexpected region:', region_id)

        # FromRegion is importing, ToRegion is exporting
        else:
            if region_id == from_region:
                import_flow = abs(initial_mw) - (loss_share * initial_loss_estimate)
                mnsp_loss = import_flow * (1 - from_lf_import)

            elif region_id == to_region:
                export_flow = abs(initial_mw) + ((1 - loss_share) * initial_loss_estimate)
                mnsp_loss = export_flow * (1 - to_lf_export)

            else:
                raise Exception('Unexpected region:', region_id)

        # Not sure why, but seems need to multiply loss by -1 when considering positive flow
        if initial_mw >= 0:
            total -= mnsp_loss
        else:
            total += mnsp_loss

    return total


def get_initial_region_net_export(data, region_id) -> float:
    """Get initial net flow out of region"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)

        if region_id not in [from_region, to_region]:
            continue

        # Initial MW flow
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)

        # Positive flow denotes export out of FromRegion
        if region_id == from_region:
            total += initial_mw

        # Positive flow denotes import into ToRegion, so must take negative to get export out of ToRegion
        elif region_id == to_region:
            total -= initial_mw
        else:
            continue

    return total


def get_initial_region_scheduled_load(data, region_id) -> float:
    """Get initial scheduled load"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch_status = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        trader_region = lookup.get_trader_period_collection_attribute(data, i, '@RegionID', str)

        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch_status == '0') and (trader_region == region_id):
            total += lookup.get_trader_collection_initial_condition_attribute(data, i, 'InitialMW', float)

    return total


def get_initial_region_fixed_demand(data, region_id) -> float:
    """Get initial region fixed demand"""

    # Fixed demand calculation terms
    demand = lookup.get_region_collection_initial_condition_attribute(data, region_id, 'InitialDemand', float)
    load = get_initial_region_scheduled_load(data, region_id)
    ade = lookup.get_region_collection_initial_condition_attribute(data, region_id, 'ADE', float)
    delta_forecast = lookup.get_region_period_collection_attribute(data, region_id, '@DF', float)
    interconnector_loss_estimate = get_initial_region_interconnector_loss_estimate(data, region_id)
    mnsp_loss_estimate = get_initial_region_mnsp_loss_estimate(data, region_id)

    # Compute fixed demand
    fixed_demand = demand - load + ade + delta_forecast - interconnector_loss_estimate + mnsp_loss_estimate

    return fixed_demand


def get_initial_region_cleared_demand(data, region_id) -> float:
    """Get initial region fixed demand"""

    # Fixed demand calculation terms
    fixed_demand = get_initial_region_fixed_demand(data, region_id)

    # TotalFixedDemand + TotalRegionLoss + TotalScheduledLoad + TotalInterconnectorLoss - TotalMNSPLoss

    # Compute fixed demand
    cleared_demand = fixed_demand

    return fixed_demand


def get_initial_total_ade(data) -> float:
    """Get total aggregate dispatch error"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_collection_initial_condition_attribute(data, i, 'ADE', float)

    return total


def get_initial_total_df(data) -> float:
    """Get total demand forecast increment"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_period_collection_attribute(data, i, '@DF', float)

    return total


def get_initial_total_regional_losses(data) -> float:
    """Get total losses associated with all interconnectors"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)
        total += calculations.get_interconnector_loss_estimate(data, i, initial_mw)
    return total


def get_initial_total_generation(data) -> float:
    """Get total generation at start of dispatch interval"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'GENERATOR':
            total += lookup.get_trader_collection_initial_condition_attribute(data, i, 'InitialMW', float)

    return total


def get_initial_total_scheduled_load(data) -> float:
    """Get total scheduled load at start of dispatch interval"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch_status = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch_status == '0'):
            total += lookup.get_trader_collection_initial_condition_attribute(data, i, 'InitialMW', float)

    return total


def get_initial_total_demand(data) -> float:
    """Get total initial demand"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_collection_initial_condition_attribute(data, i, 'InitialDemand', float)

    return total


def get_initial_total_fixed_demand(data) -> float:
    """Compute total fixed demand"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += get_initial_region_fixed_demand(data, i)

    return total


def get_initial_total_mnsp_losses(data) -> float:
    """Get total initial MNSP loss"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += get_initial_region_mnsp_loss_estimate(data, i)

    return total


def get_solution_total_losses(data) -> float:
    """Get total loss over all interconnectors"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        total += lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)

    return total


def get_solution_total_mnsp_losses(data) -> float:
    """Get total initial MNSP loss"""

    # All MNSPs
    mnsps = get_mnsp_index(data)

    total = 0
    for i in mnsps:
        to_region_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLF', float)
        from_region_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLF', float)

        to_region_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFExport', float)
        to_region_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFImport', float)

        from_region_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFExport', float)
        from_region_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFImport', float)

        flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float)
        initial_loss_estimate = calculations.get_interconnector_loss_estimate(data, i, flow)
        export_flow = abs(flow) + initial_loss_estimate

        total += (export_flow * (1 - to_region_lf_export)) + (export_flow * (1 - from_region_lf_import))

    return total


def get_solution_total_fixed_demand(data) -> float:
    """Get total fixed demand"""

    # Get regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_solution_attribute(data, i, '@FixedDemand', float)

    return total


def get_solution_total_cleared_demand(data) -> float:
    """Get total cleared demand"""

    # Get regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_solution_attribute(data, i, '@ClearedDemand', float)

    return total


def get_solution_total_generation(data) -> float:
    """Get total energy target for all generators"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'GENERATOR':
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_solution_total_normally_on_load(data) -> float:
    """Get total energy target for normally on loads"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'NORMALLY_ON_LOAD':
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_solution_total_scheduled_load(data) -> float:
    """Get total energy target for scheduled loads"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'LOAD':
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_solution_region_net_interconnector_flow(data, region_id) -> float:
    """Get net export for a given region"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)

        if region_id not in [from_region, to_region]:
            continue

        # Get solution power flow
        flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float)

        # Positive flow indicates export out of FromRegion
        if region_id == from_region:
            total += flow

        # Positive flow indicates import into ToRegion, so take negative
        elif region_id == to_region:
            total -= flow

        else:
            pass

    return total


def get_solution_region_interconnector_losses(data, region_id) -> float:
    """Get interconnector loss allocated to given region"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)

        if region_id not in [from_region, to_region]:
            continue

        # Get loss and loss share for interconnector
        loss = lookup.get_interconnector_solution_attribute(data, i, '@Losses', float)
        loss_share = lookup.get_interconnector_loss_model_attribute(data, i, '@LossShare', float)

        # Loss if from region
        if region_id == from_region:
            total += loss * loss_share

        # Loss if to region
        elif region_id == to_region:
            total += loss * (1 - loss_share)

        else:
            pass

    return total


def get_solution_region_mnsp_losses(data, region_id) -> float:
    """Get interconnector loss allocated to given region from MNSP"""

    # All interconnectors
    interconnectors = get_interconnector_index(data)

    total = 0
    for i in interconnectors:
        # MNSP status
        mnsp_status = lookup.get_interconnector_period_collection_attribute(data, i, '@MNSP', str)

        # Skip non-MNSPs
        if mnsp_status == '0':
            continue

        # From and To region
        from_region = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegion', str)
        to_region = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegion', str)

        if region_id not in [from_region, to_region]:
            continue

        # Power flow
        flow = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)

        # From region is exporting, To region is importing
        if flow >= 0:
            from_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFExport', float)
            to_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFImport', float)
        # From region is importing and To region is exporting
        else:
            from_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFImport', float)
            to_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFExport', float)

        # Loss if from region
        if region_id == from_region:
            total += abs(flow) * (1 - from_lf)

        # Loss if to region
        elif region_id == to_region:
            total += abs(flow) * (1 - to_lf)

        else:
            pass

    return total


def get_solution_region_scheduled_load(data, region_id) -> float:
    """Get solution region scheduled load"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(data, i, '@TraderType', str)
        semi_dispatch = lookup.get_trader_collection_attribute(data, i, '@SemiDispatch', str)
        trader_region_id = lookup.get_trader_period_collection_attribute(data, i, '@RegionID', str)
        if (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (semi_dispatch == '0') and (region_id == trader_region_id):
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_solution_region_net_export(data, region_id):
    """Get calculation net export"""

    # Net outflow from region over interconnectors
    net_outflow = get_solution_region_net_interconnector_flow(data, region_id)

    # Region allocated losses
    region_loss = get_solution_region_interconnector_losses(data, region_id)

    # MNSP loss
    # mnsp_loss = get_solution_region_mnsp_losses(data, region_id)

    return net_outflow + region_loss


def get_solution_region_cleared_demand(data, region_id):
    """Get region cleared demand based on FixedDemand calculation, observed flows, scheduled load, and losses"""

    # Cleared demand calculation parameters
    fixed_demand = get_initial_region_fixed_demand(data, region_id)
    net_export = get_solution_region_net_export(data, region_id)
    scheduled_load = get_solution_region_scheduled_load(data, region_id)
    interconnector_losses = get_solution_region_interconnector_losses(data, region_id)
    mnsp_losses = get_solution_region_mnsp_losses(data, region_id)

    cleared_demand = fixed_demand + interconnector_losses + scheduled_load - mnsp_losses + net_export

    return cleared_demand


def get_calculated_total_cleared_demand(data):
    """Get total cleared demand based on FixedDemand calculation and observed flows, scheduled load, and losses"""
    pass


def check_initial_region_fixed_demand(data):
    """Check region fixed demand"""

    # All regions
    regions = get_region_index(data)

    # Container for demand terms
    out = {}
    for i in regions:
        out.setdefault(i, {})

        calculated = get_initial_region_fixed_demand(data, i)
        observed = lookup.get_region_solution_attribute(data, i, '@FixedDemand', float)

        out[i] = {
            'calculated': calculated,
            'observed': observed,
            'difference': calculated - observed,
            'abs_difference': abs(calculated - observed)
        }

    # Convert to to DataFrame
    df = pd.DataFrame(out).T

    return out, df


def check_initial_region_fixed_demand_sample(data_dir, n=5):
    """Compute fixed region demand for random sample of dispatch intervals"""

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
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Check region fixed demand calculations
        fixed_demand, df = check_initial_region_fixed_demand(case_data)

        # Add date to keys
        demand_calculations = {(k, d, i): v for k, v in fixed_demand.items()}

        # Append to main container
        out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def check_initial_total_fixed_demand(data):
    """Check total fixed demand"""

    # Observed and calculated values
    observed = get_solution_total_fixed_demand(data)
    calculated = get_initial_total_fixed_demand(data)

    out = {
        'calculated': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed)
    }

    return out


def check_initial_total_fixed_demand_sample(data_dir, n=5):
    """Compute fixed total demand for random sample of dispatch intervals"""

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
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, d, i)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Check region fixed demand calculations
        fixed_demand = check_initial_total_fixed_demand(case_data)

        # Add date to keys
        demand_calculations = {(d, i): fixed_demand}

        # Append to main container
        out = {**out, **demand_calculations}

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    # Max absolute discrepancy
    max_abs_difference = df['abs_difference'].max()

    return out, df, max_abs_difference


def check_initial_total_cleared_demand(data):
    """Check initial total cleared demand calculation"""

    # Observed and calculated values
    observed = get_solution_total_cleared_demand(data)
    calculated = get_calculated_total_cleared_demand(data)

    out = {
        'calculated': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed)
    }

    return out


def check_solution_region_net_export(data):
    """Check solution region net export"""

    # All regions
    regions = get_region_index(data)

    # Container for output
    out = {}
    for i in regions:
        # Calculated and observed net export
        calculated = get_solution_region_net_export(data, i)
        observed = lookup.get_region_solution_attribute(data, i, '@NetExport', float)

        out[i] = {
            'calculated': calculated,
            'observed': observed,
            'difference': calculated - observed,
            'abs_difference': abs(calculated - observed),
        }

    # Convert to to DataFrame
    df = pd.DataFrame(out).T

    return out, df


def check_net_export(data):
    """Check net export calculation for a given dispatch interval"""

    # All regions
    regions = get_region_index(data)

    # Container for results
    out = {}
    for i in regions:
        out.setdefault(i, {})

        # Calculated and observed values
        calculated = get_region_net_export(data, i)
        observed = lookup.get_region_solution_attribute(data, i, '@NetExport', float)

        out[i] = {
            'calculated': calculated,
            'observed': observed,
            'difference': calculated - observed,
            'abs_difference': abs(calculated - observed)
        }

    return out


def check_net_export_sample(data_dir, n=5):
    """Check net export calculations for a sample of dispatch intervals"""
    pass


def perform_checks(data_dir, n=5):
    """Check demand calculations"""

    _, _, max_initial_region_fixed_demand_difference = check_initial_region_fixed_demand_sample(data_dir, n=n)
    print('Max absolute region fixed demand difference:', max_initial_region_fixed_demand_difference)

    _, _, max_initial_total_fixed_demand_difference = check_initial_total_fixed_demand_sample(data_dir, n=n)
    print('Max absolute total fixed demand difference:', max_initial_total_fixed_demand_difference)

    _, _, max_net_export_difference = check_net_export_sample(data_dir, n=n)
    print('Max absolute net export difference', max_net_export_difference)


def print_summary(data):
    """Print summary of key inputs"""

    solution_total_generation = get_solution_total_generation(data)
    solution_total_cleared_demand = get_solution_total_cleared_demand(data)
    solution_total_fixed_demand = get_solution_total_fixed_demand(data)
    solution_total_normally_on_load = get_solution_total_normally_on_load(data)
    solution_total_scheduled_load = get_solution_total_scheduled_load(data)
    solution_total_losses = get_solution_total_losses(data)
    solution_total_mnsp_losses = get_solution_total_mnsp_losses(data)
    initial_total_losses = get_initial_total_regional_losses(data)
    initial_total_ade = get_initial_total_ade(data)
    initial_total_df = get_initial_total_df(data)
    initial_total_generation = get_initial_total_generation(data)
    initial_total_scheduled_load = get_initial_total_scheduled_load(data)
    initial_total_demand = get_initial_total_demand(data)
    initial_total_mnsp_losses = get_initial_total_mnsp_losses(data)

    print('Total solution total generation:', solution_total_generation)
    print('Total solution cleared demand:', solution_total_cleared_demand)
    print('Total solution fixed demand:', solution_total_fixed_demand)
    print('Total solution normally on load:', solution_total_normally_on_load)
    print('Total solution scheduled load:', solution_total_scheduled_load)
    print('Total solution losses:', solution_total_losses)
    print('Total solution MNSP losses:', solution_total_mnsp_losses)
    print('\n')
    print('Total initial losses initial:', initial_total_losses)
    print('Total initial ADE:', initial_total_ade)
    print('Total initial DF:', initial_total_df)
    print('Total initial generation:', initial_total_generation)
    print('Total initial scheduled load:', initial_total_scheduled_load)
    print('Total initial total demand:', initial_total_demand)
    print('Total initial MNSP loss:', initial_total_mnsp_losses)


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_directory, 2019, 10, 6, 123)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Check results to ensure demand calculations correspond with NEMDE solution
    # perform_checks(data_directory, n=20)

    a1 = get_solution_region_net_export(cdata, 'SA1')
