"""Model used to construct and solve NEMDE approximation"""

import os
import json
import time

import pyomo.environ as pyo

import utils.data
from utils.data import parse_case_data_json
from utils.loaders import load_dispatch_interval_json

from components.expressions.cost_functions import define_cost_function_expressions
from components.expressions.constraint_violation import define_constraint_violation_penalty_expressions
from components.expressions.aggregate_power import define_aggregate_power_expressions
from components.expressions.generic_constraints import define_generic_constraint_expressions

from components.constraints.offers import define_offer_constraints
from components.constraints.units import define_unit_constraints
from components.constraints.regions import define_region_constraints
from components.constraints.interconnectors import define_interconnector_constraints
from components.constraints.generic_constraints import define_generic_constraints


# from components.constraints.fcas import define_fcas_constraints
# from components.constraints.loss import define_loss_model_constraints


class NEMDEModel:
    def __init__(self):
        pass

    @staticmethod
    def define_sets(m, data):
        """Define sets"""

        # NEM regions
        m.S_REGIONS = pyo.Set(initialize=data['S_REGIONS'])

        # Market participants (generators and loads)
        m.S_TRADERS = pyo.Set(initialize=data['S_TRADERS'])

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

        return m

    @staticmethod
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
                                                   initialize=data['P_TRADER_FCAS_ENABLEMENT_MIN'])

        # Trader FCAS low breakpoint
        m.P_TRADER_FCAS_LOW_BREAKPOINT = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                                   initialize=data['P_TRADER_FCAS_LOW_BREAKPOINT'])

        # Trader FCAS high breakpoint
        m.P_TRADER_FCAS_HIGH_BREAKPOINT = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                                    initialize=data['P_TRADER_FCAS_HIGH_BREAKPOINT'])

        # Trader FCAS enablement max
        m.P_TRADER_FCAS_ENABLEMENT_MAX = pyo.Param(m.S_TRADER_FCAS_OFFERS,
                                                   initialize=data['P_TRADER_FCAS_ENABLEMENT_MAX'])

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

        # Interconnector loss model lower limit. Note: absolute value is given
        m.P_INTERCONNECTOR_LOSS_LOWER_LIMIT = pyo.Param(m.S_INTERCONNECTORS,
                                                        initialize=data['P_INTERCONNECTOR_LOSS_LOWER_LIMIT'])

        # Interconnector initial loss estimate
        m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE = pyo.Param(m.S_INTERCONNECTORS,
                                                             initialize=data['P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE'])

        # Observed interconnector loss (obtained from NEMDE solution)
        m.P_INTERCONNECTOR_SOLUTION_LOSS = pyo.Param(m.S_INTERCONNECTORS,
                                                     initialize=data['P_INTERCONNECTOR_SOLUTION_LOSS'])

        # Price bands for MNSPs
        m.P_MNSP_PRICE_BAND = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, initialize=data['P_MNSP_PRICE_BAND'])

        # Quantity bands for MNSPs
        m.P_MNSP_QUANTITY_BAND = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, initialize=data['P_MNSP_QUANTITY_BAND'])

        # Max available output for given MNSP
        m.P_MNSP_MAX_AVAILABLE = pyo.Param(m.S_MNSP_OFFERS, initialize=data['P_MNSP_MAX_AVAILABLE'])

        # MNSP 'to' and 'from' region loss factor
        m.P_MNSP_TO_REGION_LF = pyo.Param(m.S_MNSPS, initialize=data['P_MNSP_TO_REGION_LF'])
        m.P_MNSP_FROM_REGION_LF = pyo.Param(m.S_MNSPS, initialize=data['P_MNSP_FROM_REGION_LF'])

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

    @staticmethod
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
        m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
        m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

        # FCAS joint capacity constraint violation pyo.Variables
        m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
        m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

        # FCAS joint regulating capacity constraint violation pyo.Variables
        m.V_CV_JOINT_REGULATING_CAPACITY_UP = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)
        m.V_CV_JOINT_REGULATING_CAPACITY_DOWN = pyo.Var(m.S_TRADER_OFFERS, within=pyo.NonNegativeReals)

        # Interconnector forward and reverse flow constraint violation
        m.V_CV_INTERCONNECTOR_FORWARD = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)
        m.V_CV_INTERCONNECTOR_REVERSE = pyo.Var(m.S_INTERCONNECTORS, within=pyo.NonNegativeReals)

        # Loss model breakpoints and intervals
        m.V_LOSS = pyo.Var(m.S_INTERCONNECTORS)
        # m.V_LOSS_LAMBDA = pyo.Var(m.S_BREAKPOINTS, within=pyo.NonNegativeReals)
        # m.V_LOSS_Y = pyo.Var(m.S_INTERVALS, within=pyo.Binary)

        # Flow between region and interconnector connection points
        m.V_FLOW_FROM_CP = pyo.Var(m.S_INTERCONNECTORS)
        m.V_FLOW_TO_CP = pyo.Var(m.S_INTERCONNECTORS)

        return m

    @staticmethod
    def define_expressions(m, data):
        """Define model expressions"""

        # Cost function expressions
        m = define_cost_function_expressions(m)
        m = define_generic_constraint_expressions(m, data)
        m = define_constraint_violation_penalty_expressions(m)
        m = define_aggregate_power_expressions(m)

        return m

    def define_constraints(self, m):
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

        # # Construct FCAS constraints
        # m = define_fcas_constraints(m)
        # print('Defined FCAS constraints:', time.time() - t0)
        #
        # # SOS2 interconnector loss model constraints
        # m = define_loss_model_constraints(m)
        # print('Defined loss model constraints:', time.time() - t0)

        return m

    @staticmethod
    def define_objective(m):
        """Define model objective"""

        # Total cost for energy and ancillary services
        m.OBJECTIVE = pyo.Objective(expr=sum(m.E_TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
                                         + sum(m.E_MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
                                         + m.E_CV_TOTAL_PENALTY
                                    # + m.E_LOSS_COST
                                    ,
                                    sense=pyo.minimize)

        return m

    def construct_model(self, data):
        """Create model object"""

        # Initialise model
        t0 = time.time()
        m = pyo.ConcreteModel()

        # Define model components
        m = self.define_sets(m, data)
        m = self.define_parameters(m, data)
        m = self.define_variables(m)
        m = self.define_expressions(m, data)
        m = self.define_constraints(m)
        m = self.define_objective(m)
        print('Constructed model in:', time.time() - t0)

        return m

    @staticmethod
    def solve_model(m):
        """Solve model"""
        # Setup solver
        solver_options = {}  # 'MIPGap': 0.0005,
        opt = pyo.SolverFactory('cplex', solver_io='lp')

        # Solve model
        t0 = time.time()

        print('Starting solve:', time.time() - t0)
        solve_status = opt.solve(m, tee=False, options=solver_options, keepfiles=False)
        print('Finished solve:', time.time() - t0)

        return m, solve_status


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # NEMDE model object
    nemde = NEMDEModel()

    # Case data in json format
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)
    # with open('example.json', 'w') as f:
    #     json.dump(cdata, f)

    case_data = parse_case_data_json(case_data_json)

    # Construct model
    nemde_model = nemde.construct_model(case_data)

    # Solve model
    nemde_model, status = nemde.solve_model(nemde_model)
