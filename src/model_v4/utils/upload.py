"""Upload data to database"""

import os
import time

import simplejson

import loaders
import database

if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Define the dispatch interval to investigate
    di_year, di_month, di_day, di_interval = 2019, 10, 7, 243
    di_case_id = f'{di_year}{di_month:02}{di_day:02}{di_interval:03}'

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_directory, di_year, di_month, di_day, di_interval)

    # Entry to post into database
    entry = {
        'upload_timestamp': time.time(),
        'case_id': di_case_id,
        'casefile': case_data_json
    }

    # Initialise tables
    database.initialise_tables(os.environ['MYSQL_DATABASE'])

    # Post casefile to database
    database.post_entry(os.environ['MYSQL_DATABASE'], 'casefiles', entry)
