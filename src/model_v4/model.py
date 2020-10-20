"""Model used to construct and solve NEMDE approximation"""

import os
import json
import time
import pickle
import zipfile
import calendar

import simplejson
import numpy as np
import pandas as pd
import pyomo.environ as pyo

import utils.fcas
import utils.data
import utils.lookup
import utils.loaders
import utils.solution
import utils.analysis
import utils.database
import utils.validate


def define_sets(m, data):
    """Define sets"""

    # NEM regions
    m.S_REGIONS = pyo.Set(initialize=data['S_REGIONS'])

    # Market participants (generators and loads)
    m.S_TRADERS = pyo.Set(initialize=data['S_TRADERS'])

    # Semi-dispatchable traders
    m.S_TRADERS_SEMI_DISPATCH = pyo.Set(initialize=data['S_TRADERS_SEMI_DISPATCH'])

    # Trader offer types
    m.S_TRADER_OFFERS = pyo.Set(initialize=data['S_TRADER_OFFERS'])

    # Trader FCAS offers
    m.S_TRADER_FCAS_OFFERS = pyo.Set(initialize=data['S_TRADER_FCAS_OFFERS'])

    # Trader energy offers
    m.S_TRADER_ENERGY_OFFERS = pyo.Set(initialize=data['S_TRADER_ENERGY_OFFERS'])

    # Trader fast start units TODO: check if '@FastStart'='0' should also be included when constructing set
    m.S_TRADER_FAST_START = pyo.Set(initialize=data['S_TRADER_FAST_START'])

    # Price tied bands
    m.S_TRADER_PRICE_TIED = pyo.Set(initialize=data['S_TRADER_PRICE_TIED'])

    # Generic constraints
    m.S_GENERIC_CONSTRAINTS = pyo.Set(initialize=data['S_GENERIC_CONSTRAINTS'])

    # Generic constraints trader pyo.Variables
    m.S_GC_TRADER_VARS = pyo.Set(initialize=data['S_GC_TRADER_VARS'])

    # Generic constraint interconnector pyo.Variables
    m.S_GC_INTERCONNECTOR_VARS = pyo.Set(initialize=data['S_GC_INTERCONNECTOR_VARS'])

    # Generic constraint region pyo.Variables
    m.S_GC_REGION_VARS = pyo.Set(initialize=data['S_GC_REGION_VARS'])

    # Price / quantity band index
    m.S_BANDS = pyo.RangeSet(1, 10, 1)

    # Market Network Service Providers (interconnectors that bid into the market)
    m.S_MNSPS = pyo.Set(initialize=data['S_MNSPS'])

    # MNSP offer types
    m.S_MNSP_OFFERS = pyo.Set(initialize=data['S_MNSP_OFFERS'])

    # All interconnectors (interconnector_id)
    m.S_INTERCONNECTORS = pyo.Set(initialize=data['S_INTERCONNECTORS'])

    # Interconnector loss model breakpoints
    m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS = pyo.Set(initialize=data['S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS'])

    # Interconnector loss model intervals
    m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS = pyo.Set(initialize=data['S_INTERCONNECTOR_LOSS_MODEL_INTERVALS'])

    return m


def define_parameters(m, data):
    """Define model parameters"""

    # Intervention status
    m.P_INTERVENTION_STATUS = pyo.Param(initialize=data['P_INTERVENTION_STATUS'])

    # Case ID
    m.P_CASE_ID = pyo.Param(initialize=data['P_CASE_ID'])

    # Price bands for traders (generators / loads)
    m.P_TRADER_PRICE_BAND = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS, initialize=data['P_TRADER_PRICE_BAND'])

    # Quantity bands for traders (generators / loads)
    m.P_TRADER_QUANTITY_BAND = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS, initialize=data['P_TRADER_QUANTITY_BAND'])

    # Max available output for given trader
    m.P_TRADER_MAX_AVAILABLE = pyo.Param(m.S_TRADER_OFFERS, initialize=data['P_TRADER_MAX_AVAILABLE'])

    # Initial MW output for generators / loads
    m.P_TRADER_INITIAL_MW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_INITIAL_MW'])
    m.P_TRADER_WHAT_IF_INITIAL_MW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_WHAT_IF_INITIAL_MW'])

    # UIGF for semi-dispatchable plant
    m.P_TRADER_UIGF = pyo.Param(m.S_TRADERS_SEMI_DISPATCH, initialize=data['P_TRADER_UIGF'])

    # Trader HMW and LMW
    m.P_TRADER_HMW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_HMW'])
    m.P_TRADER_LMW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_LMW'])

    # Trader AGC status
    m.P_TRADER_AGC_STATUS = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_AGC_STATUS'])

    # Trader semi-dispatch status
    m.P_TRADER_SEMI_DISPATCH_STATUS = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_SEMI_DISPATCH_STATUS'])

    # Trader region
    m.P_TRADER_REGION = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_REGION'])

    # Trader ramp up and down rates
    m.P_TRADER_PERIOD_RAMP_UP_RATE = pyo.Param(m.S_TRADER_ENERGY_OFFERS,
                                               initialize=data['P_TRADER_PERIOD_RAMP_UP_RATE'])
    m.P_TRADER_PERIOD_RAMP_DOWN_RATE = pyo.Param(m.S_TRADER_ENERGY_OFFERS,
                                                 initialize=data['P_TRADER_PERIOD_RAMP_DOWN_RATE'])

    # Trader FCAS enablement min
    m.P_TRADER_FCAS_ENABLEMENT_MIN = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                               initialize={k: v['EnablementMin'] for k, v in
                                                           data['preprocessed']['FCAS_TRAPEZIUM'].items()})

    # Trader FCAS low breakpoint
    m.P_TRADER_FCAS_LOW_BREAKPOINT = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                               initialize={k: v['LowBreakpoint'] for k, v in
                                                           data['preprocessed']['FCAS_TRAPEZIUM'].items()})

    # Trader FCAS high breakpoint
    m.P_TRADER_FCAS_HIGH_BREAKPOINT = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                                initialize={k: v['HighBreakpoint'] for k, v in
                                                            data['preprocessed']['FCAS_TRAPEZIUM'].items()})

    # Trader FCAS enablement max
    m.P_TRADER_FCAS_ENABLEMENT_MAX = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                               initialize={k: v['EnablementMax'] for k, v in
                                                           data['preprocessed']['FCAS_TRAPEZIUM'].items()})

    # Trader FCAS max available
    m.P_TRADER_FCAS_MAX_AVAILABLE = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                              initialize={k: v['MaxAvail'] for k, v in
                                                          data['preprocessed']['FCAS_TRAPEZIUM'].items()})

    # Trader FCAS availability
    m.P_TRADER_FCAS_AVAILABILITY_STATUS = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                                    initialize=data['preprocessed']['FCAS_AVAILABILITY_STATUS'])

    # Trader type
    m.P_TRADER_TYPE = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_TYPE'])

    # Trader fast start parameters
    m.P_TRADER_MIN_LOADING_MW = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_MIN_LOADING_MW'])
    m.P_TRADER_CURRENT_MODE = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_CURRENT_MODE'])
    m.P_TRADER_CURRENT_MODE_TIME = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_CURRENT_MODE_TIME'])
    m.P_TRADER_T1 = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_T1'])
    m.P_TRADER_T2 = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_T2'])
    m.P_TRADER_T3 = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_T3'])
    m.P_TRADER_T4 = pyo.Param(m.S_TRADER_FAST_START, initialize=data['P_TRADER_T4'])

    # Trader SCADA ramp up and down rates
    m.P_TRADER_SCADA_RAMP_UP_RATE = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_SCADA_RAMP_UP_RATE'])
    m.P_TRADER_SCADA_RAMP_DOWN_RATE = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_SCADA_RAMP_DOWN_RATE'])

    # Interconnector initial MW
    m.P_INTERCONNECTOR_INITIAL_MW = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_INITIAL_MW'])

    # Interconnector 'to' and 'from' regions
    m.P_INTERCONNECTOR_TO_REGION = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_TO_REGION'])
    m.P_INTERCONNECTOR_FROM_REGION = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_FROM_REGION'])

    # Interconnector lower and upper limits - NOTE: these are absolute values (lower limit is positive)
    m.P_INTERCONNECTOR_LOWER_LIMIT = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_LOWER_LIMIT'])
    m.P_INTERCONNECTOR_UPPER_LIMIT = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_UPPER_LIMIT'])

    # Interconnector MNSP status
    m.P_INTERCONNECTOR_MNSP_STATUS = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_MNSP_STATUS'])

    # Interconnector loss share
    m.P_INTERCONNECTOR_LOSS_SHARE = pyo.Param(m.S_INTERCONNECTORS, initialize=data['P_INTERCONNECTOR_LOSS_SHARE'])

    # Interconnector initial loss estimate
    m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE = pyo.Param(m.S_INTERCONNECTORS,
                                                         initialize=data['P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE'])

    # Interconnector loss model segment limit
    m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X = pyo.Param(
        m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, initialize=data['P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X'])

    # Interconnector loss model segment factor
    m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y = pyo.Param(
        m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, initialize=data['P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y'])

    # Price bands for MNSPs
    m.P_MNSP_PRICE_BAND = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, initialize=data['P_MNSP_PRICE_BAND'])

    # Quantity bands for MNSPs
    m.P_MNSP_QUANTITY_BAND = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, initialize=data['P_MNSP_QUANTITY_BAND'])

    # Max available output for given MNSP
    m.P_MNSP_MAX_AVAILABLE = pyo.Param(m.S_MNSP_OFFERS, initialize=data['P_MNSP_MAX_AVAILABLE'])

    # MNSP ramp rates (in offers)
    m.P_MNSP_RAMP_UP_RATE = pyo.Param(m.S_MNSP_OFFERS, initialize=data['P_MNSP_RAMP_UP_RATE'])
    m.P_MNSP_RAMP_DOWN_RATE = pyo.Param(m.S_MNSP_OFFERS, initialize=data['P_MNSP_RAMP_DOWN_RATE'])

    # MNSP 'to' and 'from' region loss factor
    m.P_MNSP_TO_REGION_LF_EXPORT = pyo.Param(m.S_MNSPS, initialize=data['P_MNSP_TO_REGION_LF_EXPORT'])
    m.P_MNSP_TO_REGION_LF_IMPORT = pyo.Param(m.S_MNSPS, initialize=data['P_MNSP_TO_REGION_LF_IMPORT'])
    m.P_MNSP_FROM_REGION_LF_EXPORT = pyo.Param(m.S_MNSPS, initialize=data['P_MNSP_FROM_REGION_LF_EXPORT'])
    m.P_MNSP_FROM_REGION_LF_IMPORT = pyo.Param(m.S_MNSPS, initialize=data['P_MNSP_FROM_REGION_LF_IMPORT'])

    # MNSP loss indicator
    m.P_MNSP_REGION_LOSS_INDICATOR = pyo.Param(m.S_MNSPS, m.S_REGIONS, initialize=data['P_MNSP_REGION_LOSS_INDICATOR'])

    # Initial region demand
    m.P_REGION_INITIAL_DEMAND = pyo.Param(m.S_REGIONS, initialize=data['P_REGION_INITIAL_DEMAND'])

    # Region aggregate dispatch error (ADE)
    m.P_REGION_ADE = pyo.Param(m.S_REGIONS, initialize=data['P_REGION_ADE'])

    # Region demand forecast increment (DF)
    m.P_REGION_DF = pyo.Param(m.S_REGIONS, initialize=data['P_REGION_DF'])

    # Generic constraint RHS
    m.P_GC_RHS = pyo.Param(m.S_GENERIC_CONSTRAINTS, initialize=data['P_GC_RHS'])

    # Generic constraint type
    m.P_GC_TYPE = pyo.Param(m.S_GENERIC_CONSTRAINTS, initialize=data['P_GC_TYPE'])

    # Generic constraint violation factors
    m.P_CVF_GC = pyo.Param(m.S_GENERIC_CONSTRAINTS, initialize=data['P_CVF_GC'])

    # Value of lost load TODO: check if necessary - not used
    m.P_CVF_VOLL = pyo.Param(initialize=data['P_CVF_VOLL'])

    # Energy deficit price
    m.P_CVF_ENERGY_DEFICIT_PRICE = pyo.Param(initialize=data['P_CVF_ENERGY_DEFICIT_PRICE'])

    # Energy surplus price
    m.P_CVF_ENERGY_SURPLUS_PRICE = pyo.Param(initialize=data['P_CVF_ENERGY_SURPLUS_PRICE'])

    # UIGF surplus price
    m.P_CVF_UIGF_SURPLUS_PRICE = pyo.Param(initialize=data['P_CVF_UIGF_SURPLUS_PRICE'])

    # Ramp-rate constraint violation factor
    m.P_CVF_RAMP_RATE_PRICE = pyo.Param(initialize=data['P_CVF_RAMP_RATE_PRICE'])

    # Capacity price (assume for constraint ensuring max available capacity not exceeded)
    m.P_CVF_CAPACITY_PRICE = pyo.Param(initialize=data['P_CVF_CAPACITY_PRICE'])

    # Offer price (assume for constraint ensuring band offer amounts are not exceeded)
    m.P_CVF_OFFER_PRICE = pyo.Param(initialize=data['P_CVF_OFFER_PRICE'])

    # MNSP offer price (assumed for constraint ensuring MNSP band offers are not exceeded)
    m.P_CVF_MNSP_OFFER_PRICE = pyo.Param(initialize=data['P_CVF_MNSP_OFFER_PRICE'])

    # MNSP ramp rate price (not sure what this applies to - unclear what MNSP ramp rates are)
    m.P_CVF_MNSP_RAMP_RATE_PRICE = pyo.Param(initialize=data['P_CVF_MNSP_RAMP_RATE_PRICE'])

    # MNSP capacity price (assume for constraint ensuring max available capacity not exceeded)
    m.P_CVF_MNSP_CAPACITY_PRICE = pyo.Param(initialize=data['P_CVF_MNSP_CAPACITY_PRICE'])

    # MNSP loss price TODO: check - not used
    m.P_CVF_MNSP_LOSS_PRICE = pyo.Param(initialize=data['P_MNSP_LOSS_PRICE'])

    # Ancillary services profile price (assume for constraint ensure FCAS trapezium not violated) TODO: check - not used
    m.P_CVF_AS_PROFILE_PRICE = pyo.Param(initialize=data['P_CVF_AS_PROFILE_PRICE'])

    # Ancillary services max available price (assume for constraint ensure max available amount not exceeded)
    m.P_CVF_AS_MAX_AVAIL_PRICE = pyo.Param(initialize=data['P_CVF_AS_MAX_AVAIL_PRICE'])

    # Ancillary services enablement min price (assume for constraint ensure FCAS > enablement min if active)
    # TODO: check - not used
    m.P_CVF_AS_ENABLEMENT_MIN_PRICE = pyo.Param(initialize=data['P_CVF_AS_ENABLEMENT_MIN_PRICE'])

    # Ancillary services enablement max price (assume for constraint ensure FCAS < enablement max if active)
    # TODO: check - not used
    m.P_CVF_AS_ENABLEMENT_MAX_PRICE = pyo.Param(initialize=data['P_CVF_AS_ENABLEMENT_MAX_PRICE'])

    # Interconnector power flow violation price
    m.P_CVF_INTERCONNECTOR_PRICE = pyo.Param(initialize=data['P_CVF_INTERCONNECTOR_PRICE'])

    # Trader fast start inflexibility constraint violation price
    m.P_CVF_FAST_START_PRICE = pyo.Param(initialize=data['P_CVF_FAST_START_PRICE'])

    # Generic constraint price TODO: check - not used
    m.P_CVF_GENERIC_CONSTRAINT_PRICE = pyo.Param(initialize=data['P_CVF_GENERIC_CONSTRAINT_PRICE'])

    # Satisfactory network constraint price TODO: check - not used
    m.P_CVF_SATISFACTORY_NETWORK_PRICE = pyo.Param(initialize=data['P_CVF_SATISFACTORY_NETWORK_PRICE'])

    # Tie-break price TODO: check - not used
    m.P_TIE_BREAK_PRICE = pyo.Param(initialize=data['P_TIE_BREAK_PRICE'])

    return m


