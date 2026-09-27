"""Model used to construct and solve NEMDE approximation

Section index (function -> line -> purpose). construct_model() calls the
define_* stages in this order. Line numbers are approximate and drift with edits.

    define_sets                                       68    ->  Pyomo sets (traders, regions,
                                                               offers, etc.)
    define_parameters                                 304   ->  Pyomo params loaded from
                                                               casefile data
    define_variables                                  710   ->  decision + constraint-violation
                                                               variables
    define_cost_function_expressions                  851   ->  bid cost expressions
    define_generic_constraint_expressions             876   ->  generic (AEMO) constraint LHS
                                                               expressions
    define_constraint_violation_penalty_expressions   911   ->  CV penalty expressions
    define_mnsp_expressions                           1262  ->  MNSP interconnector expressions
    define_aggregate_power_expressions                1312  ->  region/system power balance
                                                               expressions
    define_fcas_expressions                           1664  ->  FCAS-related expressions
    define_tie_breaking_expressions                   1726  ->  tie-break cost expressions
    define_expressions                                1751  ->  dispatcher for the expression
                                                               defs above
    define_offer_constraints                          1778  ->  trade quantity/price band
                                                               constraints
    define_bidirectional_energy_constraints           1841  ->  bidirectional unit (BDU) energy
                                                               constraints
    define_generic_constraints                        1867  ->  generic (AEMO) constraints
    define_unit_constraints                           1940  ->  per-unit operating constraints
    define_region_constraints                         2015  ->  region power balance constraints
    define_interconnector_constraints                 2039  ->  interconnector flow/loss
                                                               constraints
    define_mnsp_constraints                           2071  ->  MNSP-specific constraints
    define_fcas_constraints                           2286  ->  FCAS trapezium/joint-ramping
                                                               constraints (the only live FCAS
                                                               constraint set -- see git history
                                                               for the retired v1)
    define_loss_model_constraints                     2909  ->  interconnector loss model (SOS2)
                                                               constraints
    define_fast_start_unit_inflexibility_constraints  2989  ->  fast-start inflexibility profile
                                                               constraints
    define_tie_breaking_constraints                   3076  ->  tie-break constraints
    define_trader_target_pinning_constraints          3125  ->  NEMDE-target pinning, off unless
                                                               SolveOptions asks for it
    define_constraints                                3151  ->  dispatcher for the constraint
                                                               defs above
    define_objective                                  3210  ->  objective function
    construct_model                                   3226  ->  top-level entry point: builds
                                                               and returns m
"""

import logging
import time

import pyomo.environ as pyo

from nemde.fast_start import (
    get_mode_one_ramping_capability,
    get_mode_two_initial_mw,
    get_mode_two_ramping_capability,
    get_target_mode,
    get_target_mode_time,
)
from nemde.model_options import SolveOptions, apply_constraint_overrides

logger = logging.getLogger(__name__)


def define_sets(m, data):
    """Define sets"""

    # NEM regions
    m.S_REGIONS = pyo.Set(initialize=data["S_REGIONS"])

    # Market participants (generators and loads)
    m.S_TRADERS = pyo.Set(initialize=data["S_TRADERS"])

    # Semi-dispatchable traders
    m.S_TRADERS_SEMI_DISPATCH = pyo.Set(initialize=data["S_TRADERS_SEMI_DISPATCH"])

    # Individual trader offer types - includes direction (DUID, offer_type, direction)
    m.S_TRADER_OFFERS = pyo.Set(initialize=data["S_TRADER_OFFERS"])

    # Aggregate offer for each DUID and trade type (DUID, offer_type)
    m.S_TRADER_TOTAL_OFFERS = pyo.Set(initialize=data["S_TRADER_TOTAL_OFFERS"])

    # Trader FCAS offers
    m.S_TRADER_FCAS_OFFERS = pyo.Set(initialize=data["S_TRADER_FCAS_OFFERS"])

    # Trader energy offers
    m.S_TRADER_ENERGY_OFFERS = pyo.Set(initialize=data["S_TRADER_ENERGY_OFFERS"])

    # FCAS joint ramping (raise)
    m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_GEN_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_GEN_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_LOAD_INDEX"]
    )

    # FCAS joint ramping (lower)
    m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_GEN_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_GEN_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_LOAD_INDEX"]
    )

    # FCAS joint capacity constraints (upper slope)
    m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITH_R5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITH_R5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITHOUT_R5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITHOUT_R5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITH_L5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITH_L5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITHOUT_L5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITHOUT_L5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITH_R5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITH_R5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITHOUT_R5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITHOUT_R5RE_INDEX"]
    )

    # FCAS joint capacity constraints (lower slope)
    m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITH_L5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITH_L5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITHOUT_L5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITHOUT_L5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITH_R5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITH_R5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITHOUT_R5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITHOUT_R5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITH_L5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITH_L5RE_INDEX"]
    )

    m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITHOUT_L5RE_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITHOUT_L5RE_INDEX"]
    )

    # Energy and regulating FCAS capacity constraints (upper slope)
    m.S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_GENERATOR_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_GENERATOR_INDEX"]
    )

    m.S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_LOAD_INDEX"]
    )

    # Energy and regulating FCAS capacity constraints (lower slope)
    m.S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_GENERATOR_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_GENERATOR_INDEX"]
    )

    m.S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_LOAD_INDEX"]
    )

    # BDU energy and regulating FCAS capacity constraints
    m.S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_GEN_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_GEN_INDEX"]
    )

    m.S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_LOAD_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_LOAD_INDEX"]
    )

    # BDU regulating FCAS SCADA ramping constraints
    m.S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_UP_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_UP_INDEX"]
    )

    m.S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_DOWN_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_DOWN_INDEX"]
    )

    # Enablement min and max FCAS sets
    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_REGULATION_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_REGULATION_INDEX"]
    )

    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_CONTINGENCY_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_CONTINGENCY_INDEX"]
    )

    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_REGULATION_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_REGULATION_INDEX"]
    )

    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_CONTINGENCY_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_CONTINGENCY_INDEX"]
    )

    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_GEN_REGULATION_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_GEN_REGULATION_INDEX"]
    )

    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_CONTINGENCY_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_CONTINGENCY_INDEX"]
    )

    m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_LOAD_REGULATION_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_LOAD_REGULATION_INDEX"]
    )

    m.S_TRADER_FCAS_MAX_AVAIL_GENERATOR_REGULATION_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_MAX_AVAIL_GENERATOR_REGULATION_INDEX"]
    )

    m.S_TRADER_FCAS_MAX_AVAIL_GENERATOR_CONTINGENCY_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_MAX_AVAIL_GENERATOR_CONTINGENCY_INDEX"]
    )

    m.S_TRADER_FCAS_MAX_AVAIL_LOAD_REGULATION_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_MAX_AVAIL_LOAD_REGULATION_INDEX"]
    )

    m.S_TRADER_FCAS_MAX_AVAIL_LOAD_CONTINGENCY_INDEX = pyo.Set(
        initialize=data["S_TRADER_FCAS_MAX_AVAIL_LOAD_CONTINGENCY_INDEX"]
    )

    # Trader fast start units TODO: check if '@FastStart'='0' should also be
    # included when constructing set
    m.S_TRADER_FAST_START = pyo.Set(initialize=data["S_TRADER_FAST_START"])

    m.S_TRADERS_BIDIRECTIONAL = pyo.Set(initialize=data["S_TRADERS_BIDIRECTIONAL"])

    # Price tied bands
    m.S_TRADER_PRICE_TIED_GENERATORS = pyo.Set(initialize=data["S_TRADER_PRICE_TIED_GENERATORS"])
    m.S_TRADER_PRICE_TIED_LOADS = pyo.Set(initialize=data["S_TRADER_PRICE_TIED_LOADS"])

    # Generic constraints
    m.S_GENERIC_CONSTRAINTS = pyo.Set(initialize=data["S_GENERIC_CONSTRAINTS"])

    # Generic constraints trader pyo.Variables
    m.S_GC_TRADER_VARS = pyo.Set(initialize=data["S_GC_TRADER_VARS"])

    # Generic constraint interconnector pyo.Variables
    m.S_GC_INTERCONNECTOR_VARS = pyo.Set(initialize=data["S_GC_INTERCONNECTOR_VARS"])

    # Generic constraint region pyo.Variables
    m.S_GC_REGION_VARS = pyo.Set(initialize=data["S_GC_REGION_VARS"])

    # Price / quantity band index
    m.S_BANDS = pyo.RangeSet(1, 10, 1)

    # Market Network Service Providers (interconnectors that bid into the market)
    m.S_MNSPS = pyo.Set(initialize=data["S_MNSPS"])

    # MNSP offer types
    m.S_MNSP_OFFERS = pyo.Set(initialize=data["S_MNSP_OFFERS"])

    # All interconnectors (interconnector_id)
    m.S_INTERCONNECTORS = pyo.Set(initialize=data["S_INTERCONNECTORS"])

    # Interconnector loss model breakpoints
    m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS = pyo.Set(
        initialize=data["S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS"]
    )

    # Interconnector loss model intervals
    m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS = pyo.Set(
        initialize=data["S_INTERCONNECTOR_LOSS_MODEL_INTERVALS"]
    )

    return m


