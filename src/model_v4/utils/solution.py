"""Extract model solution"""

import lookup


def get_total_interconnector_violation(m) -> float:
    """Get total interconnector violation"""

    return sum(m.V_CV_INTERCONNECTOR_FORWARD[i].value + m.V_CV_INTERCONNECTOR_REVERSE[i].value
               for i in m.S_INTERCONNECTORS)


def get_total_generic_constraint_violation(m) -> float:
    """Get total generic constraint violation"""

    return sum(m.V_CV[i].value + m.V_CV_LHS[i].value + m.V_CV_LHS[i].value for i in m.S_GENERIC_CONSTRAINTS)


def get_total_ramp_rate_violation(m) -> float:
    """Get total ramp rate violation"""

    return sum(m.V_CV_MNSP_RAMP_UP[i].value + m.V_CV_MNSP_RAMP_DOWN[i].value for i in m.S_MNSP_OFFERS)


def get_total_unit_mw_capacity_violation(m) -> float:
    """Get total unit MW capacity violation"""

    return sum(m.V_CV_TRADER_CAPACITY[i].value for i in m.S_TRADER_OFFERS)


def get_total_energy_constraint_violation(m) -> float:
    """Get total energy constraint violation"""

    return sum(m.V_CV_REGION_GENERATION_SURPLUS[i].value + m.V_CV_REGION_GENERATION_DEFICIT[i].value
               for i in m.S_REGIONS)


def get_total_energy_offer_violation(m) -> float:
    """Get total energy offer violation"""

    return sum(m.V_CV_TRADER_OFFER[i, j, k].value for i, j in m.S_TRADER_OFFERS for k in m.S_BANDS)


def get_total_fast_start_violation(m) -> float:
    """Get total fast start constraint violation"""

    return sum(m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i].value for i in m.S_TRADER_FAST_START)


def get_total_mnsp_rate_violation(m) -> float:
    """Get total MNSP ramp rate violation"""

    return sum(m.V_CV_MNSP_RAMP_UP[i].value + m.V_CV_MNSP_RAMP_DOWN[i].value for i in m.S_MNSP_OFFERS)


def get_total_mnsp_offer_violation(m) -> float:
    """Get total MNSP offer violation"""

    return sum(m.V_CV_MNSP_OFFER[i, j, k].value for i, j in m.S_MNSP_OFFERS for k in m.S_BANDS)


def get_total_mnsp_capacity_violation(m) -> float:
    """Get total MNSP capacity violation"""

    return sum(m.V_CV_MNSP_CAPACITY[i].value for i in m.S_MNSP_OFFERS)


def get_total_uigf_violation(m) -> float:
    """Get total UIGF violation"""

    return sum(m.V_CV_TRADER_UIGF_SURPLUS[i].value for i in m.S_TRADER_OFFERS)


def get_period_solution(m) -> dict:
    """Extract period solution"""

    return {'TotalObjective': m.OBJECTIVE()}


def get_period_solution2(m) -> dict:
    """Extract period solution"""

    out = {
        # "@PeriodID": "2019-10-08T00:05:00+10:00",
        '@CaseID': m.P_CASE_ID.value,
        "@Intervention": m.P_INTERVENTION_STATUS.value,
        # "@SwitchRunBestStatus": "1",
        "@TotalObjective": m.OBJECTIVE(),
        # "@SolverStatus": "1",
        # "@NPLStatus": "0",
        # "@TotalAreaGenViolation": "0", # TODO: check this - not sure what it is
        "@TotalInterconnectorViolation": get_total_interconnector_violation(m),
        "@TotalGenericViolation": get_total_generic_constraint_violation(m),
        "@TotalRampRateViolation": get_total_ramp_rate_violation(m),
        "@TotalUnitMWCapacityViolation": get_total_unit_mw_capacity_violation(m),
        "@TotalEnergyConstrViolation": get_total_energy_constraint_violation(m),  # TODO: check this
        "@TotalEnergyOfferViolation": get_total_energy_offer_violation(m),
        "@TotalASProfileViolation": get_total_energy_offer_violation(m),
        "@TotalFastStartViolation": get_total_fast_start_violation(m),
        "@TotalMNSPRampRateViolation": get_total_mnsp_rate_violation(m),
        "@TotalMNSPOfferViolation": get_total_mnsp_offer_violation(m),
        "@TotalMNSPCapacityViolation": get_total_mnsp_capacity_violation(m),
        "@TotalUIGFViolation": get_total_uigf_violation(m)
    }

    return out


def get_trader_energy_target(m, trader_id):
    """Get energy target for a given trader"""

    if (trader_id, 'ENOF') in m.V_TRADER_TOTAL_OFFER.keys():
        return m.V_TRADER_TOTAL_OFFER[trader_id, 'ENOF'].value

    elif (trader_id, 'LDOF') in m.V_TRADER_TOTAL_OFFER.keys():
        return m.V_TRADER_TOTAL_OFFER[trader_id, 'LDOF'].value

    else:
        return 0


