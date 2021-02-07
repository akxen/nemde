"""
Test algorithms used to extract additional information from casefiles
"""

import pytest

import context
from nemde.core.casefile import lookup
from nemde.io.casefile import load_base_case
from nemde.core.casefile.algorithms import get_parsed_interconnector_loss_model_segments
from nemde.core.casefile.algorithms import get_interconnector_loss_estimate
from nemde.config.setup_variables import setup_environment_variables

setup_environment_variables()


@pytest.fixture(scope='module')
def casefile():
    return load_base_case('20201101001')


def test_get_parsed_interconnector_loss_model_segments(casefile):
    segments = get_parsed_interconnector_loss_model_segments(
        data=casefile, interconnector_id='V-SA')

    assert isinstance(segments, list)
    assert len(segments) > 0


def test_get_interconnector_loss_estimate(casefile):
    loss_estimate = get_interconnector_loss_estimate(
        data=casefile, interconnector_id='V-SA', flow=100)

    assert isinstance(loss_estimate, float)
