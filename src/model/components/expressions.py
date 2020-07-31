"""Define model expressions"""

import pyomo.environ as pyo


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


def define_aggregate_power_expressions(m):
    """Compute aggregate demand and generation in each NEM region"""

    def region_generation_rule(m, r):
        """Available energy offers in given region"""

        return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
                   if (j == 'ENOF') and (m.P_TRADER_REGION[i] == r))

    # Total generation dispatched in a given region
    m.E_REGION_GENERATION = pyo.Expression(m.S_REGIONS, rule=region_generation_rule)

    def region_load_rule(m, r):
        """Available load offers in given region"""

        return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
                   if (j == 'LDOF') and (m.P_TRADER_REGION[i] == r))

    # Total load dispatched in a given region
    m.E_REGION_LOAD = pyo.Expression(m.S_REGIONS, rule=region_load_rule)

    def region_net_export_flow_rule(m, r):
        """Net flow out of region"""

        net_flow = 0

        for i in m.S_INTERCONNECTORS:
            from_node = m.P_INTERCONNECTOR_FROM_REGION[i]
            to_node = m.P_INTERCONNECTOR_TO_REGION[i]
            mnsp_status = m.P_INTERCONNECTOR_MNSP_STATUS[i]

            if r == from_node:
                # Check if an MNSP
                if mnsp_status == 1:
                    factor = m.P_MNSP_FROM_REGION_LF[i]
                else:
                    factor = 1

                net_flow += factor * m.V_FLOW_FROM_CP[i]

            elif r == to_node:
                # Check if an MNSP
                if mnsp_status == 1:
                    factor = m.P_MNSP_TO_REGION_LF[i]
                else:
                    factor = 1

                net_flow += - (factor * m.V_FLOW_TO_CP[i])

            else:
                pass

        return net_flow

    # Net flow out of region
    m.E_REGION_NET_EXPORT_FLOW = pyo.Expression(m.S_REGIONS, rule=region_net_export_flow_rule)

    def total_initial_scheduled_load(m, r):
        """Total initial scheduled load in a given region"""

        total = 0
        for i, j in m.S_TRADER_OFFERS:
            if j == 'LDOF':
                # Semi-dispatch status
                semi_dispatch_status = m.P_TRADER_SEMI_DISPATCH_STATUS[i]

                # Trader region
                region = m.P_TRADER_REGION[i]

                if (r == region) and (semi_dispatch_status == 0):
                    total += m.P_TRADER_INITIAL_MW[i]

        return total

    # Total initial scheduled load
    m.E_TOTAL_INITIALMW_SCHEDULED_LOAD = pyo.Expression(m.S_REGIONS, rule=total_initial_scheduled_load)

    # def total_initial_allocated_losses(m, r):
    #     """Total losses assigned to region as a result of interconnector flow"""
    #
    #     return self.data.get_region_initial_net_allocated_losses(r)
    #
    # # Total initial allocated losses
    # m.E_TOTAL_INITIAL_ALLOCATED_LOSSES = pyo.Expression(m.S_REGIONS, rule=total_initial_allocated_losses)
    #
    def region_demand_rule(m, r):
        """Get demand in each region. Using forecast demand for now."""

        # Demand in each NEM region
        demand = (
                m.P_REGION_INITIAL_DEMAND[r]
                + m.P_REGION_ADE[r]
                + m.P_REGION_DF[r]
                - m.E_TOTAL_INITIALMW_SCHEDULED_LOAD[r]
            # - m.E_TOTAL_INITIAL_ALLOCATED_LOSSES[r] # TODO: need to add this
        )

        return demand

    # Region Demand
    m.E_REGION_DEMAND = pyo.Expression(m.S_REGIONS, rule=region_demand_rule)

    # def allocated_interconnector_losses_observed_rule(m, r):
    #     """Losses obtained from model solution and assigned to each region"""
    #
    #     total = 0
    #     for i in self.data.get_interconnector_index():
    #         from_region = self.data.get_interconnector_period_attribute(i, 'FromRegion')
    #         to_region = self.data.get_interconnector_period_attribute(i, 'ToRegion')
    #         loss_share = self.data.get_interconnector_loss_model_attribute(i, 'LossShare')
    #
    #         # Loss obtained from solution
    #         observed_loss = self.data.get_interconnector_solution_attribute(i, 'Losses')
    #
    #         if r == from_region:
    #             total += observed_loss * loss_share
    #
    #         elif r == to_region:
    #             total += observed_loss * (1 - loss_share)
    #         else:
    #             pass
    #
    #     return total
    #
    # # Fixed loss assigned to each region
    # m.E_ALLOCATED_INTERCONNECTOR_LOSSES_OBSERVED = pyo.Expression(m.S_REGIONS,
    #                                                               rule=allocated_interconnector_losses_observed_rule)

    return m


