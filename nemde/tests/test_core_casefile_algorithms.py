"""
Test algorithms used to extract additional information from casefiles
"""

import os
import pytest

import context
from nemde.core.casefile import lookup
from nemde.io.casefile import load_base_case
from nemde.core.casefile.algorithms import get_parsed_interconnector_loss_model_segments
from nemde.core.casefile.algorithms import get_interconnector_loss_estimate


@pytest.fixture(scope='module')
def casefile():
    year = int(os.environ['TEST_YEAR'])
    month = int(os.environ['TEST_MONTH'])
    case_id = f'{year}{month:02}01001'
    return load_base_case(case_id=case_id)


def test_get_parsed_interconnector_loss_model_segments(casefile):
    segments = get_parsed_interconnector_loss_model_segments(
        data=casefile, interconnector_id='V-SA')

    assert isinstance(segments, list)
    assert len(segments) > 0


def test_get_interconnector_loss_estimate(casefile):
    loss_estimate = get_interconnector_loss_estimate(
        data=casefile, interconnector_id='V-SA', flow=100)

    assert isinstance(loss_estimate, float)
