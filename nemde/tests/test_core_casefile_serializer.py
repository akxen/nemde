"""
Test serializing casefile data into a format that can be consumed by the model
constructor
"""

import os
import logging

import xmltodict

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.serializers.casefile_serializer import construct_case

logger = logging.getLogger(__name__)


def test_casefile_serializer():
    year = int(os.environ['TEST_YEAR'])
    month = int(os.environ['TEST_MONTH'])
    case_id = f'{year}{month:02}01001'
    casefile = load_base_case(case_id=case_id)

    serialized_casefile = construct_case(data=casefile, mode='target')
    logger.info(serialized_casefile)
