"""Check MMS data"""

import os
import io

import zipfile
import pandas as pd


if __name__ == '__main__':
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir, 'data')
    print(os.listdir(data_directory))

    with zipfile.ZipFile(os.path.join(data_directory, 'PUBLIC_DVD_DISPATCH_FCAS_REQ_201910010000.zip'), 'r') as z2:
        z2_filedata = io.BytesIO(z2.read())
    # df = pd.read_csv(os.path.join(data_directory, 'PUBLIC_DVD_DISPATCH_FCAS_REQ_201910010000.zip'))
