"""Use plots to compare model and NEMDE solutions"""

import matplotlib.pyplot as plt

import nemde.core.model

def plot_trader_solution_difference(data, solution, intervention):
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
            out[trade_type].append(
                (target, observed[(trader_id, intervention)][key_map[trade_type]]))

    # Initialise figure
    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8),
          (ax9, ax10)) = plt.subplots(nrows=5, ncols=2)

    # Mapping between trade types and axes
    ax_map = {'ENOF': ax1, 'LDOF': ax2,
              'R6SE': ax3, 'L6SE': ax4,
              'R60S': ax5, 'L60S': ax6,
              'R5MI': ax7, 'L5MI': ax8,
              'R5RE': ax9, 'L5RE': ax10}

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
