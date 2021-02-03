"""Validate by comparing model outputs with NEMDE outputs"""

import os
import json
import itertools

import pandas as pd

import context
from nemde.core.casefile import lookup
from nemde.io.casefile import load_base_case
from nemde.io.database.mysql import get_latest_run_id
from nemde.io.database.mysql import get_test_run_validation_results
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables(online=False)


def parse_validation_results(run_id):
    """Load validation results and convert to JSON"""

    results = get_test_run_validation_results(
        schema=os.environ['MYSQL_SCHEMA'], table='results', run_id=run_id)

    return [json.loads(i['results']) for i in results]


def save_basis_results(results, key, filename):
    """Save comparison results as csv"""

    # Construct basis results
    df = pd.DataFrame(itertools.chain.from_iterable([i[key] for i in results]))

    # Compute absolute difference and sort by this value
    df['abs_difference'] = df['model'].subtract(df['actual']).abs()
    df = df.sort_values(by='abs_difference', ascending=False)

    df.to_csv(filename, index=False)


def fast_start_unit_starts_up(casefile, intervention):
    """Check if a fast start unit starts up for a given dispatch interval"""

    # Get all traders
    traders = lookup.get_trader_index(data=casefile)

    # Flag indicating if at least one fast start unit starts up
    for i in traders:
        try:
            current_mode = lookup.get_trader_collection_attribute(
                data=casefile, trader_id=i, attribute='@CurrentMode', func=str)
        except KeyError:
            continue

        # Energy target
        energy_target = lookup.get_trader_solution_attribute(
            data=casefile, trader_id=i, attribute='@EnergyTarget',
            intervention=intervention, func=float)

        if (current_mode == '0') and (energy_target > 0.005):
            return True

    # No fast start units starting up identified
    return False


def fast_start_unit_startup_periods(results):
    """
    Check if a fast start unit started up during a given interval. Model
    does not currently support multi-run approach required when modelling
    fast start unit startup intervals.
    """

    # Container for output
    out = []
    for i in results:
        case_id = i['PeriodSolution'][0]['case_id']
        casefile = load_base_case(case_id=case_id)

        # Get intervention status
        intervention = i['PeriodSolution'][0]['intervention']

        # Check if fast start units found to be startint up during interval
        startup = fast_start_unit_starts_up(casefile=casefile, intervention=intervention)
        out.append({'case_id': case_id, 'intervention': intervention,
                    'startup_flag': startup})

    return out


def construct_validation_report(run_id, root_dir):
    """
    Load data and perform calculations to check how close the approximated
    model results conform with NEMDE solutions
    """

    # Load results and convert to JSON
    results = parse_validation_results(run_id=run_id)

    # Construct directory where results are to be saved
    output_dir = os.path.join(root_dir, run_id)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'basis'), exist_ok=True)

    # Save basis results
    solution_filename_map = [
        ('TraderSolution', 'traders.csv'),
        ('InterconnectorSolution', 'interconnectors.csv'),
        ('RegionSolution', 'regions.csv'),
        ('PeriodSolution', 'periods.csv')
    ]

    for (key, filename) in solution_filename_map:
        path = os.path.join(output_dir, 'basis', filename)
        save_basis_results(results=results, key=key, filename=path)

    # Check if fast start unit starts up for a given interval
    startup_flags = fast_start_unit_startup_periods(results=results)
    (pd.DataFrame(startup_flags).sort_values(by='startup_flag', ascending=False)
     .to_csv(os.path.join(output_dir, 'startup.csv'), index=False))


if __name__ == '__main__':
    run_id = get_latest_run_id(schema=os.environ['MYSQL_SCHEMA'], table='results')
    print(run_id)
    root_directory = os.path.join(os.path.dirname(__file__), 'validation')
    construct_validation_report(run_id=run_id, root_dir=root_directory)
