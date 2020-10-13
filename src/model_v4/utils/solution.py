"""Extract model solution"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

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

    trade_types = ['ENOF', 'LDOF', 'R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']

    # Container for solution
    out = []
    for i in m.S_TRADERS:
        trader_output = {
            "trader_id": i,
            "trade_type": m.P_TRADER_TYPE[i],
            "trader_region": m.P_TRADER_REGION[i],
            'case_id': m.P_CASE_ID.value,
            "intervention": m.P_INTERVENTION_STATUS.value,
            "targets": {j: get_trader_fcas_target(m, i, j) for j in trade_types if (i, j) in m.S_TRADER_OFFERS},
            "prices": {},
            'violation': {j: get_trader_fcas_target(m, i, j) for j in trade_types if (i, j) in m.S_TRADER_OFFERS},
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


def get_region_price(m, region_id, trade_type):
    """Get region price (a placeholder for now)"""

    return np.nan


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
            "@EnergyPrice": get_region_price(m, i, 'ENOF'),
            "@R6Price": get_region_price(m, i, 'R6SE'),
            "@R60Price": get_region_price(m, i, 'R60S'),
            "@R5Price": get_region_price(m, i, 'R5MI'),
            "@R5RegPrice": get_region_price(m, i, 'R5RE'),
            "@L6Price": get_region_price(m, i, 'L6SE'),
            "@L60Price": get_region_price(m, i, 'L60S'),
            "@L5Price": get_region_price(m, i, 'L5MI'),
            "@L5RegPrice": get_region_price(m, i, 'L5RE'),
            # "@AvailableGeneration": "1873",  # TODO: consider adding this
            # "@AvailableLoad": "0",  # TODO: consider adding this
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
            if (type(v) is float) or (type(v) is int):
                actual = lookup.get_region_solution_attribute(data, i['@RegionID'], k, float, i['@Intervention'])
                region_output[k] = {
                    'model': v,
                    'actual': actual,
                    'difference': v - actual,
                    'abs_difference': abs(v - actual)
                }

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


def compare_trader_solution(data, solution):
    """Compare trader solution"""

    # Mapping between offer keys
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Container for output
    out = []

    for i in solution['TraderSolution']:
        # Container used to handle data comparing model
        comparison = {}

        for trade_type, model_target in i['targets'].items():
            # Actual target
            actual = lookup.get_trader_solution_attribute(data, i['trader_id'], key_map[trade_type], float,
                                                          i['intervention'])

            # Compute marginal price bands
            model_current = get_trader_marginal_price_band(data, i['trader_id'], trade_type, model_target, 'current')
            model_marginal = get_trader_marginal_price_band(data, i['trader_id'], trade_type, model_target, 'marginal')

            actual_current = get_trader_marginal_price_band(data, i['trader_id'], trade_type, actual, 'current')
            actual_marginal = get_trader_marginal_price_band(data, i['trader_id'], trade_type, actual, 'marginal')

            # Compare solution
            info = {
                'model': model_target,
                'actual': actual,
                'difference': model_target - actual,
                'abs_difference': abs(model_target - actual),
                'model_current_price_band': model_current,
                'model_marginal_price_band': model_marginal,
                'actual_current_price_band': actual_current,
                'actual_marginal_price_band': actual_marginal,
            }

            # Append to container
            comparison[trade_type] = info

        # Append to main container
        i['comparison'] = comparison

        # Append to output container
        out.append(i)

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


def get_region_prices(comparison):
    """Get region prices"""

    # Mapping between trade types and price keys
    price_keys = ['@EnergyPrice',
                  '@R6Price', '@R60Price', '@R5Price', '@R5RegPrice',
                  '@L6Price', '@L60Price', '@L5Price', '@L5RegPrice']

    return {(i['@RegionID'], j): i[j]['actual'] for i in comparison['RegionSolution'] for j in price_keys}


def inspect_trader_solution(comparison):
    """Inspect trader solution"""

    # Get region prices - using NEMDE solution price keys
    prices = get_region_prices(comparison)

    # Mapping between trade types and price keys
    price_key_map = {'ENOF': '@EnergyPrice', 'LDOF': '@EnergyPrice',
                     'R6SE': '@R6Price', 'R60S': '@R60Price', 'R5MI': '@R5Price', 'R5RE': '@R5RegPrice',
                     'L6SE': '@L6Price', 'L60S': '@L60Price', 'L5MI': '@L5Price', 'L5RE': '@L5RegPrice'}

    # Container for output
    out = {
        (i['trader_id'], j):
            {
                **i['comparison'][j],
                **{
                    'region_id': i['trader_region'],
                    'region_price': prices[(i['trader_region'], price_key_map[j])]
                }
            }
        for i in comparison['TraderSolution'] for j in i['comparison'].keys()
    }

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False).rename_axis(['trader_id', 'trade_type'])

    return df


def inspect_interconnector_solution(comparison):
    """Inspect interconnector solution"""

    # Extract values and assign unique key
    out = {(i['@InterconnectorID'], k): {
        'abs_difference': v['abs_difference'],
        'difference': v['difference'],
        'model': v['model'],
        'actual': v['actual']
    }
        for i in comparison['InterconnectorSolution'] for k, v in i.items() if type(v) == dict}

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False)

    return df


def inspect_region_solution(comparison):
    """Inspect region solution"""

    # Extract data and assign unique key
    out = {(i['@RegionID'], k): {
        'abs_difference': v['abs_difference'],
        'difference': v['difference'],
        'model': v['model'],
        'actual': v['actual']
    }
        for i in comparison['RegionSolution'] for k, v in i.items() if type(v) == dict}

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False)

    return df


def inspect_period_solution(comparison):
    """Inspect period solution"""

    # Container use to compare period solution
    out = {k: {
        'abs_difference': v['abs_difference'],
        'difference': v['difference'],
        'model': v['model'],
        'actual': v['actual']
    }
        for k, v in comparison['PeriodSolution'].items() if type(v) == dict}

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False)

    return df


def inspect_solution(comparison):
    """Inspect solution components"""

    # Solution components
    out = {
        'traders': inspect_trader_solution(comparison),
        'interconnectors': inspect_interconnector_solution(comparison),
        'regions': inspect_region_solution(comparison),
        'period': inspect_period_solution(comparison),
    }

    return out


def print_solution_report(comparison):
    """Print heads of DataFrames showing largest discrepancies"""

    # Get solution
    solution = inspect_solution(comparison)

    for i in ['traders', 'interconnectors', 'regions', 'period']:
        print(i)
        print(solution[i].head())


def get_observed_trader_solution(data):
    """Get observed dispatch targets"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    # Keys to be treated as strings
    str_keys = ['@TraderID', '@PeriodID', '@SemiDispatchCap']

    # Container for output
    out = {}
    for i in traders:
        out.setdefault((i['@TraderID'], i['@Intervention']), {})
        for j, k in i.items():
            if j in str_keys:
                out[(i['@TraderID'], i['@Intervention'])][j] = str(k)
            else:
                out[(i['@TraderID'], i['@Intervention'])][j] = float(k)

    return out


