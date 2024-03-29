"""Check NEMDE solution components and calculations"""

import json
import calendar

import numpy as np
import pandas as pd

from nemde.errors import CasefileLookupError
from nemde.core.casefile import lookup
from nemde.core.casefile import algorithms


def get_region_initial_interconnector_loss(data, region_id) -> float:
    """
    Get initial loss allocated to each region. Losses allocated in proportion
    to LossShare attribute.

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    Returns
    -------
    region_interconnector_loss : float
        Total loss allocated to region arising from interconnectors
        connections
    """

    interconnectors = lookup.get_interconnector_index(data)

    # Initialise allocated interconnector losses
    region_interconnector_loss = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegion', func=str)

        to_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegion', func=str)

        mnsp_status = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@MNSP', func=str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(
            data=data, interconnector_id=i, attribute='InitialMW', func=float)

        # Compute loss
        loss = algorithms.get_interconnector_loss_estimate(
            data=data, interconnector_id=i, flow=initial_mw)

        loss_share = lookup.get_interconnector_loss_model_attribute(
            data=data, interconnector_id=i, attribute='@LossShare', func=float)

        # TODO: Using InitialMW seems best model for now - real NEMDE does 2
        # runs. Perhaps second run identifies flow direction has changed and
        # updates loss share. Seems like NEMDE implementation is incorrect.
        # Discrepancy arises even when considering InitialMW flow. Flow at end
        # of the dispatch interval shouldn't impact fixed demand at the start
        # of the interval, but it does.

        # MNSP losses applied to sending end - based on InitialMW
        if mnsp_status == '1':
            if initial_mw >= 0:
                mnsp_loss_share = 1
            else:
                mnsp_loss_share = 0

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                region_interconnector_loss += loss * mnsp_loss_share
            else:
                region_interconnector_loss += loss * loss_share

        # Positive flow indicates import to ToRegion (take negative to get
        # export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if mnsp_status == '1':
                region_interconnector_loss += loss * (1 - mnsp_loss_share)
            else:
                region_interconnector_loss += loss * (1 - loss_share)

        else:
            pass

    return region_interconnector_loss


def get_region_initial_mnsp_loss_estimate(data, region_id) -> float:
    """
    Get estimate of MNSP loss allocated to given region

    MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad)
    where load is varied at the connection point. Must compute the load the
    connection point for the MNSP - this will be positive or negative
    (i.e. generation) depending on the direction of flow over the
    interconnector.

    From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to
    compute the effective load at the connection point in order to compute the
    loss. Note the loss may be positive or negative depending on the MLF and
    the effective load at the connection point.

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    Returns
    -------
    total : float
        Total loss allocated to region arising from MNSP connections
    """

    mnsps = lookup.get_mnsp_index(data)

    # Initialise total MNSP loss allocated to region
    total = 0
    for i in mnsps:
        from_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegion', func=str)

        to_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegion', func=str)

        if region_id not in [from_region, to_region]:
            continue

        # Initial MW and solution flow
        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(
            data=data, interconnector_id=i, attribute='InitialMW', func=float)

        to_lf_export = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegionLFExport', func=float)

        to_lf_import = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegionLFImport', func=float)

        from_lf_import = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegionLFImport', func=float)
        from_lf_export = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegionLFExport', func=float)

        # Initial loss estimate over interconnector
        loss = algorithms.get_interconnector_loss_estimate(
            data=data, interconnector_id=i, flow=initial_mw)

        # MNSP loss share - loss applied to sending end
        if initial_mw >= 0:
            # Total loss allocated to FromRegion
            mnsp_loss_share = 1
        else:
            # Total loss allocated to ToRegion
            mnsp_loss_share = 0

        if initial_mw >= 0:
            if from_region == region_id:
                export_flow = initial_mw + (mnsp_loss_share * loss)
                mnsp_loss = (from_lf_export - 1) * export_flow
            elif to_region == region_id:
                import_flow = initial_mw - ((1 - mnsp_loss_share) * loss)

                # Multiply by -1 because flow from MNSP connection point to
                # ToRegion can be considered a negative load MLF describes how
                # loss changes with an incremental change to load at the
                # connection point. So when flow is positive (e.g. flow from
                # TAS to VIC) then must consider a negative load (i.e. a
                # generator) when computing MNSP losses.
                mnsp_loss = (to_lf_import - 1) * import_flow * -1

            else:
                raise Exception('Unexpected region:', region_id)

        else:
            if from_region == region_id:
                # Flow is negative, so add the allocated MNSP loss to get
                # total import flow
                import_flow = initial_mw + (mnsp_loss_share * loss)

                # Import flow is negative, so is considered as generation at
                # the connection point (negative load)
                mnsp_loss = (from_lf_import - 1) * import_flow

            elif to_region == region_id:
                # Flow is negative, subtract allocated MNSP loss to get total
                # export flow
                export_flow = initial_mw - ((1 - mnsp_loss_share) * loss)

                # Export flow is negative. Multiply by -1 so can be considered
                # as load at the connection point.
                mnsp_loss = (to_lf_export - 1) * export_flow * -1

            else:
                raise Exception('Unexpected region:', region_id)

        # Add to total MNSP loss allocated to a given region
        total += mnsp_loss

    return total


