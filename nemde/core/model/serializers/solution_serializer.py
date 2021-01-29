"""
Serializer used to extract solution from Pyomo model and convert to JSON
"""

import nemde.core.casefile import lookup


def get_region_total_dispatch(m, region_id, trade_type):
    """
    Compute total dispatch in a given region rounded to two decimal places
    """

    total = sum(m.V_TRADER_TOTAL_OFFER[i, j].value
                for i, j in m.S_TRADER_OFFERS
                if (j == trade_type) and (m.P_TRADER_REGION[i] == region_id))

    return total


def get_trader_dispatch_target(model, trader_id, trade_type):
    """
    Extract dispatch target for a given unit. Return 0 trade_type doesn't
    exist for a given trader_id
    """

    if (trader_id, trade_type) in model.V_TRADER_TOTAL_OFFER.keys():
        return model.V_TRADER_TOTAL_OFFER[trader_id, trade_type].value
    else:
        return 0.0


def get_energy_offer(model, trader_id):
    """Get energy offer"""

    if model.P_TRADER_TYPE[trader_id] == 'GENERATOR':
        return 'ENOF'
    elif model.P_TRADER_TYPE[trader_id] in ['LOAD', 'NORMALLY_ON_LOAD']:
        return 'LDOF'
    else:
        raise LookupError('P_TRADER_TYPE not recognised:', model.P_TRADER_TYPE[trader_id])


def get_trader_violation(model, trader_id, trade_type):
    """Get trader violation"""

    if (trader_id, trade_type) in model.V_TRADER_TOTAL_OFFER.keys():
        return sum(model.V_CV_TRADER_OFFER[trader_id, trade_type, i].value
                   for i in range(1, 11))
    else:
        return 0.0


def get_constraint_deficit(model, constraint_id):
    """Get constraint ID"""

    if model.P_GC_TYPE[constraint_id] == 'EQ':
        return model.V_CV_RHS[constraint_id].value + model.V_CV_LHS[constraint_id].value
    elif model.P_GC_TYPE[constraint_id] in ['LE', 'GE']:
        return model.V_CV[constraint_id].value
    else:
        raise LookupError('Unrecognised constraint type:', model.P_GC_TYPE[constraint_id])


def get_total_uigf_violation(model):
    """Total UIGF violation for semi-scheduled plant"""

    return sum(v.value for v in model.V_CV_TRADER_UIGF_SURPLUS.values())


def get_total_interconnector_violation(model):
    """Total interconnector violation"""

    # Total forward and reverse interconnector violation
    forward = sum(v.value for v in model.V_CV_INTERCONNECTOR_FORWARD.values())
    reverse = sum(v.value for v in model.V_CV_INTERCONNECTOR_REVERSE.values())

    return forward + reverse


def get_total_generic_constraint_violation(model):
    """Get total generic constraint violation"""

    equality_lhs = sum(v.value for v in model.V_CV_LHS.values())
    equality_rhs = sum(v.value for v in model.V_CV_RHS.values())
    violation = sum(v.value for v in model.V_CV.values())

    return equality_lhs + equality_rhs + violation


def get_total_ramp_rate_violation(model):
    """Total ramp rate violation"""

    ramp_up = sum(v.value for v in model.V_CV_TRADER_RAMP_UP.values())
    ramp_dn = sum(v.value for v in model.V_CV_TRADER_RAMP_DOWN.values())

    return ramp_up + ramp_dn


def get_total_unit_mw_capacity_violation(model):
    """Total MW capacity violation for dispatchable plant"""

    return sum(v.value for v in model.V_CV_TRADER_CAPACITY.values())


def get_total_fast_start_violation(model):
    """Total fast start unit profile violation"""

    lhs = sum(v.value for v in model.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS.values())
    rhs = sum(v.value for v in model.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS.values())
    profile = sum(v.value for v in model.V_CV_TRADER_INFLEXIBILITY_PROFILE.values())

    return lhs + rhs + profile