def plot_trader_solution(data, solution, intervention):
    """Plot trader model solution against observed solution"""

    # Observed solution
    observed = get_observed_trader_solution(data)

    # Map between NEMDE output keys and keys used in solution dictionary
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Container for output
    out = {k: [] for k in key_map.keys()}

    # Difference between observed and model solution
    # for trader_id, trader_solution in solution['traders'].items():
    for i in solution['TraderSolution']:
        for trade_type, target in i['targets'].items():
            # Append model value (x-axis) and observed value (y-axis) for given energy type
            out[trade_type].append((target, observed[(i['trader_id'], intervention)][key_map[trade_type]]))

    # Initialise figure
    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8), (ax9, ax10)) = plt.subplots(nrows=5, ncols=2)

    # Mapping between trade types and axes
    ax_map = {'ENOF': ax1, 'LDOF': ax2,
              'R6SE': ax3, 'L6SE': ax4, 'R60S': ax5, 'L60S': ax6, 'R5MI': ax7, 'L5MI': ax8, 'R5RE': ax9, 'L5RE': ax10}

    # Plot solution
    for trade_type in out.keys():
        x, y = [i[0] for i in out[trade_type]], [i[1] for i in out[trade_type]]
        ax_map[trade_type].scatter(x=x, y=y, alpha=0.5, s=5, color='r')
        min_x, max_x = min(x), max(x)
        min_y, max_y = min(y), max(y)
        smallest, largest = min(min_x, min_y), max(max_x, max_y)
        ax_map[trade_type].plot([smallest, largest], [smallest, largest], color='k', linestyle='--', linewidth=0.7,
                                alpha=0.7)
        ax_map[trade_type].set_xlabel('Model (MW)')
        ax_map[trade_type].set_ylabel('Observed (MW)')
        ax_map[trade_type].set_title(trade_type)

    fig.set_size_inches(5, 10)
    plt.show()
