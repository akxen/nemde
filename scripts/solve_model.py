"""Solve model"""

import os

import xmltodict

import context
import nemde


if __name__ == '__main__':
    # Setup env variables
    nemde.setup_environment_variables(online=False)
    db_schema = os.environ['MYSQL_SCHEMA']

    # # Get data
    # case = '20201101001'
    # case_data = nemde.core.database.mysql.get_casefile(
    #     schema=db_schema, case_id=case)
    # case_data_json = xmltodict.parse(case_data[0]['casefile'])

    # model_data = (nemde.core.model.serializers.original.json_serializer
    #               .parse_case_data(data=case_data_json, mode='physical'))

    # # Get preprocessed attributes
    # model_data_preprocessed = (nemde.core.model.utils.preprocessing
    #                            .get_preprocessed_case_file(model_data))

    # # Construct model
    # model = nemde.core.model.model.construct_model(model_data_preprocessed)

    # # Solve model
    # model = nemde.core.model.model.solve_model(model)

    # # Solve model
    # b = 10
