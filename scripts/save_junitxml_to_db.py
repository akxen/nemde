"""Save pytest report to database"""

import os
import zlib

import context
from nemde.io.database import mysql
from setup_variables import setup_environment_variables


def save_to_db():
    """Save Pytest report to database"""

    schema = os.environ['MYSQL_SCHEMA']

    # Get latest run ID
    run_id = mysql.get_most_recent_test_run_id(schema=schema, table='results')

    # Open pytest report
    report_path = os.path.join(os.path.dirname(__file__), os.path.pardir, 'reports', 'latest.xml')

    with open(report_path, 'r') as f:
        report = f.read()

    # Construct database entry and save to database
    entry = {
        'run_id': run_id,
        'report': zlib.compress(report.encode('utf-8')),
    }

    mysql.post_entry(schema=schema, table='reports', entry=entry)

    return entry


if __name__ == '__main__':
    setup_environment_variables()

    # Save junitxml report to database
    save_to_db()
