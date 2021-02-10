"""Initialise MySQL database tables"""

import os

import context
from nemde.io.database import mysql
from nemde.config.setup_variables import setup_environment_variables


if __name__ == '__main__':
    os.environ['ONLINE_FLAG'] = 'true'
    setup_environment_variables()

    mysql.initialise_tables(schema=os.environ['MYSQL_SCHEMA'])
