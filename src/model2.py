"""Class used to construct and solve NEMDE approximation"""

import os

import pandas as pd
from pyomo.environ import *
from pyomo.util.infeasible import log_infeasible_constraints

import matplotlib.pyplot as plt

from data2 import NEMDEDataHandler


class NEMDEModel:
    def __init__(self, data_dir, output_dir):
        # Directories
        self.output_dir = output_dir

        # Object used to extract NEMDE input information
        self.data = NEMDEDataHandler(data_dir)

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
            # TODO: investigate whether using "DemandForecast" / "ClearedDemand" / "FixedDemand" is most appropriate

            return self.data.get_region_initial_condition_attribute(r, 'InitialDemand')

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

        # Ancillary services max available price (assume for constraint ensure max available amount not exceeded)
        m.P_CVF_AS_MAX_AVAIL_PRICE = Param(initialize=self.data.get_case_attribute('ASMaxAvailPrice'))

        # Ancillary services enablement min price (assume for constraint ensure FCAS > enablement min if active)
        m.P_CVF_AS_ENABLEMENT_MIN_PRICE = Param(initialize=self.data.get_case_attribute('ASEnablementMinPrice'))

        # Ancillary services enablement max price (assume for constraint ensure FCAS < enablement max if active)
        m.P_CVF_AS_ENABLEMENT_MAX_PRICE = Param(initialize=self.data.get_case_attribute('ASEnablementMaxPrice'))

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

        # FCAS join capacity constraint violation variables
        m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)
        m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN = Var(m.S_TRADER_OFFERS, within=NonNegativeReals)

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

        def trader_joint_capacity_down_penalty_rule(m, i, j):
            """Penalty for FCAS joint capacity constraint down violation"""

            return m.P_CVF_AS_MAX_AVAIL_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j]

        # FCAS joint capacity constraint down violation penalty
        m.E_CV_TRADER_JOINT_CAPACITY_DOWN_PENALTY = Expression(m.S_TRADER_OFFERS,
                                                               rule=trader_joint_capacity_down_penalty_rule)

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

        # Sum of all constraint violation penalties
        m.E_CV_TOTAL_PENALTY = Expression(expr=sum(m.E_CV_GC_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
                                          + sum(m.E_CV_GC_LHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
                                          + sum(m.E_CV_GC_RHS_PENALTY[i] for i in m.S_GENERIC_CONSTRAINTS)
                                          + sum(m.E_CV_TRADER_OFFER_PENALTY[i, j, k] for i, j in m.S_TRADER_OFFERS
                                                for k in m.S_BANDS)
                                          + sum(m.E_CV_TRADER_CAPACITY_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                          + sum(m.E_CV_TRADER_RAMP_UP_PENALTY[i] for i in m.S_TRADERS)
                                          + sum(m.E_CV_TRADER_RAMP_DOWN_PENALTY[i] for i in m.S_TRADERS)
                                          + sum(m.E_CV_TRADER_JOINT_CAPACITY_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
                                          + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS
                                                for k in m.S_BANDS)
                                          + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
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

            # Check trader's semi-dispatch status
            semi_dispatch = self.data.get_trader_attribute(i, 'SemiDispatch')

            # Max available only applies to dispatchable plant (NEMDE records MaxAvail=0 for semi-dispatchable traders)
            if semi_dispatch == 0:
                return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_CAPACITY[i, j]
            else:
                return Constraint.Skip

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

    @staticmethod
    def define_region_constraints(m):
        """Define power balance constraint for each region"""

        def power_balance_rule(m, r):
            """Power balance for each region"""

            return m.E_REGION_GENERATION[r] - m.E_REGION_LOAD[r] == m.P_REGION_DEMAND[r]

        # Power balance in each region
        # TODO: add interconnectors
        m.C_POWER_BALANCE = Constraint(m.S_REGIONS, rule=power_balance_rule)

        return m

    def define_fcas_constraints(self, m):
        """Define FCAS constraints"""



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
        m = self.define_fcas_constraints(m)

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

        # Initialise concrete model instance
        m = ConcreteModel()

        # Define model components
        m = self.define_sets(m)
        m = self.define_parameters(m)
        m = self.define_variables(m)
        m = self.define_expressions(m)
        m = self.define_constraints(m)
        m = self.define_objective(m)

        return m

    def solve_model(self, m):
        """Solve model"""

        # Solve model
        solve_status = self.opt.solve(m, tee=self.tee, options=self.solver_options, keepfiles=self.keepfiles)

        return m, solve_status

    def save_generic_constraints(self, m):
        """Save generic constraints for later inspection"""

        with open(os.path.join(self.output_dir, 'constraints.txt'), 'w') as f:
            for k, v in m.C_GENERIC_CONSTRAINT.items():
                to_write = f"{k}: {v.expr}\n"
                f.write(to_write)


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


if __name__ == '__main__':
    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to construct and run NEMDE approximate model
    nemde = NEMDEModel(data_directory, output_directory)

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

    # Write generic constraints
    nemde.save_generic_constraints(model)

    # for i in model.S_TRADERS:
    #     if (nemde.data.get_trader_period_attribute(i, 'RegionID') == 'SA1') and (nemde.data.get_trader_initial_condition_attribute(i, 'InitialMW') > 0):
    #         print(i)