"""Save pytest report to database"""

import os
import zlib

import context
from nemde.io.database import mysql
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def save_to_db():
    """Save Pytest report to database"""

    # Get latest run ID
    run_id = mysql.get_latest_run_id(schema=os.environ['MYSQL_SCHEMA'], table='results')

    # Open pytest report
    report_path = os.path.join(
        os.path.dirname(__file__), os.path.pardir, 'nemde', 'tests', 'report.xml')
    with open(report_path, 'r') as f:
        report = f.read()

    # Construct database entry and save to database
    entry = {
        'run_id': run_id,
        'report': zlib.compress(report.encode('utf-8')),
    }

    mysql.post_entry(schema=os.environ['MYSQL_SCHEMA'], table='reports', entry=entry)

    return entry


if __name__ == '__main__':
    # Save junitxml report to database
    save_to_db()
