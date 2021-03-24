"""
Create JSON schema for casefile
"""

import os
import json

from dotenv import load_dotenv
from genson import SchemaBuilder

import context
from nemde.io.casefile import load_base_case


def get_casefile_schema(case_id):
    """Construct schema for a given case file"""

    # Load case file
    casefile = load_base_case(case_id=case_id)

    # Construct schema and return it as a JSON document
    schema_builder = SchemaBuilder()
    schema_builder.add_object(casefile)

    return schema_builder.to_json()


if __name__ == '__main__':
    load_dotenv('config/offline-host.env')
    schema = get_casefile_schema(case_id='20201101001')
