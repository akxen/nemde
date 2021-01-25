"""
Functions used to modify / patch casefiles
"""

import jsonpatch
from jsonpath_ng.ext import parse

from nemde.errors import CasefileUpdaterLookupError


def convert_path(path):
    """
    Convert jsonpath format so it's compatible with jsonpatch

    Parameters
    ----------
    path : str
        jsonpath format

    Returns
    -------
    Path in format compatible with jsonpatch

    Example:
        input = 'TraderPeriod.[0].TradeCollection.Trade.[0].@BandAvail1'
        output = '/TraderPeriod/0/TradeCollection/Trade/0/@BandAvail1'
    """

    return '/' + path.replace('[', '').replace(']', '').replace('.', '/')


def get_patch_operation(casefile, update):
    """
    Construct dictionary detailing patch info

    Parameters
    ----------
    casefile : dict
        NEMDE casefile

    update : dict
        Describes path to element to be updated, and an update value. E.g.

        update = {
            'path':
                "NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.\
                TraderPeriodCollection.TraderPeriod[?(@TraderID=='AGLHAL')].\
                TradeCollection.Trade[?(@TradeType=='ENOF')].@BandAvail1",
            'value': 20
        }

    Returns
    -------
    operation : dict
        Patch operation to apply
    """

    # Elements matching the update path
    elements = [match for match in parse(update.get('path')).find(casefile)]

    # Only one element should be returned
    if len(elements) != 1:
        message = f'Path does not uniquely identify object. {len(elements)} identified.'
        raise CasefileUpdaterLookupError(message)

    # Full path to element that should be updated
    element_path = str(elements[0].full_path)

    # Convert path so it's compatible with JSON patch format
    update_path = convert_path(path=element_path)

    # Path operation to perform
    operation = {'op': 'replace', 'path': update_path, 'value': update.get('value')}

    return operation


def patch_casefile(casefile, updates):
    """
    Patch an existing casefile

    Parameters
    ----------
    casefile : dict
        NEMDE casefile

    updates : list
        Operations used to patch casefile

    Returns
    -------
    Updated casefile with patches applied
    """

    # Create patch object and apply to casefile
    patch = jsonpatch.JsonPatch(updates)

    return patch.apply(casefile)