def get_trader_fcas_target(m, trader_id, trade_type):
    """Get FCAS target for a given trader"""

    if (trader_id, trade_type) in m.V_TRADER_TOTAL_OFFER.keys():
        return m.V_TRADER_TOTAL_OFFER[trader_id, trade_type].value
    else:
        return 0


def get_trader_fcas_violation(m, trader_id, trade_type):
    """Get FCAS violation"""

    if (trader_id, trade_type) in m.V_CV_TRADER_FCAS_MAX_AVAILABLE.keys():
        return m.V_CV_TRADER_FCAS_MAX_AVAILABLE[trader_id, trade_type].value
    else:
        return 0


def get_trader_solution(m) -> dict:
    """Extract trader solution"""

    # Container for output
    out = {}
    for (trader_id, trade_type), target in m.V_TRADER_TOTAL_OFFER.items():
        out.setdefault(trader_id, {})[trade_type] = target.value

    return out


def get_trader_solution2(m) -> list:
    """Extract trader solution"""

    # Container for solution
    out = []
    for i in m.S_TRADERS:
        trader_output = {
            "@TraderID": i,
            "@TraderType": m.P_TRADER_TYPE[i],
            "@TraderRegion": m.P_TRADER_REGION[i],
            # "@PeriodID": m.P_PERIOD_ID,
            '@CaseID': m.P_CASE_ID.value,
            "@Intervention": m.P_INTERVENTION_STATUS.value,
            "@EnergyTarget": get_trader_energy_target(m, i),
            "@R6Target": get_trader_fcas_target(m, i, 'R6SE'),
            "@R60Target": get_trader_fcas_target(m, i, 'R60S'),
            "@R5Target": get_trader_fcas_target(m, i, 'R5MI'),
            "@R5RegTarget": get_trader_fcas_target(m, i, 'R5RE'),
            "@L6Target": get_trader_fcas_target(m, i, 'L6SE'),
            "@L60Target": get_trader_fcas_target(m, i, 'L60S'),
            "@L5Target": get_trader_fcas_target(m, i, 'L5MI'),
            "@L5RegTarget": get_trader_fcas_target(m, i, 'L5RE'),
            # "@R6Price": "0",
            # "@R60Price": "0",
            # "@R5Price": "0",
            # "@R5RegPrice": "0",
            # "@L6Price": "0",
            # "@L60Price": "0",
            # "@L5Price": "0",
            # "@L5RegPrice": "0",
            "@R6Violation": get_trader_fcas_violation(m, i, 'R6SE'),
            "@R60Violation": get_trader_fcas_violation(m, i, 'R60S'),
            "@R5Violation": get_trader_fcas_violation(m, i, 'R5MI'),
            "@R5RegViolation": get_trader_fcas_violation(m, i, 'R5RE'),
            "@L6Violation": get_trader_fcas_violation(m, i, 'L6SE'),
            "@L60Violation": get_trader_fcas_violation(m, i, 'L60S'),
            "@L5Violation": get_trader_fcas_violation(m, i, 'L5MI'),
            "@L5RegViolation": get_trader_fcas_violation(m, i, 'L5RE'),
            # "@FSTargetMode": "0",
            # "@RampUpRate": "720",
            # "@RampDnRate": "720",
            # "@RampPrice": "0",
            "@RampDeficit": m.V_CV_TRADER_RAMP_UP[i].value + m.V_CV_TRADER_RAMP_DOWN[i].value,
        }

        # Append to container
        out.append(trader_output)

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


def get_interconnector_solution2(m) -> list:
    """Get interconnector solution"""

    # Container for output
    out = []
    for i in m.S_INTERCONNECTORS:
        interconnector_output = {
            "@InterconnectorID": i,
            "@CaseID": m.P_CASE_ID.value,
            # "@PeriodID": "2019-10-08T00:05:00+10:00",
            "@Intervention": m.P_INTERVENTION_STATUS.value,
            "@Flow": m.V_GC_INTERCONNECTOR[i].value,
            "@Losses": m.V_LOSS[i].value,
            # "@Deficit": "0",
            # "@Price": "0",
            # "@IdealLosses": "10.10597",
            # "@NPLExists": "0",
            # "@InterRegionalLossFactor": "0.792018"
        }

        # Append to container
        out.append(interconnector_output)

    return out


def get_region_dispatch(m, region_id, trade_type):
    """Get region dispatch for a given trade type"""

    return sum(m.V_TRADER_TOTAL_OFFER[i, j].value for i, j in m.S_TRADER_OFFERS
               if (j == trade_type) and (m.P_TRADER_REGION[i] == region_id))


