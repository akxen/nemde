"""Check FCAS availability calculations - equations for generators (loads require modified formulation)"""

import os
import io
import json

import zipfile
import numpy as np
import pandas as pd

import lookup
import loaders


def get_observed_fcas_availability(data_dir, tmp_dir):
    """Get FCAS availability reported in MMS"""

    with zipfile.ZipFile(os.path.join(data_dir, 'PUBLIC_DVD_DISPATCHLOAD_201910010000.zip')) as z1:
        with z1.open('PUBLIC_DVD_DISPATCHLOAD_201910010000.CSV') as z2:
            df = pd.read_csv(z2, skiprows=1).iloc[:-1]

    # Convert intervention flag and dispatch interval to string
    df['INTERVENTION'] = df['INTERVENTION'].astype(int).astype('str')
    df['DISPATCHINTERVAL'] = df['DISPATCHINTERVAL'].astype(int).astype('str')

    #  Convert to datetime
    df['SETTLEMENTDATE'] = pd.to_datetime(df['SETTLEMENTDATE'])

    # Set index
    df = df.set_index(['DISPATCHINTERVAL', 'DUID', 'INTERVENTION'])
    df = df.sort_index()

    # Save to
    df.to_pickle(os.path.join(tmp_dir, 'fcas_availability.pickle'))

    return df


def get_generator_effective_regulation_raise_max_available(data, trader_id):
    """Get effective R5RE max available"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@MaxAvail', float)

    try:
        # AGC ramp up rate - divide by 12 to get ramp rate over dispatch interval
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float) / 12
        return min([max_avail, ramp_up])
    except:
        # No scaling applied if SCADA ramp rate = 0 or absent
        return max_avail


def get_generator_effective_regulation_lower_max_available(data, trader_id):
    """Get effective L5RE max available"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'L5RE', 'MaxAvail', float)

    # AGC ramp down rate - divide by 12 to get ramp rate over dispatch interval
    ramp_down_rate = lookup.get_trader_initial_condition(data, trader_id, 'SCADARampDnRate', float) / 12

    return min(max_avail, ramp_down_rate)


def get_generator_regulation_raise_term_1(data, trader_id):
    """Get R5RE term 1 in FCAS availability calculation"""

    # Effective max available
    max_avail = get_generator_effective_regulation_raise_max_available(data, trader_id)

    return max_avail


def get_generator_regulation_raise_availability(data, trader_id):
    """Get raise regulation availability"""

    # Terms
    term_1 = get_generator_regulation_raise_term_1(data, trader_id)

    # Compute minimum of all terms - yields FCAS availability
    max_available = min([term_1])

    return max_available


def get_generator_regulation_lower_term_1(data, trader_id):
    """Get L5RE term 1 in FCAS availability calculation"""

    # Effective max available
    max_avail = get_generator_effective_regulation_lower_max_available(data, trader_id)

    return max_avail


def get_generator_regulation_lower_availability(data, trader_id):
    """Get lower regulation availability"""

    # Terms
    term_1 = get_generator_regulation_lower_term_1(data, trader_id)

    # Compute minimum of all terms - yields FCAS availability
    max_available = min(term_1)

    return max_available


def get_generator_contingency_raise_availability(data, trader_id, trade_type):
    """Get FCAS availability for contingency raise service"""
    pass


def get_generator_contingency_lower_availability(data, trader_id, trade_type):
    """Get FCAS availability for contingency lower service"""
    pass


def get_load_regulation_raise_availability(data, trader_id):
    """Get FCAS availability for raise regulation service - loads"""
    pass


def get_load_regulation_lower_availability(data, trader_id):
    """Get FCAS availability for lower regulation service - loads"""
    pass


def get_load_contingency_raise_availability(data, trader_id, trade_type):
    """Get FCAS availability for raise contingency service - loads"""
    pass


def get_load_contingency_lower_availability(data, trader_id, trade_type):
    """Get FCAS availability for lower contingency service - loads"""
    pass


