"""Import environment variables"""

import os

from dotenv import load_dotenv


def setup_environment_variables():
    """Setup environment variables depending on online / offline operation"""

    # Select correct ENV file
    if os.environ.get('ONLINE_FLAG') == 'true':
        env_filename = 'online.env'
    else:
        env_filename = 'offline.env'

    # Load variables
    load_dotenv(os.path.join(os.path.dirname(__file__), env_filename))