def get_region_initial_scheduled_load(data, region_id) -> float:
    """
    Get scheduled load in a given region - based NEMDE InitialMW values

    Parameters
    ----------
    data : dict
        NEMDE casefile

    regiond_id : str
        NEM region

    Returns
    -------
    scheduled_load : float
        Total scheduled load in given region at start of dispatch interval
    """

    traders = lookup.get_trader_index(data)

    # Initialise sum for region initial scheduled load
    scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@TraderType', func=str)

        semi_dispatch = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@SemiDispatch', func=str)

        trader_region = lookup.get_trader_period_collection_attribute(
            data=data, trader_id=i, attribute='@RegionID', func=str)

        # Conditions for a scheduled load to be included in the region count
        is_load = trader_type in ['LOAD', 'NORMALLY_ON_LOAD']
        is_scheduled = semi_dispatch == '0'
        is_in_region = trader_region == region_id

        if is_load and is_scheduled and is_in_region:
            scheduled_load += lookup.get_trader_collection_initial_condition_attribute(
                data=data, trader_id=i, attribute='InitialMW', func=float)

    return scheduled_load


def get_region_solution_interconnector_loss(data, region_id, intervention) -> float:
    """
    Get loss allocated to each region

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '0'=no inverention constraints, '1'=intervention
        constraints invoked

    Returns
    -------
    region_interconnector_loss : float
        Total loss allocated to given region from interconnectors at end of
        dispatch interval
    """

    interconnectors = lookup.get_interconnector_index(data)

    # Allocated interconnector losses
    region_interconnector_loss = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegion', func=str)

        to_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegion', func=str)

        mnsp_status = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@MNSP', func=str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        flow = lookup.get_interconnector_solution_attribute(
            data=data, interconnector_id=i, attribute='@Flow', func=float,
            intervention=intervention)

        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(
            data=data, interconnector_id=i, attribute='InitialMW', func=float)

        loss = lookup.get_interconnector_solution_attribute(
            data=data, interconnector_id=i, attribute='@Losses', func=float,
            intervention=intervention)

        loss_share = lookup.get_interconnector_loss_model_attribute(
            data=data, interconnector_id=i, attribute='@LossShare', func=float)

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            # Loss applied to sending end if MNSP
            if (mnsp_status == '1') and (initial_mw >= 0):
                region_interconnector_loss += loss

            # Loss applied to ToRegion (no loss applied to 'from' region)
            elif (mnsp_status == '1') and (initial_mw < 0):
                pass

            # Use loss share to proportion loss if not an MNSP
            elif mnsp_status == '0':
                region_interconnector_loss += loss * loss_share

            else:
                raise Exception('Unhandled case:', mnsp_status, flow)

        # Positive flow = ToRegion importing (take negative to get export from ToRegion)
        elif region_id == to_region:
            # Loss applied to sending end if MNSP
            if (mnsp_status == '1') and (initial_mw < 0):
                region_interconnector_loss += loss

            # Loss should be applied to 'from' region if flow direction is positive
            elif (mnsp_status == '1') and (initial_mw >= 0):
                pass

            # Proportion loss according to LossShare if not an MNSP
            elif mnsp_status == '0':
                region_interconnector_loss += loss * (1 - loss_share)

            else:
                raise Exception('Unhandled case:', mnsp_status, flow, initial_mw)

        # Region is not connected to the interconnector
        else:
            pass

    return region_interconnector_loss