def get_trader_fcas_availability(data, trader_id, trade_type):
    """Compute FCAS availability for a given trade type"""

    # Trader type
    trader_type = lookup.get_trader_collection_attribute(data, trader_id, '@TraderType', str)

    if trade_type == 'GENERATOR':
        if trade_type == 'R5RE':
            return get_generator_regulation_raise_availability(data, trader_id)
        elif trade_type == 'L5RE':
            return get_generator_regulation_lower_availability(data, trader_id)
        elif trade_type in ['R6SE', 'R60S', 'R5MI']:
            return get_generator_contingency_raise_availability(data, trader_id, trade_type)
        elif trade_type in ['L6SE', 'L60S', 'L5MI']:
            return get_generator_contingency_lower_availability(data, trader_id, trade_type)
        else:
            raise Exception(f'Unexpected trade type: {trader_id} {trade_type}')

    elif trader_type in ['LOAD', 'NORMALLY_ON_LOAD']:
        if trade_type == 'R5RE':
            return get_load_regulation_raise_availability(data, trader_id)
        elif trade_type == 'L5RE':
            return get_load_regulation_lower_availability(data, trader_id)
        elif trade_type in ['R6SE', 'R60S', 'R5MI']:
            return get_load_contingency_raise_availability(data, trader_id, trade_type)
        elif trade_type in ['L6SE', 'L60S', 'L5MI']:
            return get_load_contingency_lower_availability(data, trader_id, trade_type)
        else:
            raise Exception(f'Unexpected trade type: {trader_id} {trade_type}')

    else:
        raise Exception(f'Unexpected trader type: {trader_id} {trader_type} {trader_type}')


def get_calculated_fcas_availability_sample(data_dir, n=5):
    """Compute FCAS availability for all traders over a random sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(10)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    # Container for model output
    out = {}

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'{i + 1}/{len(sample)}')

        # Case data in json format
        data_json = loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        data = json.loads(data_json)

        # Dispatch interval
        dispatch_interval = f'{2019}{10:02}{day:02}{interval:03}'

        # All trader FCAS offers
        trader_offers = lookup.get_trader_offer_index(data)

        # Check net export calculation for each region
        for trader_id, trade_type in trader_offers:
            # if trade_type not in ['L6SE', 'L60S', 'L5MI', 'L5RE', 'R6SE', 'R60S', 'R5MI', 'R5RE']:
            if trade_type not in ['R5RE']:
                continue

            # FCAS availability calculation
            fcas_availability = {
                (dispatch_interval, trader_id, trade_type): get_trader_fcas_availability(data, trader_id, trade_type)
            }

            # Append to main container
            out = {**out, **fcas_availability}

    # Convert to pandas Series
    df = pd.Series(out)

    return out, df


def check_fcas_availability(calculated, observed):
    """Check FCAS availability"""

    # Re-arrange calculated FCAS availability frame
    df_1 = calculated.unstack()
    df_1 = df_1.rename_axis(['DISPATCHINTERVAL', 'DUID'])

    # Join observed FCAS availability
    df_2 = df_1.join(observed.loc[(slice(None), slice(None), '0'), :], how='left')

    # Calculated and observed FCAS availability labels
    labels = [('R5RE', 'RAISEREGACTUALAVAILABILITY')]

    # Difference
    difference = pd.concat([df_2[i].subtract(df_2[j]).rename(i) for i, j in labels], axis=1)

    # Compute max difference
    max_difference = difference.abs().max()

    return difference, max_difference


if __name__ == '__main__':
    # Directory containing MMS FCAS availability data
    fcas_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir, 'data')

    # Directory containing NEMDE case data
    nemde_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                   os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                   'NEMDE', 'zipped')

    # Directory for tmp files
    tmp_directory = os.path.join(os.path.dirname(__file__), 'tmp')

    # Case data in json format
    case_data_json = loaders.load_dispatch_interval_json(nemde_directory, 2019, 10, 1, 217)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Observed FCAS availability
    df_o = get_observed_fcas_availability(fcas_directory, tmp_directory)

    # Calculated FCAS availability
    fcas_avail, df_fcas_avail = get_calculated_fcas_availability_sample(nemde_directory, n=1)

    # Compute difference between observed and calculated FCAS availability
    df_d, max_d = check_fcas_availability(df_fcas_avail, df_o)
