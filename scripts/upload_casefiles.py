"""Upload XML NEMDE casefiles to database"""


import os
import zlib
import time
import calendar

import context
import nemde
from nemde.io.database.mysql import initialise_tables
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables(online=False)


def get_month_dispatch_intervals(year, month):
    """Get all dispatch interval IDs for a given month"""

    days = range(1, calendar.monthrange(2020, 11)[1] + 1)
    intervals = range(1, 289)

    return [(year, month, d, i) for d in days for i in intervals]


def upload_casefile(data_dir, schema, year, month, day, interval):
    """Upload a single casefile"""

    # Load casefile and construct case ID
    casefile = nemde.core.casefile.load.load_file(
        data_dir=data_dir, year=year, month=month, day=day,
        interval=interval)

    # TODO: check if compression is necessary
    # compressed = zlib.compress(casefile)

    case_id = f'{year}{month:02}{day:02}{interval:03}'

    # Construct entry to be uploaded
    entry = {
        'case_id': case_id,
        'casefile': casefile,
        'upload_timestamp': time.time(),
    }

    nemde.core.database.mysql.post_entry(
        schema=schema, table='casefiles', entry=entry)


def upload_casefiles(schema, data_dir, year, month):
    """Upload casefiles for a given month to the database"""

    # Initialise database tables
    initialise_tables(schema=schema)

    # All dispatch intervals for a given month
    intervals = get_month_dispatch_intervals(year=year, month=month)

    for interval_id in intervals:
        print('Uploading', interval_id)
        year, month, day, interval = interval_id
        upload_casefile(data_dir=data_dir, schema=schema, year=year,
                        month=month, day=day, interval=interval)


if __name__ == '__main__':
    # Setup env variables
    nemde.config.setup_variables.setup_environment_variables(online=False)

    # Folder containing zipped NEMDE casefiles
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                  os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb',
                                  'Reports', 'Data_Archive', 'NEMDE', 'zipped')

    # Upload casefiles for a given month
    db_schema = os.environ['MYSQL_SCHEMA']
    upload_casefiles(schema=db_schema, data_dir=data_directory,
                     year=2020, month=11)
