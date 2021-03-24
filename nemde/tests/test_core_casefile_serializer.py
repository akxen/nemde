"""
Test serializing casefile data into a format that can be consumed by the model
constructor
"""

import logging

import xmltodict

import context
from nemde.io.casefile import load_base_case
from nemde.core.model.serializers.casefile_serializer import construct_case

logger = logging.getLogger(__name__)


def test_casefile_serializer():

    casefile = load_base_case(case_id='20201101001')

    serialized_casefile = construct_case(data=casefile, mode='target')
    logger.info(serialized_casefile)