def define_parameters(m, data):
    """Define model parameters"""

    # Intervention status
    m.P_INTERVENTION_STATUS = pyo.Param(initialize=data["P_INTERVENTION_STATUS"], within=pyo.Any)

    # Case ID
    m.P_CASE_ID = pyo.Param(initialize=data["P_CASE_ID"], within=pyo.Any)

    # Price bands for traders (generators / loads)
    m.P_TRADER_PRICE_BAND = pyo.Param(
        m.S_TRADER_OFFERS, m.S_BANDS, initialize=data["P_TRADER_PRICE_BAND"]
    )

    # Quantity bands for traders (generators / loads)
    m.P_TRADER_QUANTITY_BAND = pyo.Param(
        m.S_TRADER_OFFERS, m.S_BANDS, initialize=data["P_TRADER_QUANTITY_BAND"]
    )

    # Max available output for given trader
    m.P_TRADER_MAX_AVAILABLE = pyo.Param(m.S_TRADER_OFFERS, initialize=data["P_TRADER_MAX_AVAIL"])

    # Initial MW output for generators / loads
    m.P_TRADER_EFFECTIVE_INITIAL_MW = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_EFFECTIVE_INITIAL_MW"]
    )

    # UIGF for semi-dispatchable plant
    m.P_TRADER_UIGF = pyo.Param(m.S_TRADERS_SEMI_DISPATCH, initialize=data["P_TRADER_UIGF"])

    # Trader HMW and LMW
    m.P_TRADER_HMW = pyo.Param(m.S_TRADERS, initialize=data["P_TRADER_HMW"])
    m.P_TRADER_LMW = pyo.Param(m.S_TRADERS, initialize=data["P_TRADER_LMW"])

    # Trader AGC status
    m.P_TRADER_AGC_STATUS = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_AGC_STATUS"], within=pyo.Any
    )

    # Trader semi-dispatch status
    m.P_TRADER_SEMI_DISPATCH_STATUS = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_SEMI_DISPATCH_STATUS"], within=pyo.Any
    )

    # Trader region
    m.P_TRADER_REGION = pyo.Param(m.S_TRADERS, initialize=data["P_TRADER_REGION"], within=pyo.Any)

    # Trader ramp up and down rates
    m.P_TRADER_PERIOD_RAMP_UP_RATE = pyo.Param(
        m.S_TRADER_ENERGY_OFFERS, initialize=data["P_TRADER_PERIOD_RAMP_UP_RATE"]
    )
    m.P_TRADER_PERIOD_RAMP_DOWN_RATE = pyo.Param(
        m.S_TRADER_ENERGY_OFFERS, initialize=data["P_TRADER_PERIOD_RAMP_DN_RATE"]
    )

    # Trader FCAS max available
    m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL"]
    )

    # Trader FCAS enablement min
    m.P_TRADER_FCAS_ENABLEMENT_MIN = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_ENABLEMENT_MIN"]
    )

    m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_EFFECTIVE_ENABLEMENT_MIN"]
    )

    # Trader FCAS low breakpoint
    m.P_TRADER_FCAS_LOW_BREAKPOINT = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_LOW_BREAKPOINT"]
    )

    m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_EFFECTIVE_LOW_BREAKPOINT"]
    )

    # Trader FCAS high breakpoint
    m.P_TRADER_FCAS_HIGH_BREAKPOINT = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_HIGH_BREAKPOINT"]
    )

    m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_EFFECTIVE_HIGH_BREAKPOINT"]
    )

    # Trader FCAS enablement max
    m.P_TRADER_FCAS_ENABLEMENT_MAX = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_ENABLEMENT_MAX"]
    )

    m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_EFFECTIVE_ENABLEMENT_MAX"]
    )

    # Trader FCAS availability
    m.P_TRADER_FCAS_AVAILABILITY_STATUS = pyo.Param(
        m.S_TRADER_FCAS_OFFERS, initialize=data["P_TRADER_FCAS_AVAILABILITY_STATUS"]
    )

    # Lower energy bound for BDU GEN regulation enablement min constraint
    # Combined BDU (GEN + LOAD both available): EnablementMin_LOAD; GEN-only: EnablementMin_GEN
    m.P_TRADER_FCAS_BDU_GEN_REGULATION_LOWER_ENERGY_BOUND = pyo.Param(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_GEN_REGULATION_INDEX,
        initialize=data["P_TRADER_FCAS_BDU_GEN_REGULATION_LOWER_ENERGY_BOUND"],
    )

    # Trader type
    m.P_TRADER_TYPE = pyo.Param(m.S_TRADERS, initialize=data["P_TRADER_TYPE"], within=pyo.Any)

    # Trader fast start parameters
    m.P_TRADER_MIN_LOADING_MW = pyo.Param(
        m.S_TRADER_FAST_START, initialize=data["P_TRADER_MIN_LOADING_MW"]
    )

    m.P_TRADER_CURRENT_MODE = pyo.Param(
        m.S_TRADER_FAST_START,
        initialize=data["P_TRADER_CURRENT_MODE"],
        within=pyo.Integers,
        mutable=True,
    )

    m.P_TRADER_CURRENT_MODE_TIME = pyo.Param(
        m.S_TRADER_FAST_START,
        initialize=data["P_TRADER_CURRENT_MODE_TIME"],
        mutable=True,
    )

    m.P_TRADER_T1 = pyo.Param(m.S_TRADER_FAST_START, initialize=data["P_TRADER_T1"])
    m.P_TRADER_T2 = pyo.Param(m.S_TRADER_FAST_START, initialize=data["P_TRADER_T2"])
    m.P_TRADER_T3 = pyo.Param(m.S_TRADER_FAST_START, initialize=data["P_TRADER_T3"])
    m.P_TRADER_T4 = pyo.Param(m.S_TRADER_FAST_START, initialize=data["P_TRADER_T4"])

    # Used to 'swap' (deactivate) inflexibility profile constraints
    m.P_TRADER_INFLEXIBILITY_PROFILE_SWAMP = pyo.Param(initialize=0, mutable=True)

    # Trader SCADA ramp up and down rates
    m.P_TRADER_SCADA_RAMP_UP_RATE = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_SCADA_RAMP_UP_RATE"]
    )

    m.P_TRADER_SCADA_RAMP_DOWN_RATE = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_SCADA_RAMP_DN_RATE"]
    )

    # Effective ramp rate - min of energy offer ramp rate and SCADA ramp rate
    m.P_TRADER_EFFECTIVE_RAMP_UP_RATE = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_EFFECTIVE_RAMP_UP_RATE"]
    )

    m.P_TRADER_OFFER_COST_FACTOR = pyo.Param(
        m.S_TRADER_OFFERS, initialize=data["P_TRADER_OFFER_COST_FACTOR"]
    )

    m.P_TRADER_EFFECTIVE_RAMP_DN_RATE = pyo.Param(
        m.S_TRADERS, initialize=data["P_TRADER_EFFECTIVE_RAMP_DN_RATE"]
    )

    m.P_TRADER_EFFECTIVE_INITIAL_ENERGY = pyo.Param(
        m.S_TRADERS_BIDIRECTIONAL, initialize=data["P_TRADER_EFFECTIVE_INITIAL_ENERGY"]
    )

    m.P_TRADER_BIDIRECTIONAL_MIN_ENERGY_LIMIT = pyo.Param(
        m.S_TRADERS_BIDIRECTIONAL,
        initialize=data["P_TRADER_BIDIRECTIONAL_MIN_ENERGY_LIMIT"],
        within=pyo.Any,
    )

    m.P_TRADER_BIDIRECTIONAL_MAX_ENERGY_LIMIT = pyo.Param(
        m.S_TRADERS_BIDIRECTIONAL,
        initialize=data["P_TRADER_BIDIRECTIONAL_MAX_ENERGY_LIMIT"],
        within=pyo.Any,
    )

    m.P_TRADER_BIDIRECTIONAL_MAX_STORAGE_CAPACITY = pyo.Param(
        m.S_TRADERS_BIDIRECTIONAL,
        initialize=data["P_TRADER_BIDIRECTIONAL_MAX_STORAGE_CAPACITY"],
    )

    m.P_TRADER_BIDIRECTIONAL_IMPORT_EFFCIENCY_FACTOR = pyo.Param(
        m.S_TRADERS_BIDIRECTIONAL,
        initialize=data["P_TRADER_BIDIRECTIONAL_IMPORT_EFFCIENCY_FACTOR"],
        within=pyo.Any,
    )

    m.P_TRADER_BIDIRECTIONAL_EXPORT_EFFCIENCY_FACTOR = pyo.Param(
        m.S_TRADERS_BIDIRECTIONAL,
        initialize=data["P_TRADER_BIDIRECTIONAL_EXPORT_EFFCIENCY_FACTOR"],
        within=pyo.Any,
    )

    m.P_CVF_BDU_MIN_ENERGY_PRICE = pyo.Param(initialize=data["P_CVF_BDU_MIN_ENERGY_PRICE"])
    m.P_CVF_BDU_MAX_ENERGY_PRICE = pyo.Param(initialize=data["P_CVF_BDU_MAX_ENERGY_PRICE"])

    # Actual energy targets - used if pinning constraints
    m.P_TRADER_TARGET = pyo.Param(
        m.S_TRADERS.cross(
            [
                "ENERGY_TARGET",
                "R1SE",
                "R6SE",
                "R60S",
                "R5MI",
                "R5RE",
                "L1SE",
                "L6SE",
                "L60S",
                "L5MI",
                "L5RE",
            ]
        ),
        initialize=data["P_TRADER_TARGET"],
    )

    m.P_INTERCONNECTOR_FLOW = pyo.Param(
        m.S_INTERCONNECTORS, initialize=data["P_INTERCONNECTOR_FLOW"]
    )

    # Interconnector initial MW (WhatIfMW used if pricing run for intervention period)
    m.P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW = pyo.Param(
        m.S_INTERCONNECTORS, initialize=data["P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW"]
    )

    # Interconnector 'to' and 'from' regions
    m.P_INTERCONNECTOR_TO_REGION = pyo.Param(
        m.S_INTERCONNECTORS,
        initialize=data["P_INTERCONNECTOR_TO_REGION"],
        within=pyo.Any,
    )

    m.P_INTERCONNECTOR_FROM_REGION = pyo.Param(
        m.S_INTERCONNECTORS,
        initialize=data["P_INTERCONNECTOR_FROM_REGION"],
        within=pyo.Any,
    )

    # Interconnector lower and upper limits.
    # NOTE: these are absolute values -- the lower limit is positive.
    m.P_INTERCONNECTOR_LOWER_LIMIT = pyo.Param(
        m.S_INTERCONNECTORS, initialize=data["P_INTERCONNECTOR_LOWER_LIMIT"]
    )

    m.P_INTERCONNECTOR_UPPER_LIMIT = pyo.Param(
        m.S_INTERCONNECTORS, initialize=data["P_INTERCONNECTOR_UPPER_LIMIT"]
    )

    # Interconnector MNSP status
    m.P_INTERCONNECTOR_MNSP_STATUS = pyo.Param(
        m.S_INTERCONNECTORS,
        initialize=data["P_INTERCONNECTOR_MNSP_STATUS"],
        within=pyo.Any,
    )

    # Interconnector loss share
    m.P_INTERCONNECTOR_LOSS_SHARE = pyo.Param(
        m.S_INTERCONNECTORS, initialize=data["P_INTERCONNECTOR_LOSS_SHARE"]
    )

    # Interconnector initial loss estimate
    m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE = pyo.Param(
        m.S_INTERCONNECTORS,
        initialize=data["P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE"],
    )

    # Interconnector loss model segment limit
    m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X = pyo.Param(
        m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS,
        initialize=data["P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X"],
    )

    # Interconnector loss model segment factor
    m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y = pyo.Param(
        m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS,
        initialize=data["P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y"],
    )

    # Price bands for MNSPs
    m.P_MNSP_PRICE_BAND = pyo.Param(
        m.S_MNSP_OFFERS, m.S_BANDS, initialize=data["P_MNSP_PRICE_BAND"]
    )

    # Quantity bands for MNSPs
    m.P_MNSP_QUANTITY_BAND = pyo.Param(
        m.S_MNSP_OFFERS, m.S_BANDS, initialize=data["P_MNSP_QUANTITY_BAND"]
    )

    # Max available output for given MNSP
    m.P_MNSP_MAX_AVAILABLE = pyo.Param(m.S_MNSP_OFFERS, initialize=data["P_MNSP_MAX_AVAILABLE"])

    # MNSP ramp rates (in offers)
    m.P_MNSP_RAMP_UP_RATE = pyo.Param(m.S_MNSP_OFFERS, initialize=data["P_MNSP_RAMP_UP_RATE"])

    m.P_MNSP_RAMP_DOWN_RATE = pyo.Param(m.S_MNSP_OFFERS, initialize=data["P_MNSP_RAMP_DOWN_RATE"])

    # MNSP 'to' and 'from' region loss factor
    m.P_MNSP_TO_REGION_LF_EXPORT = pyo.Param(
        m.S_MNSPS, initialize=data["P_MNSP_TO_REGION_LF_EXPORT"]
    )

    m.P_MNSP_TO_REGION_LF_IMPORT = pyo.Param(
        m.S_MNSPS, initialize=data["P_MNSP_TO_REGION_LF_IMPORT"]
    )

    m.P_MNSP_FROM_REGION_LF_EXPORT = pyo.Param(
        m.S_MNSPS, initialize=data["P_MNSP_FROM_REGION_LF_EXPORT"]
    )

    m.P_MNSP_FROM_REGION_LF_IMPORT = pyo.Param(
        m.S_MNSPS, initialize=data["P_MNSP_FROM_REGION_LF_IMPORT"]
    )

    # MNSP loss indicator
    m.P_MNSP_REGION_LOSS_INDICATOR = pyo.Param(
        m.S_MNSPS, m.S_REGIONS, initialize=data["P_MNSP_REGION_LOSS_INDICATOR"]
    )

    # Initial region demand
    m.P_REGION_INITIAL_DEMAND = pyo.Param(m.S_REGIONS, initialize=data["P_REGION_INITIAL_DEMAND"])

    # Region aggregate dispatch error (ADE)
    m.P_REGION_ADE = pyo.Param(m.S_REGIONS, initialize=data["P_REGION_ADE"])

    # Region demand forecast increment (DF)
    m.P_REGION_DF = pyo.Param(m.S_REGIONS, initialize=data["P_REGION_DF"])

    # Generic constraint RHS
    m.P_GC_RHS = pyo.Param(m.S_GENERIC_CONSTRAINTS, initialize=data["P_GC_RHS"])

    # Generic constraint type
    m.P_GC_TYPE = pyo.Param(m.S_GENERIC_CONSTRAINTS, initialize=data["P_GC_TYPE"], within=pyo.Any)

    # Generic constraint violation factors
    m.P_CVF_GC = pyo.Param(m.S_GENERIC_CONSTRAINTS, initialize=data["P_CVF_GC"])

    # Value of lost load
    m.P_CVF_VOLL = pyo.Param(initialize=data["P_CVF_VOLL"])

    # Energy deficit price
    m.P_CVF_ENERGY_DEFICIT_PRICE = pyo.Param(initialize=data["P_CVF_ENERGY_DEFICIT_PRICE"])
    m.P_CVF_ENERGY_SURPLUS_PRICE = pyo.Param(initialize=data["P_CVF_ENERGY_SURPLUS_PRICE"])
    m.P_CVF_UIGF_SURPLUS_PRICE = pyo.Param(initialize=data["P_CVF_UIGF_SURPLUS_PRICE"])
    m.P_CVF_RAMP_RATE_PRICE = pyo.Param(initialize=data["P_CVF_RAMP_RATE_PRICE"])

    # Capacity price (assume for constraint ensuring max available capacity not
    # exceeded)
    m.P_CVF_CAPACITY_PRICE = pyo.Param(initialize=data["P_CVF_CAPACITY_PRICE"])

    # Offer price (assume for constraint ensuring band offer amounts are not
    # exceeded)
    m.P_CVF_OFFER_PRICE = pyo.Param(initialize=data["P_CVF_OFFER_PRICE"])

    # MNSP offer price (assumed for constraint ensuring MNSP band offers are
    # ot exceeded)
    m.P_CVF_MNSP_OFFER_PRICE = pyo.Param(initialize=data["P_CVF_MNSP_OFFER_PRICE"])

    # MNSP ramp rate price (not sure what this applies to - unclear what MNSP
    # ramp rates are)
    m.P_CVF_MNSP_RAMP_RATE_PRICE = pyo.Param(initialize=data["P_CVF_MNSP_RAMP_RATE_PRICE"])

    # MNSP capacity price (assume for constraint ensuring max available
    # capacity not exceeded)
    m.P_CVF_MNSP_CAPACITY_PRICE = pyo.Param(initialize=data["P_CVF_MNSP_CAPACITY_PRICE"])

    # MNSP loss price TODO: check - not used
    m.P_CVF_MNSP_LOSS_PRICE = pyo.Param(initialize=data["P_MNSP_LOSS_PRICE"])

    # Ancillary services profile price (assume for constraint ensure FCAS
    # trapezium not violated) TODO: check - not used
    m.P_CVF_AS_PROFILE_PRICE = pyo.Param(initialize=data["P_CVF_AS_PROFILE_PRICE"])

    # Ancillary services max available price (assume for constraint ensure max
    # available amount not exceeded)
    m.P_CVF_AS_MAX_AVAIL_PRICE = pyo.Param(initialize=data["P_CVF_AS_MAX_AVAIL_PRICE"])

    # Ancillary services enablement min price (assume for constraint ensuring
    # FCAS > enablement min if active) TODO: check - not used
    m.P_CVF_AS_ENABLEMENT_MIN_PRICE = pyo.Param(initialize=data["P_CVF_AS_ENABLEMENT_MIN_PRICE"])

    # Ancillary services enablement max price (assume for constraint ensuring
    #  FCAS < enablement max if active) TODO: check - not used
    m.P_CVF_AS_ENABLEMENT_MAX_PRICE = pyo.Param(initialize=data["P_CVF_AS_ENABLEMENT_MAX_PRICE"])

    # Interconnector power flow violation price
    m.P_CVF_INTERCONNECTOR_PRICE = pyo.Param(initialize=data["P_CVF_INTERCONNECTOR_PRICE"])

    # Trader fast start inflexibility constraint violation price
    m.P_CVF_FAST_START_PRICE = pyo.Param(initialize=data["P_CVF_FAST_START_PRICE"])

    # Generic constraint price TODO: check - not used
    m.P_CVF_GENERIC_CONSTRAINT_PRICE = pyo.Param(initialize=data["P_CVF_GENERIC_CONSTRAINT_PRICE"])

    # Satisfactory network constraint price TODO: check - not used
    m.P_CVF_SATISFACTORY_NETWORK_PRICE = pyo.Param(
        initialize=data["P_CVF_SATISFACTORY_NETWORK_PRICE"]
    )

    # Tie-break price
    m.P_TIE_BREAK_PRICE = pyo.Param(initialize=data["P_TIE_BREAK_PRICE"])

    # Power output threshold used in two-pass fast start algorithm
    m.P_FAST_START_THRESHOLD = pyo.Param(initialize=data["P_FAST_START_THRESHOLD"])

    return m


