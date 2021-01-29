"""
Serializer used to extract solution from Pyomo model and convert to JSON
"""

from nemde.core.casefile import lookup
from nemde.io.casefile import load_base_case


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

    output = {
        "@ConstraintID": constraint_id,
        # "@Version": "20200817000000_1",
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@RHS": model.P_GC_RHS[constraint_id],
        # "@MarginalValue": "0",
        "@Deficit": get_constraint_deficit(model=model, constraint_id=constraint_id)
    }

    return output


def compare_solutions(dict_1, dict_2, keys):
    """
    Compare solution obtained from NEMDE approximation with observed NEMDE
    solution. Keys and values in dict_1 are used as the basis. For each key
    specified in 'keys' the model and acutal NEMDE solution is compared. Keys
    in dict_1 but not in 'keys' have their value set corresponding values in
    dict_1.

    Parameters
    ----------
    dict_1 : dict
        Model solution

    dict_2 : dict
        NEMDE solution

    keys : list
        Keys on which to compare solution.
    """

    # Container for output
    out = {}
    for k, v in dict_1.items():
        if k in keys:
            out[k] = {
                'model': v,
                'actual': float(dict_2[k]),
                'difference': v - float(dict_2[k]),
                'abs_difference': abs(v - float(dict_2[k]))
            }
        else:
            out[k] = v

    return out


def get_constraint_solution_comparison(model, constraint_id, casefile):
    """Validation intervention solution"""

    # Model solution
    solution = get_constraint_solution(model=model, constraint_id=constraint_id)

    # NEMDE solution
    actual = lookup.get_generic_constraint_solution(
        data=casefile, constraint_id=constraint_id, intervention=model.P_INTERVENTION_STATUS.value)

    # Keys to be compared
    keys = ['@RHS', '@Deficit']

    return compare_solutions(dict_1=solution, dict_2=actual, keys=keys)


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


def get_trader_solution_comparison(model, trader_id, casefile):
    """Compare trader solution with actual NEMDE trader solution"""

    # Model solution
    solution = get_trader_solution(model=model, trader_id=trader_id)

    # NEMDE solution
    actual = lookup.get_trader_solution(
        data=casefile, trader_id=trader_id, intervention=model.P_INTERVENTION_STATUS.value)

    # Keys to be compared
    keys = ['@R6Target', '@R60Target', '@R5Target', '@R5RegTarget',
            '@L6Target', '@L60Target', '@L5Target', '@L5RegTarget',
            '@R6Violation', '@R60Violation', '@R5Violation', '@R5RegViolation',
            '@L6Violation', '@L60Violation', '@L5Violation', '@L5RegViolation',
            '@EnergyTarget']

    return compare_solutions(dict_1=solution, dict_2=actual, keys=keys)


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


def get_region_solution_comparison(model, region_id, casefile):
    """Compare region solution with actual NEMDE region solution"""

    # Model solution
    solution = get_region_solution(model=model, region_id=region_id)

    # NEMDE solution
    actual = lookup.get_region_solution(
        data=casefile, region_id=region_id, intervention=model.P_INTERVENTION_STATUS.value)

    # Keys to be compared
    keys = ["@DispatchedGeneration", "@DispatchedLoad", "@FixedDemand",
            "@NetExport", "@SurplusGeneration",
            "@R6Dispatch", "@R60Dispatch", "@R5Dispatch", "@R5RegDispatch"
            "@L6Dispatch", "@L60Dispatch", "@L5Dispatch", "@L5RegDispatch",
            "@ClearedDemand"]

    return compare_solutions(dict_1=solution, dict_2=actual, keys=keys)


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


def get_interconnector_solution_comparison(model, interconnector_id, casefile):
    """Compare interconnector solution with actual NEMDE solution"""

    # Model solution
    solution = get_interconnector_solution(
        model=model, interconnector_id=interconnector_id)

    # NEMDE solution
    actual = lookup.get_interconnector_solution(
        data=casefile, interconnector_id=interconnector_id,
        intervention=model.P_INTERVENTION_STATUS.value)

    # Keys to be compared
    keys = ["@Flow", "@Losses", "@Deficit"]

    return compare_solutions(dict_1=solution, dict_2=actual, keys=keys)


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


def get_case_solution_comparison(model, casefile):
    """Compare case solution with actual NEMDE solution"""

    # Model solution
    solution = get_case_solution(model=model)

    # NEMDE solution
    actual = lookup.get_case_solution(data=casefile)

    # Keys to be compared
    keys = ["@TotalInterconnectorViolation", "@TotalGenericViolation",
            "@TotalRampRateViolation", "@TotalUnitMWCapacityViolation",
            "@TotalFastStartViolation", "@TotalUIGFViolation"]

    return compare_solutions(dict_1=solution, dict_2=actual, keys=keys)


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


def get_period_solution_comparison(model, casefile):
    """
    Compare period solution obtained from model with NEMDE period solution
    """

    # Model solution
    solution = get_period_solution(model=model)

    # NEMDE solution
    actual = lookup.get_period_solution(
        data=casefile, intervention=model.P_INTERVENTION_STATUS.value)

    # Keys to be compared
    keys = ["@TotalObjective", "@TotalInterconnectorViolation",
            "@TotalGenericViolation", "@TotalRampRateViolation",
            "@TotalUnitMWCapacityViolation", "@TotalFastStartViolation",
            "@TotalMNSPRampRateViolation", "@TotalMNSPOfferViolation",
            "@TotalMNSPCapacityViolation",
            "@TotalUIGFViolation"]

    return compare_solutions(dict_1=solution, dict_2=actual, keys=keys)


def get_solution(model):
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


def get_solution_comparison(model):
    """Compare model solution to observed NEMDE solution"""

    # Load casefile
    casefile = load_base_case(case_id=model.P_CASE_ID.value)

    # Solution components
    regions = [get_region_solution_comparison(model=model, region_id=i, casefile=casefile)
               for i in model.S_REGIONS]

    traders = [get_trader_solution_comparison(model=model, trader_id=i, casefile=casefile)
               for i in model.S_TRADERS]

    interconnectors = [get_interconnector_solution_comparison(
        model=model, interconnector_id=i, casefile=casefile)
        for i in model.S_INTERCONNECTORS]

    constraints = [get_constraint_solution_comparison(
        model=model, constraint_id=i, casefile=casefile)
        for i in model.S_GENERIC_CONSTRAINTS]

    output = {
        'CaseSolution': get_case_solution_comparison(model=model, casefile=casefile),
        'PeriodSolution': get_period_solution_comparison(model=model, casefile=casefile),
        'RegionSolution': regions,
        'TraderSolution': traders,
        'InterconnectorSolution': interconnectors,
        'ConstraintSolution': constraints,
    }

    return output
