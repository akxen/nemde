"""Get model solution"""

import pandas as pd
import matplotlib.pyplot as plt

import fcas_calculations


def get_observed_trader_solution(data):
    """Get observed energy target solution"""

    # All traders
    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    # Keys to be treated as strings
    str_keys = ['@TraderID', '@PeriodID', '@SemiDispatchCap']

    # Container for output
    out = {}
    for i in traders:
        out.setdefault(i['@TraderID'], {})
        for j, k in i.items():
            if j in str_keys:
                out[i['@TraderID']][j] = str(k)
            else:
                out[i['@TraderID']][j] = float(k)

    return out


def get_trader_marginal_price_band(data, trader_id, trade_type, output):
    """Get marginal price for a given trader"""

    # Trader price and quantity bands
    price_bands = fcas_calculations.get_trader_price_bands(data, trader_id, trade_type)
    quantity_bands = fcas_calculations.get_trader_quantity_bands(data, trader_id, trade_type)

    # Initialise total output
    total_output = 0
    for i in range(1, 11):
        total_output += quantity_bands[f'BandAvail{i}']

        # Check if aggregate output is greater than the specified level
        if total_output > output:
            # Return price corresponding to band
            return price_bands[f'PriceBand{i}']

    # Max price (highest price band)
    return price_bands[f'PriceBand10']


def check_trader_solution(data, solution):
    """Compare trader model solution with observed solution"""

    # Observed solution
    observed = get_observed_trader_solution(data)

    # Container for output
    out = {}

    # Map between NEMDE output keys and keys used in solution dictionary
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Mapping between trade types and price keys
    price_key_map = {'ENOF': '@EnergyPrice', 'LDOF': '@EnergyPrice',
                     'R6SE': '@R6Price', 'R60S': '@R60Price', 'R5MI': '@R5Price', 'R5RE': '@R5RegPrice',
                     'L6SE': '@L6Price', 'L60S': '@L60Price', 'L5MI': '@L5Price', 'L5RE': '@L5RegPrice'}

    # Difference between observed and model solution
    for trader_id, trader_solution in solution['traders'].items():
        out.setdefault(trader_id, {})
        for trade_type, target in trader_solution.items():
            # Compute difference between target and observed value
            region_id = fcas_calculations.get_trader_period_attribute(data, trader_id, '@RegionID', str)

            # Get region price for given trade type
            region_price = fcas_calculations.get_region_solution_attribute(data, region_id, price_key_map[trade_type], float)

            # Observed output
            observed_output = observed[trader_id][key_map[trade_type]]

            # Model and observed marginal price bands
            model_marginal_price = get_trader_marginal_price_band(data, trader_id, trade_type, target)
            observed_marginal_price = get_trader_marginal_price_band(data, trader_id, trade_type, observed_output)

            # Observed marginal price band
            out[trader_id][trade_type] = {
                'model': target,
                'observed': observed_output,
                'difference': target - observed_output,
                'abs_difference': abs(target - observed_output),
                'region_id': region_id,
                'region_price': region_price,
                'model_marginal_price': model_marginal_price,
                'observed_marginal_price': observed_marginal_price,
            }

    # Convert to DataFrame and sort by error corresponding to each unit
    df_out = {(k_1, k_2): v_2 for k_1, v_1 in out.items() for k_2, v_2 in v_1.items()}
    df = pd.DataFrame(df_out).T.sort_values(by='abs_difference', ascending=False)

    return out, df


def plot_trader_solution_difference(data, solution):
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
    for trader_id, trader_solution in solution['traders'].items():
        for trade_type, target in trader_solution.items():
            # Append model value (x-axis) and observed value (y-axis) for given energy type
            out[trade_type].append((target, observed[trader_id][key_map[trade_type]]))

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


def get_observed_interconnector_solution(data):
    """Get observed interconnector solution"""

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

    # Container for output
    out = {}
    for i in interconnectors:
        out[i['@InterconnectorID']] = {'Flow': float(i['@Flow']), 'Losses': float(i['@Losses'])}

    return out


def check_interconnector_solution(data, solution, attribute):
    """Check interconnector solution"""

    # Observed interconnector solution
    observed = get_observed_interconnector_solution(data)

    # Container for output
    out = {}
    for k, v in solution['interconnectors'].items():
        out[k] = {
            'model': v[attribute],
            'observed': observed[k][attribute],
            'difference': v[attribute] - observed[k][attribute],
            'abs_difference': abs(v[attribute] - observed[k][attribute]),
        }

    # Convert to DataFrame
    df = pd.DataFrame(out).T.sort_values(by='abs_difference', ascending=False).round(4)

    return out, df


