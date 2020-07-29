"""Load NEMDE case file and convert to desired format"""

import os
import io
import json
import zipfile

import xmltodict
import xml.etree.ElementTree as ET


def load_file(data_dir, year, month, day, interval):
    """
    Load NEMDE input / output file

    Parameters
    ----------
    data_dir : str
        Path to directory containing NEMDE case file data

    year : int
        Dispatch interval year

    month : int
        Dispatch interval month

    day : int
        Dispatch interval day

    interval : int
        Dispatch interval ID [1, 288]

    Returns
    -------
    File object corresponding to specified dispatch interval
    """

    z_1_name = f'NEMDE_{year}_{month:02}.zip'

    with zipfile.ZipFile(os.path.join(data_dir, z_1_name)) as z_1:
        if f'NEMDE_{year}_{month:02}/NEMDE_Market_Data/' in z_1.namelist():
            z_2_name = f'NEMDE_{year}_{month:02}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{year}{month:02}{day:02}_loaded.zip'
        elif f'{month:02}/' in z_1.namelist():
            z_2_name = f'{month:02}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{year}{month:02}{day:02}_loaded.zip'
        else:
            raise Exception('Unexpected NEMDE directory structure')

        with z_1.open(z_2_name) as z_2:
            z_2_data = io.BytesIO(z_2.read())

            with zipfile.ZipFile(z_2_data) as z_3:
                z_3_name = f'NEMSPDOutputs_{year}{month:02}{day:02}{interval:03}00.loaded'
                return z_3.open(z_3_name).read()


def load_dispatch_interval_json(data_dir, year, month, day, interval):
    """
    Load dispatch interval as JSON

    Parameters
    ----------
    data_dir : str
        Path to directory containing NEMDE case file data

    year : int
        Dispatch interval year

    month : int
        Dispatch interval month

    day : int
        Dispatch interval day

    interval : int
        Dispatch interval ID [1, 288]

    Returns
    -------
    Case file information in JSON format
    """

    # Load NEMDE inputs / outputs
    data = load_file(data_dir, year, month, day, interval)

    # Convert to dictionary - do not prepend '@' for attributes to keep consistent with XML attributes
    info = xmltodict.parse(data, attr_prefix='')

    return json.dumps(info)


def load_dispatch_interval_xml(data_dir, year, month, day, interval):
    """
    Load dispatch interval as XML

    Parameters
    ----------
    data_dir : str
        Path to directory containing NEMDE case file data

    year : int
        Dispatch interval year

    month : int
        Dispatch interval month

    day : int
        Dispatch interval day

    interval : int
        Dispatch interval ID [1, 288]

    Returns
    -------
    Case file information in XML format
    """

    # Load NEMDE inputs / outputs
    data = load_file(data_dir, year, month, day, interval)

    # Parse XML and construct tree
    tree = ET.fromstring(data)

    return tree