def get_total_mnsp_ramp_rate_violation(model):
    """Get total MNSP ramp rate violation"""

    ramp_up = sum(v.value for v in model.V_CV_MNSP_RAMP_UP.values())
    ramp_down = sum(v.value for v in model.V_CV_MNSP_RAMP_DOWN.values())

    return ramp_up + ramp_down


def get_total_mnsp_offer_violation(model):
    """Get total MNSP offer violation"""

    return sum(v.value for v in model.V_CV_MNSP_OFFER.values())


def get_total_mnsp_capacity_violation(model):
    """Get total MNSP capacity violation"""

    return sum(v.value for v in model.V_CV_MNSP_CAPACITY.values())


def get_constraint_solution(model, constraint_id):
    """Extract generic constraint solution"""

    rhs_model = model.P_GC_RHS[constraint_id]
    deficit_model = get_constraint_deficit(model=model, constraint_id=constraint_id)

    output = {
        "@ConstraintID": constraint_id,
        # "@Version": "20200817000000_1",
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        # "@Intervention": "0",
        "@RHS": rhs,
        # "@MarginalValue": "0",
        "@Deficit": deficit
    }

    return output


def get_constraint_solution_validation(model, constraint_id, data):
    """Extract generic constraint solution"""

    # NEMDE solution
    rhs_actual = lookup.get_generic_constraint_solution_attribute(
        data=data, constraint_id=constraint_id, attribute='@RHS', func=float)

    deficit_actual = lookup.get_generic_constraint_solution_attribute(
        data=data, constraint_id=constraint_id, attribute='@Deficit', func=float)

    # Model solution
    rhs_model = model.P_GC_RHS[constraint_id]
    deficit_model = get_constraint_deficit(model=model, constraint_id=constraint_id)

    # Comparison
    rhs_comparison = {
        'actual': rhs_actual,
        'model': rhs_model,
        'difference': rhs_model - rhs_actual,
        'abs_difference': abs(rhs_model - rhs_actual)
    }

    deficit_comparison = {
        'actual': deficit_actual,
        'model': deficit_model,
        'difference': deficit_model - deficit_actual,
        'abs_difference': abs(deficit_model - deficit_actual)
    }

    output = {
        "@ConstraintID": constraint_id,
        # "@Version": "20200817000000_1",
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        # "@Intervention": "0",
        "@RHS": rhs_comparison,
        # "@MarginalValue": "0",
        "@Deficit": deficit_comparison
    }

    return output


def get_trader_solution(model, trader_id):
    """Extract solution for a given trader"""

    # Energy offer target
    energy_offer = get_energy_offer(model=model, trader_id=trader_id)
    energy_target = get_trader_dispatch_target(
        model=model, trader_id=trader_id, trade_type=energy_offer)

    # FCAS targets
    trade_types = ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']
    fcas = {
        i: get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type=i)
        for i in trade_types
    }

    # FCAS violation
    violation = {
        i: get_trader_violation(model=model, trader_id=trader_id, trade_type=i)
        for i in trade_types
    }

    output = {
        "@TraderID": trader_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@EnergyTarget": energy_target,
        "@R6Target": fcas['R6SE'],
        "@R60Target": fcas['R60S'],
        "@R5Target": fcas['R5MI'],
        "@R5RegTarget": fcas['R5RE'],
        "@L6Target": fcas['L6SE'],
        "@L60Target": fcas['L60S'],
        "@L5Target": fcas['L5MI'],
        "@L5RegTarget": fcas['L5RE'],
        # "@R6Price": "0",
        # "@R60Price": "0",
        # "@R5Price": "0",
        # "@R5RegPrice": "0",
        # "@L6Price": "0",
        # "@L60Price": "0",
        # "@L5Price": "0",
        # "@L5RegPrice": "0",
        "@R6Violation": violation['R6SE'],
        "@R60Violation": violation['R60S'],
        "@R5Violation": violation['R5MI'],
        "@R5RegViolation": violation['R5RE'],
        "@L6Violation": violation['L6SE'],
        "@L60Violation": violation['L60S'],
        "@L5Violation": violation['L5MI'],
        "@L5RegViolation": violation['L5RE'],
        # "@FSTargetMode": "0",
        # "@RampUpRate": "720",
        # "@RampDnRate": "720",
        # "@RampPrice": "0",
        # "@RampDeficit": "0"
    }

    return output


