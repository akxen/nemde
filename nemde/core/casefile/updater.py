


import xmltodict

import os
import sys
import re
from collections import abc
from itertools import chain, starmap

import json
import jsonpatch
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse

base_path = os.path.join(os.path.dirname(__file__), os.path.pardir,
                         os.path.pardir, os.path.pardir)
sys.path.append(base_path)

from nemde.io.casefile import load_xml_from_database
from nemde.config.setup_variables import setup_environment_variables
setup_environment_variables()


def load_casefile(data_dir):
    with open(os.path.join(data_dir, '20201101001.json'), 'r') as f:
        data = json.load(f)

    return data


def load_patch(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), 'r') as f:
        data = json.load(f)

    return data


def unpack(parent_key, parent_value):
    """Flatten list"""

    if isinstance(parent_value, dict):
        for child_key, child_value in parent_value.items():
            flattened_key = f'{parent_key}/{child_key}'
            yield flattened_key, child_value

    elif isinstance(parent_value, list):
        i = 0
        for child_value in parent_value:
            flattened_key = f'{parent_key}/{i}'
            i += 1
            yield flattened_key, child_value

    else:
        yield parent_key, parent_value


def flatten_json(dictionary):
    """Flatten a nested json file"""

    # Keep iterating until the termination condition is satisfied
    while True:
        # Keep unpacking the json file until all values are atomic elements (not dictionary or list)
        dictionary = dict(chain.from_iterable(starmap(unpack, dictionary.items())))

        if not any(isinstance(value, abc.Mapping) for value in dictionary.values()) and \
           not any(isinstance(value, list) for value in dictionary.values()):
            break

    return dictionary


def get_path_segments(path):
    """Slice path when encountering nested arrays. Keep track of index."""

    return re.findall('([a-zA-Z/]+)(\d+)', path)


def track_path_ids(path, dictionary):
    """Extract IDs used to identify element within an array"""

    # Construct path segements
    segments = get_path_segments(path=path)

    # Container for IDs that uniquely identify list elements
    ids = []

    # Initialise ID path
    element_path = ''

    # Construct path to leaf, keeping track of ids within nested lists
    for s in segments:
        element_path = element_path + ''.join(s)

        for k, v in dictionary.items():
            # Path to key identifying list element
            id_path = re.findall(element_path + '/(@[a-zA-Z]+ID)', k)

            if id_path:
                ids.append((id_path[0], v))

    return ids


def get_json_query(path, dictionary):
    """Construct query string to use when looking up elements in casefile"""

    # Construct path segments
    segments = get_path_segments(path=path)

    # Get path IDs
    path_ids = track_path_ids(path=path, dictionary=dictionary)

    search_ids = [f"?({id_name}=='{id_value}')" for id_name, id_value in path_ids]

    if search_ids:
        search_path = ("".join([i[0][0] + i[1] for i in zip(segments, search_ids)])
                       .replace('/?', '[?')
                       .replace(')', ')]')
                       .replace('/', '.')
                       + '.' + path.split('/')[-1])
        return search_path

    # If there are no lists
    else:
        return path.replace('/', '.')


def get_casefile_path(query, dictionary):
    """Lookup element in casefile"""

    # Construct query and perform lookup
    expression = parse(query)
    elements = expression.find(dictionary)

    # Path to element
    print('EXPRESSION', expression)
    print('ELEMENTS', elements, '\n')

    if len(elements) != 1:
        raise ValueError(
            f'Should only return single element. Returned {len(elements)}')

    element_path = '/' + str(elements[0].full_path)

    # Convert to format that can be used when lookup up
    output = element_path.replace('[', '').replace(']', '').replace('.', '/')

    return output


def construct_patch_operation(path, patch, casefile):
    """Construct path operation for a given path in the patch file"""

    # Construct JSON query to perform on casefile
    query = get_json_query(path=path, dictionary=patch)

    # Lookup corresponding path in casefile
    element_path = get_casefile_path(query=query, dictionary=casefile)

    # Operation to perform
    operation = {'op': 'replace', 'path': element_path, 'value': patch[path]}

    return operation


# def patch_casefile(casefile, patch):
#     """
#     Apply a patch to a casefile. Contents of patch will overwrite corresponding
#     elemenents within the base casefile
#     """

#     # Flattened json
#     flattened = flatten_json(patch)

#     operations = []
#     for p in flattened.keys():
#         # Path operation
#         op = construct_patch_operation(path=p, patch=flattened, casefile=casefile)
#         operations.append(op)

#     # Construct patch objects and apply the patches
#     patch_operations = jsonpatch.JsonPatch(operations)
#     patched = patch_operations.apply(casefile)

#     return patched


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

    return '/' + b.replace('[', '').replace(']', '').replace('.', '/')


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
        raise ValueError(
            f'Path does not uniquely identify object. {len(elements)} identified.')

    # Full path to element that should be updated
    element_path = str(elements[0].full_path)

    # Convert path so it's compatible with JSON patch format
    update_path = convert_path(path=element_path)

    # Path operation to perform
    operation = {'op': 'replace', 'path': update_path, 'value': update.get('value')}

    return operation


def patch_casefile(casefile, updates):
    """Patch an existing casefile"""

    # Create patch object and apply to casefile
    patch = jsonpatch.JsonPatch(updates)

    return patch.apply(casefile)


if __name__ == '__main__':
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir,
                                  os.path.pardir, os.path.pardir)

    casefile = load_casefile(data_dir=data_directory)
    patch = load_patch(filename='patch_2.json')

    # patched_casefile = patch_casefile(casefile=casefile, patch=patch)

    # with open('patched.json', 'w') as f:
    #     json.dump(patched_casefile, f)

    b = 20

    # str([match for match in parse("NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.TraderPeriodCollection.TraderPeriod[?(@TraderID=='EILDON1')].TradeCollection.Trade[?(@TradeType=='ENOF')]").find(casefile)][0].full_path)

    xml = load_xml_from_database(year=2020, month=11, day=1, interval=1)

    casefile = xmltodict.parse(xml, force_list=('Trade', 'TradeTypePriceStructure',))

    # with open('list_parse.json', 'w') as f:
    #     json.dump(casefile, f)

    updates = [
        {
        'path':
        "NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.\
            TraderPeriodCollection.TraderPeriod[?(@TraderID=='AGLHAL')].\
            TradeCollection.Trade[?(@TradeType=='ENOF')].@BandAvail1",
        'value': 20
    },
    {
        'path':
        "NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.\
            TraderPeriodCollection.TraderPeriod[?(@TraderID=='EILDON1')].\
            TradeCollection.Trade[?(@TradeType=='ENOF')].@BandAvail1",
        'value': 20
    }]

    patched = patch_casefile(casefile=casefile, updates=updates)

    b = 10
