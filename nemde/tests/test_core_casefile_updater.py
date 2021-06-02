"""
Test utility used to patch / update casefiles
"""

import os
import pytest

from nemde.io.casefile import load_base_case
from nemde.core.casefile import updater

from jsonpath_ng.ext import parse


@pytest.fixture(scope='module')
def casefile():
    year = int(os.environ['TEST_YEAR'])
    month = int(os.environ['TEST_MONTH'])
    case_id = f'{year}{month:02}01001'
    return load_base_case(case_id=case_id)


def test_convert_path():
    input_path = 'NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.\
            TraderPeriodCollection.TraderPeriod.[0].TradeCollection.\
            Trade.[0].@BandAvail1'

    output_path = '/NEMSPDCaseFile/NemSpdInputs/PeriodCollection/Period/\
            TraderPeriodCollection/TraderPeriod/0/TradeCollection/\
            Trade/0/@BandAvail1'

    assert (updater.convert_path(path=input_path) == output_path)


def test_get_patch_operation(casefile):
    update = {
        'path':
            ("NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period."
             "TraderPeriodCollection.TraderPeriod[?(@TraderID=='AGLHAL')]."
             "TradeCollection.Trade[?(@TradeType == 'ENOF')].@BandAvail1"),
        'value': 20
    }

    # Construct patch operation
    operation = updater.get_patch_operation(casefile=casefile, update=update)

    # Expected output
    expected = {
        'op': 'replace',
        'path': ("/NEMSPDCaseFile/NemSpdInputs/PeriodCollection/Period/"
                 "TraderPeriodCollection/TraderPeriod/0/TradeCollection/"
                 "Trade/0/@BandAvail1"),
        'value': 20}

    assert operation == expected


@pytest.mark.skip(reason='test needs to be updated')
def test_patch_casefile(casefile):
    # Update to apply
    user_input = [
        {
            'path':
                ("NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period."
                 "TraderPeriodCollection.TraderPeriod[?(@TraderID=='AGLHAL')]."
                 "TradeCollection.Trade[?(@TradeType=='ENOF')].@BandAvail1"),
            'value': 20
        },
        {
            'path':
                ("NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period."
                 "TraderPeriodCollection.TraderPeriod[?(@TraderID=='EILDON1')]."
                 "TradeCollection.Trade[?(@TradeType=='ENOF')].@BandAvail1"),
            'value': 30
        }]

    # Construct patches
    updates = [updater.get_patch_operation(casefile=casefile, update=i) for i in user_input]

    # Patched casefile
    patched = updater.patch_casefile(casefile=casefile, updates=updates)

    # Check values have been set
    assert parse(user_input[0]['path']).find(patched)[0].value == 20
    assert parse(user_input[1]['path']).find(patched)[0].value == 30