def plot_interconnector_solution(data, solution):
    """Plot interconnector solution"""

    # Initialise plot
    fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2)

    def add_plot(attribute, ax):
        """Add axis to data"""

        # Get plot data
        plot_data, _ = check_interconnector_solution(data, solution, attribute)

        # Container for x and y data points
        x, y = [], []

        for k, v in plot_data.items():
            x.append(v['model'])
            y.append(v['observed'])

        min_x, max_x = min(x), max(x)
        min_y, max_y = min(y), max(y)

        ax.scatter(x=x, y=y, alpha=0.7, s=10, color='r')
        smallest, largest = min(min_x, min_y), max(max_x, max_y)
        ax.plot([smallest, largest], [smallest, largest], color='k', linestyle='--', linewidth=0.7, alpha=0.7)
        ax.set_xlabel('Model (MW)')
        ax.set_ylabel('Observed (MW)')
        ax.set_title(attribute)

        return ax

    ax1 = add_plot('Flow', ax1)
    ax2 = add_plot('Losses', ax2)
    fig.set_size_inches(5, 3)
    plt.show()


def plot_trapezium(trapezium, ax):
    """Plot FCAS trapezium on a given axis"""

    x = [trapezium[i] for i in ['EnablementMin', 'LowBreakpoint', 'HighBreakpoint', 'EnablementMax']]
    y = [0, trapezium['MaxAvail'], trapezium['MaxAvail'], 0]

    ax.plot(x, y)

    return ax


def plot_observed_energy_target(energy_target, max_avail, ax):
    """Add vertical line showing observed energy target"""

    x = [energy_target, energy_target]
    y = [0, 1.1 * max(1, max_avail)]
    ax.plot(x, y)

    return ax


def plot_observed_fcas_target(enablement_min, enablement_max, fcas_target, ax):
    """Add horizontal line showing observed FCAS target"""

    x = [0.9 * enablement_min, 1.1 * max(enablement_max, 1)]
    y = [fcas_target, fcas_target]
    ax.plot(x, y)

    return ax


def plot_model_energy_fcas_target(energy_target, fcas_target, ax):
    """Plot energy and FCAS solution obtained from model"""

    ax.scatter(x=[energy_target], y=[fcas_target], s=20, alpha=0.8, color='r')

    return ax


def get_fcas_solution_comparison_data(preprocessed_data, trader_solutions, trader_id, trade_type):
    """Get data required for solution comparison"""

    # Original FCAS trapezium
    unscaled = preprocessed_data['preprocessed']['FCAS_TRAPEZIUM'].get((trader_id, trade_type))

    # Scaled FCAS trapezium
    scaled = preprocessed_data['preprocessed']['FCAS_TRAPEZIUM_SCALED'].get((trader_id, trade_type))

    # FCAS availability
    availability = preprocessed_data['preprocessed']['FCAS_AVAILABILITY'].get((trader_id, trade_type))

    # Extract model and observed energy target
    if 'ENOF' in trader_solutions[trader_id].keys():
        observed_energy_target = trader_solutions[trader_id]['ENOF']['observed']
        model_energy_target = trader_solutions[trader_id]['ENOF']['model']
    elif 'LDOF' in trader_solutions[trader_id].keys():
        observed_energy_target = trader_solutions[trader_id]['LDOF']['observed']
        model_energy_target = trader_solutions[trader_id]['LDOF']['model']
    else:
        observed_energy_target = 0
        model_energy_target = 0

    # Combine into single dictionary
    comparison_data = {
        'unscaled_fcas_trapezium': unscaled, 'scaled_fcas_trapezium': scaled, 'fcas_availability': availability,
        'observed_energy_target': observed_energy_target, 'model_energy_target': model_energy_target,
        'model_fcas_target': trader_solutions[trader_id][trade_type]['model'],
        'observed_fcas_target': trader_solutions[trader_id][trade_type]['observed'], 'trade_type': trade_type
    }

    return comparison_data


