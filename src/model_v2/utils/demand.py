"""
Demand calculations

Observations:
TotalClearedDemand = TotalGeneration

TotalClearedDemand = TotalFixedDemand + TotalRegionLoss + TotalScheduledLoad + TotalInterconnectorLoss - TotalMNSPLoss

TotalFixedDemand = TotalInitialDemand - TotalInitialScheduledLoad + TotalInitialADE + TotalInitialDeltaForecast
                   - TotalInitialRegionLoss + TotalInitialMNSPLoss
"""
# initial_total_demand - initial_total_scheduled_load + initial_total_ade + initial_total_df
#              - initial_total_losses + initial_total_mnsp_losses

import os
import json

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


def get_total_ade(data) -> float:
    """Get total aggregate dispatch error"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_collection_initial_condition_attribute(data, i, 'ADE', float)

    return total


def get_total_df(data) -> float:
    """Get total demand forecast increment"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_period_collection_attribute(data, i, '@DF', float)

    return total


def get_initial_total_losses(data) -> float:
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


def get_solution_total_losses(data):
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


def get_solution_total_fixed_demand(data):
    """Get total fixed demand"""

    # Get regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_solution_attribute(data, i, '@FixedDemand', float)

    return total


def get_solution_total_cleared_demand(data):
    """Get total cleared demand"""

    # Get regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_solution_attribute(data, i, '@ClearedDemand', float)

    return total


def get_solution_total_generation(data):
    """Get total energy target for all generators"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'GENERATOR':
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_solution_total_normally_on_load(data):
    """Get total energy target for normally on loads"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'NORMALLY_ON_LOAD':
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_solution_total_scheduled_load(data):
    """Get total energy target for scheduled loads"""

    # All traders
    traders = get_trader_index(data)

    total = 0
    for i in traders:
        if lookup.get_trader_collection_attribute(data, i, '@TraderType', str) == 'LOAD':
            total += lookup.get_trader_solution_attribute(data, i, '@EnergyTarget', float)

    return total


def get_initial_total_demand(data):
    """Get total initial demand"""

    # All regions
    regions = get_region_index(data)

    total = 0
    for i in regions:
        total += lookup.get_region_collection_initial_condition_attribute(data, i, 'InitialDemand', float)

    return total


def get_initial_total_mnsp_losses(data) -> float:
    """Get total initial MNSP loss"""

    # All MNSPs
    mnsps = get_mnsp_index(data)

    # NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.InterconnectorPeriodCollection.InterconnectorPeriod[2].@FromRegionLF

    total = 0
    for i in mnsps:
        to_region_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLF', float)
        from_region_lf = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLF', float)

        to_region_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFExport', float)
        to_region_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@ToRegionLFImport', float)

        from_region_lf_export = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFExport', float)
        from_region_lf_import = lookup.get_interconnector_period_collection_attribute(data, i, '@FromRegionLFImport', float)

        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(data, i, 'InitialMW', float)
        initial_loss_estimate = calculations.get_interconnector_loss_estimate(data, i, initial_mw)
        export_flow = abs(initial_mw) + initial_loss_estimate

        total += (export_flow * (1 - to_region_lf_export)) + (export_flow * (1 - from_region_lf_import))

    return total


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_directory, 2019, 10, 10, 10)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    solution_total_generation = get_solution_total_generation(cdata)
    solution_total_cleared_demand = get_solution_total_cleared_demand(cdata)
    solution_total_fixed_demand = get_solution_total_fixed_demand(cdata)
    solution_total_normally_on_load = get_solution_total_normally_on_load(cdata)
    solution_total_scheduled_load = get_solution_total_scheduled_load(cdata)
    solution_total_losses = get_solution_total_losses(cdata)
    solution_total_mnsp_losses = get_solution_total_mnsp_losses(cdata)
    initial_total_losses = get_initial_total_losses(cdata)
    initial_total_ade = get_total_ade(cdata)
    initial_total_df = get_total_df(cdata)
    initial_total_generation = get_initial_total_generation(cdata)
    initial_total_scheduled_load = get_initial_total_scheduled_load(cdata)
    initial_total_demand = get_initial_total_demand(cdata)
    initial_total_mnsp_losses = get_initial_total_mnsp_losses(cdata)

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

    check = (initial_total_demand - initial_total_scheduled_load + initial_total_ade + initial_total_df
             - initial_total_losses + initial_total_mnsp_losses)

    print('Initial demand estimate:', check)