def get_trader_solution_validation(model, trader_id, data):
    """Extract solution for a given trader"""

    # Energy offer target
    energy_offer = get_energy_offer(model=model, trader_id=trader_id)
    energy_target_model = get_trader_dispatch_target(
        model=model, trader_id=trader_id, trade_type=energy_offer)

    energy_target_actual = lookup.get_trader_solution_attribute(
        data=data, trader_id=trader_id, attribute='@EnergyTarget', func=float)

    # Compare energy target
    energy_target_comparison = {
        'model': energy_target_model,
        'actual': energy_target_actual,
        'difference': energy_target_model - energy_target_actual,
        'abs_difference': abs(energy_target_model - energy_target_actual)
    }

    # FCAS trade types
    trade_types = {
        'R6SE': '@R6Target',
        'R60S': '@R60Target',
        'R5MI': '@R5Target',
        'R5RE': '@R5RegTarget',
        'L6SE': '@L6Target',
        'L60S': '@L60Target',
        'L5MI': '@L5Target',
        'L5RE': '@L5RegTarget'
    }

    fcas_model = {
        i: get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type=i)
        for i in trade_types.keys()
    }

    fcas_actual = {
        k: lookup.get_trader_solution_attribute(
            data=data, trader_id=trader_id, attribute=v trade_type=i)
        for k, v in trade_types.items()
    }

    fcas_comparison = {
        i: {
            'model': fcas_model[k],
            'actual': fcas_actual[k],
            'difference': fcas_model[k] - fcas_actual[k],
            'abs_difference': abs(fcas_model[k] - fcas_actual[])
        }
        for i in trade_types.keys()
    }

    # FCAS violation
    violation_types = {
        'R6SE': '@R6Violation',
        'R60S': '@R60Violation',
        'R5MI': '@R5Violation',
        'R5RE': '@R5RegViolation',
        'L6SE': '@L6Violation',
        'L60S': '@L60Violation',
        'L5MI': '@L5Violation',
        'L5RE': '@L5RegViolation'
    }

    violation_model = {
        i: get_trader_violation(model=model, trader_id=trader_id, trade_type=i)
        for i in violation_types.keys()
    }

    violation_actual = {
        k: lookup.get_trader_solution_attribute(
            data=data, trader_id=trader_id, attribute=v, func=float)
        for k, v in violation_types.items()
    }

    # Violation comparison
    violation_comparison = {
        i: {
            'model': violation_model[i],
            'actual': violation_actual[i],
            'difference': violation_model[i] - violation_actual[i],
            'abs_difference': abs(violation_model[i] - violation_actual[i])
        }
    }

    output = {
        "@TraderID": trader_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@EnergyTarget": energy_target_comparison,
        "@R6Target": fcas_comparison['R6SE'],
        "@R60Target": fcas_comparison['R60S'],
        "@R5Target": fcas_comparison['R5MI'],
        "@R5RegTarget": fcas_comparison['R5RE'],
        "@L6Target": fcas_comparison['L6SE'],
        "@L60Target": fcas_comparison['L60S'],
        "@L5Target": fcas_comparison['L5MI'],
        "@L5RegTarget": fcas_comparison['L5RE'],
        # "@R6Price": "0",
        # "@R60Price": "0",
        # "@R5Price": "0",
        # "@R5RegPrice": "0",
        # "@L6Price": "0",
        # "@L60Price": "0",
        # "@L5Price": "0",
        # "@L5RegPrice": "0",
        "@R6Violation": violation_comparison['R6SE'],
        "@R60Violation": violation_comparison['R60S'],
        "@R5Violation": violation_comparison['R5MI'],
        "@R5RegViolation": violation_comparison['R5RE'],
        "@L6Violation": violation_comparison['L6SE'],
        "@L60Violation": violation_comparison['L60S'],
        "@L5Violation": violation_comparison['L5MI'],
        "@L5RegViolation": violation_comparison['L5RE'],
        # "@FSTargetMode": "0",
        # "@RampUpRate": "720",
        # "@RampDnRate": "720",
        # "@RampPrice": "0",
        # "@RampDeficit": "0"
    }

    return output


