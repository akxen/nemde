"""Model used to construct and solve NEMDE approximation"""

import os
import json
import time

import numpy as np
import pandas as pd
import pyomo.environ as pyo

import utils.data
import utils.lookup
import utils.loaders


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

    # Ramp rate constraint violation pyo.Variables
    m.V_CV_TRADER_RAMP_UP = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_RAMP_DOWN = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)

    # FCAS trapezium violation pyo.Variables
    m.V_CV_TRADER_FCAS_TRAPEZIUM = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_AS_PROFILE_1 = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_AS_PROFILE_2 = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_AS_PROFILE_3 = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

    # FCAS joint ramping constraint violation pyo.Variables
    m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_GENERATOR_LHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_GENERATOR_RHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_GENERATOR_LHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_GENERATOR_RHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_RHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_LHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_LHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_RHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)

    # FCAS joint ramping constraint violation variables - loads
    m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_LOAD_LHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_LOAD_RHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_LOAD_LHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_LOAD_RHS = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_LHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_RHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_RHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_LHS = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)

    # FCAS joint capacity constraint violation pyo.Variables
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

    # Interconnector forward and reverse flow constraint violation
    m.V_CV_INTERCONNECTOR_FORWARD = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)
    m.V_CV_INTERCONNECTOR_REVERSE = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)

    # Loss model breakpoints and intervals
    m.V_LOSS = pyo.Var(m.S_INTERCONNECTORS)
    m.V_LOSS_LAMBDA = pyo.Var(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, within=pyo.NonNegativeReals)
    m.V_LOSS_Y = pyo.Var(m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS, within=pyo.Binary)

    # Flow between region and interconnector connection points
    m.V_FLOW_FROM_CP = pyo.Var(m.S_INTERCONNECTORS)
    m.V_FLOW_TO_CP = pyo.Var(m.S_INTERCONNECTORS)

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

    def trader_fcas_trapezium_penalty_rule(m, i, j):
        """Penalty for violating FCAS trapezium bounds"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_TRAPEZIUM[i, j]

    # FCAS trapezium violation penalty
    m.E_CV_TRADER_FCAS_TRAPEZIUM_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_trapezium_penalty_rule)

    def trader_total_trapezium_penalty_rule(m, i, j):
        """Total penalty for violating FCAS trapezium bounds"""

        return m.P_CVF_AS_PROFILE_PRICE * (m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j]
                                           + m.V_CV_TRADER_FCAS_AS_PROFILE_2[i, j]
                                           + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j])

    # FCAS trapezium penalty
    m.E_CV_TRADER_TOTAL_TRAPEZIUM_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_total_trapezium_penalty_rule)

    def trader_joint_ramping_raise_generator_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR[i]

    # FCAS joint ramping constraint raise violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_RAISE_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_joint_ramping_raise_generator_penalty_rule)

    def trader_joint_ramping_lower_generator_penalty_rule(m, i):
        """Penalty for FCAS joint ramping constraint down violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR[i]

    # FCAS joint ramping constraint lower violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_LOWER_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_joint_ramping_lower_generator_penalty_rule)

    def trader_joint_capacity_raise_generator_penalty_rhs_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint raise violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_GENERATOR_RHS[i, j]

    # FCAS joint capacity constraint raise violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_RAISE_GENERATOR_RHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_raise_generator_penalty_rhs_rule)

    def trader_joint_capacity_raise_generator_penalty_lhs_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint raise violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_GENERATOR_LHS[i, j]

    # FCAS joint capacity constraint raise violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_RAISE_GENERATOR_LHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_raise_generator_penalty_lhs_rule)

    def trader_joint_capacity_lower_generator_penalty_rhs_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint lower violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_GENERATOR_RHS[i, j]

    # FCAS joint capacity constraint lower violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_LOWER_GENERATOR_RHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_lower_generator_penalty_rhs_rule)

    def trader_joint_capacity_lower_generator_penalty_lhs_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint lower violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_GENERATOR_LHS[i, j]

    # FCAS joint capacity constraint lower violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_LOWER_GENERATOR_LHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_lower_generator_penalty_lhs_rule)

    def trader_fcas_energy_regulating_raise_generator_rhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_RHS[i]

    # FCAS joint capacity constraint raise violation penalty - upper slope
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_RHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_raise_generator_rhs_penalty_rule)

    def trader_fcas_energy_regulating_raise_generator_lhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_LHS[i]

    # FCAS joint capacity constraint raise violation penalty - lower slope
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_LHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_raise_generator_lhs_penalty_rule)

    def trader_fcas_energy_regulating_lower_generator_lhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint down violation"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_LHS[i]

    # FCAS joint capacity constraint lower violation penalty - lower slope
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_LHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_lower_generator_lhs_penalty_rule)

    def trader_fcas_energy_regulating_lower_generator_rhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint down violation"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_RHS[i]

    # FCAS joint capacity constraint lower violation penalty - upper slope
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_RHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_lower_generator_rhs_penalty_rule)

    def trader_joint_ramping_raise_load_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD[i]

    # FCAS joint ramping constraint raise violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_RAISE_LOAD_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_joint_ramping_raise_load_penalty_rule)

    def trader_joint_ramping_lower_load_penalty_rule(m, i):
        """Penalty for FCAS joint ramping constraint down violation"""

        # TODO: check if this is correct constraint violation penalty
        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD[i]

    # FCAS joint ramping constraint lower violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_LOWER_LOAD_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_joint_ramping_lower_load_penalty_rule)

    def trader_joint_capacity_raise_load_lhs_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint raise violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_LOAD_LHS[i, j]

    # FCAS joint capacity constraint raise violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_RAISE_LOAD_LHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_raise_load_lhs_penalty_rule)

    def trader_joint_capacity_raise_load_rhs_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint raise violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_LOAD_RHS[i, j]

    # FCAS joint capacity constraint raise violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_RAISE_LOAD_RHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_raise_load_rhs_penalty_rule)

    def trader_joint_capacity_lower_load_lhs_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint lower violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_LOAD_LHS[i, j]

    # FCAS joint capacity constraint lower violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_LOWER_LOAD_LHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_lower_load_lhs_penalty_rule)

    def trader_joint_capacity_lower_load_rhs_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint lower violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_LOAD_RHS[i, j]

    # FCAS joint capacity constraint lower violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_LOWER_LOAD_RHS_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_lower_load_rhs_penalty_rule)

    def trader_fcas_energy_regulating_raise_load_lhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_LHS[i]

    # FCAS joint capacity constraint raise violation penalty - lower slope
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_LHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_raise_load_lhs_penalty_rule)

    def trader_fcas_energy_regulating_raise_load_rhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_RHS[i]

    # FCAS joint capacity constraint raise violation penalty - upper slope
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_RHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_raise_load_rhs_penalty_rule)

    def trader_fcas_energy_regulating_lower_load_rhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_RHS[i]

    # FCAS joint capacity constraint raise violation penalty
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_RHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_lower_load_rhs_penalty_rule)

    def trader_fcas_energy_regulating_lower_load_lhs_penalty_rule(m, i):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_LHS[i]

    # FCAS joint capacity constraint raise violation penalty
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_LHS_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_energy_regulating_lower_load_lhs_penalty_rule)

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
             + sum(m.E_CV_TRADER_JOINT_RAMPING_RAISE_GENERATOR_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_JOINT_RAMPING_LOWER_GENERATOR_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_RAISE_GENERATOR_RHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_RAISE_GENERATOR_LHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_LOWER_GENERATOR_RHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_LOWER_GENERATOR_LHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_TRAPEZIUM_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_RHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_LHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_LHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_RHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_JOINT_RAMPING_RAISE_LOAD_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_JOINT_RAMPING_LOWER_LOAD_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_RAISE_LOAD_LHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_RAISE_LOAD_RHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_LOWER_LOAD_LHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_LOWER_LOAD_RHS_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_LHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_LOAD_RHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_RHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_LOAD_LHS_PENALTY[i] for i in m.S_TRADERS)
             + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i] for i in m.S_INTERCONNECTORS)
             + sum(m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i] for i in m.S_INTERCONNECTORS)
    )

    return m


