"""
Test loading of casefiles
"""

import context
from nemde.io.casefile import load_xml_from_database
from nemde.config.setup_variables import setup_environment_variables

setup_environment_variables(online=False)


def test_load_casefile_from_database():
    """Load casefile from a database"""

    casefile = load_xml_from_database(year=2020, month=11, day=1, interval=1)

    assert isinstance(casefile, str)