def get_region_solution(model, region_id):
    """Extract solution for a given region"""

    dispatched_generation = model.E_REGION_DISPATCHED_GENERATION[region_id].expr()
    dispatched_load = model.E_REGION_DISPATCHED_LOAD[region_id].expr()
    fixed_demand = model.E_REGION_FIXED_DEMAND[region_id].expr()
    net_export = model.E_REGION_NET_EXPORT[region_id].expr()
    surplus_generation = model.V_CV_REGION_GENERATION_SURPLUS[region_id].value
    cleared_demand = model.E_REGION_CLEARED_DEMAND[region_id].expr()

    # Total FCAS dispatch in each region
    trade_types = ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']
    fcas = {i: get_region_total_dispatch(m=model, region_id=region_id, trade_type=i)
            for i in trade_types}

    output = {
        "@RegionID": region_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        # "@EnergyPrice": "41.69967",
        "@DispatchedGeneration": dispatched_generation,
        "@DispatchedLoad": dispatched_load,
        "@FixedDemand": fixed_demand,
        "@NetExport": net_export,
        "@SurplusGeneration": surplus_generation,
        "@R6Dispatch": fcas['R6SE'],
        "@R60Dispatch": fcas['R60S'],
        "@R5Dispatch": fcas['R5MI'],
        "@R5RegDispatch": fcas['R5RE'],
        "@L6Dispatch": fcas['L6SE'],
        "@L60Dispatch": fcas['L60S'],
        "@L5Dispatch": fcas['L5MI'],
        "@L5RegDispatch": fcas['L5RE'],
        # "@R6Price": "1.49",
        # "@R60Price": "1.73",
        # "@R5Price": "0",
        # "@R5RegPrice": "13.99",
        # "@L6Price": "1.23",
        # "@L60Price": "1.95",
        # "@L5Price": "1.03",
        # "@L5RegPrice": "3.75",
        # "@AvailableGeneration": "8849",
        # "@AvailableLoad": "0",
        "@ClearedDemand": cleared_demand
    }

    return output