def define_generic_constraint_expressions(m, data):
    """Define expressions used to construct generic constraint components"""

    lhs_terms = data.get('generic_constraint_collection').get('lhs_terms')

    def lhs_terms_rule(m, i):
        """Get LHS expression for a given Generic  pyo.Constraint"""

        # LHS terms and associated factors
        # terms = self.data.get_generic_constraint_lhs_terms(i)
        terms = lhs_terms[i]

        # Trader terms
        t_terms = sum(m.V_GC_TRADER[index] * factor for index, factor in terms['traders'].items())

        # Interconnector terms
        i_terms = sum(m.V_GC_INTERCONNECTOR[index] * factor for index, factor in terms['interconnectors'].items())

        # Region terms
        r_terms = sum(m.V_GC_REGION[index] * factor for index, factor in terms['regions'].items())

        return t_terms + i_terms + r_terms

    # Generic constraint LHS
    m.E_LHS_TERMS = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=lhs_terms_rule)

    return m


def define_constraint_violation_penalty_expressions(m):
    """Define expressions relating constraint violation penalties"""

    def generic_constraint_violation_rule(m, i):
        """ Constraint violation penalty for generic constraint which is an inequality"""

        return m.P_CVF_GC[i] * m.V_CV[i]

    # Constraint violation penalty for inequality constraints
    m.E_CV_GC_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_rule)

    def generic_constraint_lhs_violation_rule(m, i):
        """ pyo.Constraint violation penalty for equality constraint"""

        return m.P_CVF_GC[i] * m.V_CV_LHS[i]

    #  pyo.Constraint violation penalty for equality constraints
    m.E_CV_GC_LHS_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_violation_rule)

    def generic_constraint_rhs_violation_rule(m, i):
        """ pyo.Constraint violation penalty for equality constraint"""

        return m.P_CVF_GC[i] * m.V_CV_RHS[i]

    #  pyo.Constraint violation penalty for equality constraints
    m.E_CV_GC_RHS_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_violation_rule)

    def trader_offer_penalty_rule(m, i, j, k):
        """Penalty for band amount exceeding band bid amount"""

        return m.P_CVF_OFFER_PRICE * m.V_CV_TRADER_OFFER[i, j, k]

    #  pyo.Constraint violation penalty for trader dispatched band amount exceeding bid amount
    m.E_CV_TRADER_OFFER_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_penalty_rule)

    def trader_capacity_penalty_rule(m, i, j):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_CAPACITY_PRICE * m.V_CV_TRADER_CAPACITY[i, j]

    #  pyo.Constraint violation penalty for total offer amount exceeding max available
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

    def trader_trapezium_penalty_rule(m, i, j):
        """Penalty for violating FCAS trapezium bounds"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_TRAPEZIUM[i, j]

    # FCAS trapezium violation penalty
    m.E_CV_TRADER_TRAPEZIUM_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_trapezium_penalty_rule)

    def trader_fcas_trapezium_penalty_rule(m, i, j):
        """Penalty for violating FCAS trapezium bounds"""

        return m.P_CVF_AS_PROFILE_PRICE * (m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j]
                                           + m.V_CV_TRADER_FCAS_AS_PROFILE_2[i, j]
                                           + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j]
                                           )

    # FCAS trapezium penalty
    m.E_CV_TRADER_FCAS_TRAPEZIUM_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                          rule=trader_fcas_trapezium_penalty_rule)

    def trader_joint_ramping_up_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_UP[i, j]

    # FCAS joint ramping constraint down violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_UP_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                            rule=trader_joint_ramping_up_penalty_rule)

    def trader_joint_ramping_down_penalty_rule(m, i, j):
        """Penalty for FCAS joint ramping constraint down violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_DOWN[i, j]

    # FCAS joint ramping constraint down violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_DOWN_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                              rule=trader_joint_ramping_down_penalty_rule)

    def trader_joint_capacity_up_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_UP[i, j]

    # FCAS joint capacity constraint up violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_UP_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                             rule=trader_joint_capacity_up_penalty_rule)

    def trader_joint_capacity_down_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint down violation"""

        return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_DOWN[i, j]

    # FCAS joint capacity constraint down violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_DOWN_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                               rule=trader_joint_capacity_down_penalty_rule)

    def trader_joint_regulating_capacity_up_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint up violation"""

        return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_JOINT_REGULATING_CAPACITY_UP[i, j]

    # FCAS joint capacity constraint down violation penalty
    m.E_CV_JOINT_REGULATING_CAPACITY_UP_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                                 rule=trader_joint_regulating_capacity_up_penalty_rule)

    def trader_joint_regulating_capacity_down_penalty_rule(m, i, j):
        """Penalty for FCAS joint capacity constraint down violation"""

        return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_JOINT_REGULATING_CAPACITY_DOWN[i, j]

    # FCAS joint capacity constraint down violation penalty
    m.E_CV_JOINT_REGULATING_CAPACITY_DOWN_PENALTY = pyo.Expression(m.S_TRADER_OFFERS,
                                                                   rule=trader_joint_regulating_capacity_down_penalty_rule)

    def mnsp_offer_penalty_rule(m, i, j, k):
        """Penalty for band amount exceeding band bid amount"""

        return m.P_CVF_MNSP_OFFER_PRICE * m.V_CV_MNSP_OFFER[i, j, k]

    #  pyo.Constraint violation penalty for MNSP dispatched band amount exceeding bid amount
    m.E_CV_MNSP_OFFER_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_penalty_rule)

    def mnsp_capacity_penalty_rule(m, i, j):
        """Penalty for total band amount exceeding max available amount"""

        return m.P_CVF_MNSP_CAPACITY_PRICE * m.V_CV_MNSP_CAPACITY[i, j]

    #  pyo.Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_MNSP_CAPACITY_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_capacity_penalty_rule)

    def interconnector_forward_penalty_rule(m, i):
        """Penalty for forward power flow exceeding max allowable flow"""

        return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_FORWARD[i]

    #  pyo.Constraint violation penalty for forward interconnector limit being violated
    m.E_CV_INTERCONNECTOR_FORWARD_PENALTY = pyo.Expression(m.S_INTERCONNECTORS,
                                                           rule=interconnector_forward_penalty_rule)

    def interconnector_reverse_penalty_rule(m, i):
        """Penalty for reverse power flow exceeding max allowable flow"""

        return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_REVERSE[i]

    #  pyo.Constraint violation penalty for forward interconnector limit being violated
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
             + sum(m.E_CV_TRADER_TRAPEZIUM_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_TRAPEZIUM_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_RAMPING_UP_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_RAMPING_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_UP_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_JOINT_REGULATING_CAPACITY_UP_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_JOINT_REGULATING_CAPACITY_DOWN_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i] for i in m.S_INTERCONNECTORS)
             + sum(m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i] for i in m.S_INTERCONNECTORS)
    )

    return m
