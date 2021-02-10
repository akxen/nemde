"""Check solution using basis report results"""

import os
import zipfile

import pandas as pd

import context
from nemde.io.database import mysql
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def check_period_solution(run_id=None):
    """Check period solution"""

    # Get latest run ID if none specified
    if run_id is None:
        run_id = mysql.get_latest_run_id(schema=os.environ['MYSQL_SCHEMA'], table='results')

    # Unzip file archive, load into DataFrame
    path = os.path.join(os.path.dirname(__file__), 'validation', f'{run_id}.zip')

    with zipfile.ZipFile(path, 'r') as f:
        df = pd.read_csv(f.open('periods.csv'))

    mask = df['key'] == '@TotalObjective'
    out = df.loc[mask, :].sort_values(by='abs_difference', ascending=False)

    # Get startup periods
    startup_path = os.path.join(
        os.path.dirname(__file__), 'casefiles', '202011_startup.csv')
    startup = pd.read_csv(startup_path)

    # Join startup periods to period solution
    out = out.merge(startup, how='left', left_on=['case_id', 'intervention'],
                    right_on=['case_id', 'intervention'])

    print(out.head(60))
    return out


def check_casefile_solution(filename, key, case_id=None, run_id=None):
    """Check trader solution for a given case"""

    # Get latest run ID if none specified
    if run_id is None:
        run_id = mysql.get_latest_run_id(schema=os.environ['MYSQL_SCHEMA'], table='results')

    # Unzip file archive, load into DataFrame
    path = os.path.join(os.path.dirname(__file__), 'validation', f'{run_id}.zip')

    with zipfile.ZipFile(path, 'r') as f:
        df = pd.read_csv(f.open(filename))

    if case_id is None:
        mask = df['key'] == key
    else:
        mask = (df['case_id'] == case_id) & (df['key'] == key)
    out = df.loc[mask, :].sort_values(by='abs_difference', ascending=False)

    # Get startup periods
    startup_path = os.path.join(
        os.path.dirname(__file__), 'casefiles', '202011_startup.csv')
    startup = pd.read_csv(startup_path)

    # Join startup periods to period solution
    out = out.merge(startup, how='left', left_on=['case_id', 'intervention'],
                    right_on=['case_id', 'intervention'])

    print(out.head(60))
    return out


if __name__ == "__main__":
    run_id = '95e84bdb88444ba2846a46aa7dc39402'
    # check_period_solution(run_id=run_id)
    # check_period_solution()
    # check_casefile_solution(filename='traders.csv', case_id=20201128127, key='@EnergyTarget')
    check_casefile_solution(filename='regions.csv', key='@EnergyPrice')
    # check_casefile_solution(filename='traders.csv', key='@EnergyTarget')
    check_casefile_solution(filename='periods.csv', key='@TotalObjective')