def get_region_solution_mnsp_loss_estimate(data, region_id, intervention) -> float:
    """
    Get estimate of MNSP loss allocated to given region

    MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad)
    where load is varied at the connection point. Must compute load at the
    connection point for the MNSP - this will be positive or negative
    (i.e. generation) depending on the direction of flow over the
    interconnector.

    From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to
    compute the effective load at the connection point in order to compute the
    loss. Note the loss may be positive or negative depending on the MLF and
    the effective load at the connection point.

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '0'=no inverention constraints, '1'=intervention
        constraints invoked

    Returns
    -------
    total : float
        Total loss (MW) allocated to region arising from MNSP connections
    """

    # All interconnectors
    mnsps = lookup.get_mnsp_index(data)

    # Initial total loss
    total = 0
    for i in mnsps:
        from_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegion', func=str)

        to_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegion', func=str)

        if region_id not in [from_region, to_region]:
            continue

        # Solution flow
        flow = lookup.get_interconnector_solution_attribute(
            data=data, interconnector_id=i, attribute='@Flow', func=float,
            intervention=intervention)

        initial_mw = lookup.get_interconnector_collection_initial_condition_attribute(
            data=data, interconnector_id=i, attribute='InitialMW', func=float)

        to_lf_export = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegionLFExport', func=float)

        to_lf_import = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegionLFImport', func=float)

        from_lf_import = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegionLFImport', func=float)

        from_lf_export = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegionLFExport', func=float)

        # Loss over interconnector
        loss = lookup.get_interconnector_solution_attribute(
            data=data, interconnector_id=i, attribute='@Losses', func=float,
            intervention=intervention)

        # Loss allocated to sending end ('FromRegion') if flow is positive
        if (region_id == from_region) and (flow >= 0) and (initial_mw >= 0):
            export_flow = flow + loss
            mnsp_loss = (from_lf_export - 1) * export_flow

        elif (region_id == from_region) and (flow >= 0) and (initial_mw < 0):
            export_flow = flow
            mnsp_loss = (from_lf_export - 1) * export_flow

        elif (region_id == from_region) and (flow < 0) and (initial_mw >= 0):
            import_flow = flow + loss
            mnsp_loss = (from_lf_import - 1) * import_flow

        elif (region_id == from_region) and (flow < 0) and (initial_mw < 0):
            import_flow = flow
            mnsp_loss = (from_lf_import - 1) * import_flow

        # ToRegion MNSP loss
        elif (region_id == to_region) and (flow >= 0) and (initial_mw >= 0):
            import_flow = flow
            mnsp_loss = (to_lf_import - 1) * import_flow * -1

        elif (region_id == to_region) and (flow >= 0) and (initial_mw < 0):
            import_flow = flow - loss
            mnsp_loss = (to_lf_import - 1) * import_flow * -1

        elif (region_id == to_region) and (flow < 0) and (initial_mw >= 0):
            export_flow = flow
            mnsp_loss = (to_lf_export - 1) * export_flow * -1

        elif (region_id == to_region) and (flow < 0) and (initial_mw < 0):
            export_flow = flow - loss
            mnsp_loss = (to_lf_export - 1) * export_flow * -1

        else:
            mnsp_loss = 0

        # Add to total MNSP loss allocated to a given region
        total += mnsp_loss

    return total


def get_region_solution_net_interconnector_export(data, region_id, intervention) -> float:
    """
    Get net export over interconnectors for a given region - based on NEMDE
    solution

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '0'=no inverention constraints, '1'=intervention
        constraints invoked

    Returns
    -------
    interconnector_export : float
        Total export out of region over interconnectors
    """

    interconnectors = lookup.get_interconnector_index(data)

    # Initialise total export flow
    interconnector_export = 0
    for i in interconnectors:
        from_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@FromRegion', func=str)

        to_region = lookup.get_interconnector_period_collection_attribute(
            data=data, interconnector_id=i, attribute='@ToRegion', func=str)

        if region_id not in [from_region, to_region]:
            continue

        # Interconnector flow from solution
        flow = lookup.get_interconnector_solution_attribute(
            data=data, interconnector_id=i, attribute='@Flow', func=float,
            intervention=intervention)

        # Positive flow indicates export from FromRegion
        if region_id == from_region:
            interconnector_export += flow

        # Positive flow = import for ToRegion (take negative to get export from ToRegion)
        elif region_id == to_region:
            interconnector_export -= flow

        else:
            pass

    return interconnector_export