def get_region_solution(m) -> dict:
    """Extract region solution"""

    # Container for output
    out = {}
    for r in m.S_REGIONS:
        # Extract energy price - use default value of -9999 if none available
        try:
            energy_price = m.dual[m.C_POWER_BALANCE[r]]
        except KeyError:
            energy_price = -9999

        out[r] = {
            'EnergyPrice': energy_price,
            'FixedDemand': m.E_REGION_FIXED_DEMAND[r].expr(),
        }

    return out


def get_region_solution2(m) -> list:
    """Get interconnector solution"""

    # Container for output
    out = []
    for i in m.S_REGIONS:
        region_output = {
            "@RegionID": i,
            # "@PeriodID": "2019-10-08T00:05:00+10:00",
            "@CaseID": m.P_CASE_ID.value,
            "@Intervention": m.P_INTERVENTION_STATUS.value,
            # "@EnergyPrice": "106.61",
            "@DispatchedGeneration": m.E_REGION_DISPATCHED_GENERATION[i].expr(),
            "@DispatchedLoad": m.E_REGION_DISPATCHED_LOAD[i].expr(),
            "@FixedDemand": m.E_REGION_FIXED_DEMAND[i].expr(),
            "@NetExport": m.E_REGION_NET_EXPORT[i].expr(),
            "@SurplusGeneration": m.V_CV_REGION_GENERATION_SURPLUS[i].value,
            "@R6Dispatch": get_region_dispatch(m, i, 'R6SE'),
            "@R60Dispatch": get_region_dispatch(m, i, 'R60S'),
            "@R5Dispatch": get_region_dispatch(m, i, 'R5MI'),
            "@R5RegDispatch": get_region_dispatch(m, i, 'R5RE'),
            "@L6Dispatch": get_region_dispatch(m, i, 'L6SE'),
            "@L60Dispatch": get_region_dispatch(m, i, 'L60S'),
            "@L5Dispatch": get_region_dispatch(m, i, 'L5MI'),
            "@L5RegDispatch": get_region_dispatch(m, i, 'L5RE'),
            # "@R6Price": "15.16275",
            # "@R60Price": "2",
            # "@R5Price": "0.99",
            # "@R5RegPrice": "21.74194",
            # "@L6Price": "0.02",
            # "@L60Price": "0.095",
            # "@L5Price": "0.16",
            # "@L5RegPrice": "14.97",
            "@AvailableGeneration": "1873",  # TODO: consider adding this
            "@AvailableLoad": "0",  # TODO: consider adding this
            "@ClearedDemand": m.E_REGION_CLEARED_DEMAND[i].expr()
        }

        # Append region solution to container
        out.append(region_output)

    return out


def get_model_solution(m) -> dict:
    """Extract model solution"""

    solution = {
        'period': get_period_solution(m),
        'traders': get_trader_solution(m),
        'interconnectors': get_interconnector_solution(m),
        'regions': get_region_solution(m),
    }

    return solution


def get_model_solution2(m) -> dict:
    """Extract model solution"""

    solution = {
        'PeriodSolution': get_period_solution2(m),
        'TraderSolution': get_trader_solution2(m),
        'InterconnectorSolution': get_interconnector_solution2(m),
        'RegionSolution': get_region_solution2(m),
    }

    return solution


def compare_period_solution(data, solution):
    """Compare period solution"""

    # Get intervention status
    intervention = solution.get('PeriodSolution').get('@Intervention')

    # Container for output
    out = {}
    for k, v in solution['PeriodSolution'].items():
        if type(v) is float:
            actual = lookup.get_period_solution_attribute(data, k, float, intervention)
            out[k] = {'model': v, 'actual': actual, 'difference': v - actual, 'abs_difference': abs(v - actual)}
        else:
            out[k] = v

    return out


def compare_region_solution(data, solution):
    """Compare region solution"""

    # Container for output
    out = []

    for i in solution['RegionSolution']:
        # Container for region output
        region_output = {}

        for k, v in i.items():
            if type(v) is float:
                actual = lookup.get_region_solution_attribute(data, i['@RegionID'], k, float, i['@Intervention'])
                region_output[k] = {'model': v, 'actual': actual, 'difference': v - actual,
                                    'abs_difference': abs(v - actual)}

            else:
                region_output[k] = v

        # Append to container
        out.append(region_output)

    return out


