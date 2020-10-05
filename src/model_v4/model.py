"""Model used to construct and solve NEMDE approximation"""

import os
import json
import time
import pickle
import zipfile

import numpy as np
import pandas as pd
import pyomo.environ as pyo

import utils.fcas
import utils.data
import utils.lookup
import utils.loaders
import utils.solution
import utils.analysis


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

    # Price bands for traders (generators / loads)
    m.P_TRADER_PRICE_BAND = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS, initialize=data['P_TRADER_PRICE_BAND'])

    # Quantity bands for traders (generators / loads)
    m.P_TRADER_QUANTITY_BAND = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS, initialize=data['P_TRADER_QUANTITY_BAND'])

    # Max available output for given trader
    m.P_TRADER_MAX_AVAILABLE = pyo.Param(m.S_TRADER_OFFERS, initialize=data['P_TRADER_MAX_AVAILABLE'])

    # Initial MW output for generators / loads
    m.P_TRADER_INITIAL_MW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_INITIAL_MW'])

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

    # MNSP loss price
    m.P_MNSP_LOSS_PRICE = pyo.Param(initialize=data['P_MNSP_LOSS_PRICE'])

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

    # Value of lost load
    m.P_CVF_VOLL = pyo.Param(initialize=data['P_CVF_VOLL'])

    # Energy deficit price
    m.P_CVF_ENERGY_DEFICIT_PRICE = pyo.Param(initialize=data['P_CVF_ENERGY_DEFICIT_PRICE'])

    # Energy surplus price
    m.P_CVF_ENERGY_SURPLUS_PRICE = pyo.Param(initialize=data['P_CVF_ENERGY_SURPLUS_PRICE'])

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

    # Ancillary services profile price (assume for constraint ensure FCAS trapezium not violated)
    m.P_CVF_AS_PROFILE_PRICE = pyo.Param(initialize=data['P_CVF_AS_PROFILE_PRICE'])

    # Ancillary services max available price (assume for constraint ensure max available amount not exceeded)
    m.P_CVF_AS_MAX_AVAIL_PRICE = pyo.Param(initialize=data['P_CVF_AS_MAX_AVAIL_PRICE'])

    # Ancillary services enablement min price (assume for constraint ensure FCAS > enablement min if active)
    m.P_CVF_AS_ENABLEMENT_MIN_PRICE = pyo.Param(initialize=data['P_CVF_AS_ENABLEMENT_MIN_PRICE'])

    # Ancillary services enablement max price (assume for constraint ensure FCAS < enablement max if active)
    m.P_CVF_AS_ENABLEMENT_MAX_PRICE = pyo.Param(initialize=data['P_CVF_AS_ENABLEMENT_MAX_PRICE'])

    # Interconnector power flow violation price
    m.P_CVF_INTERCONNECTOR_PRICE = pyo.Param(initialize=data['P_CVF_INTERCONNECTOR_PRICE'])

    # Trader fast start inflexibility constraint violation price
    m.P_CVF_FAST_START_PRICE = pyo.Param(initialize=data['P_CVF_FAST_START_PRICE'])

    # Tie-break price
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

    # Generic constraint violation pyo.Variables
    m.V_CV = pyo.Var(m.S_GENERIC_CONSTRAINTS, within=pyo.NonNegativeReals)
    m.V_CV_LHS = pyo.Var(m.S_GENERIC_CONSTRAINTS, within=pyo.NonNegativeReals)
    m.V_CV_RHS = pyo.Var(m.S_GENERIC_CONSTRAINTS, within=pyo.NonNegativeReals)

    # Trader band offer < bid violation
    m.V_CV_TRADER_OFFER = pyo.Var(m.S_TRADER_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)

    # Trader total capacity < max available violation
    m.V_CV_TRADER_CAPACITY = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

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

    # Inflexibility profile violation
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE = pyo.Var(m.S_TRADER_FAST_START, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS = pyo.Var(m.S_TRADER_FAST_START, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS = pyo.Var(m.S_TRADER_FAST_START, within=pyo.NonNegativeReals)

    # Interconnector forward and reverse flow constraint violation
    m.V_CV_INTERCONNECTOR_FORWARD = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)
    m.V_CV_INTERCONNECTOR_REVERSE = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)

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

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j]

    # Penalty factor for generator FCAS joint ramping up constraint
    m.E_CV_TRADER_FCAS_JOINT_RAMPING_UP = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_ramping_up_rule)

    def trader_fcas_joint_ramping_down_rule(m, i, j):
        """Penalty for violating FCAS constraint - generator joint ramping down"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j]

    # Penalty factor for generator FCAS joint ramping up constraint
    m.E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_ramping_down_rule)

    def trader_fcas_joint_capacity_rhs_rule(m, i, j):
        """Joint capacity constraint RHS of trapezium"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j]

    # Constraint violation for joint capacity constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_capacity_rhs_rule)

    def trader_fcas_joint_capacity_lhs_rule(m, i, j):
        """Joint capacity constraint LHS of trapezium"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j]

    # Constraint violation for joint capacity constraint - LHS of trapezium
    m.E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_joint_capacity_lhs_rule)

    def trader_fcas_energy_regulating_rhs_rule(m, i, j):
        """Energy regulating FCAS constraint RHS of trapezium"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j]

    # Constraint violation for joint energy regulating FCAS constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS = pyo.Expression(m.S_TRADER_OFFERS,
                                                              rule=trader_fcas_energy_regulating_rhs_rule)

    def trader_fcas_energy_regulating_lhs_rule(m, i, j):
        """Energy regulating FCAS constraint LHS of trapezium"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j]

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

    # Sum of all constraint violation penalties
    m.E_CV_TOTAL_PENALTY = pyo.Expression(
        expr=sum(m.E_CV_GC_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
             + sum(m.E_CV_GC_LHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
             + sum(m.E_CV_GC_RHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
             + sum(m.E_CV_TRADER_OFFER_PENALTY[i, j, k] for i, j in m.S_TRADER_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_TRADER_CAPACITY_PENALTY[i] for i in m.S_TRADER_OFFERS)
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
             + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_MNSP_RAMP_UP_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_MNSP_RAMP_DOWN_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i] for i in m.S_INTERCONNECTORS)
             + sum(m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i] for i in m.S_INTERCONNECTORS)
    )

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

    # Region initial allocated losses
    m.E_REGION_INITIAL_ALLOCATED_LOSS = pyo.Expression(m.S_REGIONS, rule=region_initial_allocated_loss)

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

    # Region allocated loss at end of dispatch interval
    m.E_REGION_ALLOCATED_LOSS = pyo.Expression(m.S_REGIONS, rule=region_allocated_loss_rule)

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

    # Region initial allocated MNSP losses
    m.E_REGION_INITIAL_MNSP_LOSS = pyo.Expression(m.S_REGIONS, rule=region_initial_mnsp_loss)

    def region_mnsp_loss_rule(m, r):
        """
        Get estimate of MNSP loss allocated to given region

        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad) where load is varied at the connection
        point. Must compute the load the connection point for the MNSP - this will be positive or negative (i.e. generation)
        depending on the direction of flow over the interconnector.

        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to compute the effective load at the connection
        point in order to compute the loss. Note the loss may be positive or negative depending on the MLF and the effective
        load at the connection point.

        TODO: a check must be performed to ensure InitialMW and solution Flow are in same direction - need re-run
        otherwise
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Initial MW and solution flow
            # initial_mw = m.P_INTERCONNECTOR_INITIAL_MW[i]
            # flow = lookup.get_interconnector_solution_attribute(data, i, '@Flow', float, intervention)

            # TODO: if InitialMW and Flow are in different directions, then need to re-run model. not sure how abstract
            # this. For now assume InitialMW will suffice.
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

    # Region MNSP loss at end of dispatch interval
    m.E_REGION_MNSP_LOSS = pyo.Expression(m.S_REGIONS, rule=region_mnsp_loss_rule)

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

        # UIGF from semi-dispatchable plant
        if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '1':
            uigf = m.P_TRADER_UIGF[i]
        else:
            uigf = None

        # Terms used to determine effective enablement max
        terms = [enablement_min, agc_down_limit, uigf]

        return max([i for i in terms if i is not None])

    # Effective enablement min
    m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN = pyo.Expression(m.S_TRADER_OFFERS, rule=fcas_effective_enablement_min)

    return m


