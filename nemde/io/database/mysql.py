"""Manage MYSQL database connection"""

import os
import csv
import time
import json

import MySQLdb
from MySQLdb.cursors import DictCursor


def get_database_credentials():
    """Get database credentials from environment variables"""

    credentials = {
        'host': os.environ['MYSQL_HOST'],
        'port': int(os.environ['MYSQL_PORT']),
        'user': os.environ['MYSQL_USER'],
        'passwd': os.environ['MYSQL_PASSWORD']
    }

    return credentials


def connect_to_database():
    """Connect to MySQL database"""

    credentials = get_database_credentials()

    # MySQL connection object
    attempts = 1
    while attempts <= 5:
        try:
            conn = MySQLdb.connect(cursorclass=DictCursor, charset='utf8', **credentials)
            break
        except MySQLdb.OperationalError as e:
            print(e)
            time.sleep(attempts * 5)

        attempts += 1

    # Cursor
    cur = conn.cursor()

    return conn, cur


def close_connection(conn, cur):
    """Close database connection"""

    cur.close()
    conn.close()


def create_table(schema, table):
    """
    Create SQL table based on template.

    Parameters
    ----------
    schema : str
        Name of database schema in which table should be created

    table : str
        Name of MySQL table. Note this must correspond with the CSV template.
    """

    # Container for rows in the CSV template
    columns = []

    with open(os.path.join(os.path.dirname(__file__), 'mysql_tables', f'{table}.csv'), newline='') as f:
        # CSV reader object
        template_writer = csv.reader(f, delimiter=',')

        # Read through roads and append column name and data type to main container
        for row in template_writer:
            columns.append(row)

    # SQL to construct column name component of MySQL syntax
    columns_sql = ', '.join([' '.join(c) for c in columns])
    sql_create_table = f"""CREATE TABLE IF NOT EXISTS {schema}.{table} ({columns_sql}, PRIMARY KEY (row_id))"""
    conn, cur = connect_to_database()

    # Create positions database if it doesn't already exist
    sql_create_database = f"""CREATE DATABASE IF NOT EXISTS {schema}"""
    cur.execute(sql_create_database)
    conn.commit()

    # Execute SQL statement then close database connection
    cur.execute(sql_create_table)
    close_connection(conn, cur)


def initialise_tables(schema):
    """
    Initialise database tables

    Parameters
    ----------
    schema : str
        Name of database
    """

    # Create tables
    tables = ['results', 'casefiles', 'reports', 'test_run_info']
    for t in tables:
        create_table(schema, t)


def post_entry(schema, table, entry):
    """
    Record entry in MySQL database

    Parameters
    ----------
    schema : str
        Name of database

    table : str
        Database table name

    entry : dict
        Data to post
    """

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


def run_query(sql):
    """Run SQL query"""

    conn, cur = connect_to_database()
    cur.execute(sql)
    conn.commit()
    results = cur.fetchall()
    close_connection(conn=conn, cur=cur)

    return results


def get_casefile_validation_results(schema, table, run_id, case_id):
    """Extract results for a given casefile for a given validation test run"""

    conn, cur = connect_to_database()
    sql = f"SELECT * FROM {schema}.{table} WHERE run_id='{run_id}' AND case_id='{case_id}'"
    cur.execute(sql)

    return cur.fetchall()[0]


def get_test_run_validation_results(schema, table, group_id):
    """Extract all results for a given validation test run"""

    conn, cur = connect_to_database()
    sql = f"SELECT * FROM {schema}.{table} WHERE group_id='{group_id}'"
    cur.execute(sql)

    return cur.fetchall()


def get_most_recent_test_run_id(schema, table):
    """Get most recent test run ID"""

    sql = f"SELECT run_id FROM {schema}.results ORDER BY row_id DESC LIMIT 1"
    result = run_query(sql=sql)

    return result[0]['run_id']


def get_most_recent_test_group_id(schema, table):
    """Get most recent test group ID"""

    sql = f"SELECT group_id FROM {schema}.results ORDER BY row_id DESC LIMIT 1"
    result = run_query(sql=sql)

    return result[0]['group_id']
