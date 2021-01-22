"""Load NEMDE case file and convert to desired format (JSON / XML)"""

import os
import io
import json
import zipfile

import xmltodict
import xml.etree.ElementTree as ET


def convert_to_json(data):
    """
    Convert NEMDE casefile to JSON format

    Parameters
    ----------
    data : str
        Casefile data as XML string

    Returns
    -------
    Case file information in JSON format
    """

    return json.dumps(xmltodict.parse(data))


def convert_to_xml(data):
    """
    Convert NEMDE casefile to XML

    Parameters
    ----------
    data : str
        Casefile data as XML string

    Returns
    -------
    Case file information in XML format
    """

    return ET.fromstring(data)
