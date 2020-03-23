"""Class used to construct and solve NEMDE approximation"""

import os

import pandas as pd
from pyomo.environ import *
from pyomo.util.infeasible import log_infeasible_constraints

import matplotlib.pyplot as plt

from data import NEMDEDataHandler
from data import MMSDMDataHandler
from fcas import FCASHandler


class NEMDEModel:
    def __init__(self, data_dir, output_dir):
        # Directories
        self.output_dir = output_dir

        # Object used to extract NEMDE input information
        self.data = NEMDEDataHandler(data_dir)

        # Object used to extract MMSDM input information
        self.mmsdm_data = MMSDMDataHandler(data_dir)
        self.fcas = FCASHandler(data_dir)

        # Solver options
        self.tee = True
        self.keepfiles = False
        self.solver_options = {}  # 'MIPGap': 0.0005,
        self.opt = SolverFactory('cplex', solver_io='lp')

    def define_sets(self, m):
        """Define model sets"""

        # Market participants (generators and loads)
        m.S_TRADERS = Set(initialize=self.data.get_trader_index())

        # Market Network Service Providers (interconnectors that bid into the market)
        m.S_MNSPS = Set(initialize=self.data.get_mnsp_index())

        # All interconnectors (interconnector_id)
        m.S_INTERCONNECTORS = Set(initialize=self.data.get_interconnector_index())

        # Trader offer types
        m.S_TRADER_OFFERS = Set(initialize=self.data.get_trader_offer_index())

        # MNSP offer types
        m.S_MNSP_OFFERS = Set(initialize=self.data.get_mnsp_offer_index())

        # Generic constraints
        m.S_GENERIC_CONSTRAINTS = Set(initialize=self.data.get_generic_constraint_index())

        # NEM regions
        m.S_REGIONS = Set(initialize=self.data.get_region_index())

        # Generic constraints trader variables
        m.S_GC_TRADER_VARS = Set(initialize=self.data.get_generic_constraint_trader_variable_index())

        # Generic constraint interconnector variables
        m.S_GC_INTERCONNECTOR_VARS = Set(initialize=self.data.get_generic_constraint_interconnector_variable_index())

        # Generic constraint region variables
        m.S_GC_REGION_VARS = Set(initialize=self.data.get_generic_constraint_region_variable_index())

        # Price / quantity band index
        m.S_BANDS = RangeSet(1, 10, 1)

        return m

    def define_parameters(self, m):
        """Define model parameters"""

        def trader_price_band_rule(m, i, j, k):
            """Price bands for traders"""

            # NOTE: Including MLFs seem to lead to better results. May not be required.
            mlf = self.mmsdm_data.get_marginal_loss_factor(i)

            # if j == 'LDOF':
            #     return self.data.get_trader_price_band_attribute(i, j, f'PriceBand{k}') * mlf
            # else:
            #     return self.data.get_trader_price_band_attribute(i, j, f'PriceBand{k}') / mlf

            return self.data.get_trader_price_band_attribute(i, j, f'PriceBand{k}')

        # Price bands for traders (generators / loads)
        m.P_TRADER_PRICE_BAND = Param(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_price_band_rule)

        def trader_quantity_band_rule(m, i, j, k):
            """Quantity bands for traders"""

            return self.data.get_trader_quantity_band_attribute(i, j, f'BandAvail{k}')

        # Quantity bands for traders (generators / loads)
        m.P_TRADER_QUANTITY_BAND = Param(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_quantity_band_rule)

        def trader_max_available_rule(m, i, j):
            """Max available energy output from given trader"""

            # Use UIGF for max available ENOF for semi-dispatchable plant
            if (self.data.get_trader_attribute(i, 'SemiDispatch') == 1) and (j == 'ENOF'):
                return self.data.get_trader_period_attribute(i, 'UIGF')
            else:
                return self.data.get_trader_quantity_band_attribute(i, j, 'MaxAvail')

        # Max available output for given trader
        m.P_TRADER_MAX_AVAILABLE = Param(m.S_TRADER_OFFERS, rule=trader_max_available_rule)

        def trader_initial_mw_rule(m, i):
            """Initial power output condition for each trader"""

            return self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

        # Initial MW output for generators / loads
        m.P_TRADER_INITIAL_MW = Param(m.S_TRADERS, rule=trader_initial_mw_rule)

        def mnsp_price_band_rule(m, i, j, k):
            """Price bands for MNSPs"""

            return self.data.get_mnsp_price_band_attribute(i, j, f'PriceBand{k}')

        # Price bands for MNSPs
        m.P_MNSP_PRICE_BAND = Param(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_price_band_rule)

        def mnsp_quantity_band_rule(m, i, j, k):
            """Quantity bands for MNSPs"""

            return self.data.get_mnsp_quantity_band_attribute(i, j, f'BandAvail{k}')

        # Quantity bands for MNSPs
        m.P_MNSP_QUANTITY_BAND = Param(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_quantity_band_rule)

        def mnsp_max_available_rule(m, i, j):
            """Max available energy output from given MNSP"""

            return self.data.get_mnsp_quantity_band_attribute(i, j, 'MaxAvail')

        # Max available output for given MNSP
        m.P_MNSP_MAX_AVAILABLE = Param(m.S_MNSP_OFFERS, rule=mnsp_max_available_rule)

        def generic_constraint_rhs_rule(m, c):
            """RHS value for given generic constraint"""

            return self.data.get_generic_constraint_solution_attribute(c, 'RHS')

        # Generic constraint RHS
        m.P_RHS = Param(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_rule)

        def region_demand_rule(m, r):
            """Get demand in each region. Using forecast demand for now."""

            return self.data.get_region_period_attribute(r, 'DemandForecast')

        # Demand in each NEM region
        m.P_REGION_DEMAND = Param(m.S_REGIONS, rule=region_demand_rule)

        def generic_constraint_violation_factor_rule(m, c):
            """Constraint violation penalty for given generic constraint"""

            return self.data.get_generic_constraint_attribute(c, 'ViolationPrice')

        # Constraint violation factors
        m.P_CVF_GC = Param(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_factor_rule)

        # Value of lost load
        m.P_CVF_VOLL = Param(initialize=self.data.get_case_attribute('VoLL'))

        # Energy deficit price
        m.P_CVF_ENERGY_DEFICIT_PRICE = Param(initialize=self.data.get_case_attribute('EnergyDeficitPrice'))

        # Energy surplus price
        m.P_CVF_ENERGY_SURPLUS_PRICE = Param(initialize=self.data.get_case_attribute('EnergySurplusPrice'))

        # Ramp-rate constraint violation factor
        m.P_CVF_RAMP_RATE_PRICE = Param(initialize=self.data.get_case_attribute('RampRatePrice'))

        # Capacity price (assume for constraint ensuring max available capacity not exceeded)
        m.P_CVF_CAPACITY_PRICE = Param(initialize=self.data.get_case_attribute('CapacityPrice'))

        # Offer price (assume for constraint ensuring band offer amounts are not exceeded)
        m.P_CVF_OFFER_PRICE = Param(initialize=self.data.get_case_attribute('OfferPrice'))

        # MNSP offer price (assumed for constraint ensuring MNSP band offers are not exceeded)
        m.P_CVF_MNSP_OFFER_PRICE = Param(initialize=self.data.get_case_attribute('MNSPOfferPrice'))

        # MNSP ramp rate price (not sure what this applies to - unclear what MNSP ramp rates are)
        m.P_CVF_MNSP_RAMP_RATE_PRICE = Param(initialize=self.data.get_case_attribute('MNSPRampRatePrice'))

        # MNSP capacity price (assume for constraint ensuring max available capacity not exceeded)
        m.P_CVF_MNSP_CAPACITY_PRICE = Param(initialize=self.data.get_case_attribute('MNSPCapacityPrice'))

        # Ancillary services profile price (assume for constraint ensure FCAS trapezium not violated)
        m.P_CVF_AS_PROFILE_PRICE = Param(initialize=self.data.get_case_attribute('ASProfilePrice'))

        # Ancillary services max available price (assume for constraint ensure max available amount not exceeded)
        m.P_CVF_AS_MAX_AVAIL_PRICE = Param(initialize=self.data.get_case_attribute('ASMaxAvailPrice'))

        # Ancillary services enablement min price (assume for constraint ensure FCAS > enablement min if active)
        m.P_CVF_AS_ENABLEMENT_MIN_PRICE = Param(initialize=self.data.get_case_attribute('ASEnablementMinPrice'))

        # Ancillary services enablement max price (assume for constraint ensure FCAS < enablement max if active)
        m.P_CVF_AS_ENABLEMENT_MAX_PRICE = Param(initialize=self.data.get_case_attribute('ASEnablementMaxPrice'))

        # Interconnector powerflow violation price
        m.P_CVF_INTERCONNECTOR_PRICE = Param(initialize=self.data.get_case_attribute('InterconnectorPrice'))

        return m

    @staticmethod
    def define_variables(m):
        """Define model variables"""

        # Offers for each quantity band
        m.V_TRADER_OFFER = Var(m.S_TRADER_OFFERS, m.S_BANDS, within=NonNegativeReals)
        m.V_MNSP_OFFER = Var(m.S_MNSP_OFFERS, m.S_BANDS, within=NonNegativeReals)

        # Total MW offer for each offer type
        m.V_TRADER_TOTAL_OFFER = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)
        m.V_MNSP_TOTAL_OFFER = Var(m.S_MNSP_OFFERS, within=NonNegativeReals)

        # Generic constraint variables
        m.V_GC_TRADER = Var(m.S_GC_TRADER_VARS)
        m.V_GC_INTERCONNECTOR = Var(m.S_GC_INTERCONNECTOR_VARS)
        m.V_GC_REGION = Var(m.S_GC_REGION_VARS)

        # Generic constraint violation variables
        m.V_CV = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_LHS = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_RHS = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)

        # Trader band offer < bid violation
        m.V_CV_TRADER_OFFER = Var(m.S_TRADER_OFFERS, m.S_BANDS, within=NonNegativeReals)

        # Trader total capacity < max available violation
        m.V_CV_TRADER_CAPACITY = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)

        # MNSP band offer < bid violation
        m.V_CV_MNSP_OFFER = Var(m.S_MNSP_OFFERS, m.S_BANDS, within=NonNegativeReals)

        # MNSP total capacity < max available violation
        m.V_CV_MNSP_CAPACITY = Var(m.S_MNSP_OFFERS, within=NonNegativeReals)

        # Ramp rate constraint violation variables
        m.V_CV_TRADER_RAMP_UP = Var(m.S_TRADERS, within=NonNegativeReals)
        m.V_CV_TRADER_RAMP_DOWN = Var(m.S_TRADERS, within=NonNegativeReals)

        # FCAS trapezium violation variables
        m.V_CV_TRADER_FCAS_TRAPEZIUM = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)

        # FCAS joint ramping constraint violation variables
        m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)
        m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)

        # FCAS joint capacity constraint violation variables
        m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)
        m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)

        # FCAS joint regulating capacity constraint violation variables
        m.V_CV_JOINT_REGULATING_CAPACITY_UP = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)
        m.V_CV_JOINT_REGULATING_CAPACITY_DOWN = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)

        # Interconnector forward and reverse flow constraint violation
        m.V_CV_INTERCONNECTOR_FORWARD = Var(m.S_INTERCONNECTORS, within=NonNegativeReals)
        m.V_CV_INTERCONNECTOR_REVERSE = Var(m.S_INTERCONNECTORS, within=NonNegativeReals)

        return m

    @staticmethod
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
        m.E_TRADER_COST_FUNCTION = Expression(m.S_TRADER_OFFERS, rule=trader_cost_function_rule)

        def mnsp_cost_function_rule(m, i, j):
            """MNSP cost function"""

            # TODO: Assumes interconnector treated as generator in each region. Need to check.
            return sum(m.P_MNSP_PRICE_BAND[i, j, b] * m.V_MNSP_OFFER[i, j, b] for b in m.S_BANDS)

        # MNSP cost functions
        m.E_MNSP_COST_FUNCTION = Expression(m.S_MNSP_OFFERS, rule=mnsp_cost_function_rule)

        return m

    def define_generic_constraint_expressions(self, m):
        """Define expressions used to construct generic constraint components"""

        def lhs_terms_rule(m, i):
            """Get LHS expression for a given Generic Constraint"""

            # LHS terms and associated factors
            terms = self.data.get_generic_constraint_lhs_terms(i)

            # Trader terms
            t_terms = sum(m.V_GC_TRADER[index] * factor for index, factor in terms['traders'].items())

            # Interconnector terms
            i_terms = sum(m.V_GC_INTERCONNECTOR[index] * factor for index, factor in terms['interconnectors'].items())

            # Region terms
            r_terms = sum(m.V_GC_REGION[index] * factor for index, factor in terms['regions'].items())

            return t_terms + i_terms + r_terms

        # Generic constraint LHS
        m.E_LHS_TERMS = Expression(m.S_GENERIC_CONSTRAINTS, rule=lhs_terms_rule)

        return m

    @staticmethod
    def define_constraint_violation_penalty_expressions(m):
        """Define expressions relating constraint violation penalties"""

        def generic_constraint_violation_rule(m, i):
            """Constraint violation penalty for generic constraint which is an inequality"""

            return m.P_CVF_GC[i] * m.V_CV[i]

        # Constraint violation penalty for inequality constraints
        m.E_CV_GC_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_rule)

        def generic_constraint_lhs_violation_rule(m, i):
            """Constraint violation penalty for equality constraint"""

            return m.P_CVF_GC[i] * m.V_CV_LHS[i]

        # Constraint violation penalty for equality constraints
        m.E_CV_GC_LHS_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_violation_rule)

        def generic_constraint_rhs_violation_rule(m, i):
            """Constraint violation penalty for equality constraint"""

            return m.P_CVF_GC[i] * m.V_CV_RHS[i]

        # Constraint violation penalty for equality constraints
        m.E_CV_GC_RHS_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_violation_rule)

        def trader_offer_penalty_rule(m, i, j, k):
            """Penalty for band amount exceeding band bid amount"""

            return m.P_CVF_OFFER_PRICE * m.V_CV_TRADER_OFFER[i, j, k]

        # Constraint violation penalty for trader dispatched band amount exceeding bid amount
        m.E_CV_TRADER_OFFER_PENALTY = Expression(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_penalty_rule)

        def trader_capacity_penalty_rule(m, i, j):
            """Penalty for total band amount exceeding max available amount"""

            return m.P_CVF_CAPACITY_PRICE * m.V_CV_TRADER_CAPACITY[i, j]

        # Constraint violation penalty for total offer amount exceeding max available
        m.E_CV_TRADER_CAPACITY_PENALTY = Expression(m.S_TRADER_OFFERS, rule=trader_capacity_penalty_rule)

        def trader_ramp_up_penalty_rule(m, i):
            """Penalty for violating ramp down constraint"""

            return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_UP[i]

        # Penalty factor for ramp up rate violation
        m.E_CV_TRADER_RAMP_UP_PENALTY = Expression(m.S_TRADERS, rule=trader_ramp_up_penalty_rule)

        def trader_ramp_down_penalty_rule(m, i):
            """Penalty for violating ramp down constraint"""

            return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_DOWN[i]

        # Penalty factor for ramp down rate violation
        m.E_CV_TRADER_RAMP_DOWN_PENALTY = Expression(m.S_TRADERS, rule=trader_ramp_down_penalty_rule)

        def trader_trapezium_penalty_rule(m, i, j):
            """Penalty for violating FCAS trapezium bounds"""

            return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_TRAPEZIUM[i, j]

        # FCAS trapezium violation penalty
        m.E_CV_TRADER_TRAPEZIUM_PENALTY = Expression(m.S_TRADER_OFFERS, rule=trader_trapezium_penalty_rule)

        def trader_joint_ramping_up_penalty_rule(m, i, j):
            """Penalty for FCAS joint capacity constraint up violation"""

            return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j]

        # FCAS joint ramping constraint down violation penalty
        m.E_CV_TRADER_JOINT_RAMPING_UP_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                            rule=trader_joint_ramping_up_penalty_rule)

        def trader_joint_ramping_down_penalty_rule(m, i, j):
            """Penalty for FCAS joint ramping constraint down violation"""

            return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j]

        # FCAS joint ramping constraint down violation penalty
        m.E_CV_TRADER_JOINT_RAMPING_DOWN_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                              rule=trader_joint_ramping_down_penalty_rule)

        def trader_joint_capacity_up_penalty_rule(m, i, j):
            """Penalty for FCAS joint capacity constraint up violation"""

            return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j]

        # FCAS joint capacity constraint up violation penalty
        m.E_CV_TRADER_JOINT_CAPACITY_UP_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                             rule=trader_joint_capacity_up_penalty_rule)

        def trader_joint_capacity_down_penalty_rule(m, i, j):
            """Penalty for FCAS joint capacity constraint down violation"""

            return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j]

        # FCAS joint capacity constraint down violation penalty
        m.E_CV_TRADER_JOINT_CAPACITY_DOWN_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                               rule=trader_joint_capacity_down_penalty_rule)

        def trader_joint_regulating_capacity_up_penalty_rule(m, i, j):
            """Penalty for FCAS joint capacity constraint up violation"""

            return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_JOINT_REGULATING_CAPACITY_UP[i, j]

        # FCAS joint capacity constraint down violation penalty
        m.E_CV_JOINT_REGULATING_CAPACITY_UP_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                                 rule=trader_joint_regulating_capacity_up_penalty_rule)

        def trader_joint_regulating_capacity_down_penalty_rule(m, i, j):
            """Penalty for FCAS joint capacity constraint down violation"""

            return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_JOINT_REGULATING_CAPACITY_DOWN[i, j]

        # FCAS joint capacity constraint down violation penalty
        m.E_CV_JOINT_REGULATING_CAPACITY_DOWN_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                                   rule=trader_joint_regulating_capacity_down_penalty_rule)

        def mnsp_offer_penalty_rule(m, i, j, k):
            """Penalty for band amount exceeding band bid amount"""

            return m.P_CVF_MNSP_OFFER_PRICE * m.V_CV_MNSP_OFFER[i, j, k]

        # Constraint violation penalty for MNSP dispatched band amount exceeding bid amount
        m.E_CV_MNSP_OFFER_PENALTY = Expression(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_penalty_rule)

        def mnsp_capacity_penalty_rule(m, i, j):
            """Penalty for total band amount exceeding max available amount"""

            return m.P_CVF_MNSP_CAPACITY_PRICE * m.V_CV_MNSP_CAPACITY[i, j]

        # Constraint violation penalty for total offer amount exceeding max available
        m.E_CV_MNSP_CAPACITY_PENALTY = Expression(m.S_MNSP_OFFERS, rule=mnsp_capacity_penalty_rule)

        def interconnector_forward_penalty_rule(m, i):
            """Penalty for forward powerflow exceeding max allowable flow"""

            return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_FORWARD[i]

        # Constraint violation penalty for forward interconnector limit being violated
        m.E_CV_INTERCONNECTOR_FORWARD_PENALTY = Expression(m.S_INTERCONNECTORS,
                                                           rule=interconnector_forward_penalty_rule)

        def interconnector_reverse_penalty_rule(m, i):
            """Penalty for reverse powerflow exceeding max allowable flow"""

            return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_REVERSE[i]

        # Constraint violation penalty for forward interconnector limit being violated
        m.E_CV_INTERCONNECTOR_REVERSE_PENALTY = Expression(m.S_INTERCONNECTORS,
                                                           rule=interconnector_reverse_penalty_rule)

        # Sum of all constraint violation penalties
        m.E_CV_TOTAL_PENALTY = Expression(expr=sum(m.E_CV_GC_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
                                               + sum(m.E_CV_GC_LHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
                                               + sum(m.E_CV_GC_RHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
                                               + sum(m.E_CV_TRADER_OFFER_PENALTY[i, j, k] for i, j in m.S_TRADER_OFFERS
                                                     for k in m.S_BANDS)
                                               + sum(m.E_CV_TRADER_CAPACITY_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(m.E_CV_TRADER_RAMP_UP_PENALTY[i] for i in m.S_TRADERS)
                                               + sum(m.E_CV_TRADER_RAMP_DOWN_PENALTY[i] for i in m.S_TRADERS)
                                               + sum(m.E_CV_TRADER_TRAPEZIUM_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(
            m.E_CV_TRADER_JOINT_RAMPING_UP_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(
            m.E_CV_TRADER_JOINT_RAMPING_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(
            m.E_CV_TRADER_JOINT_CAPACITY_UP_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(
            m.E_CV_TRADER_JOINT_CAPACITY_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(
            m.E_CV_JOINT_REGULATING_CAPACITY_UP_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(
            m.E_CV_JOINT_REGULATING_CAPACITY_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                               + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS
                                                     for k in m.S_BANDS)
                                               + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
                                               + sum(
            m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i] for i in m.S_INTERCONNECTORS)
                                               + sum(
            m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i] for i in m.S_INTERCONNECTORS)
                                          )

        return m

    def define_aggregate_power_expressions(self, m):
        """Compute aggregate demand and generation in each NEM region"""

        def region_generation_rule(m, r):
            """Available energy offers in given region"""

            return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS if (j == 'ENOF')
                       and (self.data.get_trader_period_attribute(i, 'RegionID') == r))

        # Total generation dispatched in a given region
        m.E_REGION_GENERATION = Expression(m.S_REGIONS, rule=region_generation_rule)

        def region_load_rule(m, r):
            """Available load offers in given region"""

            return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS if (j == 'LDOF')
                       and (self.data.get_trader_period_attribute(i, 'RegionID') == r))

        # Total load dispatched in a given region
        m.E_REGION_LOAD = Expression(m.S_REGIONS, rule=region_load_rule)

        def region_net_flow_rule(m, r):
            """Compute net flow out of region (export - import)"""

            # Network incidence matrix
            incidence_matrix = self.get_incidence_matrix(m)

            return sum(incidence_matrix[i][r] * m.V_GC_INTERCONNECTOR[i] for i in m.S_INTERCONNECTORS)

        # Net flow out of region
        m.E_REGION_NET_FLOW = Expression(m.S_REGIONS, rule=region_net_flow_rule)

        def region_loss_rule(m, r):
            """Approximate loss in each region based on Marginal Loss Factors"""

            return sum(m.V_TRADER_TOTAL_OFFER[i, j] * (1 - self.mmsdm_data.get_marginal_loss_factor(i))
                       for i, j in m.S_TRADER_OFFERS
                       if (j == 'ENOF') and (self.data.get_trader_period_attribute(i, 'RegionID') == r))

        # Loss in a given region
        m.E_REGION_LOSS = Expression(m.S_REGIONS, rule=region_loss_rule)

        return m

    def define_expressions(self, m):
        """Define model expressions"""

        # Define all expression types
        m = self.define_cost_function_expressions(m)
        m = self.define_generic_constraint_expressions(m)
        m = self.define_constraint_violation_penalty_expressions(m)
        m = self.define_aggregate_power_expressions(m)

        return m

    def define_generic_constraints(self, m):
        """
        Construct generic constraints. Also include constraints linking variables in objective function to variables in
        Generic Constraints.
        """

        def trader_variable_link_rule(m, i, j):
            """Link generic constraint trader variables to objective function variables"""

            return m.V_TRADER_TOTAL_OFFER[i, j] == m.V_GC_TRADER[i, j]

        # Link between total power output and quantity band output
        m.C_TRADER_VARIABLE_LINK = Constraint(m.S_GC_TRADER_VARS, rule=trader_variable_link_rule)

        def region_variable_link_rule(m, i, j):
            """Link total offer amount for each bid type to region variables"""

            return (sum(m.V_TRADER_TOTAL_OFFER[q, r] for q, r in m.S_TRADER_OFFERS
                        if (self.data.get_trader_period_attribute(q, 'RegionID') == i) and (r == j))
                    == m.V_GC_REGION[i, j])

        # Link between region variables and the trader components constituting those variables
        m.C_REGION_VARIABLE_LINK = Constraint(m.S_GC_REGION_VARS, rule=region_variable_link_rule)

        def mnsp_variable_link_rule(m, i):
            """Link generic constraint MNSP variables to objective function variables"""

            # From and to regions for a given MNSP
            from_region = self.data.get_interconnector_period_attribute(i, 'FromRegion')
            to_region = self.data.get_interconnector_period_attribute(i, 'ToRegion')

            # TODO: Taking difference between 'to' and 'from' region. Think this is correct.
            return m.V_GC_INTERCONNECTOR[i] == m.V_MNSP_TOTAL_OFFER[i, to_region] - m.V_MNSP_TOTAL_OFFER[i, from_region]

        # Link between total power output and quantity band output
        m.C_MNSP_VARIABLE_LINK = Constraint(m.S_MNSPS, rule=mnsp_variable_link_rule)

        def generic_constraint_rule(m, c):
            """NEMDE Generic Constraints"""

            # Type of generic constraint (LE, GE, EQ)
            constraint_type = self.data.get_generic_constraint_attribute(c, 'Type')

            if constraint_type == 'LE':
                return m.E_LHS_TERMS[c] <= m.P_RHS[c] + m.V_CV[c]
            elif constraint_type == 'GE':
                return m.E_LHS_TERMS[c] + m.V_CV[c] >= m.P_RHS[c]
            elif constraint_type == 'EQ':
                return m.E_LHS_TERMS[c] + m.V_CV_LHS[c] == m.P_RHS[c] + m.V_CV_RHS[c]
            else:
                raise Exception(f'Unexpected constraint type: {constraint_type}')

        # Generic constraints
        m.C_GENERIC_CONSTRAINT = Constraint(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rule)

        return m

    def define_offer_constraints(self, m):
        """Ensure trader and MNSP bids don't exceed their specified bid bands"""

        def trader_total_offer_rule(m, i, j):
            """Link quantity band offers to total offer made by trader for each offer type"""

            return m.V_TRADER_TOTAL_OFFER[i, j] == sum(m.V_TRADER_OFFER[i, j, k] for k in m.S_BANDS)

            # Linking individual quantity band offers to total amount offered by trader

        m.C_TRADER_TOTAL_OFFER = Constraint(m.S_TRADER_OFFERS, rule=trader_total_offer_rule)

        def trader_offer_rule(m, i, j, k):
            """Band output must be non-negative and less than the max offered amount for that band"""

            return m.V_TRADER_OFFER[i, j, k] <= m.P_TRADER_QUANTITY_BAND[i, j, k] + m.V_CV_TRADER_OFFER[i, j, k]

        # Bounds on quantity band variables for traders
        m.C_TRADER_OFFER = Constraint(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_rule)

        def trader_capacity_rule(m, i, j):
            """Constrain max available output"""

            return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_CAPACITY[i, j]

        # Ensure dispatch is constrained by max available offer amount
        m.C_TRADER_CAPACITY = Constraint(m.S_TRADER_OFFERS, rule=trader_capacity_rule)

        def mnsp_total_offer_rule(m, i, j):
            """Link quantity band offers to total offer made by MNSP for each offer type"""

            return m.V_MNSP_TOTAL_OFFER[i, j] == sum(m.V_MNSP_OFFER[i, j, k] for k in m.S_BANDS)

        # Linking individual quantity band offers to total amount offered by MNSP
        m.C_MNSP_TOTAL_OFFER = Constraint(m.S_MNSP_OFFERS, rule=mnsp_total_offer_rule)

        def mnsp_offer_rule(m, i, j, k):
            """Band output must be non-negative and less than the max offered amount for that band"""

            return m.V_MNSP_OFFER[i, j, k] <= m.P_MNSP_QUANTITY_BAND[i, j, k] + m.V_CV_MNSP_OFFER[i, j, k]

        # Bounds on quantity band variables for MNSPs
        m.C_MNSP_OFFER = Constraint(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_rule)

        def mnsp_capacity_rule(m, i, j):
            """Constrain max available output"""

            return m.V_MNSP_TOTAL_OFFER[i, j] <= m.P_MNSP_MAX_AVAILABLE[i, j] + m.V_CV_MNSP_CAPACITY[i, j]

        # Ensure dispatch is constrained by max available offer amount
        m.C_MNSP_CAPACITY = Constraint(m.S_MNSP_OFFERS, rule=mnsp_capacity_rule)

        return m

    def define_unit_constraints(self, m):
        """Construct ramp rate constraints for units"""

        def trader_ramp_up_rate_rule(m, i, j):
            """Ramp up rate limit for ENOF and LDOF offers"""

            # Only construct ramp-rate constraint for energy offers
            if (j != 'ENOF') and (j != 'LDOF'):
                return Constraint.Skip

            # Ramp rate
            ramp_limit = self.data.get_trader_quantity_band_attribute(i, j, 'RampUpRate')

            # Initial MW
            initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

            return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw <= (ramp_limit / 12) + m.V_CV_TRADER_RAMP_UP[i]

        # Ramp up rate limit
        m.C_TRADER_RAMP_UP_RATE = Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_up_rate_rule)

        def trader_ramp_down_rate_rule(m, i, j):
            """Ramp down rate limit for ENOF and LDOF offers"""

            # Only construct ramp-rate constraint for energy offers
            if (j != 'ENOF') and (j != 'LDOF'):
                return Constraint.Skip

            # Ramp rate
            ramp_limit = self.data.get_trader_quantity_band_attribute(i, j, 'RampDnRate')

            # Initial MW
            initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

            return m.V_TRADER_TOTAL_OFFER[i, j] - initial_mw + m.V_CV_TRADER_RAMP_DOWN[i] >= - (ramp_limit / 12)

        # Ramp up rate limit
        m.C_TRADER_RAMP_DOWN_RATE = Constraint(m.S_TRADER_OFFERS, rule=trader_ramp_down_rate_rule)

        return m

    def get_incidence_matrix(self, m):
        """
        Construct region incidence matrix for interconnectors. Coefficient of +1 indicates 'from' region, -1 indicates
        'to' region
        """

        # Initialise container for incidence matrix information
        incidence_matrix = dict()

        for i in m.S_INTERCONNECTORS:
            from_region = self.data.get_interconnector_period_attribute(i, 'FromRegion')
            to_region = self.data.get_interconnector_period_attribute(i, 'ToRegion')

            # Initialise inner dictionary to contain regions
            incidence_matrix[i] = dict()

            # Iterate over NEM regions
            for r in m.S_REGIONS:

                # Assign +1 if region is interconnector's 'from' region
                if r == from_region:
                    incidence_matrix[i][r] = 1

                # Assign -1 if region is interconnector's 'to' region
                elif r == to_region:
                    incidence_matrix[i][r] = -1

                # Assign 0 if interconnector not connected to region
                else:
                    incidence_matrix[i][r] = 0

        return incidence_matrix

    @staticmethod
    def define_region_constraints(m):
        """Define power balance constraint for each region, and constrain flows on interconnectors"""

        def power_balance_rule(m, r):
            """Power balance for each region"""

            return m.E_REGION_GENERATION[r] - m.E_REGION_LOAD[r] == m.P_REGION_DEMAND[r] + m.E_REGION_NET_FLOW[r]

        # Power balance in each region
        # TODO: add interconnectors
        m.C_POWER_BALANCE = Constraint(m.S_REGIONS, rule=power_balance_rule)

        return m

    def define_interconnector_constraints(self, m):
        """Define powerflow limits on interconnectors"""

        def interconnector_forward_flow_rule(m, i):
            """Constrain forward powerflow over interconnector"""

            return (m.V_GC_INTERCONNECTOR[i] <= self.data.get_interconnector_period_attribute(i, 'UpperLimit')
                    + m.V_CV_INTERCONNECTOR_FORWARD[i])

        # Forward power flow limit for interconnector
        m.C_INTERCONNECTOR_FORWARD_FLOW = Constraint(m.S_INTERCONNECTORS, rule=interconnector_forward_flow_rule)

        def interconnector_reverse_flow_rule(m, i):
            """Constrain reverse powerflow over interconnector"""

            return (m.V_GC_INTERCONNECTOR[i] + m.V_CV_INTERCONNECTOR_REVERSE[i]
                    >= - self.data.get_interconnector_period_attribute(i, 'LowerLimit'))

        # Forward power flow limit for interconnector
        m.C_INTERCONNECTOR_REVERSE_FLOW = Constraint(m.S_INTERCONNECTORS, rule=interconnector_reverse_flow_rule)

    def get_fcas_trapezium_offer(self, trader_id, trade_type):
        """Get FCAS trapezium offer for a given trader and trade type"""

        # Trapezium information
        enablement_min = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMin')
        enablement_max = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMax')
        low_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'LowBreakpoint')
        high_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'HighBreakpoint')
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

        # Store FCAS trapezium information in a dictionary
        trapezium = {'enablement_min': enablement_min, 'enablement_max': enablement_max, 'max_available': max_available,
                     'low_breakpoint': low_breakpoint, 'high_breakpoint': high_breakpoint}

        return trapezium

    def get_fcas_trapezium_scaled_enablement_min(self, trader_id, trapezium):
        """Scale enablement min for regulating service"""

        # Get AGC enablement min
        # TODO: Check if 'LMW' is the correct attribute (think so because it's located close the 'AGCStatus' attribute).
        try:
            agc_min = self.data.get_trader_initial_condition_attribute(trader_id, 'LMW')

        # No scaling applied if AGC enablement min not specified (from FCAS docs)
        except AssertionError:
            return trapezium

        # Difference between AGC enablement and offer enablement min
        offset = agc_min - trapezium['enablement_min']

        # If AGC min is more restrictive update the enablement and lower breakpoint
        if offset > 0:
            trapezium['low_breakpoint'] = trapezium['low_breakpoint'] + offset
            trapezium['enablement_min'] = agc_min

        return trapezium

    def get_fcas_trapezium_scaled_enablement_max(self, trader_id, trapezium):
        """Scale enablement max for regulating service"""

        # Get AGC enablement min
        # TODO: Check if 'HMW' is the correct attribute (think so because it's located close the 'AGCStatus' attribute).

        try:
            agc_max = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')

        # No scaling applied if AGC enablement min not specified (from FCAS docs)
        except AssertionError:
            return trapezium

        # Difference between AGC enablement and offer enablement min
        offset = trapezium['enablement_max'] - agc_max

        # If AGC min is more restrictive update the enablement and lower breakpoint
        if offset > 0:
            trapezium['high_breakpoint'] = trapezium['high_breakpoint'] - offset
            trapezium['enablement_max'] = agc_max

        return trapezium

    @staticmethod
    def get_trapezium_lhs_slope(trapezium):
        """Get slope on LHS of trapezium. Return None if slope is undefined."""

        try:
            return trapezium['max_available'] / (trapezium['low_breakpoint'] - trapezium['enablement_min'])
        except ZeroDivisionError:
            return None

    @staticmethod
    def get_trapezium_rhs_slope(trapezium):
        """Get slope on RHS of trapezium. Return None if slope is undefined."""

        try:
            return -trapezium['max_available'] / (trapezium['enablement_max'] - trapezium['high_breakpoint'])
        except ZeroDivisionError:
            return None

    def get_fcas_trapezium_scaled_agc_max_available(self, trader_id, trade_type, trapezium):
        """Scale max availability using AGC ramp rates"""

        # Try and get AGC ramp rate. Set to 0 if not found (will not perform scaling if ramp rate missing or = 0)
        try:
            if trade_type == 'R5RE':
                ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate') / 12
            elif trade_type == 'L5RE':
                ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampDnRate') / 12
            else:
                raise Exception(f'Should only scale FCAS trapezium for L5RE and R5RE offers. Encountered: {trade_type}')

        except AssertionError:
            ramp_rate = 0

        # Return unscaled trapezium if AGC ramp rate = 0 or missing (from FCAS NEMDE docs)
        if ramp_rate == 0:
            return trapezium

        # Update max available if AGC ramp rate is more restrictive
        if ramp_rate < trapezium['max_available']:
            lhs_slope = self.get_trapezium_lhs_slope(trapezium)
            rhs_slope = self.get_trapezium_rhs_slope(trapezium)

            trapezium['max_available'] = ramp_rate

            if lhs_slope is not None:
                trapezium['low_breakpoint'] = trapezium['enablement_min'] + (ramp_rate / lhs_slope)

            if rhs_slope is not None:
                trapezium['high_breakpoint'] = trapezium['enablement_max'] - (ramp_rate / rhs_slope)

        return trapezium

    def get_fcas_trapezium_scaled_uigf_max_available(self, trader_id, trapezium):
        """For semi-scheduled units, scale all FCAS max available offers by UIGF if UIGF more restrictive"""

        # Get UIGF value
        uigf = self.data.get_trader_period_attribute(trader_id, 'UIGF')

        # Slope on left side of trapezium (positive slope)
        lhs_slope = self.get_trapezium_lhs_slope(trapezium)
        rhs_slope = self.get_trapezium_rhs_slope(trapezium)

        # Offset between max available and UIGF
        offset = trapezium['max_available'] - uigf

        # Must restrict max available to UIGF if max available offer > UIGF. Adjust breakpoints accordingly.
        if offset > 0:
            trapezium['max_available'] = uigf

            if lhs_slope is not None:
                trapezium['low_breakpoint'] = trapezium['low_breakpoint'] - (lhs_slope * offset)

            if rhs_slope is not None:
                trapezium['high_breakpoint'] = trapezium['high_breakpoint'] - (rhs_slope * offset)

        return trapezium

    def get_scaled_fcas_trapezium(self, trader_id, trade_type):
        """
        Scale FCAS trapezium using AGC enablement min (if more restrictive than offer enablement min).

        Note: trapezium scaling only applied to contingency services
        """

        # Trapezium scaling only applied to regulation services
        assert trade_type in ['R5RE', 'L5RE']

        # Get FCAS trapezium offer information
        trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

        # Regulating services - AGC enablement min (return scaled trapezium)
        trapezium = self.get_fcas_trapezium_scaled_enablement_min(trader_id, trapezium)

        # Regulating services - AGC enablement max (return scaled trapezium)
        trapezium = self.get_fcas_trapezium_scaled_enablement_max(trader_id, trapezium)

        # Regulating services - AGC ramp rates (return scaled trapezium) - no scaling if AGC ramp rate is zero of absent
        trapezium = self.get_fcas_trapezium_scaled_agc_max_available(trader_id, trade_type, trapezium)

        # Regulating services - UIGF for FCAS from semi-scheduled units (effective max enablement if more restrictive)
        semi_dispatch = self.data.get_trader_attribute(trader_id, 'SemiDispatch')
        if semi_dispatch == 1:
            trapezium = self.get_fcas_trapezium_scaled_uigf_max_available(trader_id, trapezium)

        return trapezium

    def check_fcas_max_availability(self, trader_id, trade_type):
        """Check if max availability amount is greater than 0"""

        # Scaled FCAS trapezium for regulation offers
        if trade_type in ['R5RE', 'L5RE']:
            trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)

        # No scaling applied to contingency offers
        else:
            trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

        return trapezium['max_available'] > 0

    def check_fcas_positive_offer(self, trader_id, trade_type):
        """Check that at least one price band has capacity greater than 0"""

        # Quantities within each band for the offer type
        quantities = [self.data.get_trader_quantity_band_attribute(trader_id, trade_type, f'BandAvail{i}') for
                      i in range(1, 11)]

        # Check if at least one band has a capacity greater than 0
        return max(quantities) > 0

    def check_fcas_energy_enablement_min(self, trader_id, trade_type):
        """Check that max energy available exceeds the enablement min"""

        # Scaled FCAS trapezium
        if trade_type in ['R5RE', 'L5RE']:
            trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)
        else:
            trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

        # Energy max availability
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

        return max_available >= trapezium['max_available']

    def check_fcas_enablement_max(self, trader_id, trade_type):
        """Check FCAS max availability greater than or equal to 0"""

        # Scaled FCAS trapezium
        if trade_type in ['R5RE', 'L5RE']:
            trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)
        else:
            trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

        return trapezium['enablement_max'] >= 0

    def check_fcas_initial_mw(self, trader_id, trade_type):
        """Check that initial MW is between the enablement max and min limits"""

        # Scaled FCAS trapezium
        if trade_type in ['R5RE', 'L5RE']:
            trapezium = self.get_scaled_fcas_trapezium(trader_id, trade_type)
        else:
            trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

        # Initial MW
        initial_mw = self.data.get_trader_initial_condition_attribute(trader_id, 'InitialMW')

        return trapezium['enablement_min'] <= initial_mw <= trapezium['enablement_max']

    def check_fcas_preconditions(self, trader_id, trade_type):
        """Check pre-conditions for FCAS. Only construct constraints if conditions met."""

        # Check that max FCAS availability for offer type is greater than 0
        cond_1 = self.check_fcas_max_availability(trader_id, trade_type)

        # Check that at least one offer price band contains a capacity greater than 0
        cond_2 = self.check_fcas_positive_offer(trader_id, trade_type)

        # Check that energy availability is greater than enablement min for offer type
        cond_3 = self.check_fcas_energy_enablement_min(trader_id, trade_type)

        # Check that FCAS enablement maximum is greater than or equal to 0
        cond_4 = self.check_fcas_enablement_max(trader_id, trade_type)

        # Check that unit initially operating between enablement min and max levels
        cond_5 = self.check_fcas_initial_mw(trader_id, trade_type)

        # Check FCAS preconditions. Note: doesn't include AGC status condition
        fcas_available = cond_1 and cond_2 and cond_3 and cond_4 and cond_5

        return fcas_available

    def check_trader_has_energy_offer(self, trader_id, m):
        """Check if a unit has an energy offer"""

        # Get trader type
        trader_type = self.data.get_trader_attribute(trader_id, 'TraderType')

        if trader_type == 'GENERATOR':
            energy_key = 'ENOF'
        elif (trader_type == 'LOAD') or (trader_type == 'NORMALLY_ON_LOAD'):
            energy_key = 'LDOF'
        else:
            raise Exception(f'Unexpected trader type: {trader_type}')

        # Check if energy offer made by generator
        if (trader_id, energy_key) in m.S_TRADER_OFFERS:
            return True
        else:
            return False

    def define_fcas_constraints(self, m):
        """Define FCAS constraints"""

        def as_profile_rule(m, i, j):
            """Compute max available based on initial MW"""

            if j not in ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']:
                return Constraint.Skip

            # Scaled FCAS trapezium for regulation services. No scaling for contingency services
            if j in ['R5RE', 'L5RE']:
                # trapezium = self.get_scaled_fcas_trapezium(i, j)
                trapezium = self.get_fcas_trapezium_offer(i, j)
            else:
                trapezium = self.get_fcas_trapezium_offer(i, j)

            # Initial MW
            initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

            # LHS trapezium slope
            try:
                slope_1 = trapezium['max_available'] / (trapezium['low_breakpoint'] - trapezium['enablement_min'])
                constant_1 = - slope_1 * trapezium['enablement_min']
                value_1 = (slope_1 * initial_mw) + constant_1
            except ZeroDivisionError:
                value_1 = trapezium['max_available']

            # RHS trapezium slope
            try:
                slope_2 = - trapezium['max_available'] / (trapezium['enablement_max'] - trapezium['high_breakpoint'])
                constant_2 = - slope_2 * trapezium['enablement_max']
                value_2 = (slope_2 * initial_mw) + constant_2

                if i == 'BW01':
                    print(i, j, 'slope_2', slope_2)
                    print(i, j, 'constant_2', constant_2)

            except ZeroDivisionError:
                value_2 = trapezium['max_available']

            # Check if outside enablement min / max envelope
            if (initial_mw < trapezium['enablement_min']) or (initial_mw > trapezium['enablement_max']):
                max_value = 0
            else:
                max_value = min(value_1, value_2, trapezium['max_available'])

            if i == 'BW01':
                print(i, j, 'value 1', value_1)
                print(i, j, 'value 2', value_2)
                print(i, j, max_value)

            return m.V_TRADER_TOTAL_OFFER[i, j] <= max_value + m.V_CV_TRADER_FCAS_TRAPEZIUM[i, j]

        # Ancillary service profile violation
        m.C_FCAS_TRAPEZIUM = Constraint(m.S_TRADER_OFFERS, rule=as_profile_rule)

        def joint_ramping_up_rule(m, i, j):
            """Joint energy and FCAS ramping constraints"""

            # Only construct constraints for up regulation offers
            if j != 'R5RE':
                return Constraint.Skip

            # Check FCAS preconditions
            fcas_available = self.check_fcas_preconditions(i, j)

            # Check unit has energy offer
            has_energy_offer = self.check_trader_has_energy_offer(i, m)

            # If FCAS not available or no energy offer provided then constraint is not constructed
            if not fcas_available or not has_energy_offer:
                return Constraint.Skip

            # Check if a generator is a generator, load, or normally on load
            trader_type = self.data.get_trader_attribute(i, 'TraderType')

            # Get AGC status of generator
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # No constraint if AGC not enabled
            if agc_status != 1:
                return Constraint.Skip

            # Map between trader type and energy offer key
            offer_map = {'GENERATOR': 'ENOF', 'LOAD': 'LDOF', 'NORMALLY_ON_LOAD': 'LDOF'}

            # Get the AGC ramp rate
            ramp_rate = self.data.get_trader_initial_condition_attribute(i, 'SCADARampUpRate') / 12

            # No constraint if ramp rate <= 0
            if ramp_rate <= 0:
                return Constraint.Skip

            # Get initial MW
            initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

            return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] + m.V_TRADER_TOTAL_OFFER[i, j]
                    <= initial_mw + ramp_rate + m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, offer_map[trader_type]])

        # Joint ramp up constraint
        m.C_JOINT_RAMPING_UP = Constraint(m.S_TRADER_OFFERS, rule=joint_ramping_up_rule)

        def joint_ramping_down_rule(m, i, j):
            """Joint energy and FCAS ramping constraints"""

            # Only construct constraints for up regulation offers
            if j != 'L5RE':
                return Constraint.Skip

            # Check FCAS preconditions
            fcas_available = self.check_fcas_preconditions(i, j)

            # Check unit has energy offer
            has_energy_offer = self.check_trader_has_energy_offer(i, m)

            # If FCAS not available or no energy offer provided then constraint is constructed
            if not fcas_available or not has_energy_offer:
                return Constraint.Skip

            # Check if a generator is a generator, load, or normally on load
            trader_type = self.data.get_trader_attribute(i, 'TraderType')

            # Get AGC status of generator
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # No constraint if AGC not enabled
            if agc_status != 1:
                return Constraint.Skip

            # Map between trader type and energy offer key
            offer_map = {'GENERATOR': 'ENOF', 'LOAD': 'LDOF', 'NORMALLY_ON_LOAD': 'LDOF'}

            # Get the AGC ramp rate
            ramp_rate = self.data.get_trader_initial_condition_attribute(i, 'SCADARampDnRate') / 12

            # No constraint if ramp rate <= 0
            if ramp_rate <= 0:
                return Constraint.Skip

            # Get initial MW
            initial_mw = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')

            return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] - m.V_TRADER_TOTAL_OFFER[i, j]
                    + m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, offer_map[trader_type]] >= initial_mw - ramp_rate)

        # Joint ramp down constraint
        m.C_JOINT_RAMPING_DOWN = Constraint(m.S_TRADER_OFFERS, rule=joint_ramping_down_rule)

        def joint_capacity_up_rule(m, i, j):
            """Joint energy and FCAS contingency constraints"""

            # Only construct constraints for contingency service offers
            if j not in ['R6SE', 'R60S', 'R5MI']:
                return Constraint.Skip

            # Check if energy offer exists for the trader
            has_energy_offer = self.check_trader_has_energy_offer(i, m)

            # FCAS availability preconditions
            fcas_available = self.check_fcas_preconditions(i, j)

            # No constraint constructed if no energy offer and FCAS availability preconditions not met
            if not has_energy_offer or not fcas_available:
                return Constraint.Skip

            # AGC status
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # Get FCAS trapezium (note: no scaling because contingency offer)
            trapezium = self.get_fcas_trapezium_offer(i, j)

            # Slope coefficient
            coefficient = (trapezium['enablement_max'] - trapezium['high_breakpoint']) / trapezium['max_available']

            # Map between trader type and energy offer key
            offer_map = {'GENERATOR': 'ENOF', 'LOAD': 'LDOF', 'NORMALLY_ON_LOAD': 'LDOF'}

            # Get trader type (generator, load, or normally on load)
            trader_type = self.data.get_trader_attribute(i, 'TraderType')

            # TODO: Check if this approach is suitable
            # Note: Some traders have an energy offer and AGCStatus tag but do not offer regulating FCAS, but do offer
            # other contingency FCAS. If regulation FCAS not offered then omitting this from constraint for now.
            if (i, 'R5RE') in m.S_TRADER_OFFERS:
                return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                        + (agc_status * m.V_TRADER_TOTAL_OFFER[i, 'R5RE'])
                        <= trapezium['enablement_max'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])
            else:
                return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                        <= trapezium['enablement_max'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j])
                # return Constraint.Skip

        # FCAS join capacity constraint up
        # m.C_JOINT_CAPACITY_UP = Constraint(m.S_TRADER_OFFERS, rule=joint_capacity_up_rule)

        def joint_capacity_down_rule(m, i, j):
            """Joint energy and FCAS contingency constraints"""

            # Only construct constraints for contingency service offers
            if j not in ['L6SE', 'L60S', 'L5MI']:
                return Constraint.Skip

            # Check if energy offer exists for the trader
            has_energy_offer = self.check_trader_has_energy_offer(i, m)

            # FCAS availability preconditions
            fcas_available = self.check_fcas_preconditions(i, j)

            # No constraint constructed if no energy offer and FCAS availability preconditions not met
            if not has_energy_offer or not fcas_available:
                return Constraint.Skip

            # AGC status
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # Get FCAS trapezium (note: no scaling because contingency offer)
            trapezium = self.get_fcas_trapezium_offer(i, j)

            # Slope coefficient
            coefficient = (trapezium['low_breakpoint'] - trapezium['enablement_min']) / trapezium['max_available']

            # Map between trader type and energy offer key
            offer_map = {'GENERATOR': 'ENOF', 'LOAD': 'LDOF', 'NORMALLY_ON_LOAD': 'LDOF'}

            # Get trader type (generator, load, or normally on load)
            trader_type = self.data.get_trader_attribute(i, 'TraderType')

            # TODO: Check if this approach is suitable
            # Note: Some traders have an energy offer and AGCStatus tag but do not offer regulating FCAS, but do offer
            # other contingency FCAS. If regulation FCAS not offered then omitting this from constraint for now.
            if (i, 'L5RE') in m.S_TRADER_OFFERS:
                return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                        - (agc_status * m.V_TRADER_TOTAL_OFFER[i, 'L5RE'])
                        >= trapezium['enablement_min'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j])
            else:
                return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                        >= trapezium['enablement_min'] + m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j])

        # FCAS join capacity constraint down
        # m.C_JOINT_CAPACITY_DOWN = Constraint(m.S_TRADER_OFFERS, rule=joint_capacity_down_rule)

        def joint_regulating_capacity_up_rule(m, i, j):
            """Joint energy and regulating FCAS constraints"""

            # Only construct constraints for contingency service offers
            # TODO: Should raise and lower contingency FCAS be considered here?
            if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
                return Constraint.Skip

            # Check if energy offer exists for the trader
            has_energy_offer = self.check_trader_has_energy_offer(i, m)

            # FCAS availability preconditions
            fcas_available = self.check_fcas_preconditions(i, j)

            # No constraint constructed if no energy offer and FCAS availability preconditions not met
            if not has_energy_offer or not fcas_available:
                return Constraint.Skip

            # AGC status
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # No constraint created if trader not available for regulated services (e.g. if AGC status = 0)
            if agc_status != 1:
                return Constraint.Skip

            # Get FCAS trapezium
            trapezium = self.get_fcas_trapezium_offer(i, j)

            # Compute slope coefficient
            coefficient = (trapezium['enablement_max'] - trapezium['high_breakpoint']) / trapezium['max_available']

            # Map between trader type and energy offer key
            offer_map = {'GENERATOR': 'ENOF', 'LOAD': 'LDOF', 'NORMALLY_ON_LOAD': 'LDOF'}

            # Get trader type (generator, load, or normally on load)
            trader_type = self.data.get_trader_attribute(i, 'TraderType')

            return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] + (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                    <= trapezium['enablement_max'] + m.V_CV_JOINT_REGULATING_CAPACITY_UP[i, j])

        # FCAS joint regulating capacity up
        # m.C_JOINT_REGULATING_CAPACITY_UP = Constraint(m.S_TRADER_OFFERS, rule=joint_regulating_capacity_up_rule)

        def joint_regulating_capacity_down_rule(m, i, j):
            """Joint energy and regulating FCAS constraints"""

            # Only construct constraints for contingency service offers
            # TODO: Should raise and lower contingency FCAS be considered here?
            if j not in ['R6SE', 'R60S', 'R5MI', 'L6SE', 'L60S', 'L5MI']:
                return Constraint.Skip

            # Check if energy offer exists for the trader
            has_energy_offer = self.check_trader_has_energy_offer(i, m)

            # FCAS availability preconditions
            fcas_available = self.check_fcas_preconditions(i, j)

            # No constraint constructed if no energy offer and FCAS availability preconditions not met
            if not has_energy_offer or not fcas_available:
                return Constraint.Skip

            # AGC status
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # No constraint created if trader not available for regulated services (e.g. if AGC status = 0)
            if agc_status != 1:
                return Constraint.Skip

            # Get FCAS trapezium
            trapezium = self.get_fcas_trapezium_offer(i, j)

            # Compute slope coefficient
            coefficient = (trapezium['low_breakpoint'] - trapezium['enablement_min']) / trapezium['max_available']

            # Map between trader type and energy offer key
            offer_map = {'GENERATOR': 'ENOF', 'LOAD': 'LDOF', 'NORMALLY_ON_LOAD': 'LDOF'}

            # Get trader type (generator, load, or normally on load)
            trader_type = self.data.get_trader_attribute(i, 'TraderType')

            return (m.V_TRADER_TOTAL_OFFER[i, offer_map[trader_type]] - (coefficient * m.V_TRADER_TOTAL_OFFER[i, j])
                    + m.V_CV_JOINT_REGULATING_CAPACITY_DOWN[i, j] >= trapezium['enablement_min'])

        # FCAS joint regulating capacity down
        # m.C_JOINT_REGULATING_CAPACITY_DOWN = Constraint(m.S_TRADER_OFFERS, rule=joint_regulating_capacity_down_rule)

        return m

    @staticmethod
    def get_slope(x1, x2, y1, y2):
        """Compute slope. Return None if slope is undefined"""

        try:
            return (y2 - y1) / (x2 - x1)
        except ZeroDivisionError:
            return None

    @staticmethod
    def get_intercept(slope, x0, y0):
        """Get y-axis intercept given slope and point"""

        return y0 - (slope * x0)

    def define_fcas_constraints2(self, m):
        """FCAS constraints"""

        def as_profile_1_rule(m, i, j):
            """Constraint LHS component of FCAS trapeziums (line between enablement min and low breakpoint)"""

            if j in ['ENOF', 'LDOF']:
                return Constraint.Skip

            elif j in ['R5RE', 'L5RE']:
                trapezium = self.fcas.get_scaled_fcas_trapezium(i, j)
            else:
                trapezium = self.fcas.get_fcas_trapezium_offer(i, j)

            # Get slope between enablement min and low breakpoint
            x1, y1 = trapezium['enablement_min'], 0
            x2, y2 = trapezium['low_breakpoint'], trapezium['max_available']

            # Energy and AGC status
            energy = self.data.get_trader_initial_condition_attribute(i, 'InitialMW')
            agc_status = self.data.get_trader_initial_condition_attribute(i, 'AGCStatus')

            # Check energy output in previous interval within enablement minutes (else trapped outside trapezium)
            # TODO: check all FCAS conditions
            if (energy < trapezium['enablement_min']) or (energy > trapezium['enablement_max']) or (agc_status == 0):
                return Constraint.Skip

            slope = self.get_slope(x1, x2, y1, y2)

            if slope is not None:
                y_intercept = self.get_intercept(slope, x1, y1)
                try:
                    return m.V_TRADER_TOTAL_OFFER[i, j] <= slope * m.V_TRADER_TOTAL_OFFER[i, 'ENOF'] + y_intercept

                except KeyError:
                    return m.V_TRADER_TOTAL_OFFER[i, j] <= slope * m.V_TRADER_TOTAL_OFFER[i, 'LDOF'] + y_intercept

            else:
                # TODO: need to consider if vertical line
                return Constraint.Skip

        # AS profile constraint - between enablement min and low breakpoint
        m.AS_PROFILE_1 = Constraint(m.S_TRADER_OFFERS, rule=as_profile_1_rule)

        return m

    def define_constraints(self, m):
        """Define model constraints"""

        # Ensure offer bands aren't violated
        m = self.define_offer_constraints(m)

        # Construct generic constraints and link variables to those found in objective
        m = self.define_generic_constraints(m)

        # Construct unit constraints (e.g. ramp rate constraints)
        m = self.define_unit_constraints(m)

        # Construct region power balance constraints
        m = self.define_region_constraints(m)

        # Construct FCAS constraints
        # m = self.define_fcas_constraints(m)
        m = self.define_fcas_constraints2(m)

        return m

    @staticmethod
    def define_objective(m):
        """Define model objective"""

        # Total cost for energy and ancillary services
        m.OBJECTIVE = Objective(expr=sum(m.E_TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
                                     + sum(m.E_MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
                                     + m.E_CV_TOTAL_PENALTY,
                                sense=minimize)

        return m

    def construct_model(self, year, month, day, interval):
        """Construct NEMDE approximation"""

        # Update data for specified interval
        self.data.load_interval(year, month, day, interval)
        self.fcas.data.load_interval(year, month, day, interval)
        self.mmsdm_data.load_interval(year, month)

        # Initialise concrete model instance
        m = ConcreteModel()

        # Define model components
        m = self.define_sets(m)
        m = self.define_parameters(m)
        m = self.define_variables(m)
        m = self.define_expressions(m)
        m = self.define_constraints(m)
        m = self.define_objective(m)

        # Fix interconnector solution
        # m = self.fix_interconnector_solution(m)
        # m = self.fix_fcas_solution(m)

        return m

    def solve_model(self, m):
        """Solve model"""

        # Solve model
        solve_status = self.opt.solve(m, tee=self.tee, options=self.solver_options, keepfiles=self.keepfiles)

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
        # raise_map = [('R6SE', 'R6Target'), ('R60S', 'R60Target'), ('R5MI', 'R5Target'), ('R5RE', 'R5RegTarget')]
        raise_map = [('R60S', 'R60Target')]
        # lower_map = [('L6SE', 'L6Target'), ('L60S', 'L60Target'), ('L5MI', 'L5Target'), ('L5RE', 'L5RegTarget')]
        lower_map = []

        # Fix FCAS solution based on observed NEMDE output
        for trader in traders:

            for i, j in raise_map + lower_map:

                # Fix selected FCAS solution
                if (trader, i) in m.S_TRADER_OFFERS:
                    # FCAS solution
                    fcas_solution = self.data.get_trader_solution_attribute(trader, j)

                    # Fix variable to observed solution
                    m.V_TRADER_TOTAL_OFFER[trader, i].fix(fcas_solution)

        return m

    def save_generic_constraints(self, m):
        """Save generic constraints for later inspection"""

        with open(os.path.join(self.output_dir, 'constraints.txt'), 'w') as f:
            for k, v in m.C_GENERIC_CONSTRAINT.items():
                to_write = f"{k}: {v.expr}\n"
                f.write(to_write)

    def get_fcas_max_regulating_raise(self):
        """Get max regulating raise FCAS"""
        pass

    def get_fcas_effective_rreg_max_available(self, trader_id, trade_type):
        """Effective raise regulating FCAS max available"""
        pass


class NEMDESolution:
    def __init__(self, data_dir):
        # Important directories
        self.data_dir = data_dir

        # Object used to parse NEMDE data
        self.data = NEMDEDataHandler(data_dir)

    @staticmethod
    def get_variable_values(m, v):
        """Extract variable values from model object"""

        # Extract values into dictionary
        values = {k: v.value for k, v in m.__getattribute__(v).items()}

        return values

    def get_scheduled_traders(self):
        """Get all scheduled traders"""

        # All traders
        all_traders = self.data.get_trader_index()

        # Get scheduled generators / loads
        scheduled = [i for i in all_traders if self.data.get_trader_attribute(i, 'SemiDispatch') == 0]

        return scheduled

    def get_model_energy_output(self, m, var_name):
        """Extract energy output"""

        # Energy output values
        values = self.get_variable_values(m, var_name)

        # Wrap values in list - makes parsing DataFrame easier
        values_in_list = {k: [v] for k, v in values.items()}

        # Convert to DataFrame
        df = pd.DataFrame(values_in_list).T
        df.index.rename(['TRADER_ID', 'OFFER_TYPE'], inplace=True)
        df = df.rename(columns={0: 'output'})

        # Model output
        df_m = df.pivot_table(index='TRADER_ID', columns='OFFER_TYPE', values='output').astype(float, errors='ignore')

        return df_m

    def check_energy_solution(self, m, model_variable_name, model_key, observed_key):
        """Check model solution"""

        # Model energy output
        df_m = self.get_model_energy_output(m, model_variable_name)

        # Actual NEMDE output
        df_o = self.data.get_trader_solution_dataframe()

        # Combine into single DataFrame
        df_c = pd.concat([df_m[model_key], df_o[observed_key]], axis=1, sort=True)

        # Compute difference between model and target
        df_c['difference'] = df_c[model_key].subtract(df_c[observed_key])
        df_c['abs_difference'] = df_c['difference'].abs()
        df_c = df_c.sort_values(by='abs_difference', ascending=False)

        # Get scheduled loads
        scheduled = [i for i in df_c.index if self.data.get_trader_attribute(i, 'SemiDispatch') == 0]

        # Mean squared error (squared difference between NEMDE target values and model values)
        mse = df_c.loc[scheduled, :].apply(lambda x: (x[model_key] - x[observed_key]) ** 2, axis=1).mean()
        print(f'{model_key} MSE =', mse)

        # Compare model and observed energy output
        ax = df_c.loc[scheduled, :].plot(x=model_key, y=observed_key, kind='scatter')

        # Max value
        max_value = df_c.loc[scheduled, [model_key, observed_key]].max().max()
        ax.plot([0, max_value], [0, max_value], color='r', alpha=0.8, linestyle='--')

        plt.show()

        return df_c

    def check_trader_solution(self, m, trader_id):
        """Compare model and observed trader solution"""

        # Model solution
        e_mod = self.get_model_energy_output(m, 'V_TRADER_TOTAL_OFFER')

        # Observed solution (from NEMDE)
        e_obs = self.data.get_trader_solution_dataframe()

        # Mapping between model and NEMDE keys
        r = {'R6Target': 'R6SE', 'R60Target': 'R60S', 'R5Target': 'R5MI', 'R5RegTarget': 'R5RE',
             'L6Target': 'L6SE', 'L60Target': 'L60S', 'L5Target': 'L5MI', 'L5RegTarget': 'L5RE',
             'EnergyTarget': 'ENOF'}

        # Combine into single DataFrame
        df_c = pd.concat([e_mod.loc[trader_id].rename('model'), e_obs.loc[trader_id].rename(r).rename('observed')],
                         axis=1, sort=True).loc[list(r.values()), :]

        return df_c

    @staticmethod
    def plot_fcas_trapezium(*args):
        """Plot an FCAS trapezium"""

        enablement_max = 0

        fig, ax = plt.subplots()
        for i, arg in enumerate(args):
            x = [arg['enablement_min'], arg['low_breakpoint'], arg['high_breakpoint'], arg['enablement_max']]
            y = [0, arg['max_available'], arg['max_available'], 0]

            if i % 2 == 0:
                colour = 'b'
            else:
                colour = 'r'
            ax.plot(x, y, colour)

            if arg['enablement_max'] > enablement_max:
                enablement_max = arg['enablement_max']

        ax.set_xlim([0, enablement_max])
        plt.show()


if __name__ == '__main__':
    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to construct and run NEMDE approximate model
    nemde = NEMDEModel(data_directory, output_directory)

    # Load MMSDM data for given interval
    nemde.mmsdm_data.load_interval(2019, 10)

    # Object used to interrogate NEMDE solution
    analysis = NEMDESolution(data_directory)
    analysis.data.load_interval(2019, 10, 10, 1)

    # Construct model for given trading interval
    model = nemde.construct_model(2019, 10, 10, 1)

    # Solve model
    model, status = nemde.solve_model(model)

    # Check solution
    enof = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'ENOF', 'EnergyTarget')
    ldof = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'LDOF', 'EnergyTarget')

    r6se = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R6SE', 'R6Target')
    r60s = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R60S', 'R60Target')
    r5mi = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R5MI', 'R5Target')
    r5reg = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R5RE', 'R5RegTarget')

    l6se = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L6SE', 'L6Target')
    l60s = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L60S', 'L60Target')
    l5mi = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L5MI', 'L5Target')
    l5reg = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L5RE', 'L5RegTarget')

    # Scheduled units
    scheduled_traders = analysis.get_scheduled_traders()

    # Filter scheduled generators and loads
    enof_scheduled = enof.loc[enof.index.intersection(scheduled_traders), :]
    ldof_scheduled = ldof.loc[ldof.index.intersection(scheduled_traders), :]

    # Write generic constraints
    nemde.save_generic_constraints(model)

    raise_map = [('R6SE', 'R6Target'), ('R60S', 'R60Target'), ('R5MI', 'R5Target'), ('R5RE', 'R5RegTarget')]
    lower_map = [('L6SE', 'L6Target'), ('L60S', 'L60Target'), ('L5MI', 'L5Target'), ('L5RE', 'L5RegTarget')]

    # Model targets
    # dfs = []
    # for k in ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']:
    #     dfs.append(analysis.get_model_energy_output(model, k))
    #
    # Combine into single DataFrame
    c = analysis.check_trader_solution(model, 'TUMUT3')