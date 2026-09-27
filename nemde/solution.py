"""
Serializer used to extract solution from Pyomo model and convert to JSON
"""


def get_region_total_dispatch(m, region_id, trade_type):
    """
    Compute total dispatch in a given region rounded to two decimal places
    """

    total = sum(
        m.E_TRADER_TARGET[i, j].expr()
        for i, j in m.S_TRADER_TOTAL_OFFERS
        if (j == trade_type) and (m.P_TRADER_REGION[i] == region_id)
    )

    return total


def get_trader_dispatch_target(model, trader_id, trade_type):
    """
    Extract dispatch target for a given unit. Return 0 trade_type doesn't
    exist for a given trader_id
    """

    if (trader_id, trade_type) in model.E_TRADER_TARGET.keys():
        return model.E_TRADER_TARGET[trader_id, trade_type].expr()
    else:
        return 0.0


def get_energy_offer(model, trader_id):
    """Get energy offer"""

    if model.P_TRADER_TYPE[trader_id] == "GENERATOR":
        return "ENOF"
    elif model.P_TRADER_TYPE[trader_id] in ["LOAD", "NORMALLY_ON_LOAD"]:
        return "LDOF"
    elif model.P_TRADER_TYPE[trader_id] in ["WDR"]:
        return "DROF"
    elif model.P_TRADER_TYPE[trader_id] == "BIDIRECTIONAL":
        return "BDOF"
    else:
        raise LookupError("P_TRADER_TYPE not recognised:", model.P_TRADER_TYPE[trader_id])


def get_trader_violation(model, trader_id, trade_type):
    """Get trader violation"""

    if (trader_id, trade_type) in model.S_TRADER_TOTAL_OFFERS:
        return sum(
            model.V_CV_TRADER_OFFER[i, j, k, b].value
            for i, j, k in model.S_TRADER_OFFERS
            for b in range(1, 11)
            if (i == trader_id) and (j == trade_type)
        )
    else:
        return 0.0


def get_constraint_deficit(model, constraint_id):
    """Get constraint ID"""

    if model.P_GC_TYPE[constraint_id] == "EQ":
        return model.V_CV_RHS[constraint_id].value + model.V_CV_LHS[constraint_id].value
    elif model.P_GC_TYPE[constraint_id] in ["LE", "GE"]:
        return model.V_CV[constraint_id].value
    else:
        raise LookupError("Unrecognised constraint type:", model.P_GC_TYPE[constraint_id])


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
        "@Deficit": get_constraint_deficit(model=model, constraint_id=constraint_id),
    }

    return output