def plot_fcas_solution_comparison(comparison_data, ax):
    """Compare model and observed FCAS / Energy solution"""

    # FCAS trapezium data
    max_avail = comparison_data['unscaled_fcas_trapezium']['MaxAvail']
    enablement_min = comparison_data['unscaled_fcas_trapezium']['EnablementMin']
    enablement_max = comparison_data['unscaled_fcas_trapezium']['EnablementMax']
    model_fcas_target = comparison_data['model_fcas_target']
    observed_fcas_target = comparison_data['observed_fcas_target']
    fcas_available = comparison_data['fcas_availability']

    ax = plot_trapezium(comparison_data['unscaled_fcas_trapezium'], ax)
    ax = plot_trapezium(comparison_data['scaled_fcas_trapezium'], ax)
    ax = plot_observed_energy_target(comparison_data['observed_energy_target'], max_avail, ax)
    ax = plot_observed_fcas_target(enablement_min, enablement_max, observed_fcas_target, ax)
    ax = plot_model_energy_fcas_target(comparison_data['model_energy_target'], model_fcas_target, ax)

    ax.set_title(f"{comparison_data['trade_type']} - {fcas_available}")
    ax.set_xlabel('Energy (MW)')
    ax.set_ylabel('FCAS (MW)')


def plot_fcas_solution(data, preprocessed_data, solution):
    """Plot FCAS solution"""

    # Trader solutions
    trader_solutions, _ = check_trader_solution(data, solution)

    offers = {}
    for (trader_id, trade_type) in preprocessed_data['S_TRADER_FCAS_OFFERS']:
        offers.setdefault(trader_id, []).append(trade_type)

    # Sorted trader IDs
    trader_ids = list(offers.keys())
    trader_ids.sort()
    for trader_id in trader_ids:
        # Initialise axes
        fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8)) = plt.subplots(ncols=2, nrows=4)
        axs = {'R6SE': ax1, 'L6SE': ax2, 'R60S': ax3, 'L60S': ax4, 'R5MI': ax5, 'L5MI': ax6, 'R5RE': ax7, 'L5RE': ax8}

        for trade_type in offers[trader_id]:
            # Get FCAS and model data
            comparison_data = get_fcas_solution_comparison_data(preprocessed_data, trader_solutions, trader_id,
                                                                trade_type)

            # Plot FCAS solution
            plot_fcas_solution_comparison(comparison_data, axs[trade_type])

        # Turn off axes if missing offer
        for trade_type, ax in axs.items():
            if trade_type not in offers[trader_id]:
                ax.axis('off')

        # Format figure
        fig.suptitle(trader_id, x=0.52, y=0.98)
        fig.set_size_inches(5, 10)
        fig.subplots_adjust(hspace=0.8, wspace=0.4, top=0.92)

        fig.savefig(f"utils/plots/{trader_id.replace('/', '')}.png")
        plt.close(fig)


def check_target_mse(data, solution):
    """Compute mean square error for each trade type"""

    # Get trader solution
    _, df = check_trader_solution(data, solution)

    # Compute the MSE for each offer type
    mse = (df['abs_difference'].apply(lambda x: x ** 2).reset_index().groupby('level_1')['abs_difference'].mean()
           .rename_axis('mse').round(4))

    return mse


def check_fcas_availability(data, preprocessed_data):
    """Check if preprocessed FCAS availability conforms with observed trader solution"""

    # Trader solution
    trader_solution = get_observed_trader_solution(data)

    # Mapping between trader solution keys and model keys
    flag_map = {'L5RE': '@L5RegFlags', 'L6SE': '@L6Flags', 'L60S': '@L60Flags', 'L5MI': '@L5Flags',
                'R5RE': '@R5RegFlags', 'R6SE': '@R6Flags', 'R60S': '@R60Flags', 'R5MI': '@R5Flags'}

    # Container for output
    out = {}
    for (i, j), k in preprocessed_data['preprocessed']['FCAS_AVAILABILITY'].items():
        # Flag=1 or 3 means FCAS is enabled (from docs)
        if k in [1, 3]:
            observed_availability = True
        # FCAS isn't enabled
        else:
            observed_availability = False

        # Check if observed solution is the same as the preprocessed solution
        if observed_availability != k:
            out[(i, j)] = trader_solution[i][flag_map[j]]

    return out


def check_fcas_max_availability(data, solution):
    """Get FCAS max availability"""

    # Get trader solution
    _, df_s = check_trader_solution(data, solution)
    _, df_m = fcas_calculations.get_fcas_max_availability(data)

    # Combine computed maximum with model results DataFrame
    df_c = df_s.join(df_m[['min']], how='left')

    return df_c