def define_aggregate_power_expressions(m):
    """Compute aggregate demand and generation in each NEM region"""

    def region_generation_rule(m, r):
        """Available energy offers in given region"""

        return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
                   if (j == 'ENOF') and (m.P_TRADER_REGION[i] == r))

    # Total generation dispatched in a given region
    m.E_REGION_GENERATION = pyo.Expression(m.S_REGIONS, rule=region_generation_rule)

    def region_scheduled_load_rule(m, r):
        """Available load offers in given region"""

        return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
                   if (j == 'LDOF') and (m.P_TRADER_REGION[i] == r))

    # Total scheduled load dispatched in a given region
    m.E_REGION_SCHEDULED_LOAD = pyo.Expression(m.S_REGIONS, rule=region_scheduled_load_rule)

    def region_interconnector_export_rule(m, r):
        """Net export out of region over interconnectors"""
        pass

    # Net flow out of region
    m.E_REGION_INTERCONNECTOR_EXPORT = pyo.Expression(m.S_REGIONS, rule=region_interconnector_export_rule)

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

    # Region allocated loss
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
            flow = m.P_INTERCONNECTOR_INITIAL_MW[i]

            to_lf_export = m.P_MNSP_TO_REGION_LF_EXPORT[i]
            to_lf_import = m.P_MNSP_TO_REGION_LF_IMPORT[i]

            from_lf_import = m.P_MNSP_FROM_REGION_LF_IMPORT[i]
            from_lf_export = m.P_MNSP_FROM_REGION_LF_EXPORT[i]

            # Loss over interconnector
            loss = m.V_LOSS[i]

            # MNSP loss share - loss applied to sending end
            if flow >= 0:
                # Total loss allocated to FromRegion
                mnsp_loss_share = 1
            else:
                # Total loss allocated to ToRegion
                mnsp_loss_share = 0

            if flow >= 0:
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

    # Region MNSP loss estimate
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

    # Region fixed demand
    m.E_REGION_FIXED_DEMAND = pyo.Expression(m.S_REGIONS, rule=region_fixed_demand_rule)

    def region_cleared_demand_rule(m, r):
        """Region cleared demand rule - generation in region = cleared demand at end of dispatch interval"""

        demand = (
                m.E_REGION_FIXED_DEMAND[r]
                + m.E_REGION_ALLOCATED_LOSS[r]
                + m.E_REGION_SCHEDULED_LOAD[r]
                + m.E_REGION_MNSP_LOSS[r]
        )

        return demand

    # Region cleared demand - used in power balance constraint
    m.E_REGION_CLEARED_DEMAND = pyo.Expression(m.S_REGIONS, rule=region_cleared_demand_rule)

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

        # Ramp rate
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

        # Ramp rate
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
        """Power balance for each region"""

        return (m.E_REGION_GENERATION[r]
                ==
                m.E_REGION_DEMAND[r]
                # + m.P_REGION_FIXED_DEMAND[r]  # TODO: Assuming fixed demand
                + m.E_REGION_LOAD[r]
                + m.E_REGION_NET_EXPORT_FLOW[r]
                # + m.P_REGION_NET_EXPORT[r]  # TODO: Assuming fixed export for now - need to change back later
                )

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

    def from_node_connection_point_balance_rule(m, i):
        """Power balance at from node connection point"""

        return m.V_FLOW_FROM_CP[i] - (m.P_INTERCONNECTOR_LOSS_SHARE[i] * m.V_LOSS[i]) - m.V_GC_INTERCONNECTOR[i] == 0

    # From node connection point power balance
    m.C_FROM_NODE_CP_POWER_BALANCE = pyo.Constraint(m.S_INTERCONNECTORS, rule=from_node_connection_point_balance_rule)

    def to_node_connection_point_balance_rule(m, i):
        """Power balance at to node connection point"""

        # Loss share applied to from node connection point
        loss_share = 1 - m.P_INTERCONNECTOR_LOSS_SHARE[i]

        return m.V_GC_INTERCONNECTOR[i] - (loss_share * m.V_LOSS[i]) - m.V_FLOW_TO_CP[i] == 0

    # To node connection point power balance
    m.C_TO_NODE_CP_POWER_BALANCE = pyo.Constraint(m.S_INTERCONNECTORS, rule=to_node_connection_point_balance_rule)

    return m


