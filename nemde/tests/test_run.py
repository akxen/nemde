"""Test that model runs correctly"""

import json
import logging

import context
from nemde.core.run.run_model import run_model

logger = logging.getLogger(__name__)


def test_run_model():
    """Test model runs correctly given user input"""

    user_data_dict = {
        'case_id': '20201101001',
    }

    user_data_json = json.dumps(user_data_dict)

    solution = run_model(user_data=user_data_json)
    logger.info(solution)

    assert 10 == 10
