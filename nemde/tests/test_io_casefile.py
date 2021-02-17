"""
Test loading of casefiles
"""

import os

import pytest

import context
from nemde.io.casefile import load_xml_from_archive


@pytest.mark.skip(reason='Not including casefile archive in container')
def test_load_casefile_from_database():
    """Load casefile from a database"""

    casefile = load_xml_from_archive(data_dir=os.getenv('CASEFILE_DIR'),
                                     year=2020, month=11, day=1, interval=1)

    assert isinstance(casefile, bytes)