def get_trader_solution(model, trader_id):
    """Extract solution for a given trader"""

    # Energy offer target
    energy_offer = get_energy_offer(model=model, trader_id=trader_id)
    energy_target = get_trader_dispatch_target(
        model=model, trader_id=trader_id, trade_type=energy_offer
    )

    # FCAS targets
    trade_types = [
        "R1SE",
        "R6SE",
        "R60S",
        "R5MI",
        "R5RE",
        "L1SE",
        "L6SE",
        "L60S",
        "L5MI",
        "L5RE",
    ]
    fcas = {
        i: get_trader_dispatch_target(model=model, trader_id=trader_id, trade_type=i)
        for i in trade_types
    }

    # FCAS violation
    violation = {
        i: get_trader_violation(model=model, trader_id=trader_id, trade_type=i) for i in trade_types
    }

    trader_solution = {
        "@TraderID": trader_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@EnergyTarget": energy_target,
        "@R1Target": fcas["R1SE"],
        "@R6Target": fcas["R6SE"],
        "@R60Target": fcas["R60S"],
        "@R5Target": fcas["R5MI"],
        "@R5RegTarget": fcas["R5RE"],
        "@L1Target": fcas["L1SE"],
        "@L6Target": fcas["L6SE"],
        "@L60Target": fcas["L60S"],
        "@L5Target": fcas["L5MI"],
        "@L5RegTarget": fcas["L5RE"],
        # "@R6Price": "0",
        # "@R60Price": "0",
        # "@R5Price": "0",
        # "@R5RegPrice": "0",
        # "@L6Price": "0",
        # "@L60Price": "0",
        # "@L5Price": "0",
        # "@L5RegPrice": "0",
        "@R6Violation": violation["R6SE"],
        "@R60Violation": violation["R60S"],
        "@R5Violation": violation["R5MI"],
        "@R5RegViolation": violation["R5RE"],
        "@L6Violation": violation["L6SE"],
        "@L60Violation": violation["L60S"],
        "@L5Violation": violation["L5MI"],
        "@L5RegViolation": violation["L5RE"],
    }

    # Ramp rate information - not included for all traders
    if trader_id in model.P_TRADER_EFFECTIVE_RAMP_UP_RATE.keys():
        ramp_rates = {
            "@RampUpRate": model.P_TRADER_EFFECTIVE_RAMP_UP_RATE[trader_id],
            "@RampDnRate": model.P_TRADER_EFFECTIVE_RAMP_DN_RATE[trader_id],
            # "@RampPrice": "0",
            # "@RampDeficit": "0"
        }

    else:
        ramp_rates = {}

    # Fast start mode information - not included for all traders
    if trader_id in model.P_TRADER_CURRENT_MODE.keys():
        fast_start = {
            "@FSTargetMode": model.P_TRADER_CURRENT_MODE[trader_id].value,
        }
    else:
        fast_start = {}

    return {**trader_solution, **ramp_rates, **fast_start}


def get_region_solution(model, region_id):
    """Extract solution for a given region"""

    dispatched_generation = model.E_REGION_DISPATCHED_GENERATION[region_id].expr()
    dispatched_load = model.E_REGION_DISPATCHED_LOAD[region_id].expr()
    fixed_demand = model.E_REGION_FIXED_DEMAND[region_id].expr()
    net_export = model.E_REGION_NET_EXPORT[region_id].expr()
    surplus_generation = model.V_CV_REGION_GENERATION_SURPLUS[region_id].value
    cleared_demand = model.E_REGION_CLEARED_DEMAND[region_id].expr()

    energy_price = model.dual[model.C_POWER_BALANCE[region_id]]

    # Total FCAS dispatch in each region
    trade_types = [
        "R1SE",
        "R6SE",
        "R60S",
        "R5MI",
        "R5RE",
        "L1SE",
        "L6SE",
        "L60S",
        "L5MI",
        "L5RE",
    ]
    fcas = {
        i: get_region_total_dispatch(m=model, region_id=region_id, trade_type=i)
        for i in trade_types
    }

    output = {
        "@RegionID": region_id,
        # "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@CaseID": model.P_CASE_ID.value,  # Not in NEMDE solution
        "@Intervention": model.P_INTERVENTION_STATUS.value,
        "@EnergyPrice": energy_price,
        "@DispatchedGeneration": dispatched_generation,
        "@DispatchedLoad": dispatched_load,
        "@FixedDemand": fixed_demand,
        "@NetExport": net_export,
        "@SurplusGeneration": surplus_generation,
        "@R1Dispatch": fcas["R1SE"],
        "@R6Dispatch": fcas["R6SE"],
        "@R60Dispatch": fcas["R60S"],
        "@R5Dispatch": fcas["R5MI"],
        "@R5RegDispatch": fcas["R5RE"],
        "@L1Dispatch": fcas["L1SE"],
        "@L6Dispatch": fcas["L6SE"],
        "@L60Dispatch": fcas["L60S"],
        "@L5Dispatch": fcas["L5MI"],
        "@L5RegDispatch": fcas["L5RE"],
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
        "@ClearedDemand": cleared_demand,
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
        "@TotalUIGFViolation": uigf_violation,
    }

    return output