def define_variables(m):
    """Define model pyo.Variables"""

    # Offers for each quantity band
    m.V_TRADER_OFFER = pyo.Var(m.S_TRADER_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)
    m.V_MNSP_OFFER = pyo.Var(m.S_MNSP_OFFERS, m.S_BANDS, within=pyo.NonNegativeReals)

    # Total offer amount for each band trade type and direction
    m.E_TRADER_TOTAL_OFFER = pyo.Expression(
        m.S_TRADER_OFFERS,
        rule=lambda m, i, j, k: sum(m.V_TRADER_OFFER[i, j, k, b] for b in m.S_BANDS),
    )

    def trader_target_rule(m, i, j):
        """Trader targets"""

        trader_type = m.P_TRADER_TYPE[i]
        if (trader_type == "BIDIRECTIONAL") and (j in ["BDOF"]):
            return m.E_TRADER_TOTAL_OFFER[i, j, "GEN"] - m.E_TRADER_TOTAL_OFFER[i, j, "LOAD"]
        if (trader_type == "BIDIRECTIONAL") and (j in ["L5RE", "R5RE"]):
            return m.E_TRADER_TOTAL_OFFER[i, j, "GEN"] + m.E_TRADER_TOTAL_OFFER[i, j, "LOAD"]
        else:
            return m.E_TRADER_TOTAL_OFFER[i, j, None]

    # Trader target amount for each DUID and offer type
    m.E_TRADER_TARGET = pyo.Expression(m.S_TRADER_TOTAL_OFFERS, rule=trader_target_rule)

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
    m.V_CV_TRADER_UIGF_SURPLUS = pyo.Var(m.S_TRADER_TOTAL_OFFERS, within=pyo.NonNegativeReals)

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
    m.V_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN = pyo.Var(m.S_TRADERS, within=pyo.NonNegativeReals)

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
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS = pyo.Var(
        m.S_TRADER_OFFERS, within=pyo.NonNegativeReals
    )
    m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS = pyo.Var(
        m.S_TRADER_OFFERS, within=pyo.NonNegativeReals
    )
    m.V_CV_TRADER_FCAS_MAX_AVAILABLE = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENABLEMENT_MIN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
    m.V_CV_TRADER_FCAS_ENABLEMENT_MAX = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

    # Inflexibility profile violation
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE = pyo.Var(
        m.S_TRADER_FAST_START, within=pyo.NonNegativeReals
    )
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS = pyo.Var(
        m.S_TRADER_FAST_START, within=pyo.NonNegativeReals
    )
    m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS = pyo.Var(
        m.S_TRADER_FAST_START, within=pyo.NonNegativeReals
    )

    # Interconnector forward and reverse flow constraint violation
    m.V_CV_INTERCONNECTOR_FORWARD = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)
    m.V_CV_INTERCONNECTOR_REVERSE = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)

    # Region surplus / deficit power
    m.V_CV_REGION_GENERATION_SURPLUS = pyo.Var(m.S_REGIONS, within=pyo.NonNegativeReals)
    m.V_CV_REGION_GENERATION_DEFICIT = pyo.Var(m.S_REGIONS, within=pyo.NonNegativeReals)

    # Loss model breakpoints and intervals
    m.V_LOSS = pyo.Var(m.S_INTERCONNECTORS)
    m.V_LOSS_LAMBDA = pyo.Var(
        m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, within=pyo.NonNegativeReals
    )

    # Trader tie-break slack variables
    m.V_TRADER_SLACK_1_GENERATOR = pyo.Var(
        m.S_TRADER_PRICE_TIED_GENERATORS, within=pyo.NonNegativeReals
    )
    m.V_TRADER_SLACK_2_GENERATOR = pyo.Var(
        m.S_TRADER_PRICE_TIED_GENERATORS, within=pyo.NonNegativeReals
    )

    m.V_TRADER_SLACK_1_LOAD = pyo.Var(m.S_TRADER_PRICE_TIED_LOADS, within=pyo.NonNegativeReals)
    m.V_TRADER_SLACK_2_LOAD = pyo.Var(m.S_TRADER_PRICE_TIED_LOADS, within=pyo.NonNegativeReals)

    m.V_CV_TRADER_BIDIRECTIONAL_MAX_ENERGY = pyo.Var(
        m.S_TRADERS_BIDIRECTIONAL, within=pyo.NonNegativeReals
    )
    m.V_CV_TRADER_BIDIRECTIONAL_MIN_ENERGY = pyo.Var(
        m.S_TRADERS_BIDIRECTIONAL, within=pyo.NonNegativeReals
    )

    return m


def define_cost_function_expressions(m):
    """Define expressions relating to trader and MNSP cost functions"""

    # Trader cost functions
    m.E_TRADER_COST_FUNCTION = pyo.Expression(
        m.S_TRADER_OFFERS,
        rule=lambda m, i, j, k: sum(
            m.P_TRADER_OFFER_COST_FACTOR[i, j, k]
            * m.P_TRADER_PRICE_BAND[i, j, k, b]
            * m.V_TRADER_OFFER[i, j, k, b]
            for b in m.S_BANDS
        ),
    )

    def mnsp_cost_function_rule(m, i, j):
        """MNSP cost function"""

        return sum(m.P_MNSP_PRICE_BAND[i, j, b] * m.V_MNSP_OFFER[i, j, b] for b in m.S_BANDS)

    # MNSP cost functions
    m.E_MNSP_COST_FUNCTION = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_cost_function_rule)

    return m


def define_generic_constraint_expressions(m, data):
    """Define generic constraint expressions"""

    # LHS terms in generic constraints
    terms = data["intermediate"]["generic_constraint_lhs_terms"]

    def generic_constraint_lhs_terms_rule(m, i):
        """Get LHS expression for a given Generic Constraint"""

        # Trader terms
        t_terms = sum(
            m.V_GC_TRADER[index] * factor for index, factor in terms[i]["traders"].items()
        )

        # Interconnector terms
        i_terms = sum(
            m.V_GC_INTERCONNECTOR[index] * factor
            for index, factor in terms[i]["interconnectors"].items()
        )

        # Region terms
        r_terms = sum(
            m.V_GC_REGION[index] * factor for index, factor in terms[i]["regions"].items()
        )

        return t_terms + i_terms + r_terms

    # Generic constraint LHS terms
    m.E_GC_LHS_TERMS = pyo.Expression(
        m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_terms_rule
    )

    return m