def define_variables(m):
    """Define model pyo.Variables"""

    # Offers for each quantity band
    m.V_TRADER_OFFER = pyo.Var(m.S_TRADER_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)
    m.V_MNSP_OFFER = pyo.Var(m.S_MNSP_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)

    # Total MW offer for each offer type
    m.V_TRADER_TOTAL_OFFER = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_MNSP_TOTAL_OFFER = pyo.Var(m.S_MNSP_OFFERS, within=pyo.NonNegativeReals)

    # Generic constraint pyo.Variables
    m.V_GC_TRADER = pyo.Var(m.S_GC_TRADER_VARS)
    m.V_GC_INTERCONNECTOR = pyo.Var(m.S_GC_INTERCONNECTOR_VARS)
    m.V_GC_REGION = pyo.Var(m.S_GC_REGION_VARS)

    # MNSP loss model variables
    m.V_MNSP_TO_CP_FLOW = pyo.Var(m.S_MNSPS)
    m.V_MNSP_TO_REGION_EXPORT = pyo.Var(m.S_MNSPS)
    m.V_MNSP_TO_REGION_IMPORT = pyo.Var(m.S_MNSPS)
    m.V_MNSP_FROM_CP_FLOW = pyo.Var(m.S_MNSPS)
    m.V_MNSP_FROM_REGION_EXPORT = pyo.Var(m.S_MNSPS)
    m.V_MNSP_FROM_REGION_IMPORT = pyo.Var(m.S_MNSPS)
    m.V_MNSP_FLOW_DIRECTION = pyo.Var(m.S_MNSPS, within=pyo.Binary)

    m.V_MNSP_TO_REGION_LOSS = pyo.Var(m.S_MNSPS)
    m.V_MNSP_FROM_REGION_LOSS = pyo.Var(m.S_MNSPS)

    # Generic constraint violation pyo.Variables
    m.V_CV = pyo.Var(m.S_GENERIC_CONSTRAINTS, within=pyo.NonNegativeReals)
    m.V_CV_LHS = pyo.Var(m.S_GENERIC_CONSTRAINTS, within=pyo.NonNegativeReals)
    m.V_CV_RHS = pyo.Var(m.S_GENERIC_CONSTRAINTS, within=pyo.NonNegativeReals)

    # Trader band offer < bid violation
    m.V_CV_TRADER_OFFER = pyo.Var(m.S_TRADER_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)

    # Trader total capacity < max available violation
    m.V_CV_TRADER_CAPACITY = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_UIGF_SURPLUS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

    # MNSP band offer < bid violation
    m.V_CV_MNSP_OFFER = pyo.Var(m.S_MNSP_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)

    # MNSP total capacity < max available violation
    m.V_CV_MNSP_CAPACITY = pyo.Var(m.S_MNSP_OFFERS, within=pyo.NonNegativeReals)

    # MNSP ramp rate constraint violation
    m.V_CV_MNSP_RAMP_UP = pyo.Var(m.S_MNSP_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_MNSP_RAMP_DOWN = pyo.Var(m.S_MNSP_OFFERS, within=pyo.NonNegativeReals)

    # Ramp rate constraint violation pyo.Variables
    m.V_CV_TRADER_RAMP_UP = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_RAMP_DOWN = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)

    # FCAS trapezium violation pyo.Variables
    m.V_CV_TRADER_FCAS_TRAPEZIUM = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_AS_PROFILE_1 = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_AS_PROFILE_2 = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_AS_PROFILE_3 = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

    # FCAS constraint violation
    m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_MAX_AVAILABLE = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENABLEMENT_MIN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENABLEMENT_MAX = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

    # Inflexibility profile violation
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE = pyo.Var(m.S_TRADER_FAST_START, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS = pyo.Var(m.S_TRADER_FAST_START, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS = pyo.Var(m.S_TRADER_FAST_START, within=pyo.NonNegativeReals)

    # Interconnector forward and reverse flow constraint violation
    m.V_CV_INTERCONNECTOR_FORWARD = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)
    m.V_CV_INTERCONNECTOR_REVERSE = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)

    # Region surplus / deficit power
    m.V_CV_REGION_GENERATION_SURPLUS = pyo.Var(m.S_REGIONS, within=pyo.NonNegativeReals)
    m.V_CV_REGION_GENERATION_DEFICIT = pyo.Var(m.S_REGIONS, within=pyo.NonNegativeReals)

    # Loss model breakpoints and intervals
    m.V_LOSS = pyo.Var(m.S_INTERCONNECTORS)
    m.V_LOSS_LAMBDA = pyo.Var(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, within=pyo.NonNegativeReals)
    m.V_LOSS_Y = pyo.Var(m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS, within=pyo.Binary)

    # Trader tie-break slack variables
    m.V_TRADER_SLACK_1 = pyo.Var(m.S_TRADER_PRICE_TIED, within=pyo.NonNegativeReals)
    m.V_TRADER_SLACK_2 = pyo.Var(m.S_TRADER_PRICE_TIED, within=pyo.NonNegativeReals)

    return m


def define_cost_function_expressions(m):
    """Define expressions relating to trader and MNSP cost functions"""

    def trader_cost_function_rule(m, i, j):
        """Total cost associated with each offer"""

        # Scaling factor depending on participant type. Generator (+1), load (-1)
        if j == 'LDOF':
            factor = -1
        else:
            factor = 1

        return factor * sum(m.P_TRADER_PRICE_BAND[i, j, b] * m.V_TRADER_OFFER[i, j, b] for b in m.S_BANDS)

    # Trader cost functions
    m.E_TRADER_COST_FUNCTION = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_cost_function_rule)

    def mnsp_cost_function_rule(m, i, j):
        """MNSP cost function"""

        return sum(m.P_MNSP_PRICE_BAND[i, j, b] * m.V_MNSP_OFFER[i, j, b] for b in m.S_BANDS)

    # MNSP cost functions
    m.E_MNSP_COST_FUNCTION = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_cost_function_rule)

    return m


def define_generic_constraint_expressions(m, data):
    """Define generic constraint expressions"""

    # LHS terms in generic constraints
    terms = data['preprocessed']['GC_LHS_TERMS']

    def generic_constraint_lhs_terms_rule(m, i):
        """Get LHS expression for a given Generic Constraint"""

        # Trader terms
        t_terms = sum(m.V_GC_TRADER[index] * factor for index, factor in terms[i]['traders'].items())

        # Interconnector terms
        i_terms = sum(m.V_GC_INTERCONNECTOR[index] * factor for index, factor in terms[i]['interconnectors'].items())

        # Region terms
        r_terms = sum(m.V_GC_REGION[index] * factor for index, factor in terms[i]['regions'].items())

        return t_terms + i_terms + r_terms

    # Generic constraint LHS terms
    m.E_GC_LHS_TERMS = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_terms_rule)

    return m