def get_region_solution_scheduled_load(data, region_id, intervention) -> float:
    """
    Get scheduled load in a given region - based on NEMDE solution

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '0'=no inverention constraints, '1'=intervention
        constraints invoked

    Returns
    -------
    scheduled_load : float
        Total scheduled load for a given region
    """

    traders = lookup.get_trader_index(data)

    # Initialise scheduled load for given region
    scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@TraderType', func=str)

        semi_dispatch = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@SemiDispatch', func=str)

        trader_region = lookup.get_trader_period_collection_attribute(
            data=data, trader_id=i, attribute='@RegionID', func=str)

        # Conditions that must be satisified for load to count towards region total
        is_load = trader_type in ['LOAD', 'NORMALLY_ON_LOAD']
        is_scheduled = semi_dispatch == '0'
        is_in_region = trader_region == region_id

        if is_load and is_scheduled and is_in_region:
            scheduled_load += lookup.get_trader_solution_attribute(
                data=data, trader_id=i, attribute='@EnergyTarget',
                func=float, intervention=intervention)

    return scheduled_load


def check_aggregate_cleared_demand(data, intervention) -> dict:
    """
    Check TotalClearedDemand = TotalGeneration

    Parameters
    ----------
    data : dict
        NEMDE casefile

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        difference between expected and observed value obtained from NEMDE
        solution.
    """

    # All traders
    traders = lookup.get_trader_index(data=data)

    total_generation = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@TraderType', func=str)

        if trader_type == 'GENERATOR':
            total_generation += lookup.get_trader_solution_attribute(
                data=data, trader_id=i, attribute='@EnergyTarget', func=float,
                intervention=intervention)

    # All regions
    regions = lookup.get_region_index(data=data)

    total_cleared_demand = 0
    for i in regions:
        total_cleared_demand += lookup.get_region_solution_attribute(
            data=data, region_id=i, attribute='@ClearedDemand', func=float,
            intervention=intervention)

    # Container for output
    out = {
        'difference': total_generation - total_cleared_demand,
        'abs_difference': abs(total_generation - total_cleared_demand)
    }

    return out


def check_aggregate_fixed_demand(data, intervention) -> dict:
    """
    Check: TotalFixedDemand + Losses = TotalClearedDemand

    Parameters
    ----------
    data : dict
        NEMDE casefile

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        difference between expected and observed value obtained from NEMDE
        solution.
    """

    # All regions
    regions = lookup.get_region_index(data=data)

    # Total fixed demand
    fixed_demand = 0
    for i in regions:
        fixed_demand += lookup.get_region_solution_attribute(
            data=data, region_id=i, attribute='@FixedDemand', func=float,
            intervention=intervention)

    # All interconnectors
    interconnectors = lookup.get_interconnector_index(data=data)

    # Total interconnector
    interconnector_loss = 0
    for i in interconnectors:
        interconnector_loss += lookup.get_interconnector_solution_attribute(
            data=data, interconnector_id=i, attribute='@Losses', func=float,
            intervention=intervention)

    # All regions
    regions = lookup.get_region_index(data=data)
    mnsp_loss = 0
    for i in regions:
        mnsp_loss += get_region_solution_mnsp_loss_estimate(
            data=data, region_id=i, intervention=intervention)

    # Total actual cleared demand (from NEMDE solution)
    actual = 0
    for i in regions:
        actual += lookup.get_region_solution_attribute(
            data=data, region_id=i, attribute='@ClearedDemand', func=float,
            intervention=intervention)

    # All traders
    traders = lookup.get_trader_index(data)

    # Total scheduled demand
    scheduled_load = 0
    for i in traders:
        trader_type = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@TraderType', func=str)

        semi_dispatch = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@SemiDispatch', func=str)

        # Conditions to check if trader is a scheduled load
        is_load = trader_type in ['LOAD', 'NORMALLY_ON_LOAD']
        is_scheduled = semi_dispatch == '0'

        if is_load and is_scheduled:
            scheduled_load += lookup.get_trader_solution_attribute(
                data=data, trader_id=i, attribute='@EnergyTarget', func=float,
                intervention=intervention)

    # Calculated cleared demand
    cleared_demand = fixed_demand + interconnector_loss + mnsp_loss + scheduled_load

    # Container for output
    out = {
        'calculated': cleared_demand,
        'actual': actual,
        'difference': cleared_demand - actual,
        'abs_difference': abs(cleared_demand - actual)
    }

    return out


