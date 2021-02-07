"""Test environment variables are loaded"""

import os

import pytest

import context
from nemde import setup_environment_variables


def test_online_environment_variables_setup():
    """Test environment variables for online application are specified"""

    setup_environment_variables()

    keys = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PORT', 'MYSQL_PASSWORD']
    for key in keys:
        assert os.environ.get(key) is not None


def test_offline_environment_variables_setup():
    """Test environment variables for offline application are specified"""

    setup_environment_variables()

    keys = ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PORT', 'MYSQL_PASSWORD']
    for key in keys:
        assert os.environ.get('MYSQL_HOST') is not None