def get_trader_marginal_price_band(data, trader_id, trade_type, output, mode):
    """Get marginal price for a given trader"""

    # Trader price and quantity bands
    price_bands = {
        f'PriceBand{i}': lookup.get_trader_price_band_attribute(data, trader_id, trade_type, f'@PriceBand{i}', float)
        for i in range(1, 11)
    }

    # Trader quantity bands
    quantity_bands = {
        f'BandAvail{i}': lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, f'@BandAvail{i}', float)
        for i in range(1, 11)
    }

    # Initialise total output
    total_output = 0
    for i in range(1, 11):
        total_output += quantity_bands[f'BandAvail{i}']

        # The cost corresponding to the dispatch band (may be at end of band so marginal cost can differ)
        if mode == 'current':
            band_condition = total_output >= output

        # Check if aggregate output is greater than the specified level - the cost to produce an additional unit
        elif mode == 'marginal':
            band_condition = total_output > output

        else:
            raise Exception(f'Unhandled mode: {mode}')

        if band_condition:
            # Return price corresponding to quantity band
            return price_bands[f'PriceBand{i}']

    # Max price (highest price band)
    return price_bands['PriceBand10']


def convert_solution_trade_type(trade_type, trader_type):
    """Convert solution trade type to offer trade type"""

    # Mapping between offer keys
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               '@R6Target': 'R6SE', '@R60Target': 'R60S', '@R5Target': 'R5MI', '@R5RegTarget': 'R5RE',
               '@L6Target': 'L6SE', '@L60Target': 'L60S', '@L5Target': 'L5MI', '@L5RegTarget': 'L5RE'}

    if (trader_type == 'GENERATOR') and (trade_type == '@EnergyTarget'):
        return 'ENOF'
    elif (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (trade_type == '@EnergyTarget'):
        return 'LDOF'
    else:
        return key_map[trade_type]


def compare_trader_solution(data, solution):
    """Compare trader solution"""

    # Container for output
    out = []

    # Trade types
    trade_types = ['@R6Target', '@R60Target', '@R5Target', '@R5RegTarget',
                   '@L6Target', '@L60Target', '@L5Target', '@L5RegTarget',
                   '@EnergyTarget']

    for i in solution['TraderSolution']:
        # Container for trader output
        trader_output = {}

        # Extract trader ID
        trader_id = i['@TraderID']

        # Container for additional info
        info = {
            'price_band':
                {
                    'model': {
                        'current': {},
                        'marginal': {}
                    },
                    'actual': {
                        'current': {},
                        'marginal': {}
                    }
                }
        }

        for k, v in i.items():
            if type(v) is float:
                # Some traders have more solution attributes than others - skip these items
                try:
                    actual = lookup.get_trader_solution_attribute(data, trader_id, k, float, i['@Intervention'])
                except KeyError:
                    continue

                # Compute difference between model and NEMDE output
                trader_output[k] = {
                    'model': v,
                    'actual': actual,
                    'difference': v - actual,
                    'abs_difference': abs(v - actual)
                }

                if k in trade_types:
                    # data, trader_id, trade_type, output, mode
                    trade_type = convert_solution_trade_type(k, i['@TraderType'])

                    model_current = get_trader_marginal_price_band(data, trader_id, trade_type, v, 'current')
                    model_marginal = get_trader_marginal_price_band(data, trader_id, trade_type, v, 'marginal')

                    actual_current = get_trader_marginal_price_band(data, trader_id, trade_type, actual, 'current')
                    actual_marginal = get_trader_marginal_price_band(data, trader_id, trade_type, actual, 'marginal')

                    info['price_band']['model']['current'][trade_type] = model_current
                    info['price_band']['model']['marginal'][trade_type] = model_marginal

                    info['price_band']['actual']['current'][trade_type] = actual_current
                    info['price_band']['actual']['marginal'][trade_type] = actual_marginal

            else:
                trader_output[k] = v

        # Include additional information for the purpose of debugging
        trader_output['info'] = info

        # Append to container
        out.append(trader_output)

    return out


def compare_interconnector_solution(data, solution) -> list:
    """Compare interconnector model solution with observed NEMDE output"""

    # Container for output
    out = []

    for i in solution['InterconnectorSolution']:
        # Container for interconnector output
        interconnector_output = {}

        for k, v in i.items():
            if type(v) is float:
                # Observed output from NEMDE
                actual = lookup.get_interconnector_solution_attribute(data, i['@InterconnectorID'], k, float,
                                                                      i['@Intervention'])

                # Compute difference between model and NEMDE output
                interconnector_output[k] = {
                    'model': v,
                    'actual': actual,
                    'difference': v - actual,
                    'abs_difference': abs(v - actual)
                }

            else:
                interconnector_output[k] = v

        # Append to container
        out.append(interconnector_output)

    return out


def get_model_comparison(data, solution) -> dict:
    """Compare model with observed NEMDE output"""

    # Compare solutions
    comparison = {
        'PeriodSolution': compare_period_solution(data, solution),
        'RegionSolution': compare_region_solution(data, solution),
        'TraderSolution': compare_trader_solution(data, solution),
        'InterconnectorSolution': compare_interconnector_solution(data, solution)
    }

    return comparison
