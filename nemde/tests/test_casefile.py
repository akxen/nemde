"""
Test casefile conversion
"""

import context
from nemde.io.casefile import load_xml_from_database
from nemde.config.setup_variables import setup_environment_variables

setup_environment_variables(online=False)
