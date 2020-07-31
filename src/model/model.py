"""Class used to construct and solve NEMDE approximation"""

import os
import time
import json

import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from pyomo.util.infeasible import log_infeasible_constraints

# from components.fcas import FCASHandler
import components.parser
import components.expressions
import components.constraints
from components.utils.loader import load_dispatch_interval_json
from components.constructor import ParsedInputConstructor, JSONInputConstructor, XMLInputConstructor


class NEMDEModel:
    def __init__(self, constructor):
        # Object used to extract NEMDE input information and construct model components
        self.constructor = constructor

        # Solver options
        self.tee = True
        self.keepfiles = False
        self.solver_options = {}  # 'MIPGap': 0.0005,
        self.opt = SolverFactory('cplex', solver_io='lp')

    def define_sets(self, m, data):
        """Define model sets"""

        # Market participants (generators and loads)
        m.S_TRADERS = pyo.Set(initialize=self.constructor.get_trader_index(data))

        # Market Network Service Providers (interconnectors that bid into the market)
        m.S_MNSPS = pyo.Set(initialize=self.constructor.get_mnsp_index(data))

        # All interconnectors (interconnector_id)
        m.S_INTERCONNECTORS = pyo.Set(initialize=self.constructor.get_interconnector_index(data))

        # Trader offer types
        m.S_TRADER_OFFERS = pyo.Set(initialize=self.constructor.get_trader_offer_index(data))

        # MNSP offer types
        m.S_MNSP_OFFERS = pyo.Set(initialize=self.constructor.get_mnsp_offer_index(data))

        # Generic constraints
        m.S_GENERIC_CONSTRAINTS = pyo.Set(initialize=self.constructor.get_generic_constraint_index(data))

        # NEM regions
        m.S_REGIONS = pyo.Set(initialize=self.constructor.get_region_index(data))

        # Generic constraints trader pyo.Variables
        m.S_GC_TRADER_VARS = pyo.Set(initialize=self.constructor.get_generic_constraint_trader_variable_index(data))

        # Generic constraint interconnector pyo.Variables
        m.S_GC_INTERCONNECTOR_VARS = pyo.Set(
            initialize=self.constructor.get_generic_constraint_interconnector_variable_index(data))

        # Generic constraint region pyo.Variables
        m.S_GC_REGION_VARS = pyo.Set(initialize=self.constructor.get_generic_constraint_region_variable_index(data))

        # Price / quantity band index
        m.S_BANDS = pyo.RangeSet(1, 10, 1)

        # Mapping between regions and traders
        m.S_REGION_TRADER_MAP = pyo.Param(m.S_REGIONS, rule=self.constructor.get_region_trader_map(data))

        # TODO: Fix loss model construction
        # Loss model breakpoints
        m.S_INTERCONNECTOR_BREAKPOINTS = pyo.Set(m.S_INTERCONNECTORS,
                                                 rule=self.constructor.get_loss_model_breakpoint_index(data))

        def loss_model_interconnector_intervals_rule(m, i):
            """Interconnector loss model intervals"""

            return range(len(m.S_INTERCONNECTOR_BREAKPOINTS[i]) - 1)

        # Loss model intervals
        m.S_INTERCONNECTOR_INTERVALS = pyo.Set(m.S_INTERCONNECTORS, rule=loss_model_interconnector_intervals_rule)

        def loss_model_breakpoints_rule(m):
            """All interconnector breakpoints"""

            return [(i, j) for i in m.S_INTERCONNECTORS for j in m.S_INTERCONNECTOR_BREAKPOINTS[i]]

        # All interconnector breakpoints
        m.S_BREAKPOINTS = pyo.Set(initialize=loss_model_breakpoints_rule(m))

        def loss_model_intervals_rule(m):
            """All interconnector breakpoints"""

            return [(i, j) for i in m.S_INTERCONNECTORS for j in m.S_INTERCONNECTOR_INTERVALS[i]]

        # All interconnector intervals
        m.S_INTERVALS = pyo.Set(initialize=loss_model_intervals_rule(m))

        return m

    def define_parameters(self, m, data):
        """Define model pyo.Parameters"""

        # Price bands for traders (generators / loads)
        m.P_TRADER_PRICE_BAND = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS,
                                          rule=self.constructor.get_trader_price_bands(data))

        # Quantity bands for traders (generators / loads)
        m.P_TRADER_QUANTITY_BAND = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS,
                                             rule=self.constructor.get_trader_quantity_bands(data))

        # Max available output for given trader
        m.P_TRADER_MAX_AVAILABLE = pyo.Param(m.S_TRADER_OFFERS, rule=self.constructor.get_trader_max_available(data))

        # Initial MW output for generators / loads
        m.P_TRADER_INITIAL_MW = pyo.Param(m.S_TRADERS, rule=self.constructor.get_trader_initial_mw(data))

        # Price bands for MNSPs
        m.P_MNSP_PRICE_BAND = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, rule=self.constructor.get_mnsp_price_bands(data))

        # Quantity bands for MNSPs
        m.P_MNSP_QUANTITY_BAND = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS,
                                           rule=self.constructor.get_mnsp_quantity_bands(data))

        # Max available output for given MNSP
        m.P_MNSP_MAX_AVAILABLE = pyo.Param(m.S_MNSP_OFFERS, rule=self.constructor.get_mnsp_max_available(data))

        # Generic constraint RHS
        m.P_RHS = pyo.Param(m.S_GENERIC_CONSTRAINTS, rule=self.constructor.get_generic_constraint_rhs(data))

        #  Constraint violation factors
        m.P_CVF_GC = pyo.Param(m.S_GENERIC_CONSTRAINTS,
                               rule=self.constructor.get_generic_constraint_violation_factors(data))

        # Value of lost load
        m.P_CVF_VOLL = pyo.Param(rule=self.constructor.get_case_attribute(data, 'VoLL'))

        # Energy deficit price
        m.P_CVF_ENERGY_DEFICIT_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'EnergyDeficitPrice'))

        # Energy surplus price
        m.P_CVF_ENERGY_SURPLUS_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'EnergySurplusPrice'))

        # Ramp-rate constraint violation factor
        m.P_CVF_RAMP_RATE_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'RampRatePrice'))

        # Capacity price (assume for constraint ensuring max available capacity not exceeded)
        m.P_CVF_CAPACITY_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'CapacityPrice'))

        # Offer price (assume for constraint ensuring band offer amounts are not exceeded)
        m.P_CVF_OFFER_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'OfferPrice'))

        # MNSP offer price (assumed for constraint ensuring MNSP band offers are not exceeded)
        m.P_CVF_MNSP_OFFER_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'MNSPOfferPrice'))

        # MNSP ramp rate price (not sure what this applies to - unclear what MNSP ramp rates are)
        m.P_CVF_MNSP_RAMP_RATE_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'MNSPRampRatePrice'))

        # MNSP capacity price (assume for constraint ensuring max available capacity not exceeded)
        m.P_CVF_MNSP_CAPACITY_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'MNSPCapacityPrice'))

        # Ancillary services profile price (assume for constraint ensure FCAS trapezium not violated)
        m.P_CVF_AS_PROFILE_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'ASProfilePrice'))

        # Ancillary services max available price (assume for constraint ensure max available amount not exceeded)
        m.P_CVF_AS_MAX_AVAIL_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'ASMaxAvailPrice'))

        # Ancillary services enablement min price (assume for constraint ensure FCAS > enablement min if active)
        m.P_CVF_AS_ENABLEMENT_MIN_PRICE = pyo.Param(
            rule=self.constructor.get_case_attribute(data, 'ASEnablementMinPrice'))

        # Ancillary services enablement max price (assume for constraint ensure FCAS < enablement max if active)
        m.P_CVF_AS_ENABLEMENT_MAX_PRICE = pyo.Param(
            rule=self.constructor.get_case_attribute(data, 'ASEnablementMaxPrice'))

        # Interconnector power flow violation price
        m.P_CVF_INTERCONNECTOR_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'InterconnectorPrice'))

        # MNSP loss price
        m.P_MNSP_LOSS_PRICE = pyo.Param(rule=self.constructor.get_case_attribute(data, 'MNSPLossesPrice'))

        # Interconnector from region
        m.P_INTERCONNECTOR_FROM_REGION = pyo.Param(m.S_INTERCONNECTORS,
                                                   rule=self.constructor.get_interconnector_from_regions(data))

        # Interconnector to region
        m.P_INTERCONNECTOR_TO_REGION = pyo.Param(m.S_INTERCONNECTORS,
                                                 rule=self.constructor.get_interconnector_to_regions(data))

        # Interconnector MNSP status
        m.P_INTERCONNECTOR_MNSP_STATUS = pyo.Param(m.S_INTERCONNECTORS,
                                                   rule=self.constructor.get_interconnector_mnsp_status(data))

        # MNSP from and to region loss factor
        m.P_MNSP_FROM_REGION_LF = pyo.Param(m.S_MNSPS, rule=self.constructor.get_mnsp_from_region_loss_factor(data))
        m.P_MNSP_TO_REGION_LF = pyo.Param(m.S_MNSPS, rule=self.constructor.get_mnsp_to_region_loss_factor(data))

        # Trader region
        m.P_TRADER_REGION = pyo.Param(m.S_TRADERS, rule=self.constructor.get_trader_regions(data))

        # Semi-dispatch status
        m.P_TRADER_SEMI_DISPATCH_STATUS = pyo.Param(m.S_TRADERS,
                                                    rule=self.constructor.get_trader_semi_dispatch_status(data))

        # Initial region demand
        m.P_REGION_INITIAL_DEMAND = pyo.Param(m.S_REGIONS, rule=self.constructor.get_region_initial_demand(data))

        # Region aggregate dispatch error
        m.P_REGION_ADE = pyo.Param(m.S_REGIONS, rule=self.constructor.get_region_ade(data))

        # Region demand forecast
        m.P_REGION_DF = pyo.Param(m.S_REGIONS, rule=self.constructor.get_region_df(data))

        # Loss model breakpoints
        m.P_LOSS_MODEL_BREAKPOINTS_X = pyo.Param(m.S_BREAKPOINTS,
                                                 rule=self.constructor.get_loss_model_breakpoints_x(data))

        # Loss model breakpoints
        m.P_LOSS_MODEL_BREAKPOINTS_Y = pyo.Param(m.S_BREAKPOINTS,
                                                 rule=self.constructor.get_loss_model_breakpoints_y(data))

        # Generic constraint type
        m.P_GENERIC_CONSTRAINT_TYPE = pyo.Param(m.S_GENERIC_CONSTRAINTS,
                                                rule=self.constructor.get_generic_constraint_type(data))

        # Trader ramp-up and down rates
        m.P_TRADER_RAMP_UP_RATE = pyo.Param(m.S_TRADERS, rule=self.constructor.get_trader_ramp_up_rate(data))
        m.P_TRADER_RAMP_DOWN_RATE = pyo.Param(m.S_TRADERS, rule=self.constructor.get_trader_ramp_down_rate(data))

        # Interconnector upper and lower limits
        m.P_INTERCONNECTOR_UPPER_LIMIT = pyo.Param(m.S_INTERCONNECTORS,
                                                   rule=self.constructor.get_interconnector_upper_limits(data))

        m.P_INTERCONNECTOR_LOWER_LIMIT = pyo.Param(m.S_INTERCONNECTORS,
                                                   rule=self.constructor.get_interconnector_lower_limits(data))

        # Interconnector loss share
        m.P_INTERCONNECTOR_LOSS_SHARE = pyo.Param(m.S_INTERCONNECTORS,
                                                  rule=self.constructor.get_interconnector_loss_share(data))

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
        m.V_LOSS_LAMBDA = pyo.Var(m.S_BREAKPOINTS, within=pyo.NonNegativeReals)
        m.V_LOSS_Y = pyo.Var(m.S_INTERVALS, within=pyo.Binary)

        # Flow between region and interconnector connection points
        m.V_FLOW_FROM_CP = pyo.Var(m.S_INTERCONNECTORS)
        m.V_FLOW_TO_CP = pyo.Var(m.S_INTERCONNECTORS)

        return m

    @staticmethod
    def define_expressions(m, data):
        """Define model expressions"""

        # Define all expression types
        m = components.expressions.define_cost_function_expressions(m)
        m = components.expressions.define_aggregate_power_expressions(m)

        m = components.expressions.define_generic_constraint_expressions(m, data)
        m = components.expressions.define_constraint_violation_penalty_expressions(m)

        return m

    @staticmethod
    def define_constraints(m):
        """Define model constraints"""

        t0 = time.time()

        # Ensure offer bands aren't violated
        print('Starting to define constraints:', time.time() - t0)
        m = components.constraints.define_offer_constraints(m)
        print('Defined offer constraints:', time.time() - t0)

        # Construct generic constraints and link pyo.Variables to those found in objective
        m = components.constraints.define_generic_constraints(m)
        print('Defined generic constraints:', time.time() - t0)

        # Construct unit constraints (e.g. ramp rate constraints)
        m = components.constraints.define_unit_constraints(m)
        print('Defined unit constraints:', time.time() - t0)

        # Construct region power balance constraints
        m = components.constraints.define_region_constraints(m)
        print('Defined region constraints:', time.time() - t0)

        # Construct interconnector constraints
        m = components.constraints.define_interconnector_constraints(m)
        print('Defined interconnector constraints:', time.time() - t0)

        # # Construct FCAS constraints
        # m = components.constraints.define_fcas_constraints(m)
        # print('Defined FCAS constraints:', time.time() - t0)

        # # SOS2 interconnector loss model constraints
        # m = self.define_loss_model_constraints(m)
        # print('Defined loss model constraints:', time.time() - t0)

        return m

    @staticmethod
    def define_objective(m):
        """Define model objective"""

        # Total cost for energy and ancillary services
        m.OBJECTIVE = pyo.Objective(expr=sum(m.E_TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
                                         # + sum(m.E_MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
                                         # + m.E_CV_TOTAL_PENALTY
                                    ,
                                    sense=pyo.minimize)

        return m

    def construct_model(self, data):
        """Construct NEMDE approximation"""

        # Update data for specified interval
        t0 = time.time()
        print('Starting model construction:', time.time() - t0)

        print('Loaded data:', time.time() - t0)

        # Initialise concrete model instance
        m = pyo.ConcreteModel()
        print('Initialised model:', time.time() - t0)

        # Define model components
        m = self.define_sets(m, data)
        print('Defined sets:', time.time() - t0)

        m = self.define_parameters(m, data)
        print('Defined parameters:', time.time() - t0)

        m = self.define_variables(m)
        print('Defined variables:', time.time() - t0)

        m = self.define_expressions(m, data)
        print('Defined expressions:', time.time() - t0)

        m = self.define_constraints(m)
        print('Defined constraints:', time.time() - t0)

        m = self.define_objective(m)
        print('Defined objective:', time.time() - t0)

        return m

        # # Fix interconnector solution
        # m = self.fix_interconnector_solution(m)
        # # m = self.fix_fcas_solution(m)
        # # m = self.fix_energy_solution(m)
        #
        # return m

    def solve_model(self, m):
        """Solve model"""

        # Solve model
        t0 = time.time()

        print('Starting solve:', time.time() - t0)
        solve_status = self.opt.solve(m, tee=self.tee, options=self.solver_options, keepfiles=self.keepfiles)
        print('Finished solve:', time.time() - t0)

        return m, solve_status

    def fix_interconnector_solution(self, m):
        """Fix interconnector solution to observed values"""

        # Fix solution for each interconnector
        for i in m.S_INTERCONNECTORS:
            observed_flow = self.data.get_interconnector_solution_attribute(i, 'Flow')
            m.V_GC_INTERCONNECTOR[i].fix(observed_flow)

        return m

    def fix_fcas_solution(self, m):
        """Fix generator FCAS solution"""

        # Trader solution
        traders = self.data.get_trader_index()

        # Raise service mapping between model and NEMDE output
        raise_map = [('R6SE', 'R6Target'), ('R60S', 'R60Target'), ('R5MI', 'R5Target'), ('R5RE', 'R5RegTarget')]
        # raise_map = [('R60S', 'R60Target')]
        lower_map = [('L6SE', 'L6Target'), ('L60S', 'L60Target'), ('L5MI', 'L5Target'), ('L5RE', 'L5RegTarget')]
        # lower_map = []

        # Fix FCAS solution based on observed NEMDE output
        for trader in traders:

            for i, j in raise_map + lower_map:

                # Fix selected FCAS solution
                if (trader, i) in m.S_TRADER_OFFERS:
                    # FCAS solution
                    fcas_solution = self.data.get_trader_solution_attribute(trader, j)

                    # Fix pyo.Variable to observed solution
                    m.V_TRADER_TOTAL_OFFER[trader, i].fix(fcas_solution)

        return m

    def fix_energy_solution(self, m):
        """Fix generator energy solution"""

        # Trader solution
        traders = self.data.get_trader_index()

        # Fix energy solution based on observed NEMDE output
        for trader in traders:

            # Energy solution
            if ((trader, 'ENOF') in m.S_TRADER_OFFERS) or ((trader, 'LDOF') in m.S_TRADER_OFFERS):
                energy_solution = self.data.get_trader_solution_attribute(trader, 'EnergyTarget')

            if (trader, 'ENOF') in m.S_TRADER_OFFERS:
                m.V_TRADER_TOTAL_OFFER[trader, 'ENOF'].fix(energy_solution)

            if (trader, 'LDOF') in m.S_TRADER_OFFERS:
                m.V_TRADER_TOTAL_OFFER[trader, 'LDOF'].fix(energy_solution)

        return m


if __name__ == '__main__':
    # Data directory
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # Object used to get case data
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)
    parsed_data = components.parser.parse_data(json.loads(case_data_json))

    # Object used to construct and run approximate NEMDE model
    nemde = NEMDEModel(ParsedInputConstructor())

    # Construct model for given trading interval
    nemde_model = nemde.construct_model(parsed_data)

    # Solve model
    nemde_model, status = nemde.solve_model(nemde_model)

    # # Process solution
    # nemde_solution = nemde.get_solution(nemde_model)