def define_constraint_violation_penalty_expressions(m):
    """Define expressions relating constraint violation penalties"""

    def generic_constraint_violation_rule(m, i):
        """Constraint violation penalty for generic constraint which is an inequality"""

        return m.P_CVF_GC[i] * m.V_CV[i]

    # Constraint violation penalty for inequality constraints
    m.E_CV_GC_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_rule)

    def generic_constraint_lhs_violation_rule(m, i):
        """Constraint violation penalty for equality constraint"""

        return m.P_CVF_GC[i] * m.V_CV_LHS[i]

    # Constraint violation penalty for equality constraints
    m.E_CV_GC_LHS_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_violation_rule)

    def generic_constraint_rhs_violation_rule(m, i):
        """Constraint violation penalty for equality constraint"""

        return m.P_CVF_GC[i] * m.V_CV_RHS[i]

    # Constraint violation penalty for equality constraints
    m.E_CV_GC_RHS_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_violation_rule)

    def trader_offer_penalty_rule(m, i, j, k):
        """Penalty for band amount exceeding band bid amount"""

        return m.P_CVF_OFFER_PRICE * m.V_CV_TRADER_OFFER[i, j, k]

    # Constraint violation penalty for trader dispatched band amount exceeding bid amount
    m.E_CV_TRADER_OFFER_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_penalty_rule)

    def trader_capacity_penalty_rule(m, i, j):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_CAPACITY_PRICE * m.V_CV_TRADER_CAPACITY[i, j]

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_TRADER_CAPACITY_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_capacity_penalty_rule)

    def trader_uigf_surplus_penalty_rule(m, i, j):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_UIGF_SURPLUS_PRICE * m.V_CV_TRADER_UIGF_SURPLUS[i, j]

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_TRADER_UIGF_SURPLUS_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_uigf_surplus_penalty_rule)

    def trader_ramp_up_penalty_rule(m, i):
        """Penalty for violating ramp down constraint"""

        return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_UP[i]

    # Penalty factor for ramp up rate violation
    m.E_CV_TRADER_RAMP_UP_PENALTY = pyo.Expression(m.S_TRADERS, rule=trader_ramp_up_penalty_rule)

    def trader_ramp_down_penalty_rule(m, i):
        """Penalty for violating ramp down constraint"""

        return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_DOWN[i]

    # Penalty factor for ramp down rate violation
    m.E_CV_TRADER_RAMP_DOWN_PENALTY = pyo.Expression(m.S_TRADERS, rule=trader_ramp_down_penalty_rule)

    def trader_fcas_joint_ramping_up_rule(m, i, j):
        """Penalty for violating FCAS constraint - generator joint ramping up"""

        # return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j]
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j]

    # Penalty factor for generator FCAS joint ramping up constraint
    m.E_CV_TRADER_FCAS_JOINT_RAMPING_UP = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_ramping_up_rule)

    def trader_fcas_joint_ramping_down_rule(m, i, j):
        """Penalty for violating FCAS constraint - generator joint ramping down"""

        # return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j]
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j]

    # Penalty factor for generator FCAS joint ramping up constraint
    m.E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_ramping_down_rule)

    def trader_fcas_joint_capacity_rhs_rule(m, i, j):
        """Joint capacity constraint RHS of trapezium"""

        # return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j]
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j]
        # return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j]

    # Constraint violation for joint capacity constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_capacity_rhs_rule)

    def trader_fcas_joint_capacity_lhs_rule(m, i, j):
        """Joint capacity constraint LHS of trapezium"""

        # return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]
        # return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]

    # Constraint violation for joint capacity constraint - LHS of trapezium
    m.E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_capacity_lhs_rule)

    def trader_fcas_energy_regulating_rhs_rule(m, i, j):
        """Energy regulating FCAS constraint RHS of trapezium"""

        # return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j]
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j]
        # return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j]

    # Constraint violation for joint energy regulating FCAS constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS = pyo.Expression(m.S_TRADER_OFFERS,
                                                              rule=trader_fcas_energy_regulating_rhs_rule)

    def trader_fcas_energy_regulating_lhs_rule(m, i, j):
        """Energy regulating FCAS constraint LHS of trapezium"""

        # return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j]
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j]
        # return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j]

    # Constraint violation for joint energy regulating FCAS constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS = pyo.Expression(m.S_TRADER_OFFERS,
                                                              rule=trader_fcas_energy_regulating_lhs_rule)

    def trader_inflexibility_profile_rule(m, i):
        """Inflexibility profile penalty"""

        return m.P_CVF_FAST_START_PRICE * m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i]

    # Trader inflexibility price
    m.E_CV_TRADER_INFLEXIBILITY_PROFILE = pyo.Expression(m.S_TRADER_FAST_START, rule=trader_inflexibility_profile_rule)

    def trader_inflexibility_profile_lhs_rule(m, i):
        """Inflexibility profile penalty - LHS"""

        return m.P_CVF_FAST_START_PRICE * m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i]

    # Trader inflexibility price
    m.E_CV_TRADER_INFLEXIBILITY_PROFILE_LHS = pyo.Expression(m.S_TRADER_FAST_START,
                                                             rule=trader_inflexibility_profile_lhs_rule)

    def trader_inflexibility_profile_rhs_rule(m, i):
        """Inflexibility profile penalty - RHS"""

        return m.P_CVF_FAST_START_PRICE * m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i]

    # Trader inflexibility price
    m.E_CV_TRADER_INFLEXIBILITY_PROFILE_RHS = pyo.Expression(m.S_TRADER_FAST_START,
                                                             rule=trader_inflexibility_profile_rhs_rule)

    def trader_fcas_max_available_rule(m, i, j):
        """Max available violation for FCAS offer"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

    # Constraint violation for max available
    m.E_CV_TRADER_FCAS_MAX_AVAILABLE = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_max_available_rule)

    def trader_fcas_enablement_min_rule(m, i, j):
        """Enablement min violation for FCAS offer"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j]

    # Constraint violation for max available
    m.E_CV_TRADER_FCAS_ENABLEMENT_MIN = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_enablement_min_rule)

    def trader_fcas_enablement_max_rule(m, i, j):
        """Enablement max violation for FCAS offer"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j]

    # Constraint violation for max available
    m.E_CV_TRADER_FCAS_ENABLEMENT_MAX = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_enablement_max_rule)

    def mnsp_offer_penalty_rule(m, i, j, k):
        """Penalty for band amount exceeding band bid amount"""

        return m.P_CVF_MNSP_OFFER_PRICE * m.V_CV_MNSP_OFFER[i, j, k]

    # Constraint violation penalty for MNSP dispatched band amount exceeding bid amount
    m.E_CV_MNSP_OFFER_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_penalty_rule)

    def mnsp_capacity_penalty_rule(m, i, j):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_MNSP_CAPACITY_PRICE * m.V_CV_MNSP_CAPACITY[i, j]

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_MNSP_CAPACITY_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_capacity_penalty_rule)

    def mnsp_ramp_up_penalty_rule(m, i, j):
        """Penalty applied to MNSP ramp-up rate violation"""

        return m.P_CVF_MNSP_RAMP_RATE_PRICE * m.V_CV_MNSP_RAMP_UP[i, j]

    # Constraint violation penalty for ramp-up rate constraint violation
    m.E_CV_MNSP_RAMP_UP_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_ramp_up_penalty_rule)

    def mnsp_ramp_down_penalty_rule(m, i, j):
        """Penalty applied to MNSP ramp-down rate violation"""

        return m.P_CVF_MNSP_RAMP_RATE_PRICE * m.V_CV_MNSP_RAMP_DOWN[i, j]

    # Constraint violation penalty for ramp-down rate constraint violation
    m.E_CV_MNSP_RAMP_DOWN_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_ramp_down_penalty_rule)

    def interconnector_forward_penalty_rule(m, i):
        """Penalty for forward power flow exceeding max allowable flow"""

        return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_FORWARD[i]

    # Constraint violation penalty for forward interconnector limit being violated
    m.E_CV_INTERCONNECTOR_FORWARD_PENALTY = pyo.Expression(m.S_INTERCONNECTORS,
                                                           rule=interconnector_forward_penalty_rule)

    def interconnector_reverse_penalty_rule(m, i):
        """Penalty for reverse power flow exceeding max allowable flow"""

        return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_REVERSE[i]

    # Constraint violation penalty for forward interconnector limit being violated
    m.E_CV_INTERCONNECTOR_REVERSE_PENALTY = pyo.Expression(m.S_INTERCONNECTORS,
                                                           rule=interconnector_reverse_penalty_rule)

    def region_power_surplus_penalty_rule(m, i):
        """Surplus power in region"""

        return m.P_CVF_ENERGY_SURPLUS_PRICE * m.V_CV_REGION_GENERATION_SURPLUS[i]

    # Constraint violation penalty for region energy surplus
    m.E_CV_REGION_SURPLUS_POWER = pyo.Expression(m.S_REGIONS, rule=region_power_surplus_penalty_rule)

    def region_power_deficit_penalty_rule(m, i):
        """Deficit power in region"""

        return m.P_CVF_ENERGY_DEFICIT_PRICE * m.V_CV_REGION_GENERATION_DEFICIT[i]

    # Constraint violation penalty for region energy surplus
    m.E_CV_REGION_DEFICIT_POWER = pyo.Expression(m.S_REGIONS, rule=region_power_deficit_penalty_rule)

    # Sum of all constraint violation penalties
    m.E_CV_TOTAL_PENALTY = pyo.Expression(
        expr=sum(m.E_CV_GC_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
             + sum(m.E_CV_GC_LHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
             + sum(m.E_CV_GC_RHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
             + sum(m.E_CV_TRADER_OFFER_PENALTY[i, j, k] for i, j in m.S_TRADER_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_TRADER_CAPACITY_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_UIGF_SURPLUS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_RAMP_UP_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_RAMP_DOWN_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_MAX_AVAILABLE[i, j] for i, j in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_INFLEXIBILITY_PROFILE[i] for i in m.S_TRADER_FAST_START)
             + sum(m.E_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i] for i in m.S_TRADER_FAST_START)
             + sum(m.E_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i] for i in m.S_TRADER_FAST_START)
             + sum(m.E_CV_TRADER_FCAS_ENABLEMENT_MIN[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENABLEMENT_MAX[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_MNSP_RAMP_UP_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_MNSP_RAMP_DOWN_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i] for i in m.S_INTERCONNECTORS)
             + sum(m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i] for i in m.S_INTERCONNECTORS)
             + sum(m.E_CV_REGION_SURPLUS_POWER[i] for i in m.S_REGIONS)
             + sum(m.E_CV_REGION_DEFICIT_POWER[i] for i in m.S_REGIONS)
    )

    return m


def define_mnsp_expressions(m):
    """Expressions for MNSP loss model"""

    def mnsp_from_cp_flow_rule(m, i):
        """Net flow at FromRegion connection point for MNSP loss model"""

        from_region = m.P_INTERCONNECTOR_FROM_REGION[i]

        return m.V_GC_INTERCONNECTOR[i] + (m.V_LOSS[i] * m.P_MNSP_REGION_LOSS_INDICATOR[i, from_region])

    # MNSP FromRegion connection point flow
    m.E_MNSP_FROM_CP_FLOW = pyo.Expression(m.S_MNSPS, rule=mnsp_from_cp_flow_rule)

    def mnsp_to_cp_flow_rule(m, i):
        """Net flow at ToRegion connection point for MNSP loss model"""

        to_region = m.P_INTERCONNECTOR_TO_REGION[i]

        return m.V_GC_INTERCONNECTOR[i] - (m.V_LOSS[i] * m.P_MNSP_REGION_LOSS_INDICATOR[i, to_region])

    # MNSP ToRegion connection point flow
    m.E_MNSP_TO_CP_FLOW = pyo.Expression(m.S_MNSPS, rule=mnsp_to_cp_flow_rule)

    def mnsp_from_region_loss_rule(m, i):
        """MNSP loss allocated to given region"""

        return (((m.P_MNSP_FROM_REGION_LF_EXPORT[i] - 1) * m.V_MNSP_FROM_REGION_EXPORT[i])
                + (m.P_MNSP_FROM_REGION_LF_IMPORT[i] - 1) * m.V_MNSP_FROM_REGION_IMPORT[i])

    # MNSP from region loss
    m.E_MNSP_FROM_REGION_LOSS = pyo.Expression(m.S_MNSPS, rule=mnsp_from_region_loss_rule)

    def mnsp_to_region_loss_rule(m, i):
        """MNSP loss allocated to given region"""

        return (((m.P_MNSP_TO_REGION_LF_EXPORT[i] - 1) * m.V_MNSP_TO_REGION_EXPORT[i] * -1)
                + (m.P_MNSP_TO_REGION_LF_IMPORT[i] - 1) * m.V_MNSP_TO_REGION_IMPORT[i] * -1)

    # MNSP from region loss
    m.E_MNSP_TO_REGION_LOSS = pyo.Expression(m.S_MNSPS, rule=mnsp_to_region_loss_rule)

    return m


def define_aggregate_power_expressions(m):
    """Compute aggregate demand and generation in each NEM region"""

    def region_dispatched_generation_rule(m, r):
        """Available energy offers in given region"""

        return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
                   if (j == 'ENOF') and (m.P_TRADER_REGION[i] == r))

    # Total generation dispatched in a given region
    m.E_REGION_DISPATCHED_GENERATION = pyo.Expression(m.S_REGIONS, rule=region_dispatched_generation_rule)

    def region_dispatched_load_rule(m, r):
        """Available load offers in given region"""

        return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
                   if (j == 'LDOF') and (m.P_TRADER_REGION[i] == r))

    # Total dispatched load in a given region
    m.E_REGION_DISPATCHED_LOAD = pyo.Expression(m.S_REGIONS, rule=region_dispatched_load_rule)

    def region_initial_scheduled_load(m, r):
        """Total initial scheduled load in a given region"""

        total = 0
        for i, j in m.S_TRADER_OFFERS:
            if j == 'LDOF':
                if (r == m.P_TRADER_REGION[i]) and (m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '0'):
                    total += m.P_TRADER_INITIAL_MW[i]

        return total

    # Region initial scheduled load
    m.E_REGION_INITIAL_SCHEDULED_LOAD = pyo.Expression(m.S_REGIONS, rule=region_initial_scheduled_load)

    def region_initial_allocated_loss(m, r):
        """Losses allocated to region due to interconnector flow"""

        # Allocated interconnector losses
        region_interconnector_loss = 0

        for i in m.S_INTERCONNECTORS:

            if r not in [m.P_INTERCONNECTOR_FROM_REGION[i], m.P_INTERCONNECTOR_TO_REGION[i]]:
                continue

            # Initial loss estimate over interconnector
            loss = m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i]

            # MNSP losses applied to sending end - based on InitialMW
            if m.P_INTERCONNECTOR_MNSP_STATUS[i] == '1':
                if m.P_INTERCONNECTOR_INITIAL_MW[i] >= 0:
                    mnsp_loss_share = 1
                else:
                    mnsp_loss_share = 0

            # Positive flow indicates export from FromRegion
            if r == m.P_INTERCONNECTOR_FROM_REGION[i]:
                # Loss applied to sending end if MNSP
                if m.P_INTERCONNECTOR_MNSP_STATUS[i] == '1':
                    region_interconnector_loss += loss * mnsp_loss_share
                else:
                    region_interconnector_loss += loss * m.P_INTERCONNECTOR_LOSS_SHARE[i]

            # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
            elif r == m.P_INTERCONNECTOR_TO_REGION[i]:
                # Loss applied to sending end if MNSP
                if m.P_INTERCONNECTOR_MNSP_STATUS[i] == '1':
                    region_interconnector_loss += loss * (1 - mnsp_loss_share)
                else:
                    region_interconnector_loss += loss * (1 - m.P_INTERCONNECTOR_LOSS_SHARE[i])

            else:
                pass

        return region_interconnector_loss

    def region_initial_allocated_loss2(m, r):
        """Losses allocated to region due to interconnector flow"""

        # Allocated interconnector losses
        region_interconnector_loss = 0

        for i in m.S_INTERCONNECTORS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]
            mnsp_status = m.P_INTERCONNECTOR_MNSP_STATUS[i]

            if r not in [from_region, to_region]:
                continue

            # Initial loss estimate over interconnector
            loss = m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i]
            loss_share = m.P_INTERCONNECTOR_LOSS_SHARE[i]
            initial_mw = m.P_INTERCONNECTOR_INITIAL_MW[i]

            # Loss applied to sending end
            if (r == from_region) and (mnsp_status == '1') and (initial_mw >= 0):
                region_interconnector_loss += loss

            # Loss applied to sending end - negative flow means no loss allocated to FromRegion
            elif (r == from_region) and (mnsp_status == '1') and (initial_mw < 0):
                pass

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == from_region) and (mnsp_status == '0'):
                region_interconnector_loss += loss * loss_share

            # Flow is positive so loss applied to FromRegion
            elif (r == to_region) and (mnsp_status == '1') and (initial_mw >= 0):
                pass

            # Flow is negative so loss applied to ToRegion
            elif (r == to_region) and (mnsp_status == '1') and (initial_mw < 0):
                region_interconnector_loss += loss

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == to_region) and (mnsp_status == '0'):
                region_interconnector_loss += loss * (1 - loss_share)

            else:
                raise Exception('Unhandled case:', r, from_region, to_region)

        return region_interconnector_loss

    # Region initial allocated losses
    m.E_REGION_INITIAL_ALLOCATED_LOSS = pyo.Expression(m.S_REGIONS, rule=region_initial_allocated_loss2)

    def region_allocated_loss_rule(m, r):
        """Interconnector loss allocated to given region"""

        # Allocated interconnector losses
        region_interconnector_loss = 0
        for i in m.S_INTERCONNECTORS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]
            mnsp_status = m.P_INTERCONNECTOR_MNSP_STATUS[i]

            if r not in [from_region, to_region]:
                continue

            # Interconnector flow from solution
            loss = m.V_LOSS[i]
            loss_share = m.P_INTERCONNECTOR_LOSS_SHARE[i]
            initial_mw = m.P_INTERCONNECTOR_INITIAL_MW[i]

            # MNSP losses applied to sending end - based on InitialMW
            if mnsp_status == '1':
                if initial_mw >= 0:
                    mnsp_loss_share = 1
                else:
                    mnsp_loss_share = 0

            # Positive flow indicates export from FromRegion
            if r == from_region:
                # Loss applied to sending end if MNSP
                if mnsp_status == '1':
                    region_interconnector_loss += loss * mnsp_loss_share
                else:
                    region_interconnector_loss += loss * loss_share

            # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
            elif r == to_region:
                # Loss applied to sending end if MNSP
                if mnsp_status == '1':
                    region_interconnector_loss += loss * (1 - mnsp_loss_share)
                else:
                    region_interconnector_loss += loss * (1 - loss_share)

            else:
                pass

        return region_interconnector_loss

    def region_allocated_loss_rule2(m, r):
        """Interconnector loss allocated to given region"""

        # Allocated interconnector losses
        region_interconnector_loss = 0
        for i in m.S_INTERCONNECTORS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]
            mnsp_status = m.P_INTERCONNECTOR_MNSP_STATUS[i]

            if r not in [from_region, to_region]:
                continue

            # Interconnector flow from solution
            loss = m.V_LOSS[i]
            loss_share = m.P_INTERCONNECTOR_LOSS_SHARE[i]
            initial_mw = m.P_INTERCONNECTOR_INITIAL_MW[i]

            # Loss applied to sending end
            if (r == from_region) and (mnsp_status == '1') and (initial_mw >= 0):
                region_interconnector_loss += loss

            # Loss applied to sending end - negative flow means no loss allocated to FromRegion
            elif (r == from_region) and (mnsp_status == '1') and (initial_mw < 0):
                pass

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == from_region) and (mnsp_status == '0'):
                region_interconnector_loss += loss * loss_share

            # Flow is positive so loss applied to FromRegion
            elif (r == to_region) and (mnsp_status == '1') and (initial_mw >= 0):
                pass

            # Flow is negative so loss applied to ToRegion
            elif (r == to_region) and (mnsp_status == '1') and (initial_mw < 0):
                region_interconnector_loss += loss

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == to_region) and (mnsp_status == '0'):
                region_interconnector_loss += loss * (1 - loss_share)

            else:
                raise Exception('Unhandled case:', r, from_region, to_region)

        return region_interconnector_loss

    # Region allocated loss at end of dispatch interval
    m.E_REGION_ALLOCATED_LOSS = pyo.Expression(m.S_REGIONS, rule=region_allocated_loss_rule2)

    def region_initial_mnsp_loss(m, r):
        """
        Get estimate of MNSP loss allocated to given region

        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad) where load is varied at the
        connection point. Must compute the load the connection point for the MNSP - this will be positive or negative
        (i.e. generation) depending on the direction of flow over the interconnector.

        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to compute the effective load at the
        connection point in order to compute the loss. Note the loss may be positive or negative depending on the MLF
        and the effective load at the connection point.
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Initial MW and solution flow
            initial_mw = m.P_INTERCONNECTOR_INITIAL_MW[i]

            to_lf_export = m.P_MNSP_TO_REGION_LF_EXPORT[i]
            to_lf_import = m.P_MNSP_TO_REGION_LF_IMPORT[i]

            from_lf_import = m.P_MNSP_FROM_REGION_LF_IMPORT[i]
            from_lf_export = m.P_MNSP_FROM_REGION_LF_EXPORT[i]

            # Initial loss estimate over interconnector
            loss = m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i]

            # MNSP loss share - loss applied to sending end
            if initial_mw >= 0:
                # Total loss allocated to FromRegion
                mnsp_loss_share = 1
            else:
                # Total loss allocated to ToRegion
                mnsp_loss_share = 0

            if initial_mw >= 0:
                if r == from_region:
                    export_flow = initial_mw + (mnsp_loss_share * loss)
                    mnsp_loss = (from_lf_export - 1) * export_flow
                elif r == to_region:
                    import_flow = initial_mw - ((1 - mnsp_loss_share) * loss)

                    # Multiply by -1 because flow from MNSP connection point to ToRegion can be considered a negative
                    # load MLF describes how loss changes with an incremental change to load at the connection point.
                    # So when flow is positive (e.g. flow from TAS to VIC) then must consider a negative load
                    # (i.e. a generator) when computing MNSP losses.
                    mnsp_loss = (to_lf_import - 1) * import_flow * -1

                else:
                    raise Exception('Unexpected region:', r)

            else:
                if r == from_region:
                    # Flow is negative, so add the allocated MNSP loss to get the total import flow
                    import_flow = initial_mw + (mnsp_loss_share * loss)

                    # Import flow is negative. Can be considered as generation at the connection point (negative load).
                    mnsp_loss = (from_lf_import - 1) * import_flow

                elif r == to_region:
                    # Flow is negative, so subtract the allocated MNSP loss to get the total export flow
                    export_flow = initial_mw - ((1 - mnsp_loss_share) * loss)

                    # Export flow is negative. Multiply by -1 so can be considered as load at the connection point.
                    mnsp_loss = (to_lf_export - 1) * export_flow * -1

                else:
                    raise Exception('Unexpected region:', r)

            # Add to total MNSP loss allocated to a given region
            total += mnsp_loss

        return total

    def region_initial_mnsp_loss2(m, r):
        """
        Get estimate of MNSP loss allocated to given region

        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad) where load is varied at the
        connection point. Must compute the load the connection point for the MNSP - this will be positive or negative
        (i.e. generation) depending on the direction of flow over the interconnector.

        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to compute the effective load at the
        connection point in order to compute the loss. Note the loss may be positive or negative depending on the MLF
        and the effective load at the connection point.
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Initial MW and solution flow
            initial_mw = m.P_INTERCONNECTOR_INITIAL_MW[i]

            to_lf_export = m.P_MNSP_TO_REGION_LF_EXPORT[i]
            to_lf_import = m.P_MNSP_TO_REGION_LF_IMPORT[i]

            from_lf_import = m.P_MNSP_FROM_REGION_LF_IMPORT[i]
            from_lf_export = m.P_MNSP_FROM_REGION_LF_EXPORT[i]

            # Initial loss estimate over interconnector
            loss = m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i]

            # if r == from_region:
            #     export_loss = (from_lf_export - 1) * m.V_MNSP_FROM_REGION_EXPORT[i]
            #     import_loss = (from_lf_import - 1) * m.V_MNSP_FROM_REGION_IMPORT[i] * -1
            #     total += export_loss + import_loss
            #
            # elif r == to_region:
            #     export_loss = (to_lf_export - 1) * m.V_MNSP_TO_REGION_EXPORT[i]
            #     import_loss = (to_lf_import - 1) * m.V_MNSP_TO_REGION_IMPORT[i] * -1
            #     total += export_loss + import_loss
            #
            # else:
            #     raise Exception('Unhandled case:', r, to_region, from_region)

            if (r == from_region) and (initial_mw >= 0):
                export_flow = initial_mw + loss
                total += (from_lf_export - 1) * export_flow

            elif (r == from_region) and (initial_mw < 0):
                import_flow = initial_mw
                total += (from_lf_import - 1) * import_flow

            elif (r == to_region) and (initial_mw >= 0):
                import_flow = initial_mw
                total += (to_lf_import - 1) * import_flow * -1

            elif (r == to_region) and (initial_mw < 0):
                export_flow = initial_mw - loss
                total += (to_lf_export - 1) * export_flow * -1

            else:
                raise Exception('Unhandled case:', r, from_region, to_region, initial_mw)

        return total

    # Region initial allocated MNSP losses
    m.E_REGION_INITIAL_MNSP_LOSS = pyo.Expression(m.S_REGIONS, rule=region_initial_mnsp_loss2)

    def region_mnsp_loss_rule(m, r):
        """
        Get estimate of MNSP loss allocated to given region
        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad) where load is varied at the connection
        point. Must compute the load the connection point for the MNSP - this will be positive or negative (i.e. generation)
        depending on the direction of flow over the interconnector.
        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to compute the effective load at the connection
        point in order to compute the loss. Note the loss may be positive or negative depending on the MLF and the effective
        load at the connection point.
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Extract initial and target flow
            initial_flow = m.P_INTERCONNECTOR_INITIAL_MW[i]
            flow = m.V_GC_INTERCONNECTOR[i]

            to_lf_export = m.P_MNSP_TO_REGION_LF_EXPORT[i]
            to_lf_import = m.P_MNSP_TO_REGION_LF_IMPORT[i]

            from_lf_import = m.P_MNSP_FROM_REGION_LF_IMPORT[i]
            from_lf_export = m.P_MNSP_FROM_REGION_LF_EXPORT[i]

            # Loss over interconnector
            loss = m.V_LOSS[i]

            # MNSP loss share - loss applied to sending end
            if initial_flow >= 0:
                # Total loss allocated to FromRegion
                mnsp_loss_share = 1
            else:
                # Total loss allocated to ToRegion
                mnsp_loss_share = 0

            if initial_flow >= 0:
                if r == from_region:
                    export_flow = flow + (mnsp_loss_share * loss)
                    mnsp_loss = (from_lf_export - 1) * export_flow
                elif r == to_region:
                    import_flow = flow - ((1 - mnsp_loss_share) * loss)

                    # Multiply by -1 because flow from MNSP connection point to ToRegion can be considered a negative
                    # load MLF describes how loss changes with an incremental change to load at the connection point. So
                    # when flow is positive (e.g. flow from TAS to VIC) then must consider a negative load
                    # (i.e. a generator) when computing MNSP losses.
                    mnsp_loss = (to_lf_import - 1) * import_flow * -1

                else:
                    raise Exception('Unexpected region:', r)

            else:
                if r == from_region:
                    # Flow is negative, so add the allocated MNSP loss to get the total import flow
                    import_flow = flow + (mnsp_loss_share * loss)

                    # Import flow is negative. Can be considered as generation at the connection point (negative load).
                    mnsp_loss = (from_lf_import - 1) * import_flow

                elif r == to_region:
                    # Flow is negative, so subtract the allocated MNSP loss to get the total export flow
                    export_flow = flow - ((1 - mnsp_loss_share) * loss)

                    # Export flow is negative. Multiply by -1 so can be considered as load at the connection point.
                    mnsp_loss = (to_lf_export - 1) * export_flow * -1

                else:
                    raise Exception('Unexpected region:', r)

            # Add to total MNSP loss allocated to a given region
            total += mnsp_loss

        return total

    def region_mnsp_loss_rule2(m, r):
        """
        Get estimate of MNSP loss allocated to given region

        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad) where load is varied at the connection
        point. Must compute the load the connection point for the MNSP - this will be positive or negative (i.e. generation)
        depending on the direction of flow over the interconnector.

        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to compute the effective load at the connection
        point in order to compute the loss. Note the loss may be positive or negative depending on the MLF and the effective
        load at the connection point.
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Extract initial and target flow
            initial_flow = m.P_INTERCONNECTOR_INITIAL_MW[i]
            flow = m.V_GC_INTERCONNECTOR[i]

            to_lf_export = m.P_MNSP_TO_REGION_LF_EXPORT[i]
            to_lf_import = m.P_MNSP_TO_REGION_LF_IMPORT[i]

            from_lf_import = m.P_MNSP_FROM_REGION_LF_IMPORT[i]
            from_lf_export = m.P_MNSP_FROM_REGION_LF_EXPORT[i]

            # Loss over interconnector
            loss = m.V_LOSS[i]

            if r == from_region:
                total += m.E_MNSP_FROM_REGION_LOSS[i]

            elif r == to_region:
                total += m.E_MNSP_TO_REGION_LOSS[i]

            else:
                raise Exception('Unexpected region:', r)

        return total

    # Region MNSP loss at end of dispatch interval
    m.E_REGION_MNSP_LOSS = pyo.Expression(m.S_REGIONS, rule=region_mnsp_loss_rule2)

    def region_fixed_demand_rule(m, r):
        """Check region fixed demand calculation - demand at start of dispatch interval"""

        demand = (
                m.P_REGION_INITIAL_DEMAND[r]
                + m.P_REGION_ADE[r]
                + m.P_REGION_DF[r]
                - m.E_REGION_INITIAL_SCHEDULED_LOAD[r]
                - m.E_REGION_INITIAL_ALLOCATED_LOSS[r]
                - m.E_REGION_INITIAL_MNSP_LOSS[r]
        )

        return demand

    # Region fixed demand at start of dispatch interval
    m.E_REGION_FIXED_DEMAND = pyo.Expression(m.S_REGIONS, rule=region_fixed_demand_rule)

    def region_cleared_demand_rule(m, r):
        """Region cleared demand rule - generation in region = cleared demand at end of dispatch interval"""

        demand = (
                m.E_REGION_FIXED_DEMAND[r]
                + m.E_REGION_ALLOCATED_LOSS[r]
                + m.E_REGION_DISPATCHED_LOAD[r]
                + m.E_REGION_MNSP_LOSS[r]
        )

        return demand

    # Region cleared demand at end of dispatch interval
    m.E_REGION_CLEARED_DEMAND = pyo.Expression(m.S_REGIONS, rule=region_cleared_demand_rule)

    def region_interconnector_export(m, r):
        """Export from region - excludes MNSP and allocated interconnector losses"""

        # Export out of region
        interconnector_export = 0
        for i in m.S_INTERCONNECTORS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Interconnector flow from solution
            flow = m.V_GC_INTERCONNECTOR[i]

            # Positive flow indicates export from FromRegion
            if r == from_region:
                interconnector_export += flow

            # Positive flow indicates import to ToRegion (take negative to get export from ToRegion)
            elif r == to_region:
                interconnector_export -= flow

            else:
                pass

        return interconnector_export

    # Net export out of region over interconnector - excludes allocated losses
    m.E_REGION_INTERCONNECTOR_EXPORT = pyo.Expression(m.S_REGIONS, rule=region_interconnector_export)

    def region_net_export_rule(m, r):
        """
        Net export out of region including allocated losses

        NetExport = InterconnectorExport + RegionInterconnectorLoss + RegionMNSPLoss
        """

        return m.E_REGION_INTERCONNECTOR_EXPORT[r] + m.E_REGION_ALLOCATED_LOSS[r] + m.E_REGION_MNSP_LOSS[r]

    # Region net export - includes MNSP and allocated interconnector losses
    m.E_REGION_NET_EXPORT = pyo.Expression(m.S_REGIONS, rule=region_net_export_rule)

    return m


def define_fcas_expressions(m):
    """Define FCAS expressions"""

    def fcas_effective_enablement_max(m, i, j):
        """Effective enablement max"""

        if j not in ['L5RE', 'R5RE']:
            return None

        # Offer enablement max
        enablement_max = m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j]

        # Upper AGC limit
        if i in m.P_TRADER_HMW.keys():
            agc_up_limit = m.P_TRADER_HMW[i]
        else:
            agc_up_limit = None

        # UIGF from semi-dispatchable plant
        if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '1':
            uigf = m.P_TRADER_UIGF[i]
        else:
            uigf = None

        # Terms used to determine effective enablement max
        terms = [enablement_max, agc_up_limit, uigf]

        return min([i for i in terms if i is not None])

    # Effective enablement max
    m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX = pyo.Expression(m.S_TRADER_OFFERS, rule=fcas_effective_enablement_max)

    def fcas_effective_enablement_min(m, i, j):
        """Effective enablement min"""

        if j not in ['L5RE', 'R5RE']:
            return None

        # Offer enablement min
        enablement_min = m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j]

        # Upper AGC limit
        if i in m.P_TRADER_LMW.keys():
            agc_down_limit = m.P_TRADER_LMW[i]
        else:
            agc_down_limit = None

        # Terms used to determine effective enablement min
        terms = [enablement_min, agc_down_limit]

        return max([i for i in terms if i is not None])

    # Effective enablement min
    m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN = pyo.Expression(m.S_TRADER_OFFERS, rule=fcas_effective_enablement_min)

    return m


def define_tie_breaking_expressions(m):
    """Tie-breaking expressions"""

    # Tie break cost TODO: Note that tie-break price of 1e-4 gives better results than 1e-6.
    m.E_TRADER_TIE_BREAK_COST = pyo.Expression(
        # expr=sum(m.P_TIE_BREAK_PRICE * (m.V_TRADER_SLACK_1[i] + m.V_TRADER_SLACK_2[i]) for i in m.S_TRADER_PRICE_TIED)
        expr=sum(1e-2 * (m.V_TRADER_SLACK_1[i] + m.V_TRADER_SLACK_2[i]) for i in m.S_TRADER_PRICE_TIED)
    )

    return m


def define_expressions(m, data):
    """Define model expressions"""

    # Trader cost functions
    m = define_cost_function_expressions(m)

    # Generic constrain expressions
    m = define_generic_constraint_expressions(m, data)

    # Constraint violation penalties
    m = define_constraint_violation_penalty_expressions(m)

    # MNSP loss model expressions
    m = define_mnsp_expressions(m)

    # Aggregate power expressions
    m = define_aggregate_power_expressions(m)

    # FCAS expressions
    m = define_fcas_expressions(m)

    # Tie-breaking expressions
    m = define_tie_breaking_expressions(m)

    return m


def define_offer_constraints(m):
    """Ensure trader and MNSP bids don't exceed their specified bid bands"""

    def trader_total_offer_rule(m, i, j):
        """Link quantity band offers to total offer made by trader for each offer type"""

        return m.V_TRADER_TOTAL_OFFER[i, j] == sum(m.V_TRADER_OFFER[i, j, k] for k in m.S_BANDS)

    # Linking individual quantity band offers to total amount offered by trader
    m.C_TRADER_TOTAL_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_total_offer_rule)

    def trader_offer_rule(m, i, j, k):
        """Band output must be non-negative and less than the max offered amount for that band"""

        return m.V_TRADER_OFFER[i, j, k] <= m.P_TRADER_QUANTITY_BAND[i, j, k] + m.V_CV_TRADER_OFFER[i, j, k]

    # Bounds on quantity band variables for traders
    m.C_TRADER_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_rule)

    def trader_capacity_rule(m, i, j):
        """Constrain max available output"""

        # UIGF constrains max output for semi-dispatchable plant
        if (i in m.S_TRADERS_SEMI_DISPATCH) and (j == 'ENOF'):
            return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_UIGF[i] + m.V_CV_TRADER_UIGF_SURPLUS[i, j]
        else:
            return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_CAPACITY[i, j]

    # Ensure dispatch is constrained by max available offer amount
    m.C_TRADER_CAPACITY = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_capacity_rule)

    def mnsp_total_offer_rule(m, i, j):
        """Link quantity band offers to total offer made by MNSP for each offer type"""

        return m.V_MNSP_TOTAL_OFFER[i, j] == sum(m.V_MNSP_OFFER[i, j, k] for k in m.S_BANDS)

    # Linking individual quantity band offers to total amount offered by MNSP
    m.C_MNSP_TOTAL_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_total_offer_rule)

    def mnsp_offer_rule(m, i, j, k):
        """Band output must be non-negative and less than the max offered amount for that band"""

        return m.V_MNSP_OFFER[i, j, k] <= m.P_MNSP_QUANTITY_BAND[i, j, k] + m.V_CV_MNSP_OFFER[i, j, k]

    # Bounds on quantity band variables for MNSPs
    m.C_MNSP_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_rule)

    def mnsp_capacity_rule(m, i, j):
        """Constrain max available output"""

        return m.V_MNSP_TOTAL_OFFER[i, j] <= m.P_MNSP_MAX_AVAILABLE[i, j] + m.V_CV_MNSP_CAPACITY[i, j]

    # Ensure dispatch is constrained by max available offer amount
    m.C_MNSP_CAPACITY = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_capacity_rule)

    return m


