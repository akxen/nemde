"""Load NEMDE case file"""

import os
import io
import json
import zipfile

import xmltodict
import xml.etree.ElementTree as ET


def load_from_archive(data_dir, year, month, day, interval):
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
                try:
                    z_3_name = f'NEMSPDOutputs_{year}{month:02}{day:02}{interval:03}00.loaded'
                    return z_3.open(z_3_name).read()
                except KeyError:
                    z_3_name = f'NEMSPDOutputs_{year}{month:02}{day:02}{interval:03}00_OCD.loaded'
                    return z_3.open(z_3_name).read()


def load_from_database(year, month, day, interval):
    """Load casefile from MySQL database"""
    pass