def define_constraint_violation_penalty_expressions(m):
    """Define expressions relating constraint violation penalties"""

    def generic_constraint_violation_rule(m, i):
        """Constraint violation penalty for generic constraint which is an inequality"""

        return m.P_CVF_GC[i] * m.V_CV[i]

    # Constraint violation penalty for inequality constraints
    m.E_CV_GC_PENALTY = pyo.Expression(
        m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_rule
    )

    def generic_constraint_lhs_violation_rule(m, i):
        """Constraint violation penalty for equality constraint"""

        return m.P_CVF_GC[i] * m.V_CV_LHS[i]

    # Constraint violation penalty for equality constraints
    m.E_CV_GC_LHS_PENALTY = pyo.Expression(
        m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_violation_rule
    )

    def generic_constraint_rhs_violation_rule(m, i):
        """Constraint violation penalty for equality constraint"""

        return m.P_CVF_GC[i] * m.V_CV_RHS[i]

    # Constraint violation penalty for equality constraints
    m.E_CV_GC_RHS_PENALTY = pyo.Expression(
        m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_violation_rule
    )

    def trader_offer_penalty_rule(m, i, j, k, b):
        """Penalty for band amount exceeding band bid amount"""

        return m.P_CVF_OFFER_PRICE * m.V_CV_TRADER_OFFER[i, j, k, b]

    # Constraint violation penalty for trader dispatched band amount exceeding bid amount
    m.E_CV_TRADER_OFFER_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_penalty_rule
    )

    def trader_capacity_penalty_rule(m, i, j, k):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_CAPACITY_PRICE * m.V_CV_TRADER_CAPACITY[i, j, k]

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_TRADER_CAPACITY_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_capacity_penalty_rule
    )

    def trader_uigf_surplus_penalty_rule(m, i, j):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_UIGF_SURPLUS_PRICE * m.V_CV_TRADER_UIGF_SURPLUS[i, j]

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_TRADER_UIGF_SURPLUS_PENALTY = pyo.Expression(
        m.S_TRADER_TOTAL_OFFERS, rule=trader_uigf_surplus_penalty_rule
    )

    def trader_ramp_up_penalty_rule(m, i):
        """Penalty for violating ramp down constraint"""

        return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_UP[i]

    # Penalty factor for ramp up rate violation
    m.E_CV_TRADER_RAMP_UP_PENALTY = pyo.Expression(m.S_TRADERS, rule=trader_ramp_up_penalty_rule)

    def trader_ramp_down_penalty_rule(m, i):
        """Penalty for violating ramp down constraint"""

        return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_DOWN[i]

    # Penalty factor for ramp down rate violation
    m.E_CV_TRADER_RAMP_DOWN_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_ramp_down_penalty_rule
    )

    def trader_fcas_bdu_scada_ramping_up_penalty_rule(m, i):
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP[i]

    m.E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_bdu_scada_ramping_up_penalty_rule
    )

    def trader_fcas_bdu_scada_ramping_down_penalty_rule(m, i):
        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN[i]

    m.E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN_PENALTY = pyo.Expression(
        m.S_TRADERS, rule=trader_fcas_bdu_scada_ramping_down_penalty_rule
    )

    # NOTE on FCAS violation pricing: every unit-FCAS violation below is priced at
    # P_CVF_AS_MAX_AVAIL_PRICE. The casefile also publishes P_CVF_AS_PROFILE_PRICE
    # and P_CVF_AS_ENABLEMENT_{MIN,MAX}_PRICE, and earlier revisions used those for
    # the ramping/capacity/enablement families respectively (see git history). Which
    # price NEMDE actually applies to which violation is an open question for the
    # ongoing objective-gap investigation.

    def trader_fcas_joint_ramping_up_rule(m, i, j, k):
        """Penalty for violating FCAS constraint - generator joint ramping up"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j, k]

    # Penalty factor for generator FCAS joint ramping up constraint
    m.E_CV_TRADER_FCAS_JOINT_RAMPING_UP = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_joint_ramping_up_rule
    )

    def trader_fcas_joint_ramping_down_rule(m, i, j, k):
        """Penalty for violating FCAS constraint - generator joint ramping down"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j, k]

    # Penalty factor for generator FCAS joint ramping up constraint
    m.E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_joint_ramping_down_rule
    )

    def trader_fcas_joint_capacity_rhs_rule(m, i, j, k):
        """Joint capacity constraint RHS of trapezium"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, k]

    # Constraint violation for joint capacity constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_joint_capacity_rhs_rule
    )

    def trader_fcas_joint_capacity_lhs_rule(m, i, j, k):
        """Joint capacity constraint LHS of trapezium"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, k]

    # Constraint violation for joint capacity constraint - LHS of trapezium
    m.E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_joint_capacity_lhs_rule
    )

    def trader_fcas_energy_regulating_rhs_rule(m, i, j, k):
        """Energy regulating FCAS constraint RHS of trapezium"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j, k]

    # Constraint violation for joint energy regulating FCAS constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_energy_regulating_rhs_rule
    )

    def trader_fcas_energy_regulating_lhs_rule(m, i, j, k):
        """Energy regulating FCAS constraint LHS of trapezium"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j, k]

    # Constraint violation for joint energy regulating FCAS constraint - RHS of trapezium
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_energy_regulating_lhs_rule
    )

    def trader_inflexibility_profile_rule(m, i):
        """Inflexibility profile penalty"""

        return m.P_CVF_FAST_START_PRICE * m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i]

    # Trader inflexibility price
    m.E_CV_TRADER_INFLEXIBILITY_PROFILE = pyo.Expression(
        m.S_TRADER_FAST_START, rule=trader_inflexibility_profile_rule
    )

    def trader_inflexibility_profile_lhs_rule(m, i):
        """Inflexibility profile penalty - LHS"""

        return m.P_CVF_FAST_START_PRICE * m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i]

    # Trader inflexibility price
    m.E_CV_TRADER_INFLEXIBILITY_PROFILE_LHS = pyo.Expression(
        m.S_TRADER_FAST_START, rule=trader_inflexibility_profile_lhs_rule
    )

    def trader_inflexibility_profile_rhs_rule(m, i):
        """Inflexibility profile penalty - RHS"""

        return m.P_CVF_FAST_START_PRICE * m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i]

    # Trader inflexibility price
    m.E_CV_TRADER_INFLEXIBILITY_PROFILE_RHS = pyo.Expression(
        m.S_TRADER_FAST_START, rule=trader_inflexibility_profile_rhs_rule
    )

    def trader_fcas_max_available_rule(m, i, j, k):
        """Max available violation for FCAS offer"""

        return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j, k]

    # Constraint violation for max available
    m.E_CV_TRADER_FCAS_MAX_AVAILABLE = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_max_available_rule
    )

    def trader_fcas_enablement_min_rule(m, i, j, k):
        """Enablement min violation for FCAS offer"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, k]

    # Constraint violation for max available
    m.E_CV_TRADER_FCAS_ENABLEMENT_MIN = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_enablement_min_rule
    )

    def trader_fcas_enablement_max_rule(m, i, j, k):
        """Enablement max violation for FCAS offer"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, k]

    # Constraint violation for max available
    m.E_CV_TRADER_FCAS_ENABLEMENT_MAX = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_enablement_max_rule
    )

    def mnsp_offer_penalty_rule(m, i, j, k):
        """Penalty for band amount exceeding band bid amount"""

        return m.P_CVF_MNSP_OFFER_PRICE * m.V_CV_MNSP_OFFER[i, j, k]

    # Constraint violation penalty for MNSP dispatched band amount exceeding bid amount
    m.E_CV_MNSP_OFFER_PENALTY = pyo.Expression(
        m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_penalty_rule
    )

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
    m.E_CV_MNSP_RAMP_DOWN_PENALTY = pyo.Expression(
        m.S_MNSP_OFFERS, rule=mnsp_ramp_down_penalty_rule
    )

    def interconnector_forward_penalty_rule(m, i):
        """Penalty for forward power flow exceeding max allowable flow"""

        return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_FORWARD[i]

    # Constraint violation penalty for forward interconnector limit being violated
    m.E_CV_INTERCONNECTOR_FORWARD_PENALTY = pyo.Expression(
        m.S_INTERCONNECTORS, rule=interconnector_forward_penalty_rule
    )

    def interconnector_reverse_penalty_rule(m, i):
        """Penalty for reverse power flow exceeding max allowable flow"""

        return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_REVERSE[i]

    # Constraint violation penalty for forward interconnector limit being violated
    m.E_CV_INTERCONNECTOR_REVERSE_PENALTY = pyo.Expression(
        m.S_INTERCONNECTORS, rule=interconnector_reverse_penalty_rule
    )

    def region_power_surplus_penalty_rule(m, i):
        """Surplus power in region"""

        return m.P_CVF_ENERGY_SURPLUS_PRICE * m.V_CV_REGION_GENERATION_SURPLUS[i]

    # Constraint violation penalty for region energy surplus
    m.E_CV_REGION_SURPLUS_POWER = pyo.Expression(
        m.S_REGIONS, rule=region_power_surplus_penalty_rule
    )

    def region_power_deficit_penalty_rule(m, i):
        """Deficit power in region"""

        return m.P_CVF_ENERGY_DEFICIT_PRICE * m.V_CV_REGION_GENERATION_DEFICIT[i]

    # Constraint violation penalty for region energy surplus
    m.E_CV_REGION_DEFICIT_POWER = pyo.Expression(
        m.S_REGIONS, rule=region_power_deficit_penalty_rule
    )

    m.E_CV_TRADER_BIDIRECTIONAL_MAX_ENERGY = pyo.Expression(
        m.S_TRADERS_BIDIRECTIONAL,
        rule=lambda m, i: m.P_CVF_BDU_MAX_ENERGY_PRICE * m.V_CV_TRADER_BIDIRECTIONAL_MAX_ENERGY[i],
    )

    m.E_CV_TRADER_BIDIRECTIONAL_MIN_ENERGY = pyo.Expression(
        m.S_TRADERS_BIDIRECTIONAL,
        rule=lambda m, i: m.P_CVF_BDU_MIN_ENERGY_PRICE * m.V_CV_TRADER_BIDIRECTIONAL_MIN_ENERGY[i],
    )

    # Sum of all constraint violation penalties
    m.E_CV_TOTAL_PENALTY = pyo.Expression(
        expr=sum(m.E_CV_GC_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
        + sum(m.E_CV_GC_LHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
        + sum(m.E_CV_GC_RHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
        + sum(
            m.E_CV_TRADER_OFFER_PENALTY[i, j, k, b]
            for i, j, k in m.S_TRADER_OFFERS
            for b in m.S_BANDS
        )
        + sum(m.E_CV_TRADER_CAPACITY_PENALTY[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_UIGF_SURPLUS_PENALTY[i] for i in m.S_TRADER_TOTAL_OFFERS)
        + sum(m.E_CV_TRADER_RAMP_UP_PENALTY[i] for i in m.S_TRADERS)
        + sum(m.E_CV_TRADER_RAMP_DOWN_PENALTY[i] for i in m.S_TRADERS)
        + sum(m.E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP_PENALTY[i] for i in m.S_TRADERS)
        + sum(m.E_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN_PENALTY[i] for i in m.S_TRADERS)
        + sum(m.E_CV_TRADER_FCAS_JOINT_RAMPING_UP[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i] for i in m.S_TRADER_OFFERS)
        + sum(m.E_CV_TRADER_FCAS_MAX_AVAILABLE[i] for i in m.S_TRADER_OFFERS)
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
        + sum(m.E_CV_TRADER_BIDIRECTIONAL_MAX_ENERGY[i] for i in m.S_TRADERS_BIDIRECTIONAL)
        + sum(m.E_CV_TRADER_BIDIRECTIONAL_MIN_ENERGY[i] for i in m.S_TRADERS_BIDIRECTIONAL)
    )

    return m


def define_mnsp_expressions(m):
    """Expressions for MNSP loss model"""

    def mnsp_from_cp_flow_rule(m, i):
        """Net flow at FromRegion connection point for MNSP loss model"""

        from_region = m.P_INTERCONNECTOR_FROM_REGION[i]

        return m.V_GC_INTERCONNECTOR[i] + (
            m.V_LOSS[i] * m.P_MNSP_REGION_LOSS_INDICATOR[i, from_region]
        )

    # MNSP FromRegion connection point flow
    m.E_MNSP_FROM_CP_FLOW = pyo.Expression(m.S_MNSPS, rule=mnsp_from_cp_flow_rule)

    def mnsp_to_cp_flow_rule(m, i):
        """Net flow at ToRegion connection point for MNSP loss model"""

        to_region = m.P_INTERCONNECTOR_TO_REGION[i]

        return m.V_GC_INTERCONNECTOR[i] - (
            m.V_LOSS[i] * m.P_MNSP_REGION_LOSS_INDICATOR[i, to_region]
        )

    # MNSP ToRegion connection point flow
    m.E_MNSP_TO_CP_FLOW = pyo.Expression(m.S_MNSPS, rule=mnsp_to_cp_flow_rule)

    def mnsp_from_region_loss_rule(m, i):
        """MNSP loss allocated to given region"""

        return ((m.P_MNSP_FROM_REGION_LF_EXPORT[i] - 1) * m.V_MNSP_FROM_REGION_EXPORT[i]) + (
            m.P_MNSP_FROM_REGION_LF_IMPORT[i] - 1
        ) * m.V_MNSP_FROM_REGION_IMPORT[i]

    # MNSP from region loss
    m.E_MNSP_FROM_REGION_LOSS = pyo.Expression(m.S_MNSPS, rule=mnsp_from_region_loss_rule)

    def mnsp_to_region_loss_rule(m, i):
        """MNSP loss allocated to given region"""

        return ((m.P_MNSP_TO_REGION_LF_EXPORT[i] - 1) * m.V_MNSP_TO_REGION_EXPORT[i] * -1) + (
            m.P_MNSP_TO_REGION_LF_IMPORT[i] - 1
        ) * m.V_MNSP_TO_REGION_IMPORT[i] * -1

    # MNSP from region loss
    m.E_MNSP_TO_REGION_LOSS = pyo.Expression(m.S_MNSPS, rule=mnsp_to_region_loss_rule)

    return m


def define_aggregate_power_expressions(m):
    """Compute aggregate demand and generation in each NEM region"""

    def region_dispatched_generation_rule(m, r):
        """Available energy offers in given region"""

        return sum(
            m.V_TRADER_OFFER[i, j, k, b]
            for i, j, k in m.S_TRADER_OFFERS
            for b in m.S_BANDS
            if ((j == "ENOF") or ((j == "BDOF") and (k == "GEN"))) and (m.P_TRADER_REGION[i] == r)
        )

    # Total generation dispatched in a given region
    m.E_REGION_DISPATCHED_GENERATION = pyo.Expression(
        m.S_REGIONS, rule=region_dispatched_generation_rule
    )

    def region_dispatched_load_rule(m, r):
        """Available load offers in given region"""

        return sum(
            m.V_TRADER_OFFER[i, j, k, b]
            for i, j, k in m.S_TRADER_OFFERS
            for b in m.S_BANDS
            if ((j in ["LDOF", "DROF"]) or ((j == "BDOF") and (k == "LOAD")))
            and (m.P_TRADER_REGION[i] == r)
        )

    # Total dispatched load in a given region
    m.E_REGION_DISPATCHED_LOAD = pyo.Expression(m.S_REGIONS, rule=region_dispatched_load_rule)

    def region_initial_scheduled_load(m, r):
        """Total initial scheduled load in a given region"""

        # NOTE: BDOF is deliberately absent. For some reason bidirectional-unit load
        # is not included in initial scheduled load, so only LDOF and DROF count.
        # (This used to admit BDOF into the outer test and then silently drop it,
        # which read as an oversight rather than as the deliberate exclusion it is.)

        total = 0
        for i, j in m.S_TRADER_TOTAL_OFFERS:
            if (
                j in ["LDOF", "DROF"]
                and (r == m.P_TRADER_REGION[i])
                and (m.P_TRADER_SEMI_DISPATCH_STATUS[i] == "0")
            ):
                total += m.P_TRADER_EFFECTIVE_INITIAL_MW[i]

        return total

    # Region initial scheduled load
    m.E_REGION_INITIAL_SCHEDULED_LOAD = pyo.Expression(
        m.S_REGIONS, rule=region_initial_scheduled_load
    )

    def region_initial_allocated_loss(m, r):
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
            initial_mw = m.P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW[i]

            # Loss applied to sending end
            if (r == from_region) and (mnsp_status == "1") and (initial_mw >= 0):
                region_interconnector_loss += loss

            # Loss applied to sending end - negative flow means no loss allocated to FromRegion
            elif (r == from_region) and (mnsp_status == "1") and (initial_mw < 0):
                pass

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == from_region) and (mnsp_status == "0"):
                region_interconnector_loss += loss * loss_share

            # Flow is positive so loss applied to FromRegion
            elif (r == to_region) and (mnsp_status == "1") and (initial_mw >= 0):
                pass

            # Flow is negative so loss applied to ToRegion
            elif (r == to_region) and (mnsp_status == "1") and (initial_mw < 0):
                region_interconnector_loss += loss

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == to_region) and (mnsp_status == "0"):
                region_interconnector_loss += loss * (1 - loss_share)

            else:
                raise Exception("Unhandled case:", r, from_region, to_region)

        return region_interconnector_loss

    # Region initial allocated losses
    m.E_REGION_INITIAL_ALLOCATED_LOSS = pyo.Expression(
        m.S_REGIONS, rule=region_initial_allocated_loss
    )

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
            initial_mw = m.P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW[i]

            # Loss applied to sending end
            if (r == from_region) and (mnsp_status == "1") and (initial_mw >= 0):
                region_interconnector_loss += loss

            # Loss applied to sending end - negative flow means no loss
            # allocated to FromRegion
            elif (r == from_region) and (mnsp_status == "1") and (initial_mw < 0):
                pass

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == from_region) and (mnsp_status == "0"):
                region_interconnector_loss += loss * loss_share

            # Flow is positive so loss applied to FromRegion
            elif (r == to_region) and (mnsp_status == "1") and (initial_mw >= 0):
                pass

            # Flow is negative so loss applied to ToRegion
            elif (r == to_region) and (mnsp_status == "1") and (initial_mw < 0):
                region_interconnector_loss += loss

            # Non-MNSP interconnector has loss allocated according to LossShare
            elif (r == to_region) and (mnsp_status == "0"):
                region_interconnector_loss += loss * (1 - loss_share)

            else:
                raise Exception("Unhandled case:", r, from_region, to_region)

        return region_interconnector_loss

    # Region allocated loss at end of dispatch interval
    m.E_REGION_ALLOCATED_LOSS = pyo.Expression(m.S_REGIONS, rule=region_allocated_loss_rule)

    def region_initial_mnsp_loss(m, r):
        """
        Get estimate of MNSP loss allocated to given region

        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad)
        where load is varied at the connection point. Must compute the load the
        connection point for the MNSP - this will be positive or negative
        (i.e. generation) depending on the direction of flow over the
        interconnector.

        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to
        compute the effective load at the connection point in order to compute
        the loss. Note the loss may be positive or negative depending on the
        MLF and the effective load at the connection point.
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            # Initial MW and solution flow
            initial_mw = m.P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW[i]

            to_lf_export = m.P_MNSP_TO_REGION_LF_EXPORT[i]
            to_lf_import = m.P_MNSP_TO_REGION_LF_IMPORT[i]

            from_lf_import = m.P_MNSP_FROM_REGION_LF_IMPORT[i]
            from_lf_export = m.P_MNSP_FROM_REGION_LF_EXPORT[i]

            # Initial loss estimate over interconnector
            loss = m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i]

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
                raise Exception("Unhandled case:", r, from_region, to_region, initial_mw)

        return total

    # Region initial allocated MNSP losses
    m.E_REGION_INITIAL_MNSP_LOSS = pyo.Expression(m.S_REGIONS, rule=region_initial_mnsp_loss)

    def region_mnsp_loss_rule(m, r):
        """
        Get estimate of MNSP loss allocated to given region

        MLFs used to compute loss. MLF equation: MLF = 1 + (DeltaLoss / DeltaLoad)
        where load is varied at the connection point. Must compute the load the
        connection point for the MNSP - this will be positive or negative
        (i.e. generation) depending on the direction of flow over the
        interconnector.

        From the MLF equation: DeltaLoss = (MLF - 1) x DeltaLoad. So need to
        compute the effective load at the connection point in order to compute
        the loss. Note the loss may be positive or negative depending on the
        MLF and the effective load at the connection point.
        """

        total = 0
        for i in m.S_MNSPS:
            from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_region = m.P_INTERCONNECTOR_TO_REGION[i]

            if r not in [from_region, to_region]:
                continue

            if r == from_region:
                total += m.E_MNSP_FROM_REGION_LOSS[i]

            elif r == to_region:
                total += m.E_MNSP_TO_REGION_LOSS[i]

            else:
                raise Exception("Unexpected region:", r)

        return total

    # Region MNSP loss at end of dispatch interval
    m.E_REGION_MNSP_LOSS = pyo.Expression(m.S_REGIONS, rule=region_mnsp_loss_rule)

    def region_fixed_demand_rule(m, r):
        """
        Check region fixed demand calculation - demand at start of dispatch
        interval
        """

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
        """
        Region cleared demand rule - generation in region = cleared demand
        at end of dispatch interval
        """

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
        """
        Export from region - excludes MNSP and allocated interconnector
        losses
        """

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

            # Positive flow indicates import to ToRegion (take negative to get
            # export from ToRegion)
            elif r == to_region:
                interconnector_export -= flow

            else:
                pass

        return interconnector_export

    # Net export out of region over interconnector - excludes allocated losses
    m.E_REGION_INTERCONNECTOR_EXPORT = pyo.Expression(
        m.S_REGIONS, rule=region_interconnector_export
    )

    def region_net_export_rule(m, r):
        """
        Net export out of region including allocated losses

        NetExport = InterconnectorExport + RegionInterconnectorLoss + RegionMNSPLoss
        """

        return (
            m.E_REGION_INTERCONNECTOR_EXPORT[r]
            + m.E_REGION_ALLOCATED_LOSS[r]
            + m.E_REGION_MNSP_LOSS[r]
        )

    # Region net export - includes MNSP and allocated interconnector losses
    m.E_REGION_NET_EXPORT = pyo.Expression(m.S_REGIONS, rule=region_net_export_rule)

    return m


def define_fcas_expressions(m):
    """Define FCAS expressions"""

    def fcas_effective_enablement_max(m, i, j, k):
        """Effective enablement max"""

        if j not in ["L5RE", "R5RE"]:
            return None

        # Offer enablement max
        enablement_max = m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j, k]

        # Upper AGC limit
        if i in m.P_TRADER_HMW.keys():
            agc_up_limit = m.P_TRADER_HMW[i]
        else:
            agc_up_limit = None

        # UIGF from semi-dispatchable plant
        if m.P_TRADER_SEMI_DISPATCH_STATUS[i] == "1":
            uigf = m.P_TRADER_UIGF[i]
        else:
            uigf = None

        # Terms used to determine effective enablement max
        terms = [enablement_max, agc_up_limit, uigf]

        return min([i for i in terms if i is not None])

    # Effective enablement max
    m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX = pyo.Expression(
        m.S_TRADER_OFFERS, rule=fcas_effective_enablement_max
    )

    def fcas_effective_enablement_min(m, i, j, k):
        """Effective enablement min"""

        if j not in ["L5RE", "R5RE"]:
            return None

        # Offer enablement min
        enablement_min = m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j, k]

        # Upper AGC limit
        if i in m.P_TRADER_LMW.keys():
            agc_down_limit = m.P_TRADER_LMW[i]
        else:
            agc_down_limit = None

        # Terms used to determine effective enablement min
        terms = [enablement_min, agc_down_limit]

        return max([i for i in terms if i is not None])

    # Effective enablement min
    m.E_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN = pyo.Expression(
        m.S_TRADER_OFFERS, rule=fcas_effective_enablement_min
    )

    return m


def define_tie_breaking_expressions(m):
    """Tie-breaking expressions"""

    # Tie break cost TODO: Note that tie-break price of 1e-4 gives better results than 1e-6.
    m.E_TRADER_TIE_BREAK_COST_GENERATORS = pyo.Expression(
        expr=sum(
            m.P_TIE_BREAK_PRICE
            * m.P_CVF_VOLL
            * (m.V_TRADER_SLACK_1_GENERATOR[i] + m.V_TRADER_SLACK_2_GENERATOR[i])
            for i in m.S_TRADER_PRICE_TIED_GENERATORS
        )
    )

    m.E_TRADER_TIE_BREAK_COST_LOADS = pyo.Expression(
        expr=sum(
            m.P_TIE_BREAK_PRICE
            * m.P_CVF_VOLL
            * (m.V_TRADER_SLACK_1_LOAD[i] + m.V_TRADER_SLACK_2_LOAD[i])
            for i in m.S_TRADER_PRICE_TIED_LOADS
        )
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

    def trader_offer_rule(m, i, j, k, b):
        """Band output must be non-negative and less than the max offered amount for that band"""

        return (
            m.V_TRADER_OFFER[i, j, k, b]
            <= m.P_TRADER_QUANTITY_BAND[i, j, k, b] + m.V_CV_TRADER_OFFER[i, j, k, b]
        )

    # Bounds on quantity band variables for traders
    m.C_TRADER_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_rule)

    def trader_capacity_rule(m, i, j, k):
        """Constrain max available output"""

        # UIGF constrains max output for semi-dispatchable plant
        if (i in m.S_TRADERS_SEMI_DISPATCH) and (j == "ENOF"):
            return (
                m.E_TRADER_TOTAL_OFFER[i, j, k]
                <= m.P_TRADER_UIGF[i] + m.V_CV_TRADER_UIGF_SURPLUS[i, j]
            )
        else:
            return (
                m.E_TRADER_TOTAL_OFFER[i, j, k]
                <= m.P_TRADER_MAX_AVAILABLE[i, j, k] + m.V_CV_TRADER_CAPACITY[i, j, k]
            )

    # Ensure dispatch is constrained by max available offer amount
    m.C_TRADER_MAX_AVAIL = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_capacity_rule)

    def mnsp_total_offer_rule(m, i, j):
        """Link quantity band offers to total offer made by MNSP for each offer type"""

        return m.V_MNSP_TOTAL_OFFER[i, j] == sum(m.V_MNSP_OFFER[i, j, k] for k in m.S_BANDS)

    # Linking individual quantity band offers to total amount offered by MNSP
    m.C_MNSP_TOTAL_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_total_offer_rule)

    def mnsp_offer_rule(m, i, j, k):
        """Band output must be non-negative and less than the max offered amount for that band"""

        return (
            m.V_MNSP_OFFER[i, j, k] <= m.P_MNSP_QUANTITY_BAND[i, j, k] + m.V_CV_MNSP_OFFER[i, j, k]
        )

    # Bounds on quantity band variables for MNSPs
    m.C_MNSP_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_rule)

    def mnsp_capacity_rule(m, i, j):
        """Constrain max available output"""

        return (
            m.V_MNSP_TOTAL_OFFER[i, j] <= m.P_MNSP_MAX_AVAILABLE[i, j] + m.V_CV_MNSP_CAPACITY[i, j]
        )

    # Ensure dispatch is constrained by max available offer amount
    m.C_MNSP_CAPACITY = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_capacity_rule)

    return m


def define_bidirectional_energy_constraints(m):
    """Bidirectional energy constraints

    AEMO's Schedule of Constraint Violation Penalty Factors documents the Profiled
    Max/Min Energy Limit constraints (SurplusProfiledEnergy / DeficitProfiledEnergy)
    as "Pre-Dispatch Only" - they are not part of the 5-minute dispatch LP, so this
    dispatch-only model never enforces them.
    """

    def bdu_max_energy_rule(_m, _i):
        return pyo.Constraint.Skip

    m.C_TRADER_BIDIRECTIONAL_MAX_ENERGY = pyo.Constraint(
        m.S_TRADERS_BIDIRECTIONAL, rule=bdu_max_energy_rule
    )

    def bdu_min_energy_rule(_m, _i):
        return pyo.Constraint.Skip

    m.C_TRADER_BIDIRECTIONAL_MIN_ENERGY = pyo.Constraint(
        m.S_TRADERS_BIDIRECTIONAL, rule=bdu_min_energy_rule
    )

    return m


def define_generic_constraints(m):
    """
    Construct generic constraints. Also include constraints linking variables
    in objective function to variables in Generic Constraints.
    """

    def trader_variable_link_rule(m, i, j):
        """
        Link generic constraint trader variables to objective function
        variables
        """

        # GC trader index may include IDs that are not in Trader-Offer index.
        # This seems logically inconsistent. If this occurs don't create linking
        # constraint - will raise KeyError otherwise.
        if (i, j) in m.E_TRADER_TARGET.keys():
            return m.E_TRADER_TARGET[i, j] == m.V_GC_TRADER[i, j]
        else:
            return pyo.Constraint.Skip

    # Link between total power output and quantity band output
    m.C_TRADER_VARIABLE_LINK = pyo.Constraint(m.S_GC_TRADER_VARS, rule=trader_variable_link_rule)

    def region_variable_link_rule(m, i, j):
        """Link total offer amount for each bid type to region variables"""

        return (
            sum(
                m.E_TRADER_TARGET[q, r]
                for q, r in m.S_TRADER_TOTAL_OFFERS
                if (m.P_TRADER_REGION[q] == i) and (r == j)
            )
            == m.V_GC_REGION[i, j]
        )

    # Link between region variables and the trader components constituting those variables
    m.C_REGION_VARIABLE_LINK = pyo.Constraint(m.S_GC_REGION_VARS, rule=region_variable_link_rule)

    def mnsp_variable_link_rule(m, i):
        """Link generic constraint MNSP variables to objective function variables"""

        # From and to regions for a given MNSP
        from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
        to_region = m.P_INTERCONNECTOR_TO_REGION[i]

        # TODO: Taking difference between 'to' and 'from' region. Think this is correct.
        return (
            m.V_GC_INTERCONNECTOR[i]
            == m.V_MNSP_TOTAL_OFFER[i, to_region] - m.V_MNSP_TOTAL_OFFER[i, from_region]
        )

    # Link between total power output and quantity band output
    m.C_MNSP_VARIABLE_LINK = pyo.Constraint(m.S_MNSPS, rule=mnsp_variable_link_rule)

    def generic_constraint_rule(m, c):
        """NEMDE Generic Constraints"""

        # Type of generic constraint (LE, GE, EQ)
        if m.P_GC_TYPE[c] == "LE":
            return m.E_GC_LHS_TERMS[c] <= m.P_GC_RHS[c] + m.V_CV[c]
        elif m.P_GC_TYPE[c] == "GE":
            return m.E_GC_LHS_TERMS[c] + m.V_CV[c] >= m.P_GC_RHS[c]
        elif m.P_GC_TYPE[c] == "EQ":
            return m.E_GC_LHS_TERMS[c] + m.V_CV_LHS[c] == m.P_GC_RHS[c] + m.V_CV_RHS[c]
        else:
            raise Exception(f"Unexpected constraint type: {m.P_GC_TYPE[c]}")

    # Generic constraints
    m.C_GENERIC_CONSTRAINT = pyo.Constraint(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rule)

    return m


def define_unit_constraints(m):
    """Construct ramp rate constraints for units"""

    def trader_ramp_up_rate_rule(m, i, j):
        """Ramp up rate limit for ENOF and LDOF offers"""

        # Only construct ramp-rate constraint for energy offers
        if j not in ["ENOF", "LDOF", "DROF", "BDOF"]:
            return pyo.Constraint.Skip

        # Unit on fixed startup profile. T2 ramp rate applies while in T2, then
        # SCADA ramp rate for rest of interval
        if (i in m.P_TRADER_CURRENT_MODE.keys()) and (m.P_TRADER_CURRENT_MODE[i].value == 1):
            # Total ramp up capability when unit initially in mode 1
            ramp_up_capability = get_mode_one_ramping_capability(
                t1=m.P_TRADER_T1[i],
                t2=m.P_TRADER_T2[i],
                min_loading=m.P_TRADER_MIN_LOADING_MW[i],
                current_mode_time=m.P_TRADER_CURRENT_MODE_TIME[i].value,
                effective_ramp_rate=m.P_TRADER_EFFECTIVE_RAMP_UP_RATE[i],
            )

            # Note: InitialMW = 0 if CurrentMode is T1 (unit is synchronising)
            return m.E_TRADER_TARGET[i, j] <= ramp_up_capability + m.V_CV_TRADER_RAMP_UP[i]

        elif (i in m.P_TRADER_CURRENT_MODE.keys()) and (m.P_TRADER_CURRENT_MODE[i].value == 2):
            # Initial MW and ramping capability if in mode 2
            initial_mw = get_mode_two_initial_mw(
                t2=m.P_TRADER_T2[i],
                min_loading=m.P_TRADER_MIN_LOADING_MW[i],
                current_mode_time=m.P_TRADER_CURRENT_MODE_TIME[i].value,
            )

            # Ramp up capability
            ramp_up_capability = get_mode_two_ramping_capability(
                t2=m.P_TRADER_T2[i],
                min_loading=m.P_TRADER_MIN_LOADING_MW[i],
                current_mode_time=m.P_TRADER_CURRENT_MODE_TIME[i].value,
                effective_ramp_rate=m.P_TRADER_EFFECTIVE_RAMP_UP_RATE[i],
            )

            return (
                m.E_TRADER_TARGET[i, j]
                <= initial_mw + ramp_up_capability + m.V_CV_TRADER_RAMP_UP[i]
            )

        else:
            return (
                m.E_TRADER_TARGET[i, j] - m.P_TRADER_EFFECTIVE_INITIAL_MW[i]
                <= (m.P_TRADER_EFFECTIVE_RAMP_UP_RATE[i] / 12) + m.V_CV_TRADER_RAMP_UP[i]
            )

    # Ramp up rate limit
    m.C_TRADER_RAMP_UP_RATE = pyo.Constraint(m.S_TRADER_TOTAL_OFFERS, rule=trader_ramp_up_rate_rule)

    def trader_ramp_down_rate_rule(m, i, j):
        """Ramp down rate limit for ENOF and LDOF offers"""

        # Only construct ramp-rate constraint for energy offers
        # if (j != "ENOF") and (j != "LDOF"):
        if j not in ["ENOF", "LDOF", "DROF", "BDOF"]:
            return pyo.Constraint.Skip

        return m.E_TRADER_TARGET[i, j] - m.P_TRADER_EFFECTIVE_INITIAL_MW[
            i
        ] + m.V_CV_TRADER_RAMP_DOWN[i] >= -(m.P_TRADER_EFFECTIVE_RAMP_DN_RATE[i] / 12)

    # Ramp down rate limit
    m.C_TRADER_RAMP_DOWN_RATE = pyo.Constraint(
        m.S_TRADER_TOTAL_OFFERS, rule=trader_ramp_down_rate_rule
    )

    return m


def define_region_constraints(m):
    """Define power balance constraint for each region, and constrain flows on interconnectors"""

    def power_balance_rule(m, r):
        """
        Power balance for each region

        FixedDemand + DispatchedLoad + NetExport = DispatchedGeneration
        """

        return (
            m.E_REGION_DISPATCHED_GENERATION[r] + m.V_CV_REGION_GENERATION_DEFICIT[r]
            == m.E_REGION_FIXED_DEMAND[r]
            + m.E_REGION_DISPATCHED_LOAD[r]
            + m.E_REGION_NET_EXPORT[r]
            + m.V_CV_REGION_GENERATION_SURPLUS[r]
        )

    # Power balance in each region
    m.C_POWER_BALANCE = pyo.Constraint(m.S_REGIONS, rule=power_balance_rule)

    return m


def define_interconnector_constraints(m):
    """Define power flow limits on interconnectors"""

    def interconnector_forward_flow_rule(m, i):
        """Constrain forward power flow over interconnector"""

        return (
            m.V_GC_INTERCONNECTOR[i]
            <= m.P_INTERCONNECTOR_UPPER_LIMIT[i] + m.V_CV_INTERCONNECTOR_FORWARD[i]
        )

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_FORWARD_FLOW = pyo.Constraint(
        m.S_INTERCONNECTORS, rule=interconnector_forward_flow_rule
    )

    def interconnector_reverse_flow_rule(m, i):
        """Constrain reverse power flow over interconnector"""

        return (
            m.V_GC_INTERCONNECTOR[i] + m.V_CV_INTERCONNECTOR_REVERSE[i]
            >= -m.P_INTERCONNECTOR_LOWER_LIMIT[i]
        )

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_REVERSE_FLOW = pyo.Constraint(
        m.S_INTERCONNECTORS, rule=interconnector_reverse_flow_rule
    )

    return m


def define_mnsp_constraints(m):
    """Define MNSP ramping constraints"""

    def mnsp_ramp_up_rule(m, i, j):
        """MNSP ramp-up constraint"""

        return (
            m.V_MNSP_TOTAL_OFFER[i, j]
            <= m.P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW[i]
            + (m.P_MNSP_RAMP_UP_RATE[i, j] / 12)
            + m.V_CV_MNSP_RAMP_UP[i, j]
        )

    # MNSP ramp up constraint
    m.C_MNSP_RAMP_UP = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_ramp_up_rule)

    def mnsp_ramp_down_rule(m, i, j):
        """MNSP ramp-down constraint"""

        return m.V_MNSP_TOTAL_OFFER[i, j] + m.V_CV_MNSP_RAMP_DOWN[
            i, j
        ] >= m.P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW[i] - (m.P_MNSP_RAMP_DOWN_RATE[i, j] / 12)

    # MNSP ramp down constraint
    m.C_MNSP_RAMP_DOWN = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_ramp_down_rule)

    def mnsp_flow_direction_1_rule(m, i):
        """Indicator constraint 1 to define MNSP flow direction"""

        return m.V_GC_INTERCONNECTOR[i] >= -1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])

    # Constraint used to get flow direction for MNSP
    m.C_MNSP_FLOW_DIRECTION_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_flow_direction_1_rule)

    def mnsp_flow_direction_2_rule(m, i):
        """Indicator constraint 2 to define MNSP flow direction"""

        return m.V_GC_INTERCONNECTOR[i] <= 1000 * m.V_MNSP_FLOW_DIRECTION[i]

    # Constraint used to get flow direction for MNSP
    m.C_MNSP_FLOW_DIRECTION_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_flow_direction_2_rule)

    def mnsp_from_export_flow_1_rule(m, i):
        """From region export flow rule 1"""

        return (
            m.E_MNSP_FROM_CP_FLOW[i] - (1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]))
            <= m.V_MNSP_FROM_REGION_EXPORT[i]
        )

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_1_rule)

    def mnsp_from_export_flow_2_rule(m, i):
        """From region export flow rule 2"""

        return m.V_MNSP_FROM_REGION_EXPORT[i] <= m.E_MNSP_FROM_CP_FLOW[i] + (
            1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])
        )

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_2 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_2_rule)

    def mnsp_from_export_flow_3_rule(m, i):
        """From region export flow rule 3"""

        return -1000 * m.V_MNSP_FLOW_DIRECTION[i] <= m.V_MNSP_FROM_REGION_EXPORT[i]

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_3 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_3_rule)

    def mnsp_from_export_flow_4_rule(m, i):
        """From region export flow rule 4"""

        return m.V_MNSP_FROM_REGION_EXPORT[i] <= 1000 * m.V_MNSP_FLOW_DIRECTION[i]

    # Constraint used to determine FromRegionExport flow
    m.C_MNSP_FROM_REGION_EXPORT_4 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_export_flow_4_rule)

    def mnsp_from_import_flow_1_rule(m, i):
        """From region import flow 1"""

        return (
            m.E_MNSP_FROM_CP_FLOW[i] - (1000 * m.V_MNSP_FLOW_DIRECTION[i])
            <= m.V_MNSP_FROM_REGION_IMPORT[i]
        )

    # Constraint used to determine FromRegionImport flow
    m.C_MNSP_FROM_REGION_IMPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_from_import_flow_1_rule)

    def mnsp_from_import_flow_2_rule(m, i):
        """From region import flow 2"""

        return m.V_MNSP_FROM_REGION_IMPORT[i] <= m.E_MNSP_FROM_CP_FLOW[i] + (
            1000 * m.V_MNSP_FLOW_DIRECTION[i]
        )

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

        return (
            m.E_MNSP_TO_CP_FLOW[i] - (1000 * m.V_MNSP_FLOW_DIRECTION[i])
            <= m.V_MNSP_TO_REGION_EXPORT[i]
        )

    # MNSP ToRegion export flow condition 1
    m.C_MNSP_TO_REGION_EXPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_export_flow_1_rule)

    def mnsp_to_export_flow_2_rule(m, i):
        """ToRegion Export flow 2"""

        return m.V_MNSP_TO_REGION_EXPORT[i] <= m.E_MNSP_TO_CP_FLOW[i] + (
            1000 * m.V_MNSP_FLOW_DIRECTION[i]
        )

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

        return (
            m.E_MNSP_TO_CP_FLOW[i] - (1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i]))
            <= m.V_MNSP_TO_REGION_IMPORT[i]
        )

    # MNSP ToRegion import flow condition 1
    m.C_MNSP_TO_REGION_IMPORT_1 = pyo.Constraint(m.S_MNSPS, rule=mnsp_to_import_flow_1_rule)

    def mnsp_to_import_flow_2_rule(m, i):
        """ToRegion import flow 2"""

        return m.V_MNSP_TO_REGION_IMPORT[i] <= m.E_MNSP_TO_CP_FLOW[i] + (
            1000 * (1 - m.V_MNSP_FLOW_DIRECTION[i])
        )

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

    # The four MNSP region loss-allocation conditions (ensuring exactly one of the
    # From/To region losses is non-zero) were written and then commented out; they
    # are not part of the live model. See git history for the formulation.

    return m


def get_upper_slope_coefficient(enablement_max, high_breakpoint, max_avail):
    """Get upper slope coefficient for FCAS trapezium"""

    if max_avail == 0:
        return 0
    else:
        return (enablement_max - high_breakpoint) / max_avail


def get_lower_slope_coefficient(enablement_min, low_breakpoint, max_avail):
    """Get lower slope coefficient for FCAS trapezium"""

    if max_avail == 0:
        return 0
    else:
        return (low_breakpoint - enablement_min) / max_avail


def define_fcas_constraints(m):
    """FCAS constraints"""

    # ----------------------------------------------
    # Joint ramping constraints (raise regulation)
    # ----------------------------------------------
    m.C_FCAS_JOINT_RAMPING_RAISE_GENERATOR = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TARGET[i, "ENOF"] + m.E_TRADER_TARGET[i, "R5RE"]
            <= m.P_TRADER_EFFECTIVE_INITIAL_MW[i]
            + (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, "R5RE", None]
        ),
    )

    m.C_FCAS_JOINT_RAMPING_RAISE_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TARGET[i, "LDOF"]
            - m.E_TRADER_TARGET[i, "R5RE"]
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, "R5RE", None]
            >= m.P_TRADER_EFFECTIVE_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)
        ),
    )

    m.C_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_GEN = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_GEN_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "GEN"] + m.E_TRADER_TOTAL_OFFER[i, "R5RE", "GEN"]
            <= m.P_TRADER_EFFECTIVE_INITIAL_MW[i]
            + (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, "R5RE", "GEN"]
        ),
    )

    m.C_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_LOAD_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "LOAD"]
            - m.E_TRADER_TOTAL_OFFER[i, "R5RE", "LOAD"]
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, "R5RE", "LOAD"]
            >= m.P_TRADER_EFFECTIVE_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)
        ),
    )

    # ----------------------------------------------
    # Joint ramping constraints (lower regulation)
    # ----------------------------------------------
    m.C_FCAS_JOINT_RAMPING_LOWER_GENERATOR = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TARGET[i, "ENOF"]
            - m.E_TRADER_TARGET[i, "L5RE"]
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, "L5RE", None]
            >= m.P_TRADER_EFFECTIVE_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)
        ),
    )

    m.C_FCAS_JOINT_RAMPING_LOWER_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TARGET[i, "LDOF"] + m.E_TRADER_TARGET[i, "L5RE"]
            <= m.P_TRADER_EFFECTIVE_INITIAL_MW[i]
            + (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12)
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, "L5RE", None]
        ),
    )

    m.C_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_GEN = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_GEN_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "GEN"]
            - m.E_TRADER_TOTAL_OFFER[i, "L5RE", "GEN"]
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, "L5RE", "GEN"]
            >= m.P_TRADER_EFFECTIVE_INITIAL_MW[i] - (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)
        ),
    )

    m.C_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_LOAD_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "LOAD"] + m.E_TRADER_TOTAL_OFFER[i, "L5RE", "LOAD"]
            <= m.P_TRADER_EFFECTIVE_INITIAL_MW[i]
            + (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)
            + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, "L5RE", "LOAD"]
        ),
    )

    # ----------------------------------------------
    # Joint capacity constraints (upper slope)
    # ----------------------------------------------
    m.C_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITH_R5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITH_R5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.E_TRADER_TARGET[i, "R5RE"]
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITHOUT_R5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITHOUT_R5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITH_L5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITH_L5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.E_TRADER_TARGET[i, "L5RE"]
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITHOUT_L5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITHOUT_L5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITH_R5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITH_R5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.E_TRADER_TARGET[i, "R5RE"]
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITHOUT_R5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITHOUT_R5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RHS[i, j, None]
        ),
    )

    # ----------------------------------------------
    # Joint capacity constraints (lower slope)
    # ----------------------------------------------
    m.C_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITH_L5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITH_L5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            - m.E_TRADER_TARGET[i, "L5RE"]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITHOUT_L5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITHOUT_L5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITH_R5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITH_R5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            - m.E_TRADER_TARGET[i, "R5RE"]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITHOUT_R5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITHOUT_R5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITH_L5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITH_L5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            - m.E_TRADER_TARGET[i, "L5RE"]
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITHOUT_L5RE = pyo.Constraint(
        m.S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITHOUT_L5RE_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    # -------------------------------------------------------------
    # Energy and regulating FCAS capacity constraints (upper slope)
    # -------------------------------------------------------------
    m.C_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_GENERATOR = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_GENERATOR_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j, None]
        ),
    )

    m.C_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_LOAD_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j, None]
        ),
    )

    # BDU GEN side — upper slope: E_GEN + USC_GEN × R_GEN ≤ E_max_GEN
    m.C_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_BDU_GEN = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_GEN_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "GEN"]
            + (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, "GEN"],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, "GEN"],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, "GEN"],
                )
                * m.E_TRADER_TOTAL_OFFER[i, j, "GEN"]
            )
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, "GEN"]
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j, "GEN"]
        ),
    )

    # BDU LOAD side — "upper" capacity: E_LOAD + LSC_LOAD × R_LOAD ≤ -E_min_LOAD
    # (LOAD side uses positive E_LOAD, slope coefficients swap vs GEN side)
    m.C_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_BDU_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_LOAD_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "LOAD"]
            + (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, "LOAD"],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, "LOAD"],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, "LOAD"],
                )
                * m.E_TRADER_TOTAL_OFFER[i, j, "LOAD"]
            )
            <= -m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, "LOAD"]
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RHS[i, j, "LOAD"]
        ),
    )

    # -------------------------------------------------------------
    # Energy and regulating FCAS capacity constraints (lower slope)
    # -------------------------------------------------------------
    m.C_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_GENERATOR = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_GENERATOR_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_LOAD_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, None],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, None],
                )
                * m.E_TRADER_TARGET[i, j]
            )
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    # BDU GEN side — lower slope: E_GEN - LSC_GEN × R_GEN ≥ E_min_GEN (= 0 by contiguity)
    m.C_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_BDU_GEN = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_GEN_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "GEN"]
            - (
                get_lower_slope_coefficient(
                    enablement_min=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, "GEN"],
                    low_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_LOW_BREAKPOINT[i, j, "GEN"],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, "GEN"],
                )
                * m.E_TRADER_TOTAL_OFFER[i, j, "GEN"]
            )
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j, "GEN"]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, "GEN"]
        ),
    )

    # BDU LOAD side — "lower" minimum: E_LOAD - USC_LOAD × R_LOAD ≥ -E_max_LOAD = 0
    # (LOAD side uses positive E_LOAD, slope coefficients swap vs GEN side)
    m.C_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_BDU_LOAD = pyo.Constraint(
        m.S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_LOAD_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "LOAD"]
            - (
                get_upper_slope_coefficient(
                    enablement_max=m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, "LOAD"],
                    high_breakpoint=m.P_TRADER_FCAS_EFFECTIVE_HIGH_BREAKPOINT[i, j, "LOAD"],
                    max_avail=m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, "LOAD"],
                )
                * m.E_TRADER_TOTAL_OFFER[i, j, "LOAD"]
            )
            + m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LHS[i, j, "LOAD"]
            >= -m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, "LOAD"]
        ),
    )

    # ----------------------------------------------
    # Bidirectional FCAS SCADA ramping constraints
    # ----------------------------------------------
    m.C_FCAS_BIDIRECTIONAL_SCADA_RAMPING_UP = pyo.Constraint(
        m.S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_UP_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TARGET[i, "R5RE"]
            <= (m.P_TRADER_SCADA_RAMP_UP_RATE[i] / 12) + m.V_CV_TRADER_FCAS_BDU_SCADA_RAMPING_UP[i]
        ),
    )

    m.C_FCAS_BIDIRECTIONAL_SCADA_RAMPING_DOWN = pyo.Constraint(
        m.S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_DOWN_INDEX,
        rule=lambda m, i: (
            m.E_TRADER_TARGET[i, "L5RE"]
            <= (m.P_TRADER_SCADA_RAMP_DOWN_RATE[i] / 12)
            + m.V_CV_TRADER_FCAS_BDU_SCADA_RAMPING_DOWN[i]
        ),
    )

    # ----------------------------------------------
    # FCAS MaxAvail constraints
    # ----------------------------------------------
    m.C_FCAS_MAX_AVAIL = pyo.Constraint(
        m.S_TRADER_FCAS_OFFERS,
        rule=lambda m, i, j, k: (
            m.E_TRADER_TOTAL_OFFER[i, j, k]
            <= m.P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL[i, j, k]
            + m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j, k]
            if m.P_TRADER_FCAS_AVAILABILITY_STATUS[i, j, k]
            else m.E_TRADER_TOTAL_OFFER[i, j, k] == m.V_CV_TRADER_FCAS_MAX_AVAILABLE[i, j, k]
        ),
    )

    # ----------------------------------------------
    # FCAS EnablementMin constraints
    # ----------------------------------------------
    m.C_FCAS_ENABLEMENT_MIN_GENERATOR_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MIN_GENERATOR_CONTINGENCY = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_CONTINGENCY_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MIN_LOAD_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
            >= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MIN_LOAD_CONTINGENCY = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_CONTINGENCY_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MIN_BIDIRECTIONAL_GEN_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_GEN_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, "GEN"]
            >= m.P_TRADER_FCAS_BDU_GEN_REGULATION_LOWER_ENERGY_BOUND[i, j]
        ),
    )

    # A BDU contingency FCAS bid is a single undirected trapezium for the whole unit
    # (fcas-model-in-nemde.txt s2.4, Figure 5), so its enablement limits bound the
    # unit's *net* energy target -- E_TRADER_TARGET[i,"BDOF"] is GEN - LOAD -- rather
    # than either side separately, and the parameters are keyed with direction None.
    m.C_FCAS_ENABLEMENT_MIN_BIDIRECTIONAL_CONTINGENCY = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_CONTINGENCY_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"] + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
            >= m.P_TRADER_FCAS_ENABLEMENT_MIN[i, j, None]
        ),
    )

    # LOAD-side params use net energy axis convention (negative = consuming), so negate:
    # EnablementMin_LOAD (e.g. -98) negated gives max consumption (98).
    # EnablementMax_LOAD (e.g. 0) negated gives min consumption (0, trivially satisfied).
    m.C_FCAS_ENABLEMENT_MIN_BIDIRECTIONAL_LOAD_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_LOAD_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "LOAD"]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MIN[i, j, "LOAD"]
            >= -m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, "LOAD"]
        ),
    )

    # ----------------------------------------------
    # FCAS EnablementMax constraints
    # ----------------------------------------------
    m.C_FCAS_ENABLEMENT_MAX_GENERATOR_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MAX_GENERATOR_CONTINGENCY = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_CONTINGENCY_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "ENOF"]
            <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MAX_LOAD_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MAX_LOAD_CONTINGENCY = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_CONTINGENCY_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "LDOF"]
            <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MAX_BIDIRECTIONAL_GEN_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_GEN_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"]
            <= m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MAX[i, j, "GEN"]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, "GEN"]
        ),
    )

    m.C_FCAS_ENABLEMENT_MAX_BIDIRECTIONAL_CONTINGENCY = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_CONTINGENCY_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TARGET[i, "BDOF"]
            <= m.P_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, None]
        ),
    )

    m.C_FCAS_ENABLEMENT_MAX_BIDIRECTIONAL_LOAD_REGULATION = pyo.Constraint(
        m.S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_LOAD_REGULATION_INDEX,
        rule=lambda m, i, j: (
            m.E_TRADER_TOTAL_OFFER[i, "BDOF", "LOAD"]
            <= -m.P_TRADER_FCAS_EFFECTIVE_ENABLEMENT_MIN[i, j, "LOAD"]
            + m.V_CV_TRADER_FCAS_ENABLEMENT_MAX[i, j, "LOAD"]
        ),
    )

    return m


def define_loss_model_constraints(m):
    """Interconnector loss model constraints"""

    def approximated_loss_rule(m, i):
        """Approximate interconnector loss"""

        return m.V_LOSS[i] == sum(
            m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y[i, k] * m.V_LOSS_LAMBDA[i, k]
            for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
            if j == i
        )

    # Approximate loss over interconnector
    m.C_APPROXIMATED_LOSS = pyo.Constraint(m.S_INTERCONNECTORS, rule=approximated_loss_rule)

    def sos2_condition_1_rule(m, i):
        """SOS2 condition 1"""

        return m.V_GC_INTERCONNECTOR[i] == sum(
            m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X[i, k] * m.V_LOSS_LAMBDA[i, k]
            for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
            if j == i
        )

    # SOS2 condition 1
    m.C_SOS2_CONDITION_1 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_1_rule)

    def sos2_condition_2_rule(m, i):
        """SOS2 condition 2"""

        return (
            sum(
                m.V_LOSS_LAMBDA[i, k]
                for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
                if j == i
            )
            == 1
        )

    # SOS2 condition 2
    m.C_SOS2_CONDITION_2 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_2_rule)

    def loss_lambda_sos2_rule(m, i):
        """Only two adjacent breakpoint weights may be nonzero.

        Declared as a native SOS2 constraint rather than the previous
        hand-rolled binary-indicator encoding (V_LOSS_Y + conditions
        3-6). That encoding had a real bug — the adjacency-linking
        constraints only covered interior breakpoints (2 <= k <= end-1)
        and left breakpoint 0 completely unconstrained — but fixing it
        (verified separately) left the LP relaxation bound unchanged: on
        hard instances the relaxation can still legitimately put weight on
        two non-adjacent breakpoints (e.g. the very first and very last),
        since a correct binary-adjacency encoding's LP relaxation doesn't
        by itself force positive-weight segments to be contiguous, only
        each lambda to be bounded by its own local neighbours. That's an
        inherent property of this encoding style, not a bug.

        What the native SOS2 declaration buys instead is branching
        strategy: CBC's dedicated SOS2 branching resolves that same
        relaxation gap in far fewer nodes than generic 0/1 branching on
        the (even correctly-adjacency-constrained) binary encoding —
        confirmed empirically on a hard 2025 interval (31s / 668 nodes for
        native SOS2 vs 106s / 2368 nodes for the fixed binary encoding,
        both proving the identical optimum). The trade-off: CBC disables
        its usual MIP heuristics (feasibility pump, rounding, RINS) when
        native SOS branching objects are present, so easy instances that
        the old encoding solved almost instantly via those heuristics (raw
        LP relaxation already near-integral) may see a small constant
        overhead here — worth watching if it shows up in practice.
        """

        breakpoints = sorted(k for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i)
        return [m.V_LOSS_LAMBDA[i, k] for k in breakpoints]

    m.C_LOSS_LAMBDA_SOS2 = pyo.SOSConstraint(m.S_INTERCONNECTORS, rule=loss_lambda_sos2_rule, sos=2)

    return m


def define_fast_start_unit_inflexibility_constraints(m):
    """Fast start unit inflexibility profile constraints"""

    def profile_constraint_rule(m, i):
        """Energy profile constraint"""

        # CurrentMode and CurrentModeTime may be missing - skip constraint
        if (m.P_TRADER_CURRENT_MODE[i].value is None) or (
            m.P_TRADER_CURRENT_MODE_TIME[i].value is None
        ):
            return pyo.Constraint.Skip

        if m.P_TRADER_TYPE[i] == "GENERATOR":
            energy_offer = "ENOF"
        elif m.P_TRADER_TYPE[i] in ["LOAD", "NORMALLY_ON_LOAD"]:
            energy_offer = "LDOF"
        else:
            raise Exception("Unexpected energy offer:", i)

        effective_mode = get_target_mode(
            current_mode=m.P_TRADER_CURRENT_MODE[i].value,
            current_mode_time=m.P_TRADER_CURRENT_MODE_TIME[i].value,
            t1=m.P_TRADER_T1[i],
            t2=m.P_TRADER_T2[i],
            t3=m.P_TRADER_T3[i],
            t4=m.P_TRADER_T4[i],
        )

        effective_time = get_target_mode_time(
            current_mode=m.P_TRADER_CURRENT_MODE[i].value,
            current_mode_time=m.P_TRADER_CURRENT_MODE_TIME[i].value,
            t1=m.P_TRADER_T1[i],
            t2=m.P_TRADER_T2[i],
            t3=m.P_TRADER_T3[i],
            t4=m.P_TRADER_T4[i],
        )

        # Unit is synchronising - output = 0
        if (effective_mode == 0) or (effective_mode == 1):
            return (
                m.E_TRADER_TARGET[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i]
                == 0 + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i]
            )

        # Unit ramping to min loading - energy output fixed to profile
        elif effective_mode == 2:
            slope = m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T2[i]
            startup_profile = slope * effective_time
            return (
                m.V_TRADER_TARGET[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_LHS[i]
                == startup_profile + m.V_CV_TRADER_INFLEXIBILITY_PROFILE_RHS[i]
            )

        # Output lower bounded by MinLoadingMW
        elif effective_mode == 3:
            return (
                m.E_TRADER_TARGET[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i]
                >= m.P_TRADER_MIN_LOADING_MW[i]
            )

        # Output still lower bounded by inflexibility profile
        elif (effective_mode == 4) and (effective_time < m.P_TRADER_T4[i]):
            slope = -m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T4[i]
            max_output = (slope * effective_time) + m.P_TRADER_MIN_LOADING_MW[i]

            return (
                m.E_TRADER_TARGET[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i]
                >= max_output
            )

        # Unit operating normally - output not constrained by inflexibility profile.
        # A trivially-true row rather than Constraint.Skip, so that every fast-start
        # trader has a row in this block and run.py can deactivate the whole block
        # for its first solve pass without changing the model's shape.
        else:
            return (
                m.E_TRADER_TARGET[i, energy_offer] + m.V_CV_TRADER_INFLEXIBILITY_PROFILE[i] >= 0.0
            )

    # Profile constraint
    m.C_TRADER_INFLEXIBILITY_PROFILE = pyo.Constraint(
        m.S_TRADER_FAST_START, rule=profile_constraint_rule
    )

    return m


def define_tie_breaking_constraints(m):
    """Define tie-breaking constraints"""

    def generator_tie_breaking_rule(m, i, j, k, b, q, r, s, t):
        """Generator tie-breaking rule for price-tied energy offers"""

        if (m.P_TRADER_QUANTITY_BAND[i, j, k, b] == 0) or (
            m.P_TRADER_QUANTITY_BAND[q, r, s, t] == 0
        ):
            return pyo.Constraint.Skip

        return (m.V_TRADER_OFFER[i, j, k, b] / m.P_TRADER_QUANTITY_BAND[i, j, k, b]) - (
            m.V_TRADER_OFFER[q, r, s, t] / m.P_TRADER_QUANTITY_BAND[q, r, s, t]
        ) == m.V_TRADER_SLACK_1_GENERATOR[i, j, k, b, q, r, s, t] - m.V_TRADER_SLACK_2_GENERATOR[
            i, j, k, b, q, r, s, t
        ]

    # Generator tie-breaking rule
    m.C_TRADER_TIE_BREAK_GENERATORS = pyo.Constraint(
        m.S_TRADER_PRICE_TIED_GENERATORS, rule=generator_tie_breaking_rule
    )

    def load_tie_breaking_rule(m, i, j, k, b, q, r, s, t):
        """Load tie-breaking rule for price-tied energy offers"""

        if (m.P_TRADER_QUANTITY_BAND[i, j, k, b] == 0) or (
            m.P_TRADER_QUANTITY_BAND[q, r, s, t] == 0
        ):
            return pyo.Constraint.Skip

        return (m.V_TRADER_OFFER[i, j, k, b] / m.P_TRADER_QUANTITY_BAND[i, j, k, b]) - (
            m.V_TRADER_OFFER[q, r, s, t] / m.P_TRADER_QUANTITY_BAND[q, r, s, t]
        ) == m.V_TRADER_SLACK_1_LOAD[i, j, k, b, q, r, s, t] - m.V_TRADER_SLACK_2_LOAD[
            i, j, k, b, q, r, s, t
        ]

    # Load tie-breaking rule
    m.C_TRADER_TIE_BREAK_LOADS = pyo.Constraint(
        m.S_TRADER_PRICE_TIED_LOADS, rule=load_tie_breaking_rule
    )

    return m


ENERGY_TRADE_TYPES = ["ENOF", "LDOF", "DROF", "BDOF"]

FCAS_TRADE_TYPES = ["R1SE", "R6SE", "R60S", "R5MI", "R5RE", "L1SE", "L6SE", "L60S", "L5MI", "L5RE"]


def define_trader_target_pinning_constraints(m, options: SolveOptions):
    """Pin trader targets to NEMDE's published values -- the primary diagnostic for
    localising a misformulation. Enabled via SolveOptions.pin_trader_targets / pin_fcas_targets;
    with both off no constraint block is added at all.

    Solving with targets pinned turns "our dispatch disagrees with NEMDE" into
    "these constraints are violated at NEMDE's own dispatch", which localises a
    misformulation instead of only measuring it.
    """

    def trader_target_pinning_constraint(m, i, j):
        if options.pin_trader_targets and j in ENERGY_TRADE_TYPES:
            return m.E_TRADER_TARGET[i, j] == m.P_TRADER_TARGET[i, "ENERGY_TARGET"]

        if options.pin_fcas_targets and j in FCAS_TRADE_TYPES:
            return m.E_TRADER_TARGET[i, j] == m.P_TRADER_TARGET[i, j]

        return pyo.Constraint.Skip

    m.C_TRADER_TARGET_PINNING_CONSTRAINTS = pyo.Constraint(
        m.S_TRADER_TOTAL_OFFERS, rule=trader_target_pinning_constraint
    )

    return m


def define_constraints(m, options: SolveOptions):
    """Define model constraints"""

    t0 = time.time()

    # Ensure offer bands aren't violated
    logger.info("Starting to define constraints: %.2fs", time.time() - t0)
    m = define_offer_constraints(m)
    logger.info("Defined offer constraints: %.2fs", time.time() - t0)

    # Construct bi-directional unit energy constraints
    m = define_bidirectional_energy_constraints(m)
    logger.info("Defined bidirectional energy constraints: %.2fs", time.time() - t0)

    # Construct generic constraints and link variables to those found in objective
    m = define_generic_constraints(m)
    logger.info("Defined generic constraints: %.2fs", time.time() - t0)

    # Construct unit constraints (e.g. ramp rate constraints)
    m = define_unit_constraints(m)
    logger.info("Defined unit constraints: %.2fs", time.time() - t0)

    # Construct region power balance constraints
    m = define_region_constraints(m)
    logger.info("Defined region constraints: %.2fs", time.time() - t0)

    # Construct interconnector constraints
    m = define_interconnector_constraints(m)
    logger.info("Defined interconnector constraints: %.2fs", time.time() - t0)

    # MNSP constraints
    m = define_mnsp_constraints(m)
    logger.info("Defined MNSP constraints: %.2fs", time.time() - t0)

    # Construct FCAS constraints
    m = define_fcas_constraints(m)
    logger.info("Defined FCAS constraints: %.2fs", time.time() - t0)

    # SOS2 interconnector loss model constraints
    m = define_loss_model_constraints(m)
    logger.info("Defined loss model constraints: %.2fs", time.time() - t0)

    # Fast start unit inflexibility profile
    m = define_fast_start_unit_inflexibility_constraints(m)
    logger.info("Defined fast start unit inflexibility constraints: %.2fs", time.time() - t0)

    # Tie-breaking constraints
    if options.tie_breaking:
        m = define_tie_breaking_constraints(m)
        logger.info("Defined tie-break constraints: %.2fs", time.time() - t0)

    # Constraints pinning trader targets to NEMDE's -- off unless asked for
    if options.pin_trader_targets or options.pin_fcas_targets:
        m = define_trader_target_pinning_constraints(m, options)
        logger.info("Defined trader target pinning constraints: %.2fs", time.time() - t0)

    return m


def define_objective(m):
    """Define model objective"""

    # Total cost for energy and ancillary services
    m.OBJECTIVE = pyo.Objective(
        expr=sum(m.E_TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
        + sum(m.E_MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
        + m.E_CV_TOTAL_PENALTY
        + m.E_TRADER_TIE_BREAK_COST_GENERATORS
        + m.E_TRADER_TIE_BREAK_COST_LOADS,
        sense=pyo.minimize,
    )

    return m


def construct_model(data, options: SolveOptions | None = None):
    """Create model object.

    `data` is the case dict produced by inputs.construct_case(). Every key is read
    with `data[...]`, never `data.get(...)`, so a missing or misspelled input
    raises here rather than degrading into an empty Set that silently drops a
    whole family of constraints.
    """

    options = options or SolveOptions()

    # Initialise model
    t0 = time.time()
    m = pyo.ConcreteModel()

    # Define model components
    m = define_sets(m, data)
    m = define_parameters(m, data)
    m = define_variables(m)
    m = define_expressions(m, data)
    m = define_constraints(m, options)
    m = define_objective(m)

    apply_constraint_overrides(m, options)

    # Add component allowing dual variables to be imported
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    logger.info("Constructed model in: %.2fs", time.time() - t0)

    return m