def define_generic_constraints(m):
    """
    Construct generic constraints. Also include constraints linking variables in objective function to variables in
    Generic Constraints.
    """

    def trader_variable_link_rule(m, i, j):
        """Link generic constraint trader variables to objective function variables"""

        return m.V_TRADER_TOTAL_OFFER[i, j] == m.V_GC_TRADER[i, j]

    # Link between total power output and quantity band output
    m.C_TRADER_VARIABLE_LINK = pyo.Constraint(m.S_GC_TRADER_VARS, rule=trader_variable_link_rule)

    def region_variable_link_rule(m, i, j):
        """Link total offer amount for each bid type to region variables"""

        return (sum(
            m.V_TRADER_TOTAL_OFFER[q, r] for q, r in m.S_TRADER_OFFERS if (m.P_TRADER_REGION[q] == i) and (r == j))
                == m.V_GC_REGION[i, j])

    # Link between region variables and the trader components constituting those variables
    m.C_REGION_VARIABLE_LINK = pyo.Constraint(m.S_GC_REGION_VARS, rule=region_variable_link_rule)

    def mnsp_variable_link_rule(m, i):
        """Link generic constraint MNSP variables to objective function variables"""

        # From and to regions for a given MNSP
        from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
        to_region = m.P_INTERCONNECTOR_TO_REGION[i]

        # TODO: Taking difference between 'to' and 'from' region. Think this is correct.
        return m.V_GC_INTERCONNECTOR[i] == m.V_MNSP_TOTAL_OFFER[i, to_region] - m.V_MNSP_TOTAL_OFFER[i, from_region]

    # Link between total power output and quantity band output
    m.C_MNSP_VARIABLE_LINK = pyo.Constraint(m.S_MNSPS, rule=mnsp_variable_link_rule)

    def generic_constraint_rule(m, c):
        """NEMDE Generic Constraints"""

        # Type of generic constraint (LE, GE, EQ)
        if m.P_GC_TYPE[c] == 'LE':
            return m.E_GC_LHS_TERMS[c] <= m.P_GC_RHS[c] + m.V_CV[c]
        elif m.P_GC_TYPE[c] == 'GE':
            return m.E_GC_LHS_TERMS[c] + m.V_CV[c] >= m.P_GC_RHS[c]
        elif m.P_GC_TYPE[c] == 'EQ':
            return m.E_GC_LHS_TERMS[c] + m.V_CV_LHS[c] == m.P_GC_RHS[c] + m.V_CV_RHS[c]
        else:
            raise Exception(f'Unexpected constraint type: {m.P_GC_TYPE[c]}')

    # Generic constraints
    m.C_GENERIC_CONSTRAINT = pyo.Constraint(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rule)

    return m


