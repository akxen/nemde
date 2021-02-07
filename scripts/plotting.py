"""Plot solution results"""

import os
import json

import matplotlib.pyplot as plt

import context
from nemde.io.casefile import load_base_case
from nemde.io.database.mysql import get_latest_run_id
from nemde.io.database.mysql import get_casefile_validation_results
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def plot_trade_type_solution(ax, results, trade_type):
    """Plot trader solution for a given trade type"""

    x = [i['actual'] for i in results if i['trade_type'] == trade_type]
    y = [i['model'] for i in results if i['trade_type'] == trade_type]

    # Scatter plot comparing model and actual solution
    scatter_style = {'alpha': 0.5, 's': 5, 'color': 'r'}
    ax.scatter(x=x, y=y, **scatter_style)

    # Add line with slope=1 (perfect correspondence)
    smallest = min(min(x), min(y))
    largest = max(max(x), max(y))

    line_style = {'color': 'k', 'linestyle': '--', 'linewidth': 0.7, 'alpha': 0.7}
    ax.plot([smallest, largest], [smallest, largest], **line_style)

    ax.set_xlabel('Model (MW)')
    ax.set_ylabel('Observed (MW)')
    ax.set_title(trade_type)

    return ax


def plot_trader_solution(results):
    """Plot trader solution for all trade types"""

    # Initialise figure
    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8),
          (ax9, ax10)) = plt.subplots(nrows=5, ncols=2)

    # Mapping between trade types and axes
    axes = {'ENOF': ax1, 'LDOF': ax2,
            'R6SE': ax3, 'L6SE': ax4,
            'R60S': ax5, 'L60S': ax6,
            'R5MI': ax7, 'L5MI': ax8,
            'R5RE': ax9, 'L5RE': ax10}

    for trade_type, ax in axes.items():
        plot_trade_type_solution(ax=ax, results=results, trade_type=trade_type)

    fig.set_size_inches(5, 10)
    fig.subplots_adjust(hspace=0.8, wspace=0.5)


def save_case(case_id):
    """Save case as JSON"""

    case = load_base_case(case_id=case_id)

    with open(f'{case_id}.json', 'w') as f:
        json.dump(case, f)


if __name__ == '__main__':
    # Database parameters
    schema = os.environ['MYSQL_SCHEMA']
    case_id = '20201129139'

    # Get results from latests run_id
    run_id = get_latest_run_id(schema=schema, table='results')
    print('RUN ID', run_id)

    validation_results = get_casefile_validation_results(
        schema=schema, table='results', run_id=run_id, case_id=case_id)

    # Load JSON results
    results = json.loads(validation_results['results'])

    # Trader solution
    traders = results['summary']['traders']
    plot_trader_solution(results=traders)
    plt.show()

    # Base case
    save_case(case_id=case_id)
