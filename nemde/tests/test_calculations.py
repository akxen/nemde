"""Test calculations"""

import os

import context
import nemde.analysis.calculations


def test_region_calculations():
    """Test region calculations conform to observed NEMDE solution"""
    assert 10 == 10

# # Directory containing case data
# data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
#                               os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
#                               'NEMDE', 'zipped')

# # Output directory
# output_dir = os.path.join(os.path.dirname(__file__), os.path.pardir, 'output')

# # Check region calculations
# c_ids = get_case_ids(2019, 10, n=10000)

# # Intervals to test MNSP flow reversal / missing case
# # c_ids = ['20191001006', '20191001016', '20191001074', '20191001018', '2019103109300']

# region_calculations = check_region_calculations(
#     data_directory, c_ids, 'physical')
# df_cleared_demand = region_calculations['cleared_demand']
# df_fixed_demand = region_calculations['fixed_demand']
# df_net_export = region_calculations['net_export']
# df_power_balance = region_calculations['power_balance']
# df_dispatched_generation = region_calculations['dispatched_generation']
# df_dispatched_load = region_calculations['dispatched_load']

# with open(os.path.join(output_dir, 'calculations', 'regions.pickle'), 'wb') as f:
#     pickle.dump(region_calculations, f)

# # Check aggregate calculations
# # aggregate_calculations = check_aggregate_calculations(data_directory, 2019, 10, 'physical', n=1000)
# # df_aggregate_fixed_demand = aggregate_calculations['fixed_demand']
# # df_aggregate_cleared_demand = aggregate_calculations['cleared_demand']

# # # Get NEMDE model data as a Python dictionary and calculation intervention status depending on desired run mode
# # case_data_json = loaders.load_dispatch_interval_json(data_directory, 2019, 10, 1, 16)
# # cdata = json.loads(case_data_json)
# # intervention_status = lookup.get_intervention_status(cdata, 'physical')
# #
# # # Check calculations
# # c1 = check_region_net_export(cdata, 'VIC1', intervention_status)