def check_region_cleared_demand(data, region_id, intervention) -> dict:
    """
    Check region cleared demand calculation

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        difference between expected and observed value obtained from NEMDE
        solution.
    """

    # Fixed demand from NEMDE solution
    fixed_demand = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@FixedDemand', func=float,
        intervention=intervention)

    # Loss allocated to region based on interconnector flow
    region_interconnector_loss = get_region_solution_interconnector_loss(
        data=data, region_id=region_id, intervention=intervention)

    # Total scheduled load
    total_scheduled_load = get_region_solution_scheduled_load(
        data=data, region_id=region_id, intervention=intervention)

    # MNSP loss estimate
    mnsp_loss = get_region_solution_mnsp_loss_estimate(
        data=data, region_id=region_id, intervention=intervention)

    # Cleared demand calculation
    cleared_demand = (fixed_demand + region_interconnector_loss
                      + total_scheduled_load + mnsp_loss)

    # Cleared demand from NEMDE solution
    actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@ClearedDemand', func=float,
        intervention=intervention)

    # Container for output
    out = {
        'calculated': cleared_demand,
        'actual': actual,
        'difference': cleared_demand - actual,
        'abs_difference': abs(cleared_demand - actual)
    }

    return out


def check_region_fixed_demand(data, region_id, intervention) -> dict:
    """
    Check region fixed demand calculation

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        Difference between expected and observed value obtained from NEMDE
        solution.
    """

    # Fixed demand calculation terms
    demand = lookup.get_region_collection_initial_condition_attribute(
        data=data, region_id=region_id, attribute='InitialDemand', func=float)

    ade = lookup.get_region_collection_initial_condition_attribute(
        data=data, region_id=region_id, attribute='ADE', func=float)

    delta_forecast = lookup.get_region_period_collection_attribute(
        data=data, region_id=region_id, attribute='@DF', func=float)

    # Total scheduled load at start of dispatch interval
    total_scheduled_load = get_region_initial_scheduled_load(
        data=data, region_id=region_id)

    # Region interconnector loss
    region_interconnector_loss = get_region_initial_interconnector_loss(
        data=data, region_id=region_id)

    # MNSP loss estimate
    mnsp_loss = get_region_initial_mnsp_loss_estimate(data=data, region_id=region_id)

    # Fixed demand calculation
    fixed_demand = (demand - total_scheduled_load + ade +
                    delta_forecast - region_interconnector_loss - mnsp_loss)

    # Fixed demand from NEMDE solution
    actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@FixedDemand', func=float,
        intervention=intervention)

    # Container for output
    out = {
        'calculated': fixed_demand,
        'actual': actual,
        'difference': fixed_demand - actual,
        'abs_difference': abs(fixed_demand - actual)
    }

    return out


def check_region_net_export(data, region_id, intervention) -> dict:
    """Check net export calculation for a given region"""

    # Net export over interconnectors connected to region
    interconnector_export = get_region_solution_net_interconnector_export(
        data=data, region_id=region_id, intervention=intervention)

    # Loss allocated to region due to interconnector flow
    region_interconnector_loss = get_region_solution_interconnector_loss(
        data=data, region_id=region_id, intervention=intervention)

    # MNSP loss estimate
    mnsp_loss = get_region_solution_mnsp_loss_estimate(
        data=data, region_id=region_id, intervention=intervention)

    # Calculated net export
    net_export = interconnector_export + region_interconnector_loss + mnsp_loss

    # Net export from solution
    actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@NetExport', func=float,
        intervention=intervention)

    # Container for outputs comparing calculated and actual solutions
    out = {
        'model': net_export,
        'actual': actual,
        'difference': net_export - actual,
        'abs_difference': abs(net_export - actual)
    }

    return out


