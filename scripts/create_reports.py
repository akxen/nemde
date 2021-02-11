"""Validate by comparing model outputs with NEMDE outputs"""

import os
import zlib
import json
import shutil
import itertools

import pandas as pd

import context
from nemde.core.casefile import lookup
from nemde.io.casefile import load_base_case
from nemde.io.database.mysql import get_latest_run_id
from nemde.io.database.mysql import get_test_run_validation_results
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def parse_validation_results(run_id):
    """Load validation results and convert to JSON"""

    results = get_test_run_validation_results(
        schema=os.environ['MYSQL_SCHEMA'], table='results', run_id=run_id)

    return [json.loads(zlib.decompress(i['results'])) for i in results]


def save_basis_results(results, key, filename):
    """
    Save comparison results as csv. These data are used as the basis for
    summary reports.
    """

    # Construct basis results
    df = pd.DataFrame(itertools.chain.from_iterable([i[key] for i in results]))

    # Columns appearing in all results files
    index = ['case_id', 'intervention']
    metrics = ['key', 'model', 'actual', 'abs_difference']

    # Construct column based on filename
    if filename.endswith('traders.csv'):
        columns = index + ['trader_id'] + metrics
    elif filename.endswith('interconnectors.csv'):
        columns = index + ['interconnector_id'] + metrics
    elif filename.endswith('regions.csv'):
        columns = index + ['region_id'] + metrics
    elif filename.endswith('periods.csv'):
        columns = index + metrics
    else:
        raise ValueError("Unrecognised filename pattern", filename)

    # Compute absolute difference and sort by this value
    df['abs_difference'] = df['model'].subtract(df['actual']).abs()
    df = df.sort_values(by=['case_id', 'intervention'], ascending=False)

    df.loc[:, columns].to_csv(filename, index=False)


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
        path = os.path.join(output_dir, filename)
        save_basis_results(results=results, key=key, filename=path)

    # Zip validation results and save to disk
    shutil.make_archive(base_name=output_dir, format='zip', root_dir=output_dir)


if __name__ == '__main__':
    run_id = get_latest_run_id(schema=os.environ['MYSQL_SCHEMA'], table='results')
    print('Run ID:', run_id)
    root_directory = os.path.join(os.path.dirname(__file__), 'validation')
    construct_validation_report(run_id=run_id, root_dir=root_directory)
