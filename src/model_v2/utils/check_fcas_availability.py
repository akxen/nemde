"""Check FCAS availability calculations - equations for generators (loads require modified formulation)"""

import os
import io
import json

import zipfile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import fcas
import lookup
import loaders
import data as data_handler


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


def get_trader_fcas_trapezium(data, trader_id, trade_type) -> dict:
    """Get trader FCAS trapezium"""

    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    high_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@HighBreakpoint', float)
    low_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@LowBreakpoint', float)
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    trapezium = {
        'EnablementMin': enablement_min,
        'EnablementMax': enablement_max,
        'HighBreakpoint': high_breakpoint,
        'LowBreakpoint': low_breakpoint,
        'MaxAvail': max_avail,
    }

    return trapezium


def get_trader_fcas_trapezium_scaled(data, trader_id, trade_type) -> dict:
    """Get scaled FCAS trapezium"""

    # FCAS trapezium
    trapezium = get_trader_fcas_trapezium(data, trader_id, trade_type)

    # Parameters
    trader_type = lookup.get_trader_collection_attribute(data, trader_id, '@TraderType', str)
    semi_dispatch = lookup.get_trader_collection_attribute(data, trader_id, '@SemiDispatch', str)

    # UIGF scaled applied to contingency FCAS offers
    if (semi_dispatch == '1') and (trade_type in ['L6SE', 'L60S', 'L5MI', 'R6SE', 'R60S', 'R5MI']):
        # Scale for UIGF
        uigf = lookup.get_trader_period_collection_attribute(data, trader_id, '@UIGF', float)
        return fcas.get_scaled_fcas_trapezium_uigf(trapezium, uigf)

    # Only apply following scaling to regulation FCAS offers
    if trade_type not in ['L5RE', 'R5RE']:
        return trapezium

    # UIGF scaling for regulation offers for semi-dispatchable plant
    if semi_dispatch == '1':
        uigf = lookup.get_trader_period_collection_attribute(data, trader_id, '@UIGF', float)
        scaled_1 = fcas.get_scaled_fcas_trapezium_uigf(trapezium, uigf)

    # No UIGF scaling if not a semi-dispatchable plant
    else:
        scaled_1 = trapezium

    # Scale AGC enablement limit (LHS)
    try:
        lmw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'LMW', float)
    except:
        lmw = None
    scaled_2 = fcas.get_scaled_fcas_trapezium_agc_enablement_limits_lhs(scaled_1, lmw)

    # Scale AGC enablement limit (RHS)
    try:
        hmw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'HMW', float)
    except:
        hmw = None
    scaled_3 = fcas.get_scaled_fcas_trapezium_agc_enablement_limits_rhs(scaled_2, hmw)

    # Ramp rates
    try:
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float)
    except:
        ramp_up = None

    try:
        ramp_down = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)
    except:
        ramp_down = None

    # Scale by AGC ramp rate - will depend on whether trader is a generator or load
    if (trader_type == 'GENERATOR') and (trade_type == 'R5RE'):
        scaled_4 = fcas.get_scaled_fcas_trapezium_agc_ramp_rate(scaled_3, ramp_up)

    elif (trader_type == 'GENERATOR') and (trade_type == 'L5RE'):
        scaled_4 = fcas.get_scaled_fcas_trapezium_agc_ramp_rate(scaled_3, ramp_down)

    elif (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (trade_type == 'R5RE'):
        scaled_4 = fcas.get_scaled_fcas_trapezium_agc_ramp_rate(scaled_3, ramp_down)

    elif (trader_type in ['LOAD', 'NORMALLY_ON_LOAD']) and (trade_type == 'L5RE'):
        scaled_4 = fcas.get_scaled_fcas_trapezium_agc_ramp_rate(scaled_3, ramp_up)

    else:
        raise Exception(f'Unhandled case: {trader_id} {trader_type} {trade_type}')

    return scaled_4


def get_trader_fcas_availability_status(data, trader_id, trade_type):
    """Check FCAS availability status"""

    # Get scaled FCAS trapezium
    trapezium = get_trader_fcas_trapezium_scaled(data, trader_id, trade_type)

    # Max availability must be greater than 0
    cond_1 = trapezium['MaxAvail'] > 0

    # Quantity greater than 0 for at least one quantity band for the given service
    max_quantity = max([lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, f'@BandAvail{i}', float)
                        for i in range(1, 11)])
    cond_2 = max_quantity > 0

    # Try and use specified FCAS condition, but if energy offer doesn't exist, then set cond_3=True by default
    trader_type = lookup.get_trader_collection_attribute(data, trader_id, '@TraderType', str)

    if trader_type == 'GENERATOR':
        energy_offer = 'ENOF'
    elif trader_type in ['LOAD', 'NORMALLY_ON_LOAD']:
        energy_offer = 'LDOF'
    else:
        raise Exception(f'Unexpected trader type: {trader_id} {trader_type}')

    # Get max available for trader's energy offer
    try:
        energy_max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, energy_offer, '@MaxAvail', float)
    # Trader may not have an energy offer, in which case set max energy available to None
    except:
        energy_max_avail = None

    if energy_max_avail is None:
        cond_3 = True
    else:
        cond_3 = energy_max_avail >= trapezium['EnablementMin']

    # FCAS enablement max >= 0
    cond_4 = trapezium['EnablementMax'] >= 0

    # Initial MW within enablement min and max
    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)
    cond_5 = trapezium['EnablementMin'] <= initial_mw <= trapezium['EnablementMax']

    # AGC is activate for regulating FCAS
    agc_status = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'AGCStatus', str)
    if trade_type in ['R5RE', 'L5RE']:
        if agc_status == '1':
            cond_6 = True
        else:
            cond_6 = False
    else:
        # Set cond_6 to True if non-regulating FCAS offer
        cond_6 = True

    # All conditions must be true in order for FCAS to be enabled
    return all([cond_1, cond_2, cond_3, cond_4, cond_5, cond_6])


