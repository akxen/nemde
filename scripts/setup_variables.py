"""Import environment variables"""

import os

from dotenv import load_dotenv


def setup_environment_variables(filename=None):
    """Setup environment variables depending on online / offline operation"""

    # Select correct ENV file
    if filename is None:
        env_filename = 'default.env'
    else:
        env_filename = filename

    # Load variables
    load_dotenv(os.path.join(os.path.dirname(__file__), os.path.pardir, 'config', env_filename))
