"""Extract model solution"""


def get_period_solution(m) -> dict:
    """Extract period solution"""

    return {'TotalObjective': m.OBJECTIVE()}


def get_trader_solution(m) -> dict:
    """Extract trader solution"""

    # Container for output
    out = {}
    for (trader_id, trade_type), target in m.V_TRADER_TOTAL_OFFER.items():
        out.setdefault(trader_id, {})[trade_type] = target.value

    return out


def get_interconnector_solution(m) -> dict:
    """Extract interconnector solution"""

    # Container for output
    out = {}
    for k, v in m.V_GC_INTERCONNECTOR.items():
        out.setdefault(k, {})['Flow'] = v.value

    for k, v in m.V_LOSS.items():
        out.setdefault(k, {})['Losses'] = v.value

    return out


def get_region_solution(m) -> dict:
    """Extract region solution"""

    # Container for output
    out = {}
    for r in m.S_REGIONS:
        out[r] = {
            'EnergyPrice': m.dual[m.C_POWER_BALANCE[r]],
            'FixedDemand': m.E_REGION_FIXED_DEMAND[r].expr(),
        }

    return out


def get_case_solution(m) -> dict:
    """Extract case solution"""
    pass


def get_model_solution(m) -> dict:
    """Extract model solution"""

    solution = {
        'period': get_period_solution(m),
        'traders': get_trader_solution(m),
        'interconnectors': get_interconnector_solution(m),
        'regions': get_region_solution(m),
        # 'case': get_case_solution(m),
    }

    return solution
