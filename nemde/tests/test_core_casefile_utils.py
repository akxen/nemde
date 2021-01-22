"""
Test common utility functions used to when processing casefiles
"""

from nemde.core.casefile.utils import convert_to_list


def test_convert_to_list():
    assert isinstance(convert_to_list(['1', '2', '3']), list)
    assert isinstance(convert_to_list({'key': 'value'}), list)
