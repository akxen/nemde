"""Upload XML NEMDE casefiles to database"""


import os
import zlib
import time
import calendar

import MySQLdb

import context
import nemde
from nemde.io.casefile import load_xml_from_archive
from nemde.io.database.mysql import initialise_tables, post_entry, run_query
from setup_variables import setup_environment_variables


def get_month_dispatch_intervals(year, month):
    """Get all dispatch interval IDs for a given month"""

    days = range(1, calendar.monthrange(year, month)[1] + 1)
    intervals = range(1, 289)

    return [f'{year}{month:02}{d:02}{i:03}' for d in days for i in intervals]


def get_uploaded_casefile_ids(schema):
    """Get all uploaded casefile IDs"""

    sql = f"SELECT case_id FROM {schema}.casefiles"
    results = run_query(sql=sql)
    uploaded = [i['case_id'] for i in results]

    return uploaded


def get_intervals_to_upload(schema, year, month):
    """Get case IDs to upload"""

    intervals = get_month_dispatch_intervals(year=year, month=month)
    uploaded = get_uploaded_casefile_ids(schema=schema)

    to_upload = list(set(intervals) - set(uploaded))
    to_upload.sort()

    return to_upload


def upload_casefile(data_dir, schema, year, month, day, interval):
    """Upload a single casefile"""

    # Load casefile and construct case ID
    casefile = load_xml_from_archive(data_dir=data_dir, year=year, month=month,
                                     day=day, interval=interval)

    # Construct entry to be uploaded
    entry = {
        'case_id': f'{year}{month:02}{day:02}{interval:03}',
        'casefile': zlib.compress(casefile),
        'upload_timestamp': time.time(),
    }

    post_entry(schema=schema, table='casefiles', entry=entry)


def upload_casefiles(schema, data_dir, year, month):
    """Upload casefiles for a given month to the database"""

    # Initialise database tables
    initialise_tables(schema=schema)

    # All dispatch intervals for a given month
    intervals = get_intervals_to_upload(schema=schema, year=year, month=month)

    for i in intervals:

        # Extract year, month, day, and interval from casefile ID
        year, month, day, interval_id = int(i[:4]), int(i[4:6]), int(i[6:8]), int(i[8:])

        # Upload file if it's not already in table
        try:
            upload_casefile(data_dir=data_dir, schema=schema, year=year,
                            month=month, day=day, interval=interval_id)
            print('Uploaded', i)
        except MySQLdb.IntegrityError:
            print('Skipping', i)


if __name__ == '__main__':
    setup_environment_variables('offline-host.env')

    # Upload casefiles for a given month
    db_schema = os.getenv('MYSQL_SCHEMA')
    casefile_dir = os.getenv('CASEFILE_DIR')
    upload_casefiles(schema=db_schema, data_dir=casefile_dir, year=2020, month=11)