def get_generator_effective_regulation_raise_max_available(data, trader_id):
    """Get effective R5RE max available"""

    # Max available from FCAS offer
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@MaxAvail', float)

    try:
        # AGC ramp up rate - divide by 12 to get ramp rate over dispatch interval
        ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate',
                                                                           float) / 12
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

    return min([max_avail, ramp_down_rate])


def get_generator_effective_regulation_raise_enablement_max(data, trader_id):
    """Get effective R5RE enablement max"""

    # Offer enablement max
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@EnablementMax', float)

    # Upper AGC limit
    agc_up_limit = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'HMW', float)

    return min([enablement_max, agc_up_limit])


def get_generator_effective_regulation_raise_enablement_min(data, trader_id):
    """Get effective R5RE enablement min"""

    # Offer enablement min
    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, 'R5RE', '@EnablementMin', float)

    # Upper AGC limit
    agc_down_limit = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'LMW', float)

    return max([enablement_min, agc_down_limit])


def get_generator_joint_ramp_raise_max(data, trader_id):
    """Get generator max joint ramp raise"""

    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)
    ramp_up = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampUpRate', float)

    return initial_mw + (ramp_up / 12)


def get_generator_joint_ramp_lower_min(data, trader_id):
    """Get generator min joint ramp lower"""

    initial_mw = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'InitialMW', float)
    ramp_down = lookup.get_trader_collection_initial_condition_attribute(data, trader_id, 'SCADARampDnRate', float)

    return initial_mw - (ramp_down / 12)


def get_upper_slope_coefficient(data, trader_id, trade_type):
    """Get upper slope coefficient"""

    # FCAS trapezium parameters
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    high_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@HighBreakpoint', float)
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    # If MaxAvail is 0 then upper slope coefficient is undefined - return None
    if max_avail == 0:
        return None
    else:
        return (enablement_max - high_breakpoint) / max_avail


def get_lower_slope_coefficient(data, trader_id, trade_type):
    """Get lower slope coefficient"""

    # FCAS trapezium parameters
    enablement_min = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMin', float)
    low_breakpoint = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@LowBreakpoint', float)
    max_avail = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@MaxAvail', float)

    # If MaxAvail is 0 then lower slope coefficient is undefined - return None
    if max_avail == 0:
        return None
    else:
        return (low_breakpoint - enablement_min) / max_avail


def get_generator_regulation_raise_term_1(data, trader_id):
    """Get R5RE term 1 in FCAS availability calculation"""

    # Parameters
    joint_ramp_raise_max = get_generator_joint_ramp_raise_max(data, trader_id)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)

    return joint_ramp_raise_max - energy_target


def get_generator_regulation_raise_term_2(data, trader_id, trade_type):
    """Get R5RE term 2 in FCAS availability calculation"""

    # Map between FCAS keys
    fcas_map = {
        'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target',
        'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target'
    }

    # FCAS availability
    fcas_availability = data_handler.get_trader_fcas_availability(data)

    # No constraint constructed if contingency FCAS unavailable
    if not fcas_availability[(trader_id, trade_type)]:
        return None

    # Parameters
    enablement_max = lookup.get_trader_quantity_band_attribute(data, trader_id, trade_type, '@EnablementMax', float)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, trade_type)
    contingency_target = lookup.get_trader_solution_attribute(data, trader_id, fcas_map[trade_type], float)

    # Ignore limit if slope coefficient = 0
    if upper_slope_coefficient == 0:
        return None

    return enablement_max - energy_target - (upper_slope_coefficient * contingency_target)


def get_generator_regulation_raise_term_3(data, trader_id):
    """Get R5RE term 3 in FCAS availability calculation"""

    # Term parameters
    enablement_max = get_generator_effective_regulation_raise_enablement_max(data, trader_id)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R5RE')

    # Ignore limit if slope coefficient = 0
    if upper_slope_coefficient == 0:
        return None

    # Undefined because max available is 0 - so max R5RE is 0
    if upper_slope_coefficient is None:
        return 0
    else:
        return (enablement_max - energy_target) / upper_slope_coefficient