def get_region_solution_validation(model, region_id, data):
    """Extract solution for a given region"""

    # Actual NEMDE solution
    dispatched_generation_actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@DispatchedGeneration', func=float)

    dispatched_load_actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@DispatchedLoad', func=float)

    fixed_demand_actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@FixedDemand', func=float)

    net_export_actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@NetExport', func=float)

    surplus_generation_actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@SurplusGeneration', func=float)

    cleared_demand_actual = lookup.get_region_solution_attribute(
        data=data, region_id=region_id, attribute='@ClearedDemand', func=float)

    # Model results
    dispatched_generation_model = model.E_REGION_DISPATCHED_GENERATION[region_id].expr()
    dispatched_load_model = model.E_REGION_DISPATCHED_LOAD[region_id].expr()
    fixed_demand_model = model.E_REGION_FIXED_DEMAND[region_id].expr()
    net_export_model = model.E_REGION_NET_EXPORT[region_id].expr()
    surplus_generation_model = model.V_CV_REGION_GENERATION_SURPLUS[region_id].value
    cleared_demand_model = model.E_REGION_CLEARED_DEMAND[region_id].expr()

    # Comparison
    dispatched_generation_comparison = {
        'model': dispatched_generation_model,
        'actual': dispatched_generation_actual,
        'difference': dispatched_generation_model - dispatched_generation_actual,
        'abs_difference': abs(dispatched_generation_model - dispatched_generation_actual),
    }

    dispatched_load_comparison = {
        'model': dispatched_load_model,
        'actual': dispatched_load_actual,
        'difference': dispatched_load_model - dispatched_load_actual,
        'abs_difference': abs(dispatched_load_model - dispatched_load_actual)
    }

    fixed_demand_comparison = {
        'model': fixed_demand_model,
        'actual': fixed_demand_actual,
        'difference': fixed_demand_model - fixed_demand_actual,
        'abs_difference': abs(fixed_demand_model - fixed_demand_actual)
    }

    net_export_comparison = {
        'model': net_export_model,
        'actual': net_export_actual,
        'difference': net_export_model - net_export_actual,
        'abs_difference': abs(net_export_model - net_export_actual)
    }

    surplus_generation_comparison = {
        'model': surplus_generation_model,
        'actual': surplus_generation_actual,
        'difference': surplus_generation_model - surplus_generation_actual,
        'abs_difference': abs(surplus_generation_model - surplus_generation_actual)
    }

    cleared_demand_comparison = {
        'model': cleared_demand_model,
        'actual': cleared_demand_actual,
        'difference': cleared_demand_model - cleared_demand_actual,
        'abs_difference': abs(cleared_demand_model - cleared_demand_actual)
    }

    # Total FCAS dispatch in each region
    trade_types = ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']
    fcas = {i: get_region_total_dispatch(m=model, region_id=region_id, trade_type=i)
            for i in trade_types}

    output = {
        "@RegionID": region_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        # "@EnergyPrice": "41.69967",
        "@DispatchedGeneration": dispatched_generation,
        "@DispatchedLoad": dispatched_load,
        "@FixedDemand": fixed_demand,
        "@NetExport": net_export,
        "@SurplusGeneration": surplus_generation,
        "@R6Dispatch": fcas['R6SE'],
        "@R60Dispatch": fcas['R60S'],
        "@R5Dispatch": fcas['R5MI'],
        "@R5RegDispatch": fcas['R5RE'],
        "@L6Dispatch": fcas['L6SE'],
        "@L60Dispatch": fcas['L60S'],
        "@L5Dispatch": fcas['L5MI'],
        "@L5RegDispatch": fcas['L5RE'],
        # "@R6Price": "1.49",
        # "@R60Price": "1.73",
        # "@R5Price": "0",
        # "@R5RegPrice": "13.99",
        # "@L6Price": "1.23",
        # "@L60Price": "1.95",
        # "@L5Price": "1.03",
        # "@L5RegPrice": "3.75",
        # "@AvailableGeneration": "8849",
        # "@AvailableLoad": "0",
        "@ClearedDemand": cleared_demand
    }

    return output


def get_interconnector_solution(model, interconnector_id):
    """Extract interconnector solution"""

    flow = model.V_GC_INTERCONNECTOR[interconnector_id].value
    losses = model.V_LOSS[interconnector_id].value
    deficit = model.V_CV_INTERCONNECTOR_REVERSE[interconnector_id].value

    output = {
        "@InterconnectorID": interconnector_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@Flow": flow,
        "@Losses": losses,
        "@Deficit": deficit,
        # "@Price": "0",
        # "@IdealLosses": "-0.59167",
        # "@NPLExists": "0",
        # "@InterRegionalLossFactor": "0.989524"
    }

    return output


