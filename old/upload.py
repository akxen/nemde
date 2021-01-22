"""Upload data to database"""

import os
import time
import json
import calendar

import simplejson

import loaders
import nemde.code.database

import lookup
import transforms.simplified.case


def get_case_id(year, month, day, interval):
    """Construct case ID"""

    return f'{year}{month:02}{day:02}{interval:03}'


def upload_case(data_dir, year, month, day, interval) -> None:
    """Upload case"""

    # Get case ID
    case_id = get_case_id(year, month, day, interval)

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(data_dir, year, month, day, interval)

    # Entry to post into database
    entry = {
        'upload_timestamp': time.time(),
        'case_id': case_id,
        'casefile': case_data_json
    }

    # Initialise tables
    database.initialise_tables(os.environ['MYSQL_DATABASE'])

    # Post casefile to database
    database.post_entry(os.environ['MYSQL_DATABASE'], 'casefiles', entry)


def upload_preprocessed_case(data_dir, year, month, day, interval) -> None:
    """Upload case"""

    # Get case ID
    case_id = get_case_id(year, month, day, interval)

    # Case data in json format
    json_data = loaders.load_dispatch_interval_json(data_dir, year, month, day, interval)

    # Get NEMDE model data as a Python dictionary
    nemde_data = json.loads(json_data)

    # Check intervention status - will influence how generic constraint information is parsed
    # intervention = lookup.get_intervention_status(nemde_data, 'physical')

    # Case data presented in a simplified format - constructed from NEMDE case file
    preprocessed_case = transforms.simplified.case.construct_case(nemde_data, 'physical')

    # Entry to post into database
    entry = {
        'upload_timestamp': time.time(),
        'case_id': case_id,
        # 'case_data': simplejson.dumps(nemde_data),
        'case_data': simplejson.dumps({"placeholder": "placeholder"}),
        'preprocessed_case_data': simplejson.dumps(preprocessed_case),
    }

    # entry = {
    #     'upload_timestamp': time.time(),
    #     'case_id': case_id,
    #     'case_data': simplejson.dumps({"hi": "there"}),
    #     'preprocessed_case_data': simplejson.dumps({"hi": "there"}),
    # }

    # Initialise tables
    database.initialise_tables(os.environ['MYSQL_DATABASE'])

    # Post casefile to database
    database.post_entry(os.environ['MYSQL_DATABASE'], 'casefiles', entry)


def upload_preprocessed_month(data_dir, year, month):
    """Upload preprocessed for each day in a given month"""

    for day in range(1, calendar.monthlen(year, month) + 1):
        for interval in range(1, 289):
            case_id = get_case_id(year, month, day, interval)
            print('Processing:', case_id)
            try:
                upload_preprocessed_case(data_dir, year, month, day, interval)
            except Exception as e:
                print(e)


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Dispatch interval
    di_year, di_month, di_day, di_interval = 2019, 10, 10, 11

    # Upload pre-processed case data
    upload_preprocessed_case(data_directory, di_year, di_month, di_day, di_interval)

    # Upload month of preprocessed casefiles
    # upload_preprocessed_month(data_directory, di_year, di_month)
