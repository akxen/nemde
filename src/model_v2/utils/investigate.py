"""Check MMS data"""

import os
import io

import zipfile
import pandas as pd


def get_fcas_requirement(data_dir, settlement_date, region_id):
    """Get FCAS requirement"""

    with zipfile.ZipFile(os.path.join(data_dir, 'PUBLIC_DVD_DISPATCH_FCAS_REQ_201910010000.zip')) as z1:
        with z1.open('PUBLIC_DVD_DISPATCH_FCAS_REQ_201910010000.CSV') as z2:
            df = pd.read_csv(z2, skiprows=1).iloc[:-1]

    df_o = df.loc[(df['SETTLEMENTDATE'] == settlement_date) & (df['REGIONID'] == region_id), :]

    return df_o


def get_fcas_price(data_dir, settlement_date, region_id):
    """Get FCAS price"""

    with zipfile.ZipFile(os.path.join(data_dir, 'PUBLIC_DVD_DISPATCHPRICE_201910010000.zip')) as z1:
        with z1.open('PUBLIC_DVD_DISPATCHPRICE_201910010000.CSV') as z2:
            df = pd.read_csv(z2, skiprows=1).iloc[:-1]

    df_o = df.loc[(df['SETTLEMENTDATE'] == settlement_date) & (df['REGIONID'] == region_id), :]

    return df_o


if __name__ == '__main__':
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir, 'data')
    print(os.listdir(data_directory))

    # Settlement date and region ID
    interval_date = '2019/10/10 04:05:00'
    region = 'TAS1'

    # FCAS requirement data for a given region and trading interval
    df_r = get_fcas_requirement(data_directory, interval_date, region)

    # FCAS price
    df_p = get_fcas_price(data_directory, interval_date, region)

    # Save CSVs
    df_r.to_csv('fcas_req.csv')
    df_p.T.to_csv('fcas_price.csv')