def get_case_solution(model):
    """Extract case solution attributes"""

    interconnector_violation = get_total_interconnector_violation(model=model)
    generic_constraint_violation = get_total_generic_constraint_violation(model=model)
    ramp_rate_violation = get_total_ramp_rate_violation(model=model)
    unit_mw_capacity_violation = get_total_unit_mw_capacity_violation(model=model)
    fast_start_violation = get_total_fast_start_violation(model=model)
    uigf_violation = get_total_uigf_violation(model=model)

    output = {
        # "@SolverStatus": "0",
        # "@Terminal": "NORREWMDS1A",
        "@InterventionStatus": model.P_INTERVENTION_STATUS.value,
        # "@SolverVersion": "3.3.15",
        # "@NPLStatus": "0",
        # "@TotalObjective": "-42158401.095",
        # "@TotalAreaGenViolation": "0",
        "@TotalInterconnectorViolation": interconnector_violation,
        "@TotalGenericViolation": generic_constraint_violation,
        "@TotalRampRateViolation": ramp_rate_violation,
        "@TotalUnitMWCapacityViolation": unit_mw_capacity_violation,
        # "@TotalEnergyConstrViolation": "0",
        # "@TotalEnergyOfferViolation": "0",
        # "@TotalASProfileViolation": "0",
        "@TotalFastStartViolation": fast_start_violation,
        # "@NumberOfDegenerateLPsSolved": "0",
        "@TotalUIGFViolation": uigf_violation,
        # "@OCD_Status": "Not_OCD"
    }

    return output


def get_period_solution(model):
    """Extract period solution"""

    objective = model.OBJECTIVE.expr()
    interconnector_violation = get_total_interconnector_violation(model=model)
    generic_constraint_violation = get_total_generic_constraint_violation(model=model)
    ramp_rate_violation = get_total_ramp_rate_violation(model=model)
    unit_mw_capacity_violation = get_total_unit_mw_capacity_violation(model=model)
    fast_start_violation = get_total_fast_start_violation(model=model)
    mnsp_ramp_rate_violation = get_total_mnsp_ramp_rate_violation(model=model)
    mnsp_offer_violation = get_total_mnsp_offer_violation(model=model)
    mnsp_capacity_violation = get_total_mnsp_capacity_violation(model=model)
    uigf_violation = get_total_uigf_violation(model=model)

    output = {
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        # "@SwitchRunBestStatus": "1",
        "@TotalObjective": objective,
        # "@SolverStatus": "0",
        # "@NPLStatus": "0",
        # "@TotalAreaGenViolation": "0",
        "@TotalInterconnectorViolation": interconnector_violation,
        "@TotalGenericViolation": generic_constraint_violation,
        "@TotalRampRateViolation": ramp_rate_violation,
        "@TotalUnitMWCapacityViolation": unit_mw_capacity_violation,
        # "@TotalEnergyConstrViolation": "0",
        # "@TotalEnergyOfferViolation": "0",
        # "@TotalASProfileViolation": "0",
        "@TotalFastStartViolation": fast_start_violation,
        "@TotalMNSPRampRateViolation": mnsp_ramp_rate_violation,
        "@TotalMNSPOfferViolation": mnsp_offer_violation,
        "@TotalMNSPCapacityViolation": mnsp_capacity_violation,
        "@TotalUIGFViolation": uigf_violation
    }

    return output


def get_solution(model, format=None):
    """Extract model solution solution"""

    output = {
        'CaseSolution': get_case_solution(model=model),
        'PeriodSolution': get_period_solution(model=model),
        'RegionSolution': [get_region_solution(model=model, region_id=i) for i in model.S_REGIONS],
        'TraderSolution': [get_trader_solution(model=model, trader_id=i) for i in model.S_TRADERS],
        'InterconnectorSolution': [get_interconnector_solution(model=model, interconnector_id=i) for i in model.S_INTERCONNECTORS],
        'ConstraintSolution': [get_constraint_solution(model=model, constraint_id=i) for i in model.S_GENERIC_CONSTRAINTS],
    }

    return output
