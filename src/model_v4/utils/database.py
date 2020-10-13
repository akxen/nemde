"""Manage database connection"""

import os
import csv
import json
import time

import simplejson
import MySQLdb
import MySQLdb.cursors

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


def connect_to_database():
    """Connect to MySQL database"""

    # MySQL connection object
    conn = MySQLdb.connect(host=os.environ['MYSQL_DOCKER_HOST'],
                           user=os.environ['MYSQL_USER'],
                           passwd=os.environ['MYSQL_PASSWORD'],
                           cursorclass=MySQLdb.cursors.DictCursor)

    # Cursor
    cur = conn.cursor()

    return conn, cur


def close_connection(conn, cur):
    """Close database connection"""

    cur.close()
    conn.close()


def create_table(schema, table):
    """Create SQL table based on template.

    Parameters
    ----------
    schema : str
        Name of database schema in which table should be created

    table : str
        Name of MySQL table. Note this must correspond with the CSV template.
    """

    # Container for rows in the CSV template
    columns = []

    with open(os.path.join(os.path.dirname(__file__), 'templates', f'{table}.csv'), newline='') as f:
        # CSV reader object
        template_writer = csv.reader(f, delimiter=',')

        # Read through roads and append column name and data type to main container
        for row in template_writer:
            columns.append(row)

    # SQL to construct column name component of MySQL syntax
    columns_sql = ', '.join([' '.join(c) for c in columns])

    # SQL statement to create table
    sql_create_table = f"""CREATE TABLE IF NOT EXISTS {schema}.{table} ({columns_sql}, PRIMARY KEY (row_id))"""

    # Execute SQL statement
    conn, cur = connect_to_database()

    # Create positions database if it doesn't already exist
    sql_create_database = f"""CREATE DATABASE IF NOT EXISTS {schema}"""
    cur.execute(sql_create_database)

    conn.commit()

    # Execute SQL statement
    # print(sql_create_table)
    cur.execute(sql_create_table)

    # Close database connections
    close_connection(conn, cur)


def initialise_tables(schema):
    """Initialise database tables"""

    # Tables to create
    tables = ['run_info', 'results']

    for t in tables:
        create_table(schema, t)


def post_entry(schema, table, entry):
    """Record entry in MySQL database"""

    # Connect to MySQL database
    conn, cur = connect_to_database()

    # Column names and values corresponding to those columns
    columns, values = zip(*entry.items())

    # Columns components of SQL query
    sql_columns = ', '.join(columns)

    # Values placeholder
    sql_values_placeholder = ', '.join(len(columns) * ['%s'])

    # SQL used to insert record into database table
    sql = f'INSERT INTO {schema}.{table} ({sql_columns}) VALUES ({sql_values_placeholder})'

    # Execute query and insert record into database
    cur.execute(sql, values)
    conn.commit()

    # Close database connection
    close_connection(conn, cur)


def get_latest_run_info(schema):
    """Get most recent run ID"""

    # Get last run information
    sql_run_info = f"""SELECT * FROM {schema}.run_info ORDER BY row_id desc LIMIT 1"""

    # Connect to database
    conn, cur = connect_to_database()

    # Get last run information
    cur.execute(sql_run_info)
    results = cur.fetchall()

    # All case IDs corresponding to run
    run_id = results[0]['run_id']

    # Close connection
    close_connection(conn, cur)

    return run_id


def get_remaining_case_ids(schema):
    """Get remaining case IDs for the most recent run"""

    # Get last run information
    sql_run_info = f"""SELECT * FROM {schema}.run_info ORDER BY row_id desc LIMIT 1"""

    # Connect to database
    conn, cur = connect_to_database()

    # Get last run information
    cur.execute(sql_run_info)
    run_info_results = cur.fetchall()

    # All case IDs corresponding to run
    run_id = run_info_results[0]['run_id']
    all_case_ids = json.loads(run_info_results[0]['parameters'])['case_ids']

    # Cases that have already been completed
    sql_result_info = f"""SELECT case_id FROM {schema}.results where run_id = {run_id}"""

    # Get case IDs that have already been completed
    cur.execute(sql_result_info)
    case_results = cur.fetchall()
    completed_cases = [i['case_id'] for i in case_results]

    # Close database connection
    close_connection(conn, cur)

    # Cases that must still be completed
    remaining_cases = list(set(all_case_ids).difference(set(completed_cases)))
    remaining_cases.sort()

    return run_id, remaining_cases


def get_most_recent_run_id(schema):
    """Get the most recent run ID"""

    # Get last run information
    sql = f"""SELECT * FROM {schema}.run_info ORDER BY row_id desc LIMIT 1"""

    # Connect to database
    conn, cur = connect_to_database()

    # Get last run information
    cur.execute(sql)
    results = cur.fetchall()

    # Most recent run ID
    run_id = results[0]['run_id']

    # Close SQL connection
    close_connection(conn, cur)

    return run_id


def get_case_results(schema):
    """Get results corresponding to the most recent run"""

    # Get most recent run ID
    run_id = get_most_recent_run_id(schema)

    # Connect to database
    conn, cur = connect_to_database()

    # Cases that have already been completed
    sql = f"""SELECT * FROM {schema}.results where run_id = {run_id}"""

    # Get case IDs that have already been completed
    cur.execute(sql)
    results = cur.fetchall()

    # Close connection
    close_connection(conn, cur)

    return results


if __name__ == '__main__':
    # Initialise tables
    # initialise_tables(os.environ['MYSQL_DATABASE'])

    # Test run info entry
    run_info_entry = {
        'run_id': 20,
        'parameters': json.dumps({'case_ids': ['20191003202', '20191003210', '20191003260']})
    }
    # post_entry(os.environ['MYSQL_DATABASE'], 'run_info', run_info_entry)

    # Test results entry
    results_entry = {
        'run_id': 20,
        'run_time': int(time.time()),
        'case_id': '20191003210',
        'results': json.dumps({'': 'my results'})
    }
    # post_entry(os.environ['MYSQL_DATABASE'], 'results', results_entry)

    # Get case results corresponding to most recent run
    r = get_case_results(os.environ['MYSQL_DATABASE'])