def define_tie_breaking_expressions(m):
    """Tie-breaking expressions"""

    # Tie break cost TODO: Note that tie-break price of 1e-5 gives better results than 1e-6.
    m.E_TRADER_TIE_BREAK_COST = pyo.Expression(
        # expr=sum(m.P_TIE_BREAK_PRICE * (m.V_TRADER_SLACK_1[i] + m.V_TRADER_SLACK_2[i]) for i in m.S_TRADER_PRICE_TIED)
        expr=sum(1e-4 * (m.V_TRADER_SLACK_1[i] + m.V_TRADER_SLACK_2[i]) for i in m.S_TRADER_PRICE_TIED)
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
            return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_UIGF[i] + m.V_CV_TRADER_CAPACITY[i, j]
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

        # Initial MW
        initial_mw = m.P_TRADER_INITIAL_MW[i]

        return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw <= (ramp_limit / 12) + m.V_CV_TRADER_RAMP_UP[i]

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
        return (m.E_REGION_DISPATCHED_GENERATION[r]
                == m.E_REGION_FIXED_DEMAND[r]
                + m.E_REGION_DISPATCHED_LOAD[r]
                + m.E_REGION_NET_EXPORT[r])

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
                    <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j])

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
    solver_options = {'mip tolerances mipgap': 1e-9}
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


