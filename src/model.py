"""Model used to simulate AEMO's National Electricity Market Dispatch Engine (NEMDE)"""

import pandas as pd
from pyomo.environ import *

import matplotlib.pyplot as plt

from data import NEMDEData


class NEMDEModel:
    def __init__(self, data_dir):
        self.data = NEMDEData(data_dir)

        # Solver options
        self.tee = True
        self.keepfiles = False
        self.solver_options = {}  # 'MIPGap': 0.0005,
        self.opt = SolverFactory('cplex', solver_io='mps')

    def define_sets(self, m):
        """Define model sets"""

        # Set of market participants (generators and loads) ('GENERATOR', DUID, offer_type)
        m.S_PARTICIPANT_UNITS = Set(initialize=self.data.get_participant_unit_index())

        # Market participant interconnectors ('INTERCONNECTOR', interconnector ID, region)
        m.S_PARTICIPANT_INTERCONNECTORS = Set(initialize=self.data.get_participant_interconnector_index())

        # All market participants (generators, loads, and interconnectors)
        m.S_PARTICIPANTS = m.S_PARTICIPANT_UNITS.union(m.S_PARTICIPANT_INTERCONNECTORS)

        # Generic constraints
        m.S_GENERIC_CONSTRAINTS = Set(initialize=self.data.get_generic_constraint_index())

        # Generic constraints trader variables
        m.S_TRADER_VARS = Set(initialize=self.data.get_trader_factor_variables())

        # Generic constraint interconnector variables
        m.S_INTERCONNECTOR_VARS = Set(initialize=self.data.get_interconnector_factor_variables())

        # Generic constraint region variables
        m.S_REGION_VARS = Set(initialize=self.data.get_region_factor_variables())

        # Trader types (generator, load, normally_on_load)
        m.S_PARTICIPANT_TYPES = Set(initialize=self.data.get_participant_types())

        # Price / quantity band index
        m.S_BANDS = RangeSet(1, 10, 1)

        return m

    def define_parameters(self, m):
        """Define model parameters"""

        def price_bands_rule(m, i, j, k, b):
            """Price bands for all participants"""

            if (i == 'GENERATOR') or (i == 'LOAD') or (i == 'NORMALLY_ON_LOAD'):
                return self.data.get_trader_price_band_value(j, k, b)
            elif i == 'INTERCONNECTOR':
                return self.data.get_interconnector_price_band_value(j, k, b)
            else:
                raise Exception(f'Unexpected participant type: {i}')

        # Price bands
        m.PRICE_BANDS = Param(m.S_PARTICIPANTS, m.S_BANDS, rule=price_bands_rule)

        def quantity_bands_rule(m, i, j, k, b):
            """Quantity bands for all participants"""

            if (i == 'GENERATOR') or (i == 'LOAD') or (i == 'NORMALLY_ON_LOAD'):
                return self.data.get_trader_quantity_band_value(j, k, b)
            elif i == 'INTERCONNECTOR':
                return self.data.get_interconnector_quantity_band_value(j, k, b)
            else:
                raise Exception(f'Unexpected participant type: {i}')

        # Price bands
        m.QUANTITY_BANDS = Param(m.S_PARTICIPANTS, m.S_BANDS, rule=quantity_bands_rule)

        def max_available_rule(m, i, j, k):
            """Max available energy output from given trader"""

            if (i == 'GENERATOR') or (i == 'LOAD') or (i == 'NORMALLY_ON_LOAD'):
                return self.data.get_trader_max_available_value(j, k)
            elif i == 'INTERCONNECTOR':
                return self.data.get_interconnector_max_available_value(j, k)
            else:
                raise Exception(f'Unexpected participant type: {i}')

        # Max available output for given trader
        m.MAX_AVAILABLE = Param(m.S_PARTICIPANTS, rule=max_available_rule)

        def generic_constraint_rhs_rule(m, c):
            """RHS value for given generic constraint"""

            return self.data.get_generic_constraint_rhs_value(c)

        # Generic constraint RHS
        m.RHS = Param(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_rule)

        def generic_constraint_violation_factor_rule(m, c):
            """Constraint violation penalty for given generic constraint"""

            return self.data.get_generic_constraint_cvf_value(c)

        # Constraint violation factors
        m.CVF = Param(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_factor_rule)

        def participant_type_factor_rule(m, i):
            """Scaling factor to assign to trader (generator / load) and interconnector cost functions"""

            # TODO: Assuming interconnector treated as generator. Must verify this.
            if (i == 'GENERATOR') or (i == 'INTERCONNECTOR'):
                return 1
            elif (i == 'LOAD') or (i == 'NORMALLY_ON_LOAD'):
                return -1
            else:
                raise Exception(f'Unexpected trader type: {i}')

        # Trader type scaling factor to be used trader cost function formulation
        m.PARTICIPANT_TYPE_FACTOR = Param(m.S_PARTICIPANT_TYPES, rule=participant_type_factor_rule)

        return m

    def define_variables(self, m):
        """Define model variables"""

        # Objective function variables
        m.V_PARTICIPANT_OFFERS = Var(m.S_PARTICIPANTS, m.S_BANDS, within=NonNegativeReals)

        # Generic constraint variables
        m.V_TRADER = Var(m.S_TRADER_VARS)
        m.V_INTERCONNECTOR = Var(m.S_INTERCONNECTOR_VARS)
        m.V_REGION = Var(m.S_REGION_VARS)

        # Constraint violation variables
        m.V_CV = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_LHS = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_RHS = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)

        return m

    def define_expressions(self, m):
        """Define model expressions"""

        def total_offer_mw_rule(m, i, j, k):
            """Total energy offered over all bands"""
            return sum(m.V_PARTICIPANT_OFFERS[i, j, k, b] for b in m.S_BANDS)

        # Total offered energy
        m.TOTAL_OFFER_MW = Expression(m.S_PARTICIPANTS, rule=total_offer_mw_rule)

        def trader_cost_function_rule(m, i, j, k):
            return m.PARTICIPANT_TYPE_FACTOR[i] * sum(m.V_PARTICIPANT_OFFERS[i, j, k, b] * m.PRICE_BANDS[i, j, k, b]
                                                      for b in m.S_BANDS)

        # Trader cost functions
        # Note: terms are scaled by PARTICIPANT_TYPE_FACTOR to denote loads (-1) and generators / interconnectors (+1)
        m.COST_FUNCTION = Expression(m.S_PARTICIPANTS, rule=trader_cost_function_rule)

        def lhs_terms_rule(m, i):
            """Get LHS expression for a given Generic Constraint"""

            # LHS terms and associated factors
            terms = self.data.get_lhs_terms(i)

            # Trader terms
            trader_terms = sum(m.V_TRADER[index] * factor for index, factor in terms['trader_factors'].items())

            # Interconnector terms
            interconnector_terms = sum(m.V_INTERCONNECTOR[index] * factor
                                       for index, factor in terms['interconnector_factors'].items())

            # Region terms
            region_terms = sum(m.V_REGION[index] * factor for index, factor in terms['region_factors'].items())

            return trader_terms + interconnector_terms + region_terms

        # Generic constraint LHS
        m.LHS_TERMS = Expression(m.S_GENERIC_CONSTRAINTS, rule=lhs_terms_rule)

        def constraint_violation_penalty_rule(m, i):
            """Constraint violation penalty for generic constraint which is an inequality"""

            return m.V_CV[i] * m.CVF[i]

        # Constraint violation penalty for inequality constraints
        m.CONSTRAINT_VIOLATION_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=constraint_violation_penalty_rule)

        def constraint_violation_lhs_penalty_rule(m, i):
            """Constraint violation penalty for equality constraint"""

            return m.V_CV_LHS[i] * m.CVF[i]

        # Constraint violation penalty for inequality constraints
        m.CONSTRAINT_VIOLATION_LHS_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS,
                                                        rule=constraint_violation_lhs_penalty_rule)

        def constraint_violation_rhs_penalty_rule(m, i):
            """Constraint violation penalty for equality constraint"""

            return m.V_CV_RHS[i] * m.CVF[i]

        # Constraint violation penalty for inequality constraints
        m.CONSTRAINT_VIOLATION_RHS_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS,
                                                        rule=constraint_violation_rhs_penalty_rule)

        return m

    def define_constraints(self, m):
        """Define model constraints"""

        def quantity_band_limit_rule(m, i, j, k, b):
            """Band output must be non-negative and less than the max offered amount for that band"""
            return m.V_PARTICIPANT_OFFERS[i, j, k, b] <= m.QUANTITY_BANDS[i, j, k, b]

        # Bounds on quantity band variables
        m.QUANTITY_BANDS_LIMIT = Constraint(m.S_PARTICIPANTS, m.S_BANDS, rule=quantity_band_limit_rule)

        def max_available_limit_rule(m, i, j, k):
            """Constraint max available output"""
            return m.TOTAL_OFFER_MW[i, j, k] <= m.MAX_AVAILABLE[i, j, k]

        # Ensure dispatch is constrained by max available offer amount
        m.MAX_AVAILABLE_LIMIT = Constraint(m.S_PARTICIPANTS, rule=max_available_limit_rule)

        def trader_var_link_rule(m, i, j):
            """Link generic constraint trader variables to objective function variables"""

            # Get type of trader
            trader_type = self.data.get_trader_type(i)

            return m.TOTAL_OFFER_MW[trader_type, i, j] == m.V_TRADER[i, j]

        # Link between total power output and quantity band output
        m.TRADER_VAR_LINK = Constraint(m.S_TRADER_VARS, rule=trader_var_link_rule)

        def interconnector_var_link_rule(m, i):
            """Link generic constraint interconnector variables to objective function variables"""

            if i in [j[1] for j in m.S_PARTICIPANT_INTERCONNECTORS]:

                from_region = self.data.get_interconnector_from_region(i)
                to_region = self.data.get_interconnector_to_region(i)

                return (m.V_INTERCONNECTOR[i] == m.TOTAL_OFFER_MW['INTERCONNECTOR', i, to_region]
                        - m.TOTAL_OFFER_MW['INTERCONNECTOR', i, from_region])

            else:
                return Constraint.Skip

        # Link between total power output and quantity band output
        m.INTERCONNECTOR_VAR_LINK = Constraint(m.S_INTERCONNECTOR_VARS, rule=interconnector_var_link_rule)

        def generic_constraint_rule(m, c):
            """NEMDE Generic Constraints"""

            # Type of generic constraint (LE, GE, EQ)
            constraint_type = self.data.get_generic_constraint_type(c)

            if constraint_type == 'LE':
                return m.LHS_TERMS[c] <= m.RHS[c] + m.V_CV[c]
            elif constraint_type == 'GE':
                return m.LHS_TERMS[c] + m.V_CV[c] >= m.RHS[c]
            elif constraint_type == 'EQ':
                return m.LHS_TERMS[c] + m.V_CV_LHS[c] == m.RHS[c] + m.V_CV_RHS[c]

        # Generic constraints
        m.GENERIC_CONSTRAINT = Constraint(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rule)

        return m

    def define_objective(self, m):
        """Define model objective"""

        # Total cost for energy and ancillary services
        m.OBJECTIVE = Objective(expr=sum(m.COST_FUNCTION[u] for u in m.S_PARTICIPANTS)
                                     + sum(m.CONSTRAINT_VIOLATION_PENALTY[c] for c in m.S_GENERIC_CONSTRAINTS)
                                     + sum(m.CONSTRAINT_VIOLATION_RHS_PENALTY[c] for c in m.S_GENERIC_CONSTRAINTS)
                                     + sum(m.CONSTRAINT_VIOLATION_LHS_PENALTY[c] for c in m.S_GENERIC_CONSTRAINTS),
                                sense=minimize)

        return m

    def construct_model(self, year, month, day, interval):
        """Construct model components"""

        # Update data for specified interval
        self.data.load_interval(year, month, day, interval)

        # Initialise model
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

    def get_model_energy_output(self, m):
        """Extract energy output"""

        # Convert to DataFrame
        df = pd.DataFrame({k: [v.expr()] for k, v in m.TOTAL_OFFER_MW.items()}).T
        df.index.rename(['PARTICIPANT_TYPE', 'TRADER_ID', 'OFFER_TYPE'], inplace=True)
        df = df.rename(columns={0: 'output'})

        # Model output
        df_m = df.pivot_table(index='TRADER_ID', columns='OFFER_TYPE', values='output').astype(float, errors='ignore')

        return df_m

    def check_solution(self, m):
        """Check model solution"""

        # Model energy output
        df_m = nemde.get_model_energy_output(model)

        # Actual NEMDE output
        df_o = nemde.data.get_trader_observed_dispatch_dataframe()

        # Combine into single DataFrame
        df_c = pd.concat([df_m['ENOF'], df_o['EnergyTarget']], axis=1, sort=True)

        # Mean squared error for energy output
        mse = df_c.apply(lambda x: (x['ENOF'] - x['EnergyTarget']) ** 2, axis=1).mean()
        print('Energy MSE =', mse)

        # Compare model and observed energy output
        ax = df_c.plot(x='ENOF', y='EnergyTarget', kind='scatter')
        ax.plot([0, 600], [0, 600], color='r', alpha=0.8, linestyle='--')

        plt.show()

        return df_c


if __name__ == '__main__':
    # Construct model objective
    data_directory = 'C:/Users/eee/Desktop/nemweb/Reports/Data_Archive'
    nemde = NEMDEModel(data_directory)

    # Create model
    yr, mn, dy, inter = 2019, 10, 1, 1
    model = nemde.construct_model(yr, mn, dy, inter)
    nemde.solve_model(model)

    # Check solution
    energy = nemde.check_solution(model)