def define_fcas_constraints(m):
    """Define FCAS constraints"""
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


def define_constraints(m):
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

    # Construct FCAS constraints
    m = define_fcas_constraints(m)
    print('Defined FCAS constraints:', time.time() - t0)

    # SOS2 interconnector loss model constraints
    m = define_loss_model_constraints(m)
    print('Defined loss model constraints:', time.time() - t0)

    return m


def define_objective(m):
    """Define model objective"""

    # Total cost for energy and ancillary services
    m.OBJECTIVE = pyo.Objective(expr=sum(m.E_TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
                                     + sum(m.E_MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
                                     + m.E_CV_TOTAL_PENALTY
                                ,
                                sense=pyo.minimize)

    return m


def construct_model(data):
    """Create model object"""

    # Initialise model
    t0 = time.time()
    m = pyo.ConcreteModel()

    # Define model components
    m = define_sets(m, data)
    m = define_parameters(m, data)
    m = define_variables(m)
    m = define_expressions(m, data)
    # m = define_constraints(m)
    # m = define_objective(m)
    #
    # # Add component allowing dual variables to be imported
    # m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    print('Constructed model in:', time.time() - t0)

    return m


def solve_model(m):
    """Solve model"""

    # Setup solver
    solver_options = {}  # 'MIPGap': 0.0005,
    opt = pyo.SolverFactory('cplex', solver_io='lp')

    # Solve model
    t0 = time.time()

    print('Starting MILP solve:', time.time() - t0)
    solve_status_1 = opt.solve(m, tee=False, options=solver_options, keepfiles=False)
    print('Finished MILP solve:', time.time() - t0)
    print('Objective value - 1:', m.OBJECTIVE.expr())

    return m, solve_status_1


def get_intervention_status(data) -> str:
    """Check if intervention pricing run occurred - trying to model physical run if intervention occurred"""

    return '0' if utils.lookup.get_case_attribute(data, '@Intervention', str) == 'False' else '1'


def check_region_fixed_demand(data, m, r):
    """Check fixed demand calculation"""

    # Get intervention flag corresponding to physical NEMDE run
    intervention = get_intervention_status(data)

    # Container for output
    calculated = m.E_REGION_FIXED_DEMAND[r].expr()
    observed = utils.lookup.get_region_solution_attribute(data, r, '@FixedDemand', float, intervention)

    out = {
        'calculated': calculated,
        'observed': observed,
        'difference': calculated - observed,
        'abs_difference': abs(calculated - observed)
    }

    return out


def check_region_fixed_demand_calculation_sample(data_dir, n=5):
    """Check region fixed demand calculations for a random sample of dispatch intervals"""

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
        m = construct_model(processed_data)

        # All regions
        regions = utils.lookup.get_region_index(case_data)

        for r in regions:
            # Check difference between calculated region fixed demand and fixed demand from NEMDE solution
            fixed_demand_info = check_region_fixed_demand(case_data, m, r)

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


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # Case data in json format
    case_data_json = utils.loaders.load_dispatch_interval_json(data_directory, 2019, 10, 10, 10)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)

    # Preprocessed case data
    model_data = utils.data.parse_case_data_json(case_data_json)

    # Construct model
    model = construct_model(model_data)

    # Check fixed demand
    df_fixed_demand_check = check_region_fixed_demand_calculation_sample(data_directory, n=1000)

    # (6, 288, 'SA1')

    # # Case data in json format
    # case_data_json = utils.loaders.load_dispatch_interval_json(data_directory, 2019, 10, 24, 268)
    #
    # # Get NEMDE model data as a Python dictionary
    # cdata = json.loads(case_data_json)
