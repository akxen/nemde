"""
Serializer used to extract solution from Pyomo model and convert to JSON
"""


def get_region_total_dispatch(m, region_id, trade_type):
    """Compute total dispatch in a given region rounded to two decimal places"""

    total = sum(m.V_TRADER_TOTAL_OFFER[i, j].value
                for i, j in m.S_TRADER_OFFERS
                if (j == trade_type) and (m.P_TRADER_REGION[i] == region_id))

    return total


def get_region_solution(model, region_id):
    """Extract solution for a given region"""

    output = {
        "@RegionID": region_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        # "@EnergyPrice": "41.69967",
        "@DispatchedGeneration": model.E_REGION_DISPATCHED_GENERATION[region_id].expr(),
        "@DispatchedLoad": model.E_REGION_DISPATCHED_LOAD[region_id].expr(),
        "@FixedDemand": model.E_REGION_FIXED_DEMAND[region_id].expr(),
        "@NetExport": model.E_REGION_NET_EXPORT[region_id].expr(),
        "@SurplusGeneration": model.V_CV_REGION_GENERATION_SURPLUS[region_id].value,
        "@R6Dispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='R6SE'),
        "@R60Dispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='R60S'),
        "@R5Dispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='R5MI'),
        "@R5RegDispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='R5RE'),
        "@L6Dispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='L6SE'),
        "@L60Dispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='L60S'),
        "@L5Dispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='L5MI'),
        "@L5RegDispatch": get_region_total_dispatch(m=model, region_id=region_id, trade_type='L5RE'),
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
        "@ClearedDemand": model.E_REGION_CLEARED_DEMAND[region_id].expr(),
    }

    return output


def get_interconnector_solution(model, interconnector_id):
    """Extract interconnector solution"""

    output = {
        "@InterconnectorID": interconnector_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@Flow": model.V_GC_INTERCONNECTOR[interconnector_id].value,
        "@Losses": model.V_LOSS[interconnector_id].value,
        "@Deficit": model.V_CV_INTERCONNECTOR_REVERSE[interconnector_id].value,
        # "@Price": "0",
        # "@IdealLosses": "-0.59167",
        # "@NPLExists": "0",
        # "@InterRegionalLossFactor": "0.989524"
    }

    return output


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


def get_trader_solution(model, trader_id):
    """Extract solution for a given trader"""

    energy_offer = get_energy_offer(model=model, trader_id=trader_id)

    output = {
        "@TraderID": trader_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@EnergyTarget": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type=energy_offer),
        "@R6Target": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='R6SE'),
        "@R60Target": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='R60S'),
        "@R5Target": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='R5MI'),
        "@R5RegTarget": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='R5RE'),
        "@L6Target": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='L6SE'),
        "@L60Target": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='L60S'),
        "@L5Target": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='L5MI'),
        "@L5RegTarget": get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type='L5RE'),
        # "@R6Price": "0",
        # "@R60Price": "0",
        # "@R5Price": "0",
        # "@R5RegPrice": "0",
        # "@L6Price": "0",
        # "@L60Price": "0",
        # "@L5Price": "0",
        # "@L5RegPrice": "0",
        "@R6Violation": get_trader_violation(model=model, trader_id=trader_id, trade_type='R6SE'),
        "@R60Violation": get_trader_violation(model=model, trader_id=trader_id, trade_type='R60S'),
        "@R5Violation": get_trader_violation(model=model, trader_id=trader_id, trade_type='R5MI'),
        "@R5RegViolation": get_trader_violation(model=model, trader_id=trader_id, trade_type='R5RE'),
        "@L6Violation": get_trader_violation(model=model, trader_id=trader_id, trade_type='L6SE'),
        "@L60Violation": get_trader_violation(model=model, trader_id=trader_id, trade_type='L60S'),
        "@L5Violation": get_trader_violation(model=model, trader_id=trader_id, trade_type='L5MI'),
        "@L5RegViolation": get_trader_violation(model=model, trader_id=trader_id, trade_type='LRE'),
        # "@FSTargetMode": "0",
        # "@RampUpRate": "720",
        # "@RampDnRate": "720",
        # "@RampPrice": "0",
        # "@RampDeficit": "0"
    }

    return output


