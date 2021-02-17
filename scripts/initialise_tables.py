"""Initialise MySQL database tables"""

import os

import context
from nemde.io.database import mysql
from setup_variables import setup_environment_variables


if __name__ == '__main__':
    setup_environment_variables()

    mysql.initialise_tables(schema=os.environ['MYSQL_SCHEMA'])