def define_unit_constraints(m):
    """Construct ramp rate constraints for units"""

    def trader_ramp_up_rate_rule(m, i, j):
        """Ramp up rate limit for ENOF and LDOF offers"""

        # Only construct ramp-rate constraint for energy offers
        if (j != 'ENOF') and (j != 'LDOF'):
            return pyo.Constraint.Skip

        # Ramp rate TODO: check if second condition is necessary
        if (i in m.P_TRADER_SCADA_RAMP_UP_RATE.keys()) and (m.P_TRADER_SCADA_RAMP_UP_RATE[i] > 0):
            ramp_limit = min([m.P_TRADER_SCADA_RAMP_UP_RATE[i], m.P_TRADER_PERIOD_RAMP_UP_RATE[(i, j)]])
        else:
            ramp_limit = m.P_TRADER_PERIOD_RAMP_UP_RATE[(i, j)]

        # Unit on fixed startup profile. T2 ramp rate applies while in T2, then SCADA ramp rate for rest of interval
        if (i in m.P_TRADER_CURRENT_MODE.keys()) and (m.P_TRADER_CURRENT_MODE[i] == '1'):
            # Output fixed to 0 for this amount of time over dispatch interval
            t1_time_remaining = m.P_TRADER_T1[i] - m.P_TRADER_CURRENT_MODE_TIME[i]

            # Unit follows fixed startup trajectory
            t2_time = max(0, min(m.P_TRADER_T2[i], 5 - t1_time_remaining))

            # Time unit above min loading
            min_loading_time = max([0, 5 - t1_time_remaining - t2_time])

            # If T2=0 then unit immediately operates at min loading after synchronisation complete
            if m.P_TRADER_T2[i] == 0:
                t2_ramp_capability = m.P_TRADER_MIN_LOADING_MW[i]

            # Else unit must follow fixed startup trajectory
            else:
                t2_ramp_capability = (m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T2[i]) * t2_time

            # Ramping capability over T3
            t3_ramp_capability = (ramp_limit / 60) * min_loading_time

            # Total ramp up capability
            ramp_up_capability = t2_ramp_capability + t3_ramp_capability

            # InitialMW = 0 if CurrentMode is T1
            initial_mw = 0

            return m.V_TRADER_TOTAL_OFFER[i, j] <= initial_mw + ramp_up_capability + m.V_CV_TRADER_RAMP_UP[i]

        elif (i in m.P_TRADER_CURRENT_MODE.keys()) and (m.P_TRADER_CURRENT_MODE[i] == '2'):
            # Amount of time remaining in T2
            t2_time_remaining = m.P_TRADER_T2[i] - m.P_TRADER_CURRENT_MODE_TIME[i]

            # Time unit is above min loading level over the dispatch interval
            min_loading_time = max([0, 5 - t2_time_remaining])

            # If T2=0 then unit immediately operates at min loading after synchronisation complete
            if m.P_TRADER_T2[i] == 0:
                t2_ramp_capability = m.P_TRADER_MIN_LOADING_MW[i]

            # Else unit must follow fixed startup trajectory
            else:
                t2_ramp_capability = (m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T2[i]) * t2_time_remaining

            # Ramping capability over T3
            t3_ramp_capability = (ramp_limit / 60) * min_loading_time

            # Total ramp up capability
            ramp_up_capability = t2_ramp_capability + t3_ramp_capability

            # InitialMW based on anticipated startup profile MW (may differ from actual InitialMW recorded by SCADA)
            initial_mw = (m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T2[i]) * m.P_TRADER_CURRENT_MODE_TIME[i]

            return m.V_TRADER_TOTAL_OFFER[i, j] <= initial_mw + ramp_up_capability + m.V_CV_TRADER_RAMP_UP[i]

        return m.V_TRADER_TOTAL_OFFER[i, j] - m.P_TRADER_INITIAL_MW[i] <= (ramp_limit / 12) + m.V_CV_TRADER_RAMP_UP[i]

    # Ramp up rate limit
    m.C_TRADER_RAMP_UP_RATE = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_up_rate_rule)

    def trader_ramp_down_rate_rule(m, i, j):
        """Ramp down rate limit for ENOF and LDOF offers"""

        # Only construct ramp-rate constraint for energy offers
        if (j != 'ENOF') and (j != 'LDOF'):
            return pyo.Constraint.Skip

        # Ramp rate TODO: check if second condition is necessary
        if (i in m.P_TRADER_SCADA_RAMP_DOWN_RATE.keys()) and (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] > 0):
            ramp_limit = min([m.P_TRADER_SCADA_RAMP_DOWN_RATE[i], m.P_TRADER_PERIOD_RAMP_DOWN_RATE[(i, j)]])
        else:
            ramp_limit = m.P_TRADER_PERIOD_RAMP_DOWN_RATE[(i, j)]

        # Initial MW
        initial_mw = m.P_TRADER_INITIAL_MW[i]

        return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw + m.V_CV_TRADER_RAMP_DOWN[i] >= - (ramp_limit / 12)

    # Ramp up rate limit
    m.C_TRADER_RAMP_DOWN_RATE = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_down_rate_rule)

    return m


def define_region_constraints(m):
    """Define power balance constraint for each region, and constrain flows on interconnectors"""

    def power_balance_rule(m, r):
        """
        Power balance for each region

        FixedDemand + DispatchedLoad + NetExport = DispatchedGeneration
        """
        # TODO: check if a penalty factor needs to be applied here - probably not because captured by other expressions
        return (m.E_REGION_DISPATCHED_GENERATION[r] + m.V_CV_REGION_GENERATION_DEFICIT[r]
                == m.E_REGION_FIXED_DEMAND[r]
                + m.E_REGION_DISPATCHED_LOAD[r]
                + m.E_REGION_NET_EXPORT[r]
                + m.V_CV_REGION_GENERATION_SURPLUS[r])

    # Power balance in each region
    m.C_POWER_BALANCE = pyo.Constraint(m.S_REGIONS, rule=power_balance_rule)

    return m


def define_interconnector_constraints(m):
    """Define power flow limits on interconnectors"""

    def interconnector_forward_flow_rule(m, i):
        """Constrain forward power flow over interconnector"""

        return m.V_GC_INTERCONNECTOR[i] <= m.P_INTERCONNECTOR_UPPER_LIMIT[i] + m.V_CV_INTERCONNECTOR_FORWARD[i]

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_FORWARD_FLOW = pyo.Constraint(m.S_INTERCONNECTORS, rule=interconnector_forward_flow_rule)

    def interconnector_reverse_flow_rule(m, i):
        """Constrain reverse power flow over interconnector"""

        return m.V_GC_INTERCONNECTOR[i] + m.V_CV_INTERCONNECTOR_REVERSE[i] >= - m.P_INTERCONNECTOR_LOWER_LIMIT[i]

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_REVERSE_FLOW = pyo.Constraint(m.S_INTERCONNECTORS, rule=interconnector_reverse_flow_rule)

    return m


