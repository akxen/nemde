"""Check solution using basis report results"""

import os
import zipfile

import pandas as pd

import context
from setup_variables import setup_environment_variables


def check_casefile_solution(filename, key, run_id, case_id=None):
    """Check trader solution for a given case"""

    base_dir = os.path.join(os.path.dirname(__file__), os.path.pardir)

    # Unzip file archive, load into DataFrame
    path = os.path.join(base_dir, 'reports', f'{run_id}.zip')

    with zipfile.ZipFile(path, 'r') as f:
        df = pd.read_csv(f.open(filename))

    if case_id is None:
        mask = df['key'] == key
    else:
        mask = (df['case_id'] == case_id) & (df['key'] == key)
    out = df.loc[mask, :].sort_values(by='abs_difference', ascending=False)

    # Get startup periods
    startup_path = os.path.join(base_dir, 'casefiles', 'features', '202011_startup.csv')
    startup = pd.read_csv(startup_path)

    # Join startup periods to period solution
    out = out.merge(startup, how='left', left_on=['case_id', 'intervention'],
                    right_on=['case_id', 'intervention'])

    print(out.head(60))
    return out


if __name__ == "__main__":
    setup_environment_variables()

    run_id = 'e504c885dd38408d861a125c4f9b38d6'
    # check_casefile_solution(filename='regions.csv', key='@EnergyPrice', run_id=run_id)
    check_casefile_solution(filename='periods.csv', key='@TotalObjective', run_id=run_id)
    # check_casefile_solution(filename='regions.csv', key='@EnergyPrice', run_id=run_id)
    # s = check_casefile_solution(filename='traders.csv', key='@EnergyTarget', run_id=run_id)
    # b = 10

    # case_id = 20201116112
    # check_casefile_solution(filename='traders.csv', key='@EnergyTarget', run_id=run_id, case_id=case_id)
    # check_casefile_solution(filename='regions.csv', key='@EnergyPrice', run_id=run_id, case_id=case_id)