def check_region_power_balance(data, region_id, intervention) -> dict:
    """
    Check power balance for a given region

    FixedDemand + Load + NetExport = DispatchedGeneration

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        Difference between expected and observed value obtained from NEMDE
        solution.
    """

    # Fixed demand
    fixed_demand = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@FixedDemand', func=float,
        intervention=intervention)

    # Dispatched load
    load = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@DispatchedLoad', func=float,
        intervention=intervention)

    # Net export
    net_export = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@NetExport', func=float,
        intervention=intervention)

    # Dispatched generation
    generation = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@DispatchedGeneration',
        func=float, intervention=intervention)

    # Power balance expression (should = 0)
    power_balance = fixed_demand + load + net_export - generation

    # Container for output
    out = {
        'difference': power_balance,
        'abs_difference': abs(power_balance)
    }

    return out


def check_region_dispatched_generation(data, region_id, intervention) -> dict:
    """
    Check region dispatched generation calculation

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        Difference between expected and observed value obtained from NEMDE
        solution.
    """

    # All traders
    traders = lookup.get_trader_index(data)

    total = 0
    for i in traders:
        trader_region = lookup.get_trader_period_collection_attribute(
            data=data, trader_id=i, attribute='@RegionID', func=str)

        trader_type = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@TraderType', func=str)

        if (trader_region == region_id) and (trader_type == 'GENERATOR'):
            total += lookup.get_trader_solution_attribute(
                data=data, trader_id=i, attribute='@EnergyTarget', func=float,
                intervention=intervention)

    # Dispatched generation from region solution
    generation = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@DispatchedGeneration',
        func=float, intervention=intervention)

    # Container for output
    out = {
        'calculated': total,
        'actual': generation,
        'difference': total - generation,
        'abs_difference': abs(total - generation)
    }

    return out


def check_region_dispatched_load(data, region_id, intervention) -> dict:
    """
    Check region dispatched load calculation

    Parameters
    ----------
    data : dict
        NEMDE casefile

    region_id : str
        NEM region

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        Difference between expected and observed value obtained from NEMDE
        solution.
    """

    # All traders
    traders = lookup.get_trader_index(data=data)

    # Initialise total dispatched load
    total = 0
    for i in traders:
        trader_region = lookup.get_trader_period_collection_attribute(
            data=data, trader_id=i, attribute='@RegionID', func=str)

        trader_type = lookup.get_trader_collection_attribute(
            data=data, trader_id=i, attribute='@TraderType', func=str)

        # Only loads in given region contribute to total region dispatch load
        is_load = trader_type in ['LOAD', 'NORMALLY_ON_LOAD']
        is_in_region = trader_region == region_id

        if is_load and is_in_region:
            total += lookup.get_trader_solution_attribute(
                data=data, trader_id=i, attribute='@EnergyTarget', func=float,
                intervention=intervention)

    # Dispatched load from region solution
    actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@DispatchedLoad', func=float,
        intervention=intervention)

    # Container for output
    out = {
        'calculated': total,
        'actual': actual,
        'difference': total - actual,
        'abs_difference': abs(total - actual)
    }

    return out


def check_generic_constraint_rhs_calculation(data, constraint_id, intervention) -> float:
    """
    Check generic constraint RHS calculation

    Parameters
    ----------
    data : dict
        NEMDE casefile

    constraint_id : str
        Generic constraint ID

    intervention : str
        Intervention flag. '1'=intervention constraints included, '0'=no
        inverention constraints.

    Returns
    -------
    out : dict
        Difference between RHS defined in NEMDE inputs and RHS given in NEMDE
        constraint solution
    """

    # Generic constraints
    constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs')
                   .get('GenericConstraintCollection')
                   .get('GenericConstraint'))

    for i in constraints:
        if i['@ConstraintID'] == constraint_id:
            # NEMDE input
            nemde_input = lookup.get_generic_constraint_collection_attribute(
                data=data, constraint_id=constraint_id, attribute='@RHS', func=float)

            # Constraint solution
            solution = lookup.get_generic_constraint_solution_attribute(
                data=data, constraint_id=constraint_id, attribute='@RHS',
                func=float, intervention=intervention)

            # Difference between input and RHS value in NEMDE solution
            difference = nemde_input - solution

            out = {
                'difference': difference,
                'abs_difference': abs(difference)
            }
            return out

    raise CasefileLookupError('Unable to find constraint:', constraint_id, intervention)
