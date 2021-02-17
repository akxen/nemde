"""
Load NEMDE casefile
"""

import os
import io
import zlib
import zipfile

import xmltodict

from nemde.io.database.mysql import connect_to_database
from nemde.errors import CasefileNotFoundError, CasefileQueryError, CasefileValueError


def load_xml_from_archive(data_dir, year, month, day, interval):
    """
    Load NEMDE casefile from zip archive

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


def load_xml_from_database(year, month, day, interval):
    """Load casefile from MySQL database

    Parameters
    ----------
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
    Casefile as an XML string
    """

    # Get schema and construct case ID
    schema = os.environ.get('MYSQL_SCHEMA')
    case_id = f'{year}{month:02}{day:02}{interval:03}'

    # Connect to database and extract NEMDE casefile
    conn, cur = connect_to_database()
    sql = f"SELECT casefile FROM {schema}.casefiles WHERE case_id='{case_id}'"
    cur.execute(sql)
    result = cur.fetchall()

    # Check result set is expected length
    if not result:
        raise CasefileNotFoundError

    if len(result) > 1:
        raise CasefileQueryError

    # Extract casefile string from record
    casefile = zlib.decompress(result[0].get('casefile')).decode('utf-8')

    if isinstance(casefile, str):
        return casefile
    else:
        raise CasefileValueError


def load_base_case(case_id):
    """Load case data as dictionary given case ID"""

    # Decompose case ID
    year, month, day, interval = (int(case_id[:4]), int(case_id[4:6]),
                                  int(case_id[6:8]), int(case_id[8:]))

    # Load XML and convert to dictionary
    # base = load_xml_from_archive(data_dir=os.getenv('CASEFILE_DIR'), year=year,
    #  month=month, day=day, interval=interval)
    base = load_xml_from_database(year=year, month=month, day=day, interval=interval)

    # Force some nodes to always have lists
    force_list = ('Trade', 'TradeTypePriceStructure',)

    return xmltodict.parse(base, force_list=force_list)


def load_base_case_from_archive(case_id, data_dir):
    """Load case data as dictionary given case ID"""

    # Decompose case ID
    year, month, day, interval = (int(case_id[:4]), int(case_id[4:6]),
                                  int(case_id[6:8]), int(case_id[8:]))

    # Load XML and convert to dictionary
    base = load_xml_from_archive(data_dir=data_dir, year=year,
                                 month=month, day=day, interval=interval)

    # Force some nodes to always have lists
    force_list = ('Trade', 'TradeTypePriceStructure',)

    return xmltodict.parse(base, force_list=force_list)