def get_constraint_deficit(model, constraint_id):
    """Get constraint ID"""

    if model.P_GC_TYPE[constraint_id] == 'EQ':
        return model.V_CV_RHS[constraint_id].value + model.V_CV_LHS[constraint_id].value
    elif model.P_GC_TYPE[constraint_id] in ['LE', 'GE']:
        return model.V_CV[constraint_id].value
    else:
        raise LookupError('Unrecognised constraint type:', model.P_GC_TYPE[constraint_id])


def get_constraint_solution(model, constraint_id):
    """Extract generic constraint solution"""

    output = {
        "@ConstraintID": constraint_id,
        # "@Version": "20200817000000_1",
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        # "@Intervention": "0",
        "@RHS": model.P_GC_RHS[constraint_id],
        # "@MarginalValue": "0",
        "@Deficit": get_constraint_deficit(model=model, constraint_id=constraint_id)
    }

    return output


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


def get_case_solution(model):
    """Extract case solution attributes"""

    output = {
        # "@SolverStatus": "0",
        # "@Terminal": "NORREWMDS1A",
        "@InterventionStatus": model.P_INTERVENTION_STATUS.value,
        # "@SolverVersion": "3.3.15",
        # "@NPLStatus": "0",
        # "@TotalObjective": "-42158401.095",
        # "@TotalAreaGenViolation": "0",
        "@TotalInterconnectorViolation": get_total_interconnector_violation(model=model),
        "@TotalGenericViolation": get_total_generic_constraint_violation(model=model),
        "@TotalRampRateViolation": get_total_ramp_rate_violation(model=model),
        "@TotalUnitMWCapacityViolation": get_total_unit_mw_capacity_violation(model=model),
        # "@TotalEnergyConstrViolation": "0",
        # "@TotalEnergyOfferViolation": "0",
        # "@TotalASProfileViolation": "0",
        "@TotalFastStartViolation": get_total_fast_start_violation(model=model),
        # "@NumberOfDegenerateLPsSolved": "0",
        "@TotalUIGFViolation": get_total_uigf_violation(model=model),
        # "@OCD_Status": "Not_OCD"
    }

    return output


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


def get_period_solution(model):
    """Extract period solution"""

    output = {
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        # "@SwitchRunBestStatus": "1",
        "@TotalObjective": model.OBJECTIVE.expr(),
        # "@SolverStatus": "0",
        # "@NPLStatus": "0",
        # "@TotalAreaGenViolation": "0",
        "@TotalInterconnectorViolation": get_total_interconnector_violation(model=model),
        "@TotalGenericViolation": get_total_generic_constraint_violation(model=model),
        "@TotalRampRateViolation": get_total_ramp_rate_violation(model=model),
        "@TotalUnitMWCapacityViolation": get_total_unit_mw_capacity_violation(model=model),
        # "@TotalEnergyConstrViolation": "0",
        # "@TotalEnergyOfferViolation": "0",
        # "@TotalASProfileViolation": "0",
        "@TotalFastStartViolation": get_total_fast_start_violation(model=model),
        "@TotalMNSPRampRateViolation": get_total_mnsp_ramp_rate_violation(model=model),
        "@TotalMNSPOfferViolation": get_total_mnsp_offer_violation(model=model),
        "@TotalMNSPCapacityViolation": get_total_mnsp_capacity_violation(model=model),
        "@TotalUIGFViolation": get_total_uigf_violation(model=model)
    }

    return output


def get_solution(model, format=None):
    """Extract model solution solution"""

    output = {
        'CaseSolution': get_case_solution(model=model),
        'PeriodSolution': get_period_solution(model=model),
        'RegionSolution': [get_region_solution(model=model, region_id=r) for r in model.S_REGIONS],
        'TraderSolution': [get_trader_solution(model=model, trader_id=t) for t in model.S_TRADERS],
        'InterconnectorSolution': [get_interconnector_solution(model=model, interconnector_id=i) for i in model.S_INTERCONNECTORS],
        'ConstraintSolution': [get_constraint_solution(model=model, constraint_id=i) for i in model.S_GENERIC_CONSTRAINTS],
    }

    return output
