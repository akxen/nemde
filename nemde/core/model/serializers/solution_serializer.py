"""
Serializer used to extract solution from Pyomo model and convert to JSON
"""


def get_case_solution(model):
    """Extract case solution attributes"""

    output = {
        # "@SolverStatus": "0",
        # "@Terminal": "NORREWMDS1A",
        "@InterventionStatus": "0",
        # "@SolverVersion": "3.3.15",
        # "@NPLStatus": "0",
        # "@TotalObjective": "-42158401.095",
        "@TotalAreaGenViolation": "0",
        "@TotalInterconnectorViolation": "0",
        "@TotalGenericViolation": "0",
        "@TotalRampRateViolation": "0",
        "@TotalUnitMWCapacityViolation": "0",
        "@TotalEnergyConstrViolation": "0",
        "@TotalEnergyOfferViolation": "0",
        "@TotalASProfileViolation": "0",
        "@TotalFastStartViolation": "0",
        # "@NumberOfDegenerateLPsSolved": "0",
        "@TotalUIGFViolation": "0",
        # "@OCD_Status": "Not_OCD"
    }

    return output


def get_period_solution(model):
    """Extract period solution"""

    output = {
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        # "@SwitchRunBestStatus": "1",
        "@TotalObjective": model.OBJECTIVE.expr(),
        # "@SolverStatus": "0",
        # "@NPLStatus": "0",
        "@TotalAreaGenViolation": "0",
        "@TotalInterconnectorViolation": "0",
        "@TotalGenericViolation": "0",
        "@TotalRampRateViolation": "0",
        "@TotalUnitMWCapacityViolation": "0",
        "@TotalEnergyConstrViolation": "0",
        "@TotalEnergyOfferViolation": "0",
        "@TotalASProfileViolation": "0",
        "@TotalFastStartViolation": "0",
        "@TotalMNSPRampRateViolation": "0",
        "@TotalMNSPOfferViolation": "0",
        "@TotalMNSPCapacityViolation": "0",
        "@TotalUIGFViolation": "0"
    }

    return output


def get_region_solution(model, region_id):
    """Extract solution for a given region"""

    output = {
        "@RegionID": region_id,
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@EnergyPrice": "41.69967",
        "@DispatchedGeneration": "5818.37",
        "@DispatchedLoad": "0",
        "@FixedDemand": "5654.29",
        "@NetExport": "164.08",
        "@SurplusGeneration": "0",
        "@R6Dispatch": "213",
        "@R60Dispatch": "196",
        "@R5Dispatch": "52",
        "@R5RegDispatch": "118.17",
        "@L6Dispatch": "112.35",
        "@L60Dispatch": "173",
        "@L5Dispatch": "78.97",
        "@L5RegDispatch": "34",
        "@R6Price": "1.49",
        "@R60Price": "1.73",
        "@R5Price": "0",
        "@R5RegPrice": "13.99",
        "@L6Price": "1.23",
        "@L60Price": "1.95",
        "@L5Price": "1.03",
        "@L5RegPrice": "3.75",
        "@AvailableGeneration": "8849",
        "@AvailableLoad": "0",
        "@ClearedDemand": "5660.54"
    }

    return output


def get_interconnector_solution(model, interconnector_id):
    """Extract interconnector solution"""

    output = {
        "@InterconnectorID": interconnector_id,
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@Flow": "-33",
        "@Losses": "-0.59167",
        "@Deficit": "0",
        "@Price": "0",
        "@IdealLosses": "-0.59167",
        # "@NPLExists": "0",
        "@InterRegionalLossFactor": "0.989524"
    }

    return output


def get_trader_solution(model, trader_id):
    """Extract solution for a given trader"""

    output = {
        "@TraderID": trader_id,
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@EnergyTarget": "0",
        "@R6Target": "0",
        "@R60Target": "0",
        "@R5Target": "0",
        "@R5RegTarget": "0",
        "@L6Target": "0",
        "@L60Target": "0",
        "@L5Target": "0",
        "@L5RegTarget": "0",
        "@R6Price": "0",
        "@R60Price": "0",
        "@R5Price": "0",
        "@R5RegPrice": "0",
        "@L6Price": "0",
        "@L60Price": "0",
        "@L5Price": "0",
        "@L5RegPrice": "0",
        "@R6Violation": "0",
        "@R60Violation": "0",
        "@R5Violation": "0",
        "@R5RegViolation": "0",
        "@L6Violation": "0",
        "@L60Violation": "0",
        "@L5Violation": "0",
        "@L5RegViolation": "0",
        "@FSTargetMode": "0",
        "@RampUpRate": "720",
        "@RampDnRate": "720",
        "@RampPrice": "0",
        "@RampDeficit": "0"
    }

    return output


def get_constraint_solution(model, constraint_id):
    """Extract generic constraint solution"""

    output = {
        "@ConstraintID": constraint_id,
        # "@Version": "20200817000000_1",
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@RHS": "25",
        "@MarginalValue": "0",
        "@Deficit": "0"
    }

    return output


def serialize_model_solution(model, format=None):
    """Extract model solution solution"""

    output = {
        'CaseSolution': get_case_solution(model=model),
        'PeriodSolution': get_period_solution(model=model),
        'RegionSolution': [get_region_solution(model=model, region_id=r) for r in model.S_REGIONS],
        'InterconnectorSolution': [get_interconnector_solution(model=model, interconnector_id=i) for i in model.S_INTERCONNECTORS],
        'ConstraintSolution': [get_constraint_solution(model=model, constraint_id=i) for i in model.S_GENERIC_CONSTRAINTS],
    }

    return output
