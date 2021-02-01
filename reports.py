"""Validate by comparing model outputs with NEMDE outputs"""

import os
import json
import itertools

import pandas as pd

from nemde.io.database.mysql import get_latest_run_id
from nemde.io.database.mysql import get_validation_results
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables(online=False)


def parse_validation_results(run_id):
    """Load validation results and convert to JSON"""

    results = get_validation_results(
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


def get_trader_price_band_results(results):
    """Get trader price band results"""

    # Construct DataFrame
    traders = [i['summary']['traders'] for i in results]
    df = pd.DataFrame(itertools.chain.from_iterable(traders))

    # Compute absolute difference between model and NEMDE values
    df['abs_difference'] = df['model'].subtract(df['actual']).abs()
    df = df.sort_values(by='abs_difference', ascending=False)

    # Conditions to check if FCAS result is consistent with price-tied solution
    cond_1 = df['model_current_price_band'] == df['actual_current_price_band']
    cond_2 = df['model_marginal_price_band'] == df['actual_current_price_band']
    cond_3 = df['model_current_price_band'] == df['actual_marginal_price_band']

    df['same_price_band'] = cond_1 | cond_2 | cond_3

    return df


def save_trader_price_band_results(results, filename):
    """Save trader summary results"""

    df = get_trader_price_band_results(results=results)
    df.to_csv(filename, index=False)


def save_trader_price_band_filtered_results(results, filename):
    """
    Only include traders for which a mismatch between model and NEMDE
    results is observed. Ignore mismatch if price band is the same between both
    solutions. Mismatches will always exist because no tie-breaking is
    enforced by NEMDE for FCAS solutions
    """

    df = get_trader_price_band_results(results=results)
    mask = ~df.loc[:, 'same_price_band'] & (df.loc[:, 'abs_difference'] > 0.001)
    df.loc[mask, :].to_csv(filename, index=False)


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

    # Save basis results
    solution_filename_map = [
        ('TraderSolution', 'traders.csv'),
        ('InterconnectorSolution', 'interconnectors.csv'),
        ('RegionSolution', 'regions.csv'),
        ('PeriodSolution', 'periods.csv')
    ]

    for (key, filename) in solution_filename_map:
        save_basis_results(results=results, key=key,
                           filename=os.path.join(output_dir, filename))

    # Save trader summary results - used to validate price-tied FCAS offers
    save_trader_price_band_results(
        results=results, filename=os.path.join(output_dir, 'traders_price_bands.csv'))

    # Save filtered trader summary results
    save_trader_price_band_filtered_results(
        results=results, filename=os.path.join(output_dir, 'traders_price_bands_filtered.csv'))


if __name__ == '__main__':
    run_id = get_latest_run_id(schema=os.environ['MYSQL_SCHEMA'], table='results')
    print(run_id)
    root_directory = os.path.join(os.path.dirname(__file__), 'validation')
    construct_validation_report(run_id=run_id, root_dir=root_directory)
