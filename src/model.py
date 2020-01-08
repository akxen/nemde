"""Model used to simulate AEMO's National Electricity Market Dispatch Engine (NEMDE)"""

import pandas as pd
from pyomo.environ import *
from pyomo.util.infeasible import log_infeasible_constraints

import matplotlib.pyplot as plt

from data import NEMDEData


class NEMDEModel:
    def __init__(self, data_dir):
        self.data = NEMDEData(data_dir)

        # Solver options
        self.tee = True
        self.keepfiles = False
        self.solver_options = {}  # 'MIPGap': 0.0005,
        self.opt = SolverFactory('cplex', solver_io='lp')

    def define_sets(self, m):
        """Define model sets"""

        # Market participants (generators and loads)
        m.S_TRADERS = Set(initialize=self.data.get_trader_ids())

        # Market Network Service Providers (interconnectors that bid into the market)
        m.S_MNSPS = Set(initialize=self.data.get_mnsp_ids())

        # All interconnectors (interconnector_id)
        m.S_INTERCONNECTORS = Set(initialize=self.data.get_interconnector_ids())

        # Trader offer types
        m.S_TRADER_OFFERS = Set(initialize=self.data.get_trader_offer_index())

        # MNSP offer types
        m.S_MNSP_OFFERS = Set(initialize=self.data.get_mnsp_offer_index())

        # Generic constraints
        m.S_GENERIC_CONSTRAINTS = Set(initialize=self.data.get_generic_constraint_index())

        # Generic constraints trader variables
        m.S_TRADER_VARS = Set(initialize=self.data.get_generic_constraint_trader_variables())

        # Generic constraint interconnector variables
        m.S_INTERCONNECTOR_VARS = Set(initialize=self.data.get_generic_constraint_interconnector_variables())

        # Generic constraint region variables
        m.S_REGION_VARS = Set(initialize=self.data.get_generic_constraint_region_variables())

        # Trader types (generator, load, normally_on_load)
        m.S_PARTICIPANT_TYPES = Set(initialize=self.data.get_participant_types())

        # Price / quantity band index
        m.S_BANDS = RangeSet(1, 10, 1)

        return m

    def define_parameters(self, m):
        """Define model parameters"""

        def trader_price_band_rule(m, i, j, k):
            """Price bands for traders"""

            return self.data.get_trader_price_band_value(i, j, k)

        # Price bands for traders (generators / loads)
        m.TRADER_PRICE_BAND = Param(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_price_band_rule)

        def trader_quantity_band_rule(m, i, j, k):
            """Quantity bands for traders"""

            return self.data.get_trader_quantity_band_value(i, j, k)

        # Quantity bands for traders (generators / loads)
        m.TRADER_QUANTITY_BAND = Param(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_quantity_band_rule)

        def trader_max_available_rule(m, i, j):
            """Max available energy output from given trader"""
            return self.data.get_trader_max_available_value(i, j)

        # Max available output for given trader
        m.TRADER_MAX_AVAILABLE = Param(m.S_TRADER_OFFERS, rule=trader_max_available_rule)

        def trader_initial_mw_rule(m, i):
            """Initial power output condition for each trader"""

            return self.data.get_trader_initial_condition_mw(i)

        # Initial MW output for generators / loads
        m.TRADER_INITIAL_MW = Param(m.S_TRADERS, rule=trader_initial_mw_rule)

        def mnsp_price_band_rule(m, i, j, k):
            """Price bands for MNSPs"""

            return self.data.get_mnsp_price_band_value(i, j, k)

        # Price bands for MNSPs
        m.MNSP_PRICE_BAND = Param(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_price_band_rule)

        def mnsp_quantity_band_rule(m, i, j, k):
            """Quantity bands for MNSPs"""

            return self.data.get_mnsp_quantity_band_value(i, j, k)

        # Quantity bands for MNSPs
        m.MNSP_QUANTITY_BAND = Param(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_quantity_band_rule)

        def mnsp_max_available_rule(m, i, j):
            """Max available energy output from given MNSP"""
            return self.data.get_mnsp_max_available_value(i, j)

        # Max available output for given MNSP
        m.MNSP_MAX_AVAILABLE = Param(m.S_MNSP_OFFERS, rule=mnsp_max_available_rule)

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

        # Ramp-rate constraint violation factor
        m.CVF_RAMP_RATE = Param(initialize=self.data.get_constraint_violation_ramp_rate_penalty())

        return m

    def define_variables(self, m):
        """Define model variables"""

        # Objective function variables
        m.V_TRADER_OFFER = Var(m.S_TRADER_OFFERS, m.S_BANDS, within=NonNegativeReals)
        m.V_MNSP_OFFER = Var(m.S_MNSP_OFFERS, m.S_BANDS, within=NonNegativeReals)

        # Generic constraint variables
        m.V_TRADER = Var(m.S_TRADER_VARS)
        m.V_INTERCONNECTOR = Var(m.S_INTERCONNECTOR_VARS)
        m.V_REGION = Var(m.S_REGION_VARS)

        # Constraint violation variables
        m.V_CV = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_LHS = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_RHS = Var(m.S_GENERIC_CONSTRAINTS, within=NonNegativeReals)
        m.V_CV_RAMP_UP = Var(m.S_TRADERS, within=NonNegativeReals)
        m.V_CV_RAMP_DOWN = Var(m.S_TRADERS, within=NonNegativeReals)

        return m

    def define_expressions(self, m):
        """Define model expressions"""

        def trader_total_offer_rule(m, i, j):
            """Total energy offered over all bands"""

            return sum(m.V_TRADER_OFFER[i, j, b] for b in m.S_BANDS)

        # Total offered energy for each trader and bid type
        m.TRADER_TOTAL_OFFER_MW = Expression(m.S_TRADER_OFFERS, rule=trader_total_offer_rule)

        def trader_cost_function_rule(m, i, j):
            """Total cost associated with each offer"""

            # Scaling factor depending on participant type. Generator (+1), load (-1)
            trader_type = self.data.get_trader_type(i)

            if ((trader_type == 'LOAD') or (trader_type == 'NORMALLY_ON_LOAD')) and (j == 'ENOF'):
                factor = -1
            else:
                factor = 1

            return factor * sum(m.V_TRADER_OFFER[i, j, b] * m.TRADER_PRICE_BAND[i, j, b] for b in m.S_BANDS)

        # Trader cost functions
        m.TRADER_COST_FUNCTION = Expression(m.S_TRADER_OFFERS, rule=trader_cost_function_rule)

        def mnsp_total_offer_rule(m, i, j):
            """Total energy offered over all bands"""

            return sum(m.V_MNSP_OFFER[i, j, b] for b in m.S_BANDS)

        # Total offered energy for each MNSP
        m.MNSP_TOTAL_OFFER_MW = Expression(m.S_MNSP_OFFERS, rule=mnsp_total_offer_rule)

        def mnsp_cost_function_rule(m, i, j):
            """MNSP cost function"""

            # TODO: Assumes interconnector treated as generator in each region. Need to check.
            return sum(m.V_MNSP_OFFER[i, j, b] * m.MNSP_PRICE_BAND[i, j, b] for b in m.S_BANDS)

        # MNSP cost functions
        m.MNSP_COST_FUNCTION = Expression(m.S_MNSP_OFFERS, rule=mnsp_cost_function_rule)

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
        m.CV_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=constraint_violation_penalty_rule)

        def constraint_violation_lhs_penalty_rule(m, i):
            """Constraint violation penalty for equality constraint"""

            return m.V_CV_LHS[i] * m.CVF[i]

        # Constraint violation penalty for equality constraints
        m.CV_LHS_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=constraint_violation_lhs_penalty_rule)

        def constraint_violation_rhs_penalty_rule(m, i):
            """Constraint violation penalty for equality constraint"""

            return m.V_CV_RHS[i] * m.CVF[i]

        # Constraint violation penalty for equality constraints
        m.CV_RHS_PENALTY = Expression(m.S_GENERIC_CONSTRAINTS, rule=constraint_violation_rhs_penalty_rule)

        def constraint_violation_ramp_down_penalty_rule(m, i):
            """Penalty for violating ramp down constraint"""

            return m.V_CV_RAMP_DOWN[i] * m.CVF_RAMP_RATE

        # Penalty factor for ramp down rate violation
        m.CV_RAMP_DOWN_PENALTY = Expression(m.S_TRADERS, rule=constraint_violation_ramp_down_penalty_rule)

        def constraint_violation_ramp_up_penalty_rule(m, i):
            """Penalty for violating ramp down constraint"""

            return m.V_CV_RAMP_UP[i] * m.CVF_RAMP_RATE

        # Penalty factor for ramp up rate violation
        m.CV_RAMP_UP_PENALTY = Expression(m.S_TRADERS, rule=constraint_violation_ramp_up_penalty_rule)

        return m

    def define_constraints(self, m):
        """Define model constraints"""

        def trader_quantity_band_limit_rule(m, i, j, k):
            """Band output must be non-negative and less than the max offered amount for that band"""

            return m.V_TRADER_OFFER[i, j, k] <= m.TRADER_QUANTITY_BAND[i, j, k]

        # Bounds on quantity band variables for traders
        m.TRADER_QUANTITY_BAND_LIMIT = Constraint(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_quantity_band_limit_rule)

        def trader_max_available_limit_rule(m, i, j):
            """Constrain max available output"""

            # Check trader's semi-dispatch status
            semi_dispatch = self.data.get_trader_semi_dispatch_value(i)

            # Max available only applies to dispatchable plant (NEMDE records MaxAvail=0 for semi-dispatchable traders)
            if semi_dispatch == 0:
                return m.TRADER_TOTAL_OFFER_MW[i, j] <= m.TRADER_MAX_AVAILABLE[i, j] + 1
            else:
                return Constraint.Skip

        # Ensure dispatch is constrained by max available offer amount
        m.TRADER_MAX_AVAILABLE_LIMIT = Constraint(m.S_TRADER_OFFERS, rule=trader_max_available_limit_rule)

        def mnsp_quantity_band_limit_rule(m, i, j, k):
            """Band output must be non-negative and less than the max offered amount for that band"""

            return m.V_MNSP_OFFER[i, j, k] <= m.MNSP_QUANTITY_BAND[i, j, k]

        # Bounds on quantity band variables for MNSPs
        m.MNSP_QUANTITY_BAND_LIMIT = Constraint(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_quantity_band_limit_rule)

        def mnsp_max_available_limit_rule(m, i, j):
            """Constrain max available output"""

            return m.MNSP_TOTAL_OFFER_MW[i, j] <= m.MNSP_MAX_AVAILABLE[i, j]

        # Ensure dispatch is constrained by max available offer amount
        m.MNSP_MAX_AVAILABLE_LIMIT = Constraint(m.S_MNSP_OFFERS, rule=mnsp_max_available_limit_rule)

        def trader_var_link_rule(m, i, j):
            """Link generic constraint trader variables to objective function variables"""

            return m.TRADER_TOTAL_OFFER_MW[i, j] == m.V_TRADER[i, j]

        # Link between total power output and quantity band output
        m.TRADER_VAR_LINK = Constraint(m.S_TRADER_VARS, rule=trader_var_link_rule)

        def mnsp_var_link_rule(m, i):
            """Link generic constraint MNSP variables to objective function variables"""

            # From and to regions for a given MNSP
            from_region = self.data.get_interconnector_from_region(i)
            to_region = self.data.get_interconnector_to_region(i)

            return m.V_INTERCONNECTOR[i] == m.MNSP_TOTAL_OFFER_MW[i, to_region] - m.MNSP_TOTAL_OFFER_MW[i, from_region]

        # Link between total power output and quantity band output
        m.MNSP_VAR_LINK = Constraint(m.S_MNSPS, rule=mnsp_var_link_rule)

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

        def trader_ramp_up_rate_limit_rule(m, i):
            """Ramp up rate limit for ENOF offers"""

            if (i, 'ENOF') in m.S_TRADER_OFFERS:
                ramp_up_limit = self.data.get_trader_ramp_up_rate(i)
                return (m.TRADER_TOTAL_OFFER_MW[i, 'ENOF'] - m.TRADER_INITIAL_MW[i]
                        <= (ramp_up_limit / 12) + m.V_CV_RAMP_UP[i])
            else:
                return Constraint.Skip

        # Ramp up rate limit
        m.TRADER_RAMP_UP_RATE_LIMIT = Constraint(m.S_TRADERS, rule=trader_ramp_up_rate_limit_rule)

        def trader_ramp_down_rate_limit_rule(m, i):
            """Ramp down rate limit for ENOF offers"""

            if (i, 'ENOF') in m.S_TRADER_OFFERS:
                ramp_down_limit = self.data.get_trader_ramp_down_rate(i)
                return (m.TRADER_TOTAL_OFFER_MW[i, 'ENOF'] - m.TRADER_INITIAL_MW[i] + m.V_CV_RAMP_DOWN[i]
                        >= - ramp_down_limit / 12)
            else:
                return Constraint.Skip

        # Ramp down rate limit
        m.TRADER_RAMP_DOWN_RATE_LIMIT = Constraint(m.S_TRADERS, rule=trader_ramp_down_rate_limit_rule)

        def trader_min_output_limit_rule(m, i):
            """Minimum energy output for a given trader"""

            # Get trader semi-dispatch status
            semi_dispatch = self.data.get_trader_semi_dispatch_value(i)

            try:
                # Minimum output level
                min_output = self.data.get_trader_initial_condition_min_mw(i)

            # Not all traders will have a minimum energy level specified
            except AttributeError:
                min_output = None

            if (min_output is not None) and ((i, 'ENOF') in m.S_TRADER_OFFERS) and (semi_dispatch == 0):
                print(i, min_output)
                return m.TRADER_TOTAL_OFFER_MW[i, 'ENOF'] >= min_output
            else:
                return Constraint.Skip

        # Minimum output
        # m.TRADER_MIN_OUTPUT_LIMIT = Constraint(m.S_TRADERS, rule=trader_min_output_limit_rule)

        def trader_max_output_limit_rule(m, i):
            """Maximum energy output for a given trader"""

            # Get trader semi-dispatch status
            semi_dispatch = self.data.get_trader_semi_dispatch_value(i)

            try:
                # Maximum output level
                max_output = self.data.get_trader_initial_condition_max_mw(i)

            # Not all traders will have a minimum energy level specified
            except AttributeError:
                max_output = None

            if (max_output is not None) and ((i, 'ENOF') in m.S_TRADER_OFFERS) and (semi_dispatch == 0):
                print(i, max_output)
                return m.TRADER_TOTAL_OFFER_MW[i, 'ENOF'] <= max_output
            else:
                return Constraint.Skip

        # Maximum output
        # m.TRADER_MAX_OUTPUT_LIMIT = Constraint(m.S_TRADERS, rule=trader_max_output_limit_rule)

        return m

    def define_objective(self, m):
        """Define model objective"""

        # Total cost for energy and ancillary services
        m.OBJECTIVE = Objective(expr=sum(m.TRADER_COST_FUNCTION[t] for t in m.S_TRADER_OFFERS)
                                     + sum(m.MNSP_COST_FUNCTION[t] for t in m.S_MNSP_OFFERS)
                                     + sum(m.CV_PENALTY[c] for c in m.S_GENERIC_CONSTRAINTS)
                                     + sum(m.CV_RHS_PENALTY[c] for c in m.S_GENERIC_CONSTRAINTS)
                                     + sum(m.CV_LHS_PENALTY[c] for c in m.S_GENERIC_CONSTRAINTS)
                                     + sum(m.CV_RAMP_DOWN_PENALTY[t] for t in m.S_TRADERS)
                                     + sum(m.CV_RAMP_UP_PENALTY[t] for t in m.S_TRADERS),
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

    @staticmethod
    def get_model_energy_output(m):
        """Extract energy output"""

        # Convert to DataFrame
        df = pd.DataFrame({k: [v.expr()] for k, v in m.TRADER_TOTAL_OFFER_MW.items()}).T
        df.index.rename(['TRADER_ID', 'OFFER_TYPE'], inplace=True)
        df = df.rename(columns={0: 'output'})

        # Model output
        df_m = df.pivot_table(index='TRADER_ID', columns='OFFER_TYPE', values='output').astype(float, errors='ignore')

        return df_m

    @staticmethod
    def get_model_max_available_energy(m):
        """Get max available energy output for all generators"""

        # Convert to DataFrame
        df = pd.DataFrame({k: [v] for k, v in m.TRADER_MAX_AVAILABLE.items()}).T
        df.index.rename(['TRADER_ID', 'OFFER_TYPE'], inplace=True)
        df = df.rename(columns={0: 'max_available'})

        # Model output
        df_m = (df.pivot_table(index='TRADER_ID', columns='OFFER_TYPE', values='max_available')
                .astype(float, errors='ignore'))

        return df_m

    def check_energy_solution(self, m, model_key, observed_key):
        """Check model solution"""

        # Model energy output
        df_m = self.get_model_energy_output(model)

        # Actual NEMDE output
        df_o = self.data.get_trader_observed_dispatch_dataframe()

        # Combine into single DataFrame
        df_c = pd.concat([df_m[model_key], df_o[observed_key]], axis=1, sort=True)

        # Compute difference between model and target
        df_c['difference'] = df_c[model_key].subtract(df_c[observed_key])
        df_c['abs_difference'] = df_c['difference'].abs()
        df_c = df_c.sort_values(by='abs_difference', ascending=False)

        # Get scheduled loads
        scheduled = [i for i in df_c.index if self.data.get_trader_semi_dispatch_value(i) == 0]

        # Mean squared error (squared difference between NEMDE target values and model values)
        mse = df_c.loc[scheduled, :].apply(lambda x: (x[model_key] - x[observed_key]) ** 2, axis=1).mean()
        print('Energy MSE =', mse)

        # Compare model and observed energy output
        ax = df_c.loc[scheduled, :].plot(x=model_key, y=observed_key, kind='scatter')

        # Max value
        max_value = df_c.loc[scheduled, [model_key, observed_key]].max().max()
        ax.plot([0, max_value], [0, max_value], color='r', alpha=0.8, linestyle='--')

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
    e = nemde.get_model_energy_output(model)
    observed = nemde.data.get_trader_observed_dispatch_dataframe()

    # Max available energy output
    available = nemde.get_model_max_available_energy(model)

    # All scheduled generators
    scheduled_traders = [i for i in e.index if nemde.data.get_trader_semi_dispatch_value(i) == 0]

    # Comparison between model and output energy target
    energy = nemde.check_energy_solution(model, 'ENOF', 'EnergyTarget')
    energy_scheduled = energy.loc[scheduled_traders, :]

    # Raise services
    R6S = nemde.check_energy_solution(model, 'R6SE', 'R6Target')
    R60S = nemde.check_energy_solution(model, 'R60S', 'R60Target')
    R5RE = nemde.check_energy_solution(model, 'R5RE', 'R5RegTarget')
    R5MI = nemde.check_energy_solution(model, 'R5MI', 'R5Target')