def get_generator_regulation_raise_term_4(data, trader_id):
    """Get R5RE term 4 in FCAS availability calculation"""

    # Term parameters
    enablement_min = get_generator_effective_regulation_raise_enablement_min(data, trader_id)
    energy_target = lookup.get_trader_solution_attribute(data, trader_id, '@EnergyTarget', float)
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'R5RE')

    # Ignore limit if slope coefficient = 0
    if lower_slope_coefficient == 0:
        return None

    # Undefined because max available is 0 - so max R5RE is 0
    if lower_slope_coefficient is None:
        return 0
    else:
        return (energy_target - enablement_min) / lower_slope_coefficient


def get_generator_regulation_raise_term_5(data, trader_id):
    """Get R5RE term 5 in FCAS availability calculation"""

    # Effective max available
    max_avail = get_generator_effective_regulation_raise_max_available(data, trader_id)

    return max_avail


def get_generator_regulation_raise_availability(data, trader_id):
    """Get raise regulation availability"""

    # All trader offers
    offers = lookup.get_trader_offer_index(data)

    # Terms
    term_1 = get_generator_regulation_raise_term_1(data, trader_id)

    # Container for contingency FCAS terms
    contingency_fcas_terms = []
    for i in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
        # Check if contingency offer made by generator
        if (trader_id, i) in offers:
            contingency_fcas_terms.append(get_generator_regulation_raise_term_2(data, trader_id, i))

    term_3 = get_generator_regulation_raise_term_3(data, trader_id)
    term_4 = get_generator_regulation_raise_term_4(data, trader_id)
    term_5 = get_generator_regulation_raise_term_5(data, trader_id)

    # All terms
    terms = [term_1, term_3, term_4, term_5] + contingency_fcas_terms

    # Compute minimum of all terms - yields FCAS availability
    max_available = min([i for i in terms if i is not None])

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

    if trader_type == 'GENERATOR':
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

        # Check FCAS availability for each trader
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


def check_trader_fcas_trapezium(data, trader_id, trade_type):
    """Check scaled and unscaled FCAS trapezia"""

    # Scaled and unscaled FCAS trapezia
    t_1 = get_trader_fcas_trapezium(data, trader_id, trade_type)
    t_2 = get_trader_fcas_trapezium_scaled(data, trader_id, trade_type)

    fig, ax = plt.subplots()
    x_1 = [t_1['EnablementMin'], t_1['LowBreakpoint'], t_1['HighBreakpoint'], t_1['EnablementMax']]
    y_1 = [0, t_1['MaxAvail'], t_1['MaxAvail'], 0]

    x_2 = [t_2['EnablementMin'], t_2['LowBreakpoint'], t_2['HighBreakpoint'], t_2['EnablementMax']]
    y_2 = [0, t_2['MaxAvail'], t_2['MaxAvail'], 0]

    ax.plot(x_1, y_1, color='b')
    ax.plot(x_2, y_2, color='r')
    ax.set_title(f'{trader_id} {trade_type}')

    filename = f"{trader_id.replace('#', '').replace('/', '')}-{trade_type}"
    print(filename)

    fig.savefig(f"plots/fcas_check/{filename}.png")
    plt.show()
    # plt.close()


def check_trader_fcas_trapezia(data):
    """Check scaled and unscaled FCAS trapezia for all FCAS offers"""

    offers = lookup.get_trader_offer_index(data)

    for i, j in offers:
        if j not in ['ENOF', 'LDOF']:
            check_trader_fcas_trapezium(data, i, j)


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
    case_data_json = loaders.load_dispatch_interval_json(nemde_directory, 2019, 10, 10, 1)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)
    cdata_parsed = data_handler.parse_case_data_json(case_data_json)

    # Observed FCAS availability
    # df_o = get_observed_fcas_availability(fcas_directory, tmp_directory)
    # df_o = pd.read_pickle('tmp/fcas_availability.pickle')

    # Calculated FCAS availability
    # fcas_avail, df_fcas_avail = get_calculated_fcas_availability_sample(nemde_directory, n=1)

    # Compute difference between observed and calculated FCAS availability
    # df_d, max_d = check_fcas_availability(df_fcas_avail, df_o)

    # c1 = get_generator_regulation_raise_availability(cdata, 'BW02')
    # c1_s = lookup.get_trader_solution_attribute(cdata, 'BW02', '@R5RegTarget', float)

    # c3 = get_trader_fcas_availability_status(cdata, 'BW02', 'R5RE')
    # trader_id, trade_type = 'BW02', 'R5RE'
    # check_trader_fcas_trapezium(cdata, trader_id, trade_type)
    # check_trader_fcas_trapezia(cdata)

    # Scaled and unscaled FCAS trapezia
    trader_id, trade_type = 'ER01', 'L5RE'
    t_1 = get_trader_fcas_trapezium(cdata, trader_id, trade_type)
    t_2 = get_trader_fcas_trapezium_scaled(cdata, trader_id, trade_type)
    check_trader_fcas_trapezium(cdata, trader_id, trade_type)