def get_solution(model):
    """Extract model solution solution"""

    output = {
        "CaseSolution": get_case_solution(model=model),
        "PeriodSolution": get_period_solution(model=model),
        "RegionSolution": [get_region_solution(model=model, region_id=i) for i in model.S_REGIONS],
        "TraderSolution": [get_trader_solution(model=model, trader_id=i) for i in model.S_TRADERS],
        "InterconnectorSolution": [
            get_interconnector_solution(model=model, interconnector_id=i)
            for i in model.S_INTERCONNECTORS
        ],
        "ConstraintSolution": [
            get_constraint_solution(model=model, constraint_id=i)
            for i in model.S_GENERIC_CONSTRAINTS
        ],
    }

    return output


def get_objective_breakdown(m) -> list[dict]:
    """Term-by-term decomposition of the solved objective: the trader/MNSP cost
    functions and every constraint-violation penalty expression, evaluated at the
    solution.

    Returned as structured data on the solution dict rather than written to a CSV,
    so it can be diffed across runs and read by the objective-gap investigation
    without re-parsing a file. (This used to write a timestamped CSV into a
    hard-coded, CWD-relative data/debug/ on every single solve.)
    """

    return [
        {"name": "OBJECTIVE", "value": m.OBJECTIVE.expr()},
        {
            "name": "E_TRADER_COST_FUNCTION",
            "value": sum(m.E_TRADER_COST_FUNCTION[t].expr() for t in m.S_TRADER_OFFERS),
        },
        {
            "name": "E_MNSP_COST_FUNCTION",
            "value": sum(m.E_MNSP_COST_FUNCTION[t].expr() for t in m.S_MNSP_OFFERS),
        },
        {
            "name": "E_CV_GC_PENALTY",
            "value": sum(m.E_CV_GC_PENALTY[i].expr() for i in m.S_GENERIC_CONSTRAINTS),
        },
        {
            "name": "E_CV_GC_LHS_PENALTY",
            "value": sum(m.E_CV_GC_LHS_PENALTY[i].expr() for i in m.S_GENERIC_CONSTRAINTS),
        },
        {
            "name": "E_CV_GC_RHS_PENALTY",
            "value": sum(m.E_CV_GC_RHS_PENALTY[i].expr() for i in m.S_GENERIC_CONSTRAINTS),
        },
        {
            "name": "E_CV_TRADER_OFFER_PENALTY",
            "value": sum(
                m.E_CV_TRADER_OFFER_PENALTY[i, j, k, b].expr()
                for i, j, k in m.S_TRADER_OFFERS
                for b in m.S_BANDS
            ),
        },
        {
            "name": "E_CV_TRADER_CAPACITY_PENALTY",
            "value": sum(m.E_CV_TRADER_CAPACITY_PENALTY[i].expr() for i in m.S_TRADER_OFFERS),
        },
        {
            "name": "E_CV_TRADER_UIGF_SURPLUS_PENALTY",
            "value": sum(
                m.E_CV_TRADER_UIGF_SURPLUS_PENALTY[i].expr() for i in m.S_TRADER_TOTAL_OFFERS
            ),
        },
        {
            "name": "E_CV_TRADER_RAMP_UP_PENALTY",
            "value": sum(m.E_CV_TRADER_RAMP_UP_PENALTY[i].expr() for i in m.S_TRADERS),
        },
        {
            "name": "E_CV_TRADER_RAMP_DOWN_PENALTY",
            "value": sum(m.E_CV_TRADER_RAMP_DOWN_PENALTY[i].expr() for i in m.S_TRADERS),
        },
        {
            "name": "E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP_PENALTY",
            "value": sum(
                m.E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP_PENALTY[i].expr() for i in m.S_TRADERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN_PENALTY",
            "value": sum(
                m.E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN_PENALTY[i].expr() for i in m.S_TRADERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_JOINT_RAMPING_UP",
            "value": sum(m.E_CV_TRADER_FCAS_JOINT_RAMPING_UP[i].expr() for i in m.S_TRADER_OFFERS),
        },
        {
            "name": "E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN",
            "value": sum(
                m.E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i].expr() for i in m.S_TRADER_OFFERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS",
            "value": sum(
                m.E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i].expr() for i in m.S_TRADER_OFFERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS",
            "value": sum(
                m.E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i].expr() for i in m.S_TRADER_OFFERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS",
            "value": sum(
                m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i].expr() for i in m.S_TRADER_OFFERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS",
            "value": sum(
                m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i].expr() for i in m.S_TRADER_OFFERS
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_MAX_AVAILABLE",
            "value": sum(m.E_CV_TRADER_FCAS_MAX_AVAILABLE[i].expr() for i in m.S_TRADER_OFFERS),
        },
        {
            "name": "E_CV_TRADER_INFLEXIBILITY_PROFILE",
            "value": sum(
                m.E_CV_TRADER_INFLEXIBILITY_PROFILE[i].expr() for i in m.S_TRADER_FAST_START
            ),
        },
        {
            "name": "E_CV_TRADER_INFLEXIBILITY_PROFILE_LHS",
            "value": sum(
                m.E_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i].expr() for i in m.S_TRADER_FAST_START
            ),
        },
        {
            "name": "E_CV_TRADER_INFLEXIBILITY_PROFILE_RHS",
            "value": sum(
                m.E_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i].expr() for i in m.S_TRADER_FAST_START
            ),
        },
        {
            "name": "E_CV_TRADER_FCAS_ENABLEMENT_MIN",
            "value": sum(m.E_CV_TRADER_FCAS_ENABLEMENT_MIN[i].expr() for i in m.S_TRADER_OFFERS),
        },
        {
            "name": "E_CV_TRADER_FCAS_ENABLEMENT_MAX",
            "value": sum(m.E_CV_TRADER_FCAS_ENABLEMENT_MAX[i].expr() for i in m.S_TRADER_OFFERS),
        },
        {
            "name": "E_CV_MNSP_OFFER_PENALTY",
            "value": sum(
                m.E_CV_MNSP_OFFER_PENALTY[i, j, k].expr()
                for i, j in m.S_MNSP_OFFERS
                for k in m.S_BANDS
            ),
        },
        {
            "name": "E_CV_MNSP_CAPACITY_PENALTY",
            "value": sum(m.E_CV_MNSP_CAPACITY_PENALTY[i].expr() for i in m.S_MNSP_OFFERS),
        },
        {
            "name": "E_CV_MNSP_RAMP_UP_PENALTY",
            "value": sum(m.E_CV_MNSP_RAMP_UP_PENALTY[i].expr() for i in m.S_MNSP_OFFERS),
        },
        {
            "name": "E_CV_MNSP_RAMP_DOWN_PENALTY",
            "value": sum(m.E_CV_MNSP_RAMP_DOWN_PENALTY[i].expr() for i in m.S_MNSP_OFFERS),
        },
        {
            "name": "E_CV_INTERCONNECTOR_FORWARD_PENALTY",
            "value": sum(
                m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i].expr() for i in m.S_INTERCONNECTORS
            ),
        },
        {
            "name": "E_CV_INTERCONNECTOR_REVERSE_PENALTY",
            "value": sum(
                m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i].expr() for i in m.S_INTERCONNECTORS
            ),
        },
        {
            "name": "E_CV_REGION_SURPLUS_POWER",
            "value": sum(m.E_CV_REGION_SURPLUS_POWER[i].expr() for i in m.S_REGIONS),
        },
        {
            "name": "E_CV_REGION_DEFICIT_POWER",
            "value": sum(m.E_CV_REGION_DEFICIT_POWER[i].expr() for i in m.S_REGIONS),
        },
    ]