def check_region_fixed_demand(data, m, region_id, intervention):
    """Check fixed demand calculation"""

    # Container for output
    calculated = m.E_REGION_FIXED_DEMAND[region_id].expr()
    observed = utils.lookup.get_region_solution_attribute(data, region_id, '@FixedDemand', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_net_export(data, m, region_id, intervention):
    """Check net export calculation"""

    # Container for output
    calculated = m.E_REGION_NET_EXPORT[region_id].expr()
    observed = utils.lookup.get_region_solution_attribute(data, region_id, '@NetExport', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_dispatched_generation(data, m, region_id, intervention):
    """Check region dispatched generation"""

    # Container for output
    calculated = m.E_REGION_DISPATCHED_GENERATION[region_id].expr()
    observed = utils.lookup.get_region_solution_attribute(data, region_id, '@DispatchedGeneration', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_dispatched_load(data, m, region_id, intervention):
    """Check region dispatched load"""

    # Container for output
    calculated = m.E_REGION_DISPATCHED_LOAD[region_id].expr()
    observed = utils.lookup.get_region_solution_attribute(data, region_id, '@DispatchedLoad', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_interconnector_flow(data, m, interconnector_id, intervention):
    """Check interconnector flow calculation"""

    # Container for output
    calculated = m.V_GC_INTERCONNECTOR[interconnector_id].value
    observed = utils.lookup.get_interconnector_solution_attribute(data, interconnector_id, '@Flow', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'interconnector_id': interconnector_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_interconnector_loss(data, m, interconnector_id, intervention):
    """Check interconnector loss calculation"""

    # Container for output
    calculated = m.V_LOSS[interconnector_id].value
    observed = utils.lookup.get_interconnector_solution_attribute(data, interconnector_id, '@Losses', float,
                                                                  intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'interconnector_id': interconnector_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_trader_output(data, m, trader_id, trade_type, intervention):
    """Check trader output"""

    # Calculated and observed values
    calculated = m.V_TRADER_TOTAL_OFFER[trader_id, trade_type].value

    # Map between NEMDE output keys and keys used in solution dictionary
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Observed dispatch
    observed = utils.lookup.get_trader_solution_attribute(data, trader_id, key_map[trade_type], float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'trader_id': trader_id,
        'trade_type': trade_type,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_region_price(data, m, region_id, intervention):
    """Check region energy price (exclude FCAS for now)"""

    # Extract energy price - use default value of -9999 if none available
    try:
        calculated = m.dual[m.C_POWER_BALANCE[region_id]]
    except KeyError:
        calculated = -9999

    # Observed energy price
    observed = utils.lookup.get_region_solution_attribute(data, region_id, '@EnergyPrice', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'region_id': region_id,
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def check_objective_value(data, m, intervention):
    """Check objective value calculation"""

    # Container for output
    calculated = m.OBJECTIVE.expr()
    observed = utils.lookup.get_period_solution_attribute(data, '@TotalObjective', float, intervention)

    out = {
        'model': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed),
        'intervention_flag': intervention,
        'case_id': utils.lookup.get_case_attribute(data, '@CaseID', str),
        'case_intervention': utils.lookup.get_case_attribute(data, '@Intervention', str),
    }

    return out


def get_solution_report(data, m, intervention):
    """Check solution"""

    # Columns to retain in DataFrame
    cols = ['abs_difference', 'difference', 'model', 'observed']

    fixed_demand = []
    for i in m.S_REGIONS:
        fixed_demand.append(check_region_fixed_demand(data, m, i, intervention))
    print('Region fixed demand')
    df_fixed_demand = pd.DataFrame(fixed_demand).set_index('region_id')[cols]
    print(df_fixed_demand)

    net_export = []
    for i in m.S_REGIONS:
        net_export.append(check_region_net_export(data, m, i, intervention))
    print('Region net export')
    df_net_export = pd.DataFrame(net_export).set_index('region_id')[cols]
    print(df_net_export)

    dispatched_generation = []
    for i in m.S_REGIONS:
        dispatched_generation.append(check_region_dispatched_generation(data, m, i, intervention))
    print('Region dispatched generation')
    df_dispatched_generation = pd.DataFrame(dispatched_generation).set_index('region_id')[cols]
    print(df_dispatched_generation)

    dispatched_load = []
    for i in m.S_REGIONS:
        dispatched_load.append(check_region_dispatched_load(data, m, i, intervention))
    print('Region dispatched load')
    df_dispatched_load = pd.DataFrame(dispatched_load).set_index('region_id')[cols]
    print(df_dispatched_load)

    energy_price = []
    for i in m.S_REGIONS:
        energy_price.append(check_region_price(data, m, i, intervention))
    print('Region energy price')
    df_energy_price = pd.DataFrame(energy_price).set_index('region_id')[cols]
    print(df_energy_price)

    interconnector_flow = []
    for i in m.S_INTERCONNECTORS:
        interconnector_flow.append(check_interconnector_flow(data, m, i, intervention))
    print('Interconnector flow')
    df_interconnector_flow = pd.DataFrame(interconnector_flow).set_index('interconnector_id')[cols]
    print(df_interconnector_flow)

    interconnector_losses = []
    for i in m.S_INTERCONNECTORS:
        interconnector_losses.append(check_interconnector_loss(data, m, i, intervention))
    print('Interconnector losses')
    df_interconnector_losses = pd.DataFrame(interconnector_losses).set_index('interconnector_id')[cols]
    print(df_interconnector_losses)

    trader_output = []
    for i, j in m.S_TRADER_OFFERS:
        trader_output.append(check_trader_output(data, m, i, j, intervention))
    print('Trader output')
    df_trader_output = (pd.DataFrame(trader_output).set_index(['trader_id', 'trade_type'])[cols]
                        .sort_values(by='abs_difference', ascending=False))
    print(df_trader_output.head())

    print('Objective value')
    print(pd.Series(check_objective_value(data, m, intervention)).T)

    # Summary of model output
    output = {
        'fixed_demand': fixed_demand,
        'net_export': net_export,
        'energy_price': energy_price,
        'dispatched_generation': dispatched_generation,
        'dispatched_load': dispatched_load,
        'interconnector_flow': interconnector_flow,
        'interconnector_losses': interconnector_losses,
        'trader_output': trader_output,
    }

    return output


def get_dispatch_interval_sample(n, seed=10):
    """Get sample of dispatch intervals"""

    # Seed random number generator to get reproducable results
    np.random.seed(seed)

    # Population of dispatch intervals for a given month
    population = [(i, j) for i in range(1, 30) for j in range(1, 289)]
    population_map = {i: j for i, j in enumerate(population)}

    # Random sample of dispatch intervals
    sample_keys = np.random.choice(list(population_map.keys()), n, replace=False)
    sample = [population_map[i] for i in sample_keys]

    return sample


def check_region_fixed_demand_calculation_sample(data_dir, intervention, n=5):
    """Check region fixed demand calculations for a random sample of dispatch intervals"""

    # Random sample of dispatch intervals (with seeded random number generator for reproducible results)
    sample = get_dispatch_interval_sample(n, seed=10)

    # Container for model output
    out = {}

    # Placeholder for max absolute difference observed
    max_abs_difference = 0
    max_abs_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'({day}, {interval}) {i + 1}/{len(sample)}')

        # Case data in json format
        data_json = utils.loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Preprocessed case data
        processed_data = utils.data.parse_case_data_json(data_json)

        # Construct model
        m = construct_model(processed_data, case_data)

        # All regions
        regions = utils.lookup.get_region_index(case_data)

        for r in regions:
            # Check difference between calculated region fixed demand and fixed demand from NEMDE solution
            fixed_demand_info = check_region_fixed_demand(case_data, m, r, intervention)

            # Add to dictionary
            out[(day, interval, r)] = fixed_demand_info

            if fixed_demand_info['abs_difference'] > max_abs_difference:
                max_abs_difference = fixed_demand_info['abs_difference']
                max_abs_difference_interval = (day, interval, r)

        # Periodically print max absolute difference observed
        if (i + 1) % 10 == 0:
            print('Max absolute difference:', max_abs_difference_interval, max_abs_difference)

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    return df


def check_generic_constraint_rhs(data, m, constraint_id, intervention):
    """Check generic constraint RHS"""

    # Container for output
    calculated = m.P_GC_RHS[constraint_id]
    observed = utils.lookup.get_generic_constraint_solution_attribute(data, constraint_id, '@RHS', float, intervention)

    out = {
        'calculated': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed)
    }

    return out


def check_generic_constraint_rhs_sample(data_dir, intervention, n=5):
    """Check generic constraint RHS for a random sample of dispatch intervals"""

    # Random sample of dispatch intervals (with seeded random number generator for reproducible results)
    sample = get_dispatch_interval_sample(n, seed=10)

    # Container for model output
    out = {}

    # Placeholder for max absolute difference observed
    max_abs_difference = 0
    max_abs_difference_interval = None

    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'({day}, {interval}) {i + 1}/{len(sample)}')

        # Case data in json format
        data_json = utils.loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

        # Get NEMDE model data as a Python dictionary
        case_data = json.loads(data_json)

        # Preprocessed case data
        processed_data = utils.data.parse_case_data_json(data_json)

        # Construct model
        m = construct_model(processed_data, case_data)

        # All constraints
        constraints = utils.lookup.get_generic_constraint_index(case_data)

        for j in constraints:
            # Check difference
            info = check_generic_constraint_rhs(case_data, m, j, intervention)

            # Add to dictionary
            out[(j, day, interval)] = info

            if info['abs_difference'] > max_abs_difference:
                max_abs_difference = info['abs_difference']
                max_abs_difference_interval = (j, day, interval)

        # Periodically print max absolute difference observed
        if (i + 1) % 10 == 0:
            print('Max absolute difference:', max_abs_difference_interval, max_abs_difference)

    # Convert to DataFrame
    df = pd.DataFrame(out).T
    df = df.sort_values(by='abs_difference', ascending=False)

    return df


def check_model(data_dir, n=5):
    """Run model for a random selection of dispatch intervals - compare model output with observed output"""

    # Random sample of dispatch intervals (with seeded random number generator for reproducible results)
    sample = get_dispatch_interval_sample(n, seed=10)

    # Container for results comparing model output with observed values
    output = []
    # Compute fixed demand for each interval
    for i, (day, interval) in enumerate(sample):
        print(f'({day}, {interval}) {i + 1}/{len(sample)}')

        # Case data in json format
        data_json = utils.loaders.load_dispatch_interval_json(data_dir, 2019, 10, day, interval)

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

        # Append solution report to results container
        output.append(get_solution_report(case_data, m, intervention))

    def extract_values(results, key, sort_key):
        """Extract data and convert to DataFrame"""
        return pd.DataFrame([s for r in results for s in r[key]]).sort_values(by=sort_key, ascending=False)

    # Summary of results
    summary = {
        'fixed_demand': extract_values(output, 'fixed_demand', 'abs_difference'),
        'net_export': extract_values(output, 'net_export', 'abs_difference'),
        'energy_price': extract_values(output, 'energy_price', 'abs_difference'),
        'dispatched_generation': extract_values(output, 'dispatched_generation', 'abs_difference'),
        'dispatched_load': extract_values(output, 'dispatched_load', 'abs_difference'),
        'interconnector_flow': extract_values(output, 'interconnector_flow', 'abs_difference'),
        'interconnector_losses': extract_values(output, 'interconnector_losses', 'abs_difference'),
        'trader_output': extract_values(output, 'trader_output', 'abs_difference'),
    }

    # Print summary
    for k, v in summary.items():
        print(k)
        print(v.head())

    # Save results
    with open(os.path.join(os.path.dirname(__file__), 'output', 'summary.json'), 'w') as f:
        json.dump(output, f)

    with open(os.path.join(os.path.dirname(__file__), 'output', 'summary.pickle'), 'wb') as f:
        pickle.dump(summary, f)

    return summary


def save_case_json(data_dir, year, month, day, interval):
    """Save casefile in JSON format for inspection"""

    # Case data in json format
    data_json = utils.loaders.load_dispatch_interval_json(data_dir, year, month, day, interval)

    # Get NEMDE model data as a Python dictionary
    data = json.loads(data_json)

    with open(f'example-{year}-{month:02}-{day:02}-{interval:03}.json', 'w') as f:
        json.dump(data, f)


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


def check_fcas_solution(case_id, sample_dir, tmp_dir, use_cache=True):
    """Check FCAS solution and compare availability with observed availability"""

    # Load observed FCAS data
    if use_cache:
        observed_fcas = pd.read_pickle(os.path.join(tmp_dir, 'fcas_availability.pickle'))
    else:
        observed_fcas = get_observed_fcas_availability(sample_dir, tmp_dir)

    # Column map
    column_map = {
        'RAISEREGAVAILABILITY': 'R5RE',
        'RAISE6SECACTUALAVAILABILITY': 'R6SE',
        'RAISE60SECACTUALAVAILABILITY': 'R60S',
        'RAISE5MINACTUALAVAILABILITY': 'R5MI',
        'LOWERREGACTUALAVAILABILITY': 'L5RE',
        'LOWER6SECACTUALAVAILABILITY': 'L6SE',
        'LOWER60SECACTUALAVAILABILITY': 'L60S',
        'LOWER5MINACTUALAVAILABILITY': 'L5MI',
    }

    # Augment DataFrame
    observed_fcas_formatted = (observed_fcas.loc[(case_id, slice(None), intervention_status), column_map.keys()]
                               .rename(columns=column_map).stack().to_frame('fcas_availability').droplevel([0, 2])
                               .rename_axis(['trader_id', 'trade_type']))

    # Combine trader solution with observed FCAS availability
    df_c = df_trader_solution.join(observed_fcas_formatted, how='left')

    # Difference between observed FCAS and available FCAS
    df_c['fcas_availability_difference'] = df_c['model'] - df_c['fcas_availability']
    df_c['fcas_availability_abs_difference'] = df_c['fcas_availability_difference'].abs()

    # Sort to largest difference is first - if difference is positive then model > actual available --> problem
    df_c = df_c.sort_values(by='fcas_availability_difference', ascending=False)

    return df_c


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    sample_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'data')
    tmp_directory = os.path.join(os.path.dirname(__file__), 'tmp')

    # Case data in json format
    di_day, di_interval = 25, 254
    case_data_json = utils.loaders.load_dispatch_interval_json(data_directory, 2019, 10, di_day, di_interval)
    save_case_json(data_directory, 2019, 10, di_day, di_interval)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Preprocessed case data
    intervention_status = utils.lookup.get_intervention_status(cdata, 'physical')
    # intervention_status = '0'
    model_data = utils.data.parse_case_data_json(case_data_json, intervention_status)

    # Construct model
    model = construct_model(model_data, cdata)

    # Perform model checks
    # df_fixed_demand_check = check_region_fixed_demand_calculation_sample(data_directory, n=1000)
    # df_rhs = check_generic_constraint_rhs_sample(data_directory, n=1000)

    # Fix variables (debugging)
    # model = fix_interconnector_flow_solution(model, cdata, intervention_status)
    # model = fix_trader_solution(model, cdata, intervention_status, ['ENOF', 'LDOF'])
    # model = fix_trader_solution(model, cdata, intervention_status, ['R5RE', 'L5RE'])

    # Solve model
    model = solve_model(model)

    # Extract solution
    solution = utils.solution.get_model_solution(model)

    # Difference
    trader_solution, df_trader_solution = utils.analysis.check_trader_solution(cdata, solution, intervention_status)
    di_case_id = f'201910{di_day:02}{di_interval:03}'
    df_trader_fcas_solution = check_fcas_solution(di_case_id, sample_directory, tmp_directory)
    utils.analysis.plot_trader_solution_difference(cdata, solution, intervention_status)

    # Get solution report
    get_solution_report(cdata, model, intervention_status)

    # # Check model for a random selection of dispatch intervals
    # model_output = check_model(data_directory, n=20)
    #
    # df_fixed_demand_output = model_output['fixed_demand']
    # df_net_export_output = model_output['net_export']
    # df_energy_price_output = model_output['energy_price']
    # df_dispatched_generation_output = model_output['dispatched_generation']
    # df_dispatched_load_output = model_output['dispatched_load']
    # df_interconnector_flow_output = model_output['interconnector_flow']
    # df_interconnector_losses_output = model_output['interconnector_losses']
    # df_trader_output_output = model_output['trader_output']