def define_mnsp_constraints(m):
    """Define MNSP ramping constraints"""

    def mnsp_ramp_up_rule(m, i, j):
        """MNSP ramp-up constraint"""

        return (m.V_MNSP_TOTAL_OFFER[i, j] <= m.P_INTERCONNECTOR_INITIAL_MW[i] + (m.P_MNSP_RAMP_UP_RATE[i, j] / 12)
                + m.V_CV_MNSP_RAMP_UP[i, j])

    # MNSP ramp up constraint
    m.C_MNSP_RAMP_UP = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_ramp_up_rule)

    def mnsp_ramp_down_rule(m, i, j):
        """MNSP ramp-down constraint"""

        return (m.V_MNSP_TOTAL_OFFER[i, j] + m.V_CV_MNSP_RAMP_DOWN[i, j]
                >= m.P_INTERCONNECTOR_INITIAL_MW[i] - (m.P_MNSP_RAMP_DOWN_RATE[i, j] / 12))

    # MNSP ramp down constraint
    m.C_MNSP_RAMP_DOWN = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_ramp_down_rule)

    def mnsp_flow_direction_1_rule(m, i):
        """Indicator constraint 1 to define MNSP flow direction"""

        return m.V_GC_INTERCONNECTOR[i] >= - 1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])

    # Constraint used to get flow direction for MNSP
    m.C_MNSP_FLOW_DIRECTION_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_flow_direction_1_rule)

    def mnsp_flow_direction_2_rule(m, i):
        """Indicator constraint 2 to define MNSP flow direction"""

        return m.V_GC_INTERCONNECTOR[i] <= 1000 * m.V_MNSP_FLOW_DIRECTION[i]

    # Constraint used to get flow direction for MNSP
    m.C_MNSP_FLOW_DIRECTION_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_flow_direction_2_rule)

    def mnsp_from_export_flow_1_rule(m, i):
        """From region export flow rule 1"""

        return m.E_MNSP_FROM_CP_FLOW[i] - (1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])) <= m.V_MNSP_FROM_REGION_EXPORT[i]

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_1_rule)

    def mnsp_from_export_flow_2_rule(m, i):
        """From region export flow rule 2"""

        return m.V_MNSP_FROM_REGION_EXPORT[i] <= m.E_MNSP_FROM_CP_FLOW[i] + (1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]))

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_2_rule)

    def mnsp_from_export_flow_3_rule(m, i):
        """From region export flow rule 3"""

        return - 1000 * m.V_MNSP_FLOW_DIRECTION[i] <= m.V_MNSP_FROM_REGION_EXPORT[i]

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_3 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_3_rule)

    def mnsp_from_export_flow_4_rule(m, i):
        """From region export flow rule 4"""

        return m.V_MNSP_FROM_REGION_EXPORT[i] <= 1000 * m.V_MNSP_FLOW_DIRECTION[i]

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_4 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_4_rule)

    def mnsp_from_import_flow_1_rule(m, i):
        """From region import flow 1"""

        return m.E_MNSP_FROM_CP_FLOW[i] - (1000 * m.V_MNSP_FLOW_DIRECTION[i]) <= m.V_MNSP_FROM_REGION_IMPORT[i]

    # Constraint used to determine FromRegionImport flow
    m.C_MNSP_FROM_REGION_IMPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_import_flow_1_rule)

    def mnsp_from_import_flow_2_rule(m, i):
        """From region import flow 2"""

        return m.V_MNSP_FROM_REGION_IMPORT[i] <= m.E_MNSP_FROM_CP_FLOW[i] + (1000 * m.V_MNSP_FLOW_DIRECTION[i])

    # Constraint used to determine FromRegionImport flow
    m.C_MNSP_FROM_REGION_IMPORT_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_import_flow_2_rule)

    def mnsp_from_import_flow_3_rule(m, i):
        """From region import flow 3"""

        return -1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]) <= m.V_MNSP_FROM_REGION_IMPORT[i]

    # Constraint used to determine FromRegionImport flow
    m.C_MNSP_FROM_REGION_IMPORT_3 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_import_flow_3_rule)

    def mnsp_from_import_flow_4_rule(m, i):
        """From region import flow 4"""

        return m.V_MNSP_FROM_REGION_IMPORT[i] <= 1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])

    # Constraint used to determine FromRegionImport flow
    m.C_MNSP_FROM_REGION_IMPORT_4 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_import_flow_4_rule)

    def mnsp_to_export_flow_1_rule(m, i):
        """ToRegion Export flow 1"""

        return m.E_MNSP_TO_CP_FLOW[i] - (1000 * m.V_MNSP_FLOW_DIRECTION[i]) <= m.V_MNSP_TO_REGION_EXPORT[i]

    # MNSP ToRegion export flow condition 1
    m.C_MNSP_TO_REGION_EXPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_export_flow_1_rule)

    def mnsp_to_export_flow_2_rule(m, i):
        """ToRegion Export flow 2"""

        return m.V_MNSP_TO_REGION_EXPORT[i] <= m.E_MNSP_TO_CP_FLOW[i] + (1000 * m.V_MNSP_FLOW_DIRECTION[i])

    # MNSP ToRegion export flow condition 2
    m.C_MNSP_TO_REGION_EXPORT_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_export_flow_2_rule)

    def mnsp_to_export_flow_3_rule(m, i):
        """ToRegion Export flow 3"""

        return -1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]) <= m.V_MNSP_TO_REGION_EXPORT[i]

    # MNSP ToRegion export flow condition 3
    m.C_MNSP_TO_REGION_EXPORT_3 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_export_flow_3_rule)

    def mnsp_to_export_flow_4_rule(m, i):
        """ToRegion Export flow 4"""

        return m.V_MNSP_TO_REGION_EXPORT[i] <= 1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])

    # MNSP ToRegion export flow condition 4
    m.C_MNSP_TO_REGION_EXPORT_4 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_export_flow_4_rule)

    def mnsp_to_import_flow_1_rule(m, i):
        """ToRegion import flow 1"""

        return m.E_MNSP_TO_CP_FLOW[i] - (1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])) <= m.V_MNSP_TO_REGION_IMPORT[i]

    # MNSP ToRegion import flow condition 1
    m.C_MNSP_TO_REGION_IMPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_import_flow_1_rule)

    def mnsp_to_import_flow_2_rule(m, i):
        """ToRegion import flow 2"""

        return m.V_MNSP_TO_REGION_IMPORT[i] <= m.E_MNSP_TO_CP_FLOW[i] + (1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]))

    # MNSP ToRegion import flow condition 2
    m.C_MNSP_TO_REGION_IMPORT_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_import_flow_2_rule)

    def mnsp_to_import_flow_3_rule(m, i):
        """ToRegion import flow 3"""

        return -1000 * m.V_MNSP_FLOW_DIRECTION[i] <= m.V_MNSP_TO_REGION_IMPORT[i]

    # MNSP ToRegion import flow condition 3
    m.C_MNSP_TO_REGION_IMPORT_3 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_import_flow_3_rule)

    def mnsp_to_import_flow_4_rule(m, i):
        """ToRegion import flow 4"""

        return m.V_MNSP_TO_REGION_IMPORT[i] <= 1000 * m.V_MNSP_FLOW_DIRECTION[i]

    # MNSP ToRegion import flow condition 4
    m.C_MNSP_TO_REGION_IMPORT_4 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_import_flow_4_rule)

    def mnsp_region_loss_allocation_1_rule(m, i):
        """Condition ensures either From or To region loss is non-zero"""

        return -1000 * m.V_MNSP_FLOW_DIRECTION[i] <= m.E_MNSP_FROM_REGION_LOSS[i]

    # MNSP loss allocation rule 1
    # m.C_MNSP_REGION_LOSS_ALLOCATION_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_region_loss_allocation_1_rule)

    def mnsp_region_loss_allocation_2_rule(m, i):
        """Condition ensures either From or To region loss is non-zero"""

        return m.E_MNSP_FROM_REGION_LOSS[i] <= 1000 * m.V_MNSP_FLOW_DIRECTION[i]

    # MNSP loss allocation rule 2
    # m.C_MNSP_REGION_LOSS_ALLOCATION_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_region_loss_allocation_2_rule)

    def mnsp_region_loss_allocation_3_rule(m, i):
        """Condition ensures either From or To region loss is non-zero"""

        return -1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]) <= m.E_MNSP_TO_REGION_LOSS[i]

    # MNSP loss allocation rule 3
    # m.C_MNSP_REGION_LOSS_ALLOCATION_3 = pyo.Constraint(m.S_MNSPS, rule=mnsp_region_loss_allocation_3_rule)

    def mnsp_region_loss_allocation_4_rule(m, i):
        """Condition ensures either From or To region loss is non-zero"""

        return m.E_MNSP_TO_REGION_LOSS[i] <= 1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])

    # MNSP loss allocation rule 2
    # m.C_MNSP_REGION_LOSS_ALLOCATION_4 = pyo.Constraint(m.S_MNSPS, rule=mnsp_region_loss_allocation_4_rule)

    return m


