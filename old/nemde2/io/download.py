"""Download NEMDE casefiles"""

import os
import sys

import dropbox
import requests
import pandas as pd
from datetime import datetime


class NEMDEDownloader:
    def __init__(self, download_dir):
        self.download_dir = download_dir

    def download(self, year, month):
        """Download NEMDE data fro a given year and month"""

        # Filename
        filename = f'NEMDE_{year}_{month:02}.zip'

        # Check if file already downloaded
        if filename in os.listdir(self.download_dir):
            print(filename, 'already downloaded. Skipping.')
            return

        # URL to NEMDE file
        url = f'http://nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/{year}/{filename}'

        with open(os.path.join(self.download_dir, filename), 'wb') as f:
            print(f'Downloading {filename}')
            response = requests.get(url, stream=True)
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                f.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    done = int(50 * dl / total_length)
                    sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50 - done)))
                    sys.stdout.flush()

    def upload(self, year, month):
        """Upload downloaded NEMDE file to Dropbox"""

        # Filename
        # filename = f'NEMDE_{year}_{month:02}.zip'
        filename = 'test.txt'

        # target location in Dropbox
        target_file = os.path.join(self.download_dir, filename)

        # target = "/data/nemde/"  # the target folder
        # targetfile = target + filename  # the target path and file name
        # targetfile = os.path.join(target, filename)

        # Create a dropbox object using an API v2 key
        d = dropbox.Dropbox('token')

        # open the file and upload it
        # with filepath.open("rb") as f:
        # with open(os.path.join(filepath), 'rb') as f:
        with open(target_file, 'rb') as f:
            # upload gives you metadata about the file
            # we want to overwite any previous version of the file
            meta = d.files_upload(f.read(), target_file, mode=dropbox.files.WriteMode("overwrite"))

    def download_files(self, start, end):
        """Download files over a given date range e.g. 2018-03 to 2019-07"""

        # Months to downloaded
        months = [(i.year, i.month) for i in pd.date_range(*(pd.to_datetime([start, end]) + pd.offsets.MonthEnd()),
                                                           freq='M')]

        # Sort from most recent to oldest
        months.sort(reverse=True)

        for year, month in months:
            self.download(year, month)

    def download_latest_files(self, start='2018-01'):
        """Download latest files"""

        # Current year and month
        year, month = datetime.now().year, datetime.now().month

        # Download latest files from a given starting point
        self.download_files(start, f'{year}-{month:02}')


if __name__ == '__main__':
    # Download directory
    download_directory = os.path.join(os.path.dirname(__file__), 'output')

    # Object used to download NEMDE files
    nemde_downloader = NEMDEDownloader(download_directory)

    # Download file
    # nemde_downloader.download(2020, 3)
    # nemde_downloader.upload(2020, 3)
    nemde_downloader.download_latest_files()