def define_fcas_constraints(m, data):
    """Define FCAS constraints"""

    def generator_joint_ramping_up_rule(m, i, j):
        """Generator joint ramp up constraints"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider raise regulation FCAS
        if j != 'R5RE':
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # SCADA ramp rate must be defined and greater than 0
        elif (i not in m.P_TRADER_SCADA_RAMP_UP_RATE.keys()) or (m.P_TRADER_SCADA_RAMP_UP_RATE[i] <= 0):
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'ENOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        else:
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
                    <= m.P_TRADER_INITIAL_MW[i] + (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)
                    + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j])

    # Generator joint ramp up constraint
    m.C_FCAS_GENERATOR_JOINT_RAMPING_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=generator_joint_ramping_up_rule)

    def generator_joint_ramping_down_rule(m, i, j):
        """Generator joint ramp down constraints"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider raise regulation FCAS
        if j != 'L5RE':
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # SCADA ramp rate must be defined and greater than 0
        elif (i not in m.P_TRADER_SCADA_RAMP_DOWN_RATE.keys()) or (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] <= 0):
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'ENOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        else:
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
                    + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j]
                    >= m.P_TRADER_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12))

    # Generator joint ramp down constraint
    m.C_FCAS_GENERATOR_JOINT_RAMPING_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=generator_joint_ramping_down_rule)

    def generator_joint_capacity_rhs_rule(m, i, j):
        """Joint capacity constraint - RHS of FCAS trapezium"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider contingency FCAS
        if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'ENOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        elif (i, 'R5RE') in m.S_TRADER_OFFERS:
            usc = utils.fcas.get_upper_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (usc * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
                    <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j]
                    + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j]
                    )
        else:
            usc = utils.fcas.get_upper_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (usc * m.V_TRADER_TOTAL_OFFER[i, j])
                    <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j])

    # Joint capacity constraint - generator
    m.C_FCAS_GENERATOR_CONTINGENCY_RHS = pyo.Constraint(m.S_TRADER_OFFERS, rule=generator_joint_capacity_rhs_rule)

    def generator_joint_capacity_lhs_rule(m, i, j):
        """Joint capacity raise constraint - LHS of FCAS trapezium"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider contingency FCAS
        if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'ENOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        elif (i, 'L5RE') in m.S_TRADER_OFFERS:
            lsc = utils.fcas.get_lower_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (lsc * m.V_TRADER_TOTAL_OFFER[i, j])
                    - m.V_TRADER_TOTAL_OFFER[i, 'L5RE'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]
                    >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j])

        else:
            lsc = utils.fcas.get_lower_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (lsc * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]
                    >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j])

    # Joint capacity constraint - generator
    m.C_FCAS_GENERATOR_CONTINGENCY_LHS = pyo.Constraint(m.S_TRADER_OFFERS, rule=generator_joint_capacity_lhs_rule)

    def generator_joint_energy_regulating_rhs_rule(m, i, j):
        """Joint energy and regulating FCAS constraint - RHS of trapezium"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider regulation raise service
        if j not in ['R5RE', 'L5RE']:
            return pyo.Constraint.Skip

        # Trader must have an energy offer
        elif (i, 'ENOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Regulating FCAS must be available
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        else:
            usc = utils.fcas.get_upper_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + (usc * m.V_TRADER_TOTAL_OFFER[i, j])
                    <= m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j] + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j])

    # Energy and regulating FCAS constraint - RHS of trapezium
    m.C_FCAS_GENERATOR_JOINT_ENERGY_REGULATING_RHS = pyo.Constraint(m.S_TRADER_OFFERS,
                                                                    rule=generator_joint_energy_regulating_rhs_rule)

    def generator_joint_energy_regulating_lhs_rule(m, i, j):
        """Joint energy and regulating FCAS constraint - LHS of trapezium"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider regulation raise service
        if j not in ['R5RE', 'L5RE']:
            return pyo.Constraint.Skip

        # Trader must have an energy offer
        elif (i, 'ENOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Regulating FCAS must be available
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        else:
            lsc = utils.fcas.get_lower_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] - (lsc * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j]
                    >= m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j])

    # Energy and regulating FCAS constraint - LHS of trapezium
    m.C_FCAS_GENERATOR_JOINT_ENERGY_REGULATING_LHS = pyo.Constraint(m.S_TRADER_OFFERS,
                                                                    rule=generator_joint_energy_regulating_lhs_rule)

    def generator_fcas_max_available_rule(m, i, j):
        """Effective max available"""

        # Only consider generators
        if m.P_TRADER_TYPE[i] != 'GENERATOR':
            return pyo.Constraint.Skip

        # Only consider FCAS offers
        if j not in ['R5RE', 'R6SE', 'R60S', 'R5MI', 'L5RE', 'L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Fix to zero if FCAS service is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return m.V_TRADER_TOTAL_OFFER[i, j] == 0 + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

        elif j == 'R5RE':
            # No AGC ramp scaling applied if SCADA ramp rate missing (from FCAS docs)
            if i not in m.P_TRADER_SCADA_RAMP_UP_RATE.keys():
                effective_max_avail = m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]
            else:
                effective_max_avail = min(
                    [(m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12), m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]])
            return m.V_TRADER_TOTAL_OFFER[i, j] <= effective_max_avail + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

        elif j == 'L5RE':
            # No AGC ramp scaling applied if SCADA ramp rate missing (from FCAS docs)
            if i not in m.P_TRADER_SCADA_RAMP_DOWN_RATE.keys():
                effective_max_avail = m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]
            else:
                effective_max_avail = min(
                    [(m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12), m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]])
            return m.V_TRADER_TOTAL_OFFER[i, j] <= effective_max_avail + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

        else:
            return (m.V_TRADER_TOTAL_OFFER[i, j]
                    <= m.P_TRADER_FCAS_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j])

    # Effective max available FCAS
    m.C_FCAS_GENERATOR_MAX_AVAILABLE = pyo.Constraint(m.S_TRADER_OFFERS, rule=generator_fcas_max_available_rule)

    def load_joint_ramping_up_rule(m, i, j):
        """Load joint ramp up constraints"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider raise regulation FCAS
        if j != 'R5RE':
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # SCADA ramp rate must be defined and greater than 0
        elif (i not in m.P_TRADER_SCADA_RAMP_DOWN_RATE.keys()) or (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] <= 0):
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'LDOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        else:
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - m.V_TRADER_TOTAL_OFFER[i, 'R5RE']
                    + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j]
                    >= m.P_TRADER_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12))

    # Load joint ramp up constraint
    m.C_FCAS_LOAD_JOINT_RAMPING_UP = pyo.Constraint(m.S_TRADER_OFFERS, rule=load_joint_ramping_up_rule)

    def load_joint_ramping_down_rule(m, i, j):
        """Load joint ramp down constraints"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider raise regulation FCAS
        if j != 'L5RE':
            return pyo.Constraint.Skip

        # Lower regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # SCADA ramp rate must be defined and greater than 0
        elif (i not in m.P_TRADER_SCADA_RAMP_UP_RATE.keys()) or (m.P_TRADER_SCADA_RAMP_UP_RATE[i] <= 0):
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'LDOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        else:
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
                    <= m.P_TRADER_INITIAL_MW[i] + (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)
                    + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j])

    # Load joint ramp down constraint
    m.C_FCAS_LOAD_JOINT_RAMPING_DOWN = pyo.Constraint(m.S_TRADER_OFFERS, rule=load_joint_ramping_down_rule)

    def load_joint_capacity_rhs_rule(m, i, j):
        """Joint capacity constraint - RHS of FCAS trapezium"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider contingency FCAS
        if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'LDOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        elif (i, 'L5RE') in m.S_TRADER_OFFERS:
            usc = utils.fcas.get_upper_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (usc * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_TRADER_TOTAL_OFFER[i, 'L5RE']
                    <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j])

        else:
            usc = utils.fcas.get_upper_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (usc * m.V_TRADER_TOTAL_OFFER[i, j])
                    <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j])

    # Joint capacity constraint - load - RHS of trapezium
    m.C_FCAS_LOAD_CONTINGENCY_RHS = pyo.Constraint(m.S_TRADER_OFFERS, rule=load_joint_capacity_rhs_rule)

    def load_joint_capacity_lhs_rule(m, i, j):
        """Joint capacity constraint - RHS of FCAS trapezium"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider contingency FCAS
        if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Raise regulation FCAS is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # Must have an energy offer
        elif (i, 'LDOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        elif (i, 'R5RE') in m.S_TRADER_OFFERS:
            lsc = utils.fcas.get_lower_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (lsc * m.V_TRADER_TOTAL_OFFER[i, j])
                    - m.V_TRADER_TOTAL_OFFER[i, 'R5RE'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]
                    >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j])

        else:
            lsc = utils.fcas.get_lower_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (lsc * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]
                    >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j])

    # Joint capacity constraint - load - LHS of trapezium
    m.C_FCAS_LOAD_CONTINGENCY_LHS = pyo.Constraint(m.S_TRADER_OFFERS, rule=load_joint_capacity_lhs_rule)

    def load_joint_energy_regulating_rhs_rule(m, i, j):
        """Joint energy and regulating FCAS constraint - RHS of trapezium"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider regulation raise service
        if j not in ['R5RE', 'L5RE']:
            return pyo.Constraint.Skip

        # Trader must have an energy offer
        elif (i, 'LDOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Regulating FCAS must be available
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        else:
            usc = utils.fcas.get_upper_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + (usc * m.V_TRADER_TOTAL_OFFER[i, j])
                    <= m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j] + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j])

    # Energy and regulating FCAS constraint - RHS of trapezium
    m.C_FCAS_LOAD_JOINT_ENERGY_REGULATING_RHS = pyo.Constraint(m.S_TRADER_OFFERS,
                                                               rule=load_joint_energy_regulating_rhs_rule)

    def load_joint_energy_regulating_lhs_rule(m, i, j):
        """Joint energy and regulating FCAS constraint - LHS of trapezium"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider regulation raise service
        if j not in ['R5RE', 'L5RE']:
            return pyo.Constraint.Skip

        # Trader must have an energy offer
        elif (i, 'LDOF') not in m.S_TRADER_OFFERS:
            return pyo.Constraint.Skip

        # Regulating FCAS must be available
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        else:
            lsc = utils.fcas.get_lower_slope_coefficient(data, i, j)
            return (m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] - (lsc * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j]
                    >= m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j])

    # Energy and regulating FCAS constraint - LHS of trapezium
    m.C_FCAS_LOAD_JOINT_ENERGY_REGULATING_LHS = pyo.Constraint(m.S_TRADER_OFFERS,
                                                               rule=load_joint_energy_regulating_lhs_rule)

    def load_fcas_max_available_rule(m, i, j):
        """Effective max available"""

        # Only consider loads
        if m.P_TRADER_TYPE[i] not in ['LOAD', 'NORMALLY_ON_LOAD']:
            return pyo.Constraint.Skip

        # Only consider FCAS offers
        if j not in ['R5RE', 'R6SE', 'R60S', 'R5MI', 'L5RE', 'L6SE', 'L60S', 'L5MI']:
            return pyo.Constraint.Skip

        # Fix to zero if FCAS service is unavailable
        elif not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return m.V_TRADER_TOTAL_OFFER[i, j] == 0 + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

        elif j == 'R5RE':
            # No AGC ramp scaling applied if SCADA ramp rate missing (from FCAS docs)
            if i not in m.P_TRADER_SCADA_RAMP_DOWN_RATE.keys():
                effective_max_avail = m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]
            else:
                effective_max_avail = min(
                    [(m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12), m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]])
            return m.V_TRADER_TOTAL_OFFER[i, j] <= effective_max_avail + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

        elif j == 'L5RE':
            # No AGC ramp scaling applied if SCADA ramp rate missing (from FCAS docs)
            if i not in m.P_TRADER_SCADA_RAMP_UP_RATE.keys():
                effective_max_avail = m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]
            else:
                effective_max_avail = min(
                    [(m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12), m.P_TRADER_FCAS_MAX_AVAILABLE[i, j]])
            return m.V_TRADER_TOTAL_OFFER[i, j] <= effective_max_avail + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j]

        else:
            return (m.V_TRADER_TOTAL_OFFER[i, j]
                    <= m.P_TRADER_FCAS_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j])

    # Effective max available FCAS
    m.C_FCAS_LOAD_MAX_AVAILABLE = pyo.Constraint(m.S_TRADER_OFFERS, rule=load_fcas_max_available_rule)

    def enablement_min_rule(m, i, j):
        """Energy target must be >= EnablementMin"""

        # Only consider FCAS offers
        if j not in ['L6SE', 'L60S', 'L5MI', 'L5RE', 'R6SE', 'R60S', 'R5MI', 'R5RE']:
            return pyo.Constraint.Skip

        # Get energy offer type
        if m.P_TRADER_TYPE[i] == 'GENERATOR':
            energy_offer = 'ENOF'
        elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
            energy_offer = 'LDOF'
        else:
            raise Exception('Unexpected trade type:', m.P_TRADER_TYPE[i])

        # Trader does not have an energy offer
        if (i, energy_offer) not in m.V_TRADER_TOTAL_OFFER.keys():
            return pyo.Constraint.Skip

        # Check if FCAS is available - skip constraint if unavailable
        if not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # Effective EnablementMin
        if j in ['L5RE', 'R5RE']:
            enablement_min = m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j]
        elif j in ['L6SE', 'L60S', 'L5MI', 'R6SE', 'R60S', 'R5MI']:
            enablement_min = m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j]
        else:
            raise Exception('Unexpected trade type:', j)

        return m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j] >= enablement_min

    # Enablement min
    m.C_FCAS_ENABLEMENT_MIN = pyo.Constraint(m.S_TRADER_OFFERS, rule=enablement_min_rule)

    def enablement_max_rule(m, i, j):
        """Energy target must be <= EnablementMax"""

        # Only consider FCAS offers
        if j not in ['L6SE', 'L60S', 'L5MI', 'L5RE', 'R6SE', 'R60S', 'R5MI', 'R5RE']:
            return pyo.Constraint.Skip

        # Get energy offer type
        if m.P_TRADER_TYPE[i] == 'GENERATOR':
            energy_offer = 'ENOF'
        elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
            energy_offer = 'LDOF'
        else:
            raise Exception('Unexpected trade type:', m.P_TRADER_TYPE[i])

        # Trader does not have an energy offer
        if (i, energy_offer) not in m.V_TRADER_TOTAL_OFFER.keys():
            return pyo.Constraint.Skip

        # Check if FCAS is available - skip constraint if unavailable
        if not m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j]:
            return pyo.Constraint.Skip

        # Effective EnablementMax
        if j in ['L5RE', 'R5RE']:
            enablement_max = m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j]
        elif j in ['L6SE', 'L60S', 'L5MI', 'R6SE', 'R60S', 'R5MI']:
            enablement_max = m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j]
        else:
            raise Exception('Unexpected trade type:', j)

        return m.V_TRADER_TOTAL_OFFER[i, energy_offer] <= enablement_max + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j]

    # Enablement max
    m.C_FCAS_ENABLEMENT_MAX = pyo.Constraint(m.S_TRADER_OFFERS, rule=enablement_max_rule)

    return m


def define_loss_model_constraints(m):
    """Interconnector loss model constraints"""

    def approximated_loss_rule(m, i):
        """Approximate interconnector loss"""

        return (m.V_LOSS[i]
                == sum(m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y[i, k] * m.V_LOSS_LAMBDA[i, k]
                       for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i)
                )

    # Approximate loss over interconnector
    m.C_APPROXIMATED_LOSS = pyo.Constraint(m.S_INTERCONNECTORS, rule=approximated_loss_rule)

    def sos2_condition_1_rule(m, i):
        """SOS2 condition 1"""

        return (m.V_GC_INTERCONNECTOR[i] == sum(m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X[i, k] * m.V_LOSS_LAMBDA[i, k]
                                                for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i))

    # SOS2 condition 1
    m.C_SOS2_CONDITION_1 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_1_rule)

    def sos2_condition_2_rule(m, i):
        """SOS2 condition 2"""

        return sum(m.V_LOSS_LAMBDA[i, k] for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i) == 1

    # SOS2 condition 2
    m.C_SOS2_CONDITION_2 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_2_rule)

    def sos2_condition_3_rule(m, i):
        """SOS2 condition 3"""

        return sum(m.V_LOSS_Y[i, k] for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS if j == i) == 1

    # SOS2 condition 3
    m.C_SOS2_CONDITION_3 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_3_rule)

    def sos2_condition_4_rule(m, i, j):
        """SOS2 condition 4"""

        # Last interconnector breakpoint index
        end = max(segment_id for interconnector_id, segment_id in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
                  if interconnector_id == i)

        # TODO: not sure if j >= 2 or j >= 1 because S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS starts from 0. Similarly,
        # not sure if (j <= end - 1) is correct
        if (j >= 2) and (j <= end - 1):
            return (sum(m.V_LOSS_Y[i, z] for z in range(j + 1, end))
                    <= sum(m.V_LOSS_LAMBDA[i, z] for z in range(j + 1, end + 1)))
        else:
            return pyo.Constraint.Skip

    # SOS2 condition 4
    m.C_SOS2_CONDITION_4 = pyo.Constraint(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, rule=sos2_condition_4_rule)

    def sos2_condition_5_rule(m, i, j):
        """SOS2 condition 5"""

        # Last interconnector breakpoint index
        end = max(segment_id for interconnector_id, segment_id in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
                  if interconnector_id == i)

        # TODO: not sure if j >= 2 or j >= 1 because S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS starts from 0. Similarly,
        # not sure if (j <= end - 1) is correct
        if (j >= 2) and (j <= end - 1):
            return (sum(m.V_LOSS_LAMBDA[i, z] for z in range(j + 1, end + 1))
                    <= sum(m.V_LOSS_Y[i, z] for z in range(j, end)))
        else:
            return pyo.Constraint.Skip

    # SOS2 condition 5
    m.C_SOS2_CONDITION_5 = pyo.Constraint(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, rule=sos2_condition_5_rule)

    def sos2_condition_6_rule(m, i, j):
        """SOS2 condition 6"""

        # Last interconnector breakpoint index
        end = max(segment_id for interconnector_id, segment_id in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
                  if interconnector_id == i)

        if j == 1:
            return m.V_LOSS_LAMBDA[i, j] <= m.V_LOSS_Y[i, j]
        elif j == end:
            return m.V_LOSS_LAMBDA[i, j] <= m.V_LOSS_Y[i, j - 1]
        else:
            return pyo.Constraint.Skip

    # SOS2 condition 6
    m.C_SOS2_CONDITION_6 = pyo.Constraint(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, rule=sos2_condition_6_rule)

    return m


def define_fast_start_unit_inflexibility_constraints(m):
    """Fast start unit inflexibility profile constraints"""

    def get_inflexibility_profile_base_time(mode, mode_time, t1, t2, t3):
        """Get number of minutes from start of inflexibility profile"""

        if mode == '0':
            return mode_time
        elif mode == '1':
            return mode_time
        elif mode == '2':
            return t1 + mode_time
        elif mode == '3':
            return t1 + t2 + mode_time
        elif mode == '4':
            return t1 + t2 + t3 + mode_time
        else:
            raise Exception('Unhandled case:', mode, mode_time, t1, t2, t3)

    def get_inflexibility_profile_effective_mode_and_time(mode, mode_time, t1, t2, t3, t4):
        """Get effective mode and time at end of dispatch interval"""

        # Time at end of dispatch interval - offsetting by 5 minutes to correspond to end of dispatch interval
        minutes = get_inflexibility_profile_base_time(mode, mode_time + 5, t1, t2, t3)

        # Time interval endpoints
        t1_end = t1
        t2_end = t1 + t2
        t3_end = t1 + t2 + t3
        t4_end = t1 + t2 + t3 + t4

        # Get effective mode
        # TODO: need to fix this in the future - possible that unit in mode 0 has EnergyTarget > 0. Two NEMDE runs must
        # be performed. See fast start unit docs.
        if mode == '0':
            effective_mode = '0'
        elif minutes <= t1_end:
            effective_mode = '1'
        elif (minutes > t1_end) and (minutes <= t2_end):
            effective_mode = '2'
        elif (minutes > t2_end) and (minutes <= t3_end):
            effective_mode = '3'
        elif (minutes > t3_end) and (minutes <= t4_end):
            effective_mode = '4'
        elif minutes > t4_end:
            effective_mode = '4'
        else:
            raise Exception('Unhandled case:', minutes, t1_end, t2_end, t3_end, t4_end)

        # Get effective time based on effective mode and time interval endpoints
        if effective_mode == '0':
            effective_time = mode_time
        elif effective_mode == '1':
            effective_time = minutes
        elif effective_mode == '2':
            effective_time = minutes - t1_end
        elif effective_mode == '3':
            effective_time = minutes - t2_end
        elif effective_mode == '4':
            effective_time = minutes - t3_end
        else:
            raise Exception('Unhandled case:', effective_mode)

        return effective_mode, effective_time

    def profile_constraint_rule(m, i):
        """Energy profile constraint"""

        # CurrentMode and CurrentModeTime may be missing - skip constraint
        if (m.P_TRADER_CURRENT_MODE[i] is None) or (m.P_TRADER_CURRENT_MODE_TIME[i] is None):
            return pyo.Constraint.Skip

        if m.P_TRADER_TYPE[i] == 'GENERATOR':
            energy_offer = 'ENOF'
        elif m.P_TRADER_TYPE[i] in ['LOAD', 'NORMALLY_ON_LOAD']:
            energy_offer = 'LDOF'
        else:
            raise Exception('Unexpected energy offer:', i)

        # Get effective mode and time at end of dispatch interval
        effective_mode, effective_time = get_inflexibility_profile_effective_mode_and_time(
            m.P_TRADER_CURRENT_MODE[i],
            m.P_TRADER_CURRENT_MODE_TIME[i],
            m.P_TRADER_T1[i],
            m.P_TRADER_T2[i],
            m.P_TRADER_T3[i],
            m.P_TRADER_T4[i])

        # effective_mode = m.P_TRADER_CURRENT_MODE[i]
        # effective_time = m.P_TRADER_CURRENT_MODE_TIME[i]

        # Unit is synchronising - output = 0
        if (effective_mode == '0') or (effective_mode == '1'):
            return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i]
                    == 0 + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i])

        # Unit ramping to min loading - energy output fixed to profile
        elif effective_mode == '2':
            slope = m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T2[i]
            startup_profile = slope * effective_time
            return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i]
                    == startup_profile + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i])

        # Output lower bounded by MinLoadingMW
        elif effective_mode == '3':
            return (m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i]
                    >= m.P_TRADER_MIN_LOADING_MW[i])

        # Output still lower bounded by inflexibility profile
        elif (effective_mode == '4') and (effective_time < m.P_TRADER_T4[i]):
            slope = - m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T4[i]
            max_output = (slope * effective_time) + m.P_TRADER_MIN_LOADING_MW[i]

            return m.V_TRADER_TOTAL_OFFER[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i] >= max_output

        # Unit operating normally - output not constrained by inflexibility profile
        else:
            return pyo.Constraint.Skip

    # Profile constraint
    m.C_TRADER_INFLEXIBILITY_PROFILE = pyo.Constraint(m.S_TRADER_FAST_START, rule=profile_constraint_rule)

    return m


def define_tie_breaking_constraints(m):
    """Define tie-breaking constraints"""

    def generator_tie_breaking_rule(m, i, j, k, q, r, s):
        """Generator tie-breaking rule for price-tied energy offers"""

        if (m.P_TRADER_QUANTITY_BAND[i, j, k] == 0) or (m.P_TRADER_QUANTITY_BAND[q, r, s] == 0):
            return pyo.Constraint.Skip

        return ((m.V_TRADER_OFFER[i, j, k] / m.P_TRADER_QUANTITY_BAND[i, j, k])
                - (m.V_TRADER_OFFER[q, r, s] / m.P_TRADER_QUANTITY_BAND[q, r, s])
                == m.V_TRADER_SLACK_1[i, j, k, q, r, s] - m.V_TRADER_SLACK_2[i, j, k, q, r, s])

    # Generator tie-breaking rule
    m.C_TRADER_TIE_BREAK = pyo.Constraint(m.S_TRADER_PRICE_TIED, rule=generator_tie_breaking_rule)

    return m


def define_constraints(m, case_data):
    """Define model constraints"""

    t0 = time.time()

    # Ensure offer bands aren't violated
    print('Starting to define constraints:', time.time() - t0)
    m = define_offer_constraints(m)
    print('Defined offer constraints:', time.time() - t0)

    # Construct generic constraints and link variables to those found in objective
    m = define_generic_constraints(m)
    print('Defined generic constraints:', time.time() - t0)

    # Construct unit constraints (e.g. ramp rate constraints)
    m = define_unit_constraints(m)
    print('Defined unit constraints:', time.time() - t0)

    # Construct region power balance constraints
    m = define_region_constraints(m)
    print('Defined region constraints:', time.time() - t0)

    # Construct interconnector constraints
    m = define_interconnector_constraints(m)
    print('Defined interconnector constraints:', time.time() - t0)

    # MNSP constraints
    m = define_mnsp_constraints(m)
    print('Defined MNSP constraints:', time.time() - t0)

    # Construct FCAS constraints
    m = define_fcas_constraints(m, case_data)
    print('Defined FCAS constraints:', time.time() - t0)

    # SOS2 interconnector loss model constraints
    m = define_loss_model_constraints(m)
    print('Defined loss model constraints:', time.time() - t0)

    # Fast start unit inflexibility profile
    m = define_fast_start_unit_inflexibility_constraints(m)
    print('Defined fast start unit inflexibility constraints:', time.time() - t0)

    # Tie-breaking constraints
    m = define_tie_breaking_constraints(m)
    print('Defined tie-breaking constraints:', time.time() - t0)

    return m


def define_objective(m):
    """Define model objective"""

    # Total cost for energy and ancillary services
    m.OBJECTIVE = pyo.Objective(expr=sum(m.E_TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
                                     + sum(m.E_MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
                                     + m.E_CV_TOTAL_PENALTY
                                     + m.E_TRADER_TIE_BREAK_COST
                                ,
                                sense=pyo.minimize)

    return m


def construct_model(data, case_data):
    """Create model object"""

    # Initialise model
    t0 = time.time()
    m = pyo.ConcreteModel()

    # Define model components
    m = define_sets(m, data)
    m = define_parameters(m, data)
    m = define_variables(m)
    m = define_expressions(m, data)
    m = define_constraints(m, case_data)
    m = define_objective(m)

    # Add component allowing dual variables to be imported
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    print('Constructed model in:', time.time() - t0)

    return m


def fix_interconnector_flow_solution(m, data, intervention):
    """Fix interconnector solution to observed values"""

    for i in m.S_GC_INTERCONNECTOR_VARS:
        observed_flow = utils.lookup.get_interconnector_solution_attribute(data, i, '@Flow', float, intervention)
        m.V_GC_INTERCONNECTOR[i].fix(observed_flow)

    return m


def unfix_interconnector_flow_solution(m):
    """Fix interconnector solution to observed values"""

    for i in m.S_GC_INTERCONNECTOR_VARS:
        m.V_GC_INTERCONNECTOR[i].unfix()

    return m


def fix_trader_solution(m, data, intervention, offers=None):
    """Fix FCAS solution"""

    # Map between NEMDE output keys and keys used in solution dictionary
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Use all offers by default
    if offers is None:
        trader_offers = ['ENOF', 'LDOF', 'R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']
    else:
        trader_offers = offers

    for i, j in m.S_TRADER_OFFERS:
        if j in trader_offers:
            target = utils.lookup.get_trader_solution_attribute(data, i, key_map[j], float, intervention)
            m.V_TRADER_TOTAL_OFFER[(i, j)].fix(target)

    return m


def fix_binary_variables(m):
    """Fix all binary variables"""

    for i in m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS:
        m.V_LOSS_Y[i].fix()

    return m


def solve_model(m):
    """Solve model"""

    # Setup solver
    solver_options = {
        # 'mip tolerances mipgap': 1e-50,
        # 'mip tolerances absmipgap': 1,
        'mip tolerances mipgap': 1e-20,
    }

    # solver_options = {
    #     'MIPGapAbs': 1e-20,
    #     'MIPGap': 1e-20,
    # }

    # solver_options = {}
    opt = pyo.SolverFactory('cplex', solver_io='mps')

    # Solve model
    t0 = time.time()

    print('Starting MILP solve:', time.time() - t0)
    solve_status_1 = opt.solve(m, tee=True, options=solver_options, keepfiles=False)
    print('Finished MILP solve:', time.time() - t0)
    print('Objective value - 1:', m.OBJECTIVE.expr())

    # # Fix binary variables
    # m = fix_binary_variables(m)
    #
    # # Unfix interconnector solution
    # # m = unfix_interconnector_flow_solution(m)
    #
    # solve_status_2 = opt.solve(m, tee=True, options=solver_options, keepfiles=False)
    # print('Finished MILP solve:', time.time() - t0)
    # print('Objective value - 2:', m.OBJECTIVE.expr())

    return m


def get_case_ids(year, month, n, seed=10):
    """Get random collection of dispatch interval case IDs"""

    # Get days in specified month
    _, days_in_month = calendar.monthrange(year, month)

    # Seed random number generator for reproducable results
    np.random.seed(seed)

    # Population of dispatch intervals for a given month
    population = [f'{year}{month:02}{i:02}{j:03}' for i in range(1, days_in_month + 1) for j in range(1, 289)]

    # Shuffle list to randomise sample (should be reproducible though because seed is set)
    np.random.shuffle(population)

    # Return Sample of case IDs
    return population[:n]


def check_model(data_dir, mode, case_ids=None):
    """Run model for a set of dispatch intervals - compare model output with observed output"""

    # Initialise database tables where solution will be stored
    utils.database.initialise_tables(os.environ['MYSQL_DATABASE'])

    # Start a new run
    if mode == 'new':
        assert case_ids is not None, f'Must supply case IDs when starting a new run: case_ids={case_ids}'

        # ID for new case is the timestamp (in seconds from epoch) when case was created
        run_id = int(time.time())

        # Initialise the sample as the provided set of case IDs
        sample = case_ids

        # Record start of new run in database
        run_info_entry = {'run_id': run_id, 'parameters': json.dumps({'case_ids': case_ids})}

        # Post to database
        utils.database.post_entry(os.environ['MYSQL_DATABASE'], 'run_info', run_info_entry)

    # Continue the previous run - solve for remaining case IDs
    elif mode == 'continue':
        run_id, sample = utils.database.get_remaining_case_ids(os.environ['MYSQL_DATABASE'])

    # Unhandled case
    else:
        raise Exception('Unexpected mode:', mode)

    # Run model for each case ID
    for i, case_id in enumerate(sample):
        # Extract day and interval from string
        year, month, day, interval = int(case_id[:4]), int(case_id[4:6]), int(case_id[6:8]), int(case_id[8:11])

        print(f'{case_id} {i + 1}/{len(sample)}')

        # Case data in json format
        data_json = utils.loaders.load_dispatch_interval_json(data_dir, year, month, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Get intervention status - only want physical run
        intervention = utils.lookup.get_intervention_status(case_data, 'physical')

        # Preprocessed case data
        processed_data = utils.data.parse_case_data_json(data_json, intervention)

        # Construct model
        m = construct_model(processed_data, case_data)

        # Solve model
        m = solve_model(m)

        # Extract model solution
        solution = utils.solution.get_model_solution(m)

        # Compare model solution with output from NEMDE
        comparison = utils.solution.get_model_comparison(case_data, solution)

        # Print solution report
        utils.solution.print_solution_report(comparison)

        # Prepare entry for database
        results_entry = {
            'run_id': run_id,
            'run_time': int(time.time()),
            'case_id': case_id,
            'results': simplejson.dumps(comparison, ignore_nan=True)
        }

        # Save case solution to database
        utils.database.post_entry(os.environ['MYSQL_DATABASE'], 'results', results_entry)


def save_case_json(data_dir, output_dir, year, month, day, interval, overwrite=True):
    """Save casefile in JSON format for inspection"""

    # Case data in json format
    data_json = utils.loaders.load_dispatch_interval_json(data_dir, year, month, day, interval)

    # Get NEMDE model data as a Python dictionary
    data = json.loads(data_json)

    # Filename for JSON data
    filename = f'case-{year}-{month:02}-{day:02}-{interval:03}.json'

    if filename in os.listdir(output_dir) and not overwrite:
        pass
    else:
        with open(os.path.join(output_dir, filename), 'w') as f:
            json.dump(data, f)


def get_positive_variables(obj):
    """Get all variables that are > 0"""

    return [(i, obj[i].value) for i in obj.keys() if obj[i].value > 0]


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # Root output directory
    output_directory = os.path.join(os.path.dirname(__file__), 'output')

    # Directory containing model data, and directory where temporary files are stored
    sample_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'data')
    tmp_directory = os.path.join(os.path.dirname(__file__), 'tmp')

    # Define the dispatch interval to investigate
    # c_ids = ['20191001006', '20191001016', '20191001074', '20191001018', '2019103109300']
    di_year, di_month, di_day, di_interval = 2019, 10, 1, 18
    di_case_id = f'{di_year}{di_month:02}{di_day:02}{di_interval:03}'

    # Case data in json format
    case_data_json = utils.loaders.load_dispatch_interval_json(data_directory, di_year, di_month, di_day, di_interval)
    save_case_json(data_directory, os.path.join(output_directory, 'cases'), di_year, di_month, di_day, di_interval,
                   overwrite=False)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Extract data from case file into a standardised format
    intervention_status = utils.lookup.get_intervention_status(cdata, 'physical')
    model_data = utils.transforms.original.data(cdata, intervention_status)

    # Construct and solve model
    model = construct_model(model_data, cdata)
    model = solve_model(model)

    # Extract model solution
    model_solution = utils.solution.get_model_solution(model)
    solution_comparison = utils.solution.get_model_comparison(cdata, model_solution)

    # Format solution - split into traders, interconnectors, regions, period
    formatted_solution = utils.solution.inspect_solution(solution_comparison)

    # Add additional FCAS data to check FCAS availability
    # df_fcas_solution = utils.validate.check_fcas_solution(cdata, model_solution, intervention_status, di_case_id,
    #                                                       sample_directory, tmp_directory)

    # Plot trader solution
    utils.solution.plot_trader_solution(cdata, model_solution, intervention_status)

    # Print solution report
    utils.solution.print_solution_report(solution_comparison)

    # Check constraint violation
    utils.validate.check_constraint_violation(model)

    # Extract solution
    period_results = formatted_solution['period']
    regions_results = formatted_solution['regions']
    traders_results = formatted_solution['traders']
    interconnectors_results = formatted_solution['interconnectors']

    # Check model for a random selection of dispatch intervals
    # case_id_sample = get_case_ids(2019, 10, n=1000)
    # check_model(data_directory, mode='new', case_ids=case_id_sample)
    # check_model(data_directory, mode='continue')

    # Extract latest run results from database
    # db_results = utils.solution.get_latest_run_results(os.environ['MYSQL_DATABASE'])

    # Find cases where MNSP flow inverts
    # utils.analysis.find_mnsp_flow_inversion(data_directory, output_directory, 2019, 10)
