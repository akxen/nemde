"""Aggregate power expressions"""

import pyomo.environ as pyo


def region_generation_rule(m, r):
    """Available energy offers in given region"""

    return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
               if (j == 'ENOF') and (m.P_TRADER_REGION[i] == r))


def region_load_rule(m, r):
    """Available load offers in given region"""

    return sum(m.V_TRADER_TOTAL_OFFER[i, j] for i, j in m.S_TRADER_OFFERS
               if (j == 'LDOF') and (m.P_TRADER_REGION[i] == r))


def region_net_export_flow_rule(m, r):
    """Net flow out of region"""

    net_flow = 0

    for i in m.S_INTERCONNECTORS:

        if r == m.P_INTERCONNECTOR_FROM_REGION[i]:
            # Check if an MNSP
            if m.P_INTERCONNECTOR_MNSP_STATUS[i] == '1':
                factor = m.P_MNSP_FROM_REGION_LF[i]
            else:
                factor = 1

            net_flow += factor * m.V_FLOW_FROM_CP[i]

        elif r == m.P_INTERCONNECTOR_TO_REGION[i]:
            # Check if an MNSP
            if m.P_INTERCONNECTOR_MNSP_STATUS[i] == '1':
                factor = m.P_MNSP_TO_REGION_LF[i]
            else:
                factor = 1

            net_flow += - (factor * m.V_FLOW_TO_CP[i])

        else:
            pass

    return net_flow


def total_initial_scheduled_load(m, r):
    """Total initial scheduled load in a given region"""

    total = 0
    for i, j in m.S_TRADER_OFFERS:
        if j == 'LDOF':
            if (r == m.P_TRADER_REGION[i]) and (m.P_TRADER_SEMI_DISPATCH_STATUS[i] == '0'):
                total += m.P_TRADER_INITIAL_MW[i]

    return total


def total_initial_allocated_losses(m, r):
    """Total losses assigned to region as a result of interconnector flow"""

    total = 0
    for i in m.S_INTERCONNECTORS:
        # from_region = self.get_interconnector_period_attribute(i, 'FromRegion')
        # to_region = self.get_interconnector_period_attribute(i, 'ToRegion')
        # loss_share = self.get_interconnector_loss_model_attribute(i, 'LossShare')
        # initial_flow = self.get_interconnector_initial_condition_attribute(i, 'InitialMW')

        # TODO: need to figure out an abstraction here - pass data or model object (think model object is better)
        # estimated_losses = loss_model.get_interconnector_loss_estimate(i, m.P_INTERCONNECTOR_INITIAL_MW[i])

        if r == m.P_INTERCONNECTOR_FROM_REGION[i]:
            total += m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i] * m.P_INTERCONNECTOR_LOSS_SHARE[i]

        elif r == m.P_INTERCONNECTOR_TO_REGION[i]:
            total += m.P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE[i] * (1 - m.P_INTERCONNECTOR_LOSS_SHARE[i])
        else:
            pass

    return total


def region_demand_rule(m, r):
    """Get demand in each region. Using forecast demand for now."""

    # Demand in each NEM region
    demand = (
            m.P_REGION_INITIAL_DEMAND[r]
            + m.P_REGION_ADE[r]
            + m.P_REGION_DF[r]
            - m.E_TOTAL_INITIALMW_SCHEDULED_LOAD[r]
            - m.E_TOTAL_INITIAL_ALLOCATED_LOSSES[r]
    )

    return demand


def allocated_interconnector_losses_observed_rule(m, r):
    """Losses obtained from model solution and assigned to each region"""

    total = 0
    for i in m.S_INTERCONNECTORS:

        if r == m.P_INTERCONNECTOR_FROM_REGION[i]:
            total += m.P_INTERCONNECTOR_SOLUTION_LOSS[i] * m.P_INTERCONNECTOR_LOSS_SHARE[i]

        elif r == m.P_INTERCONNECTOR_TO_REGION[i]:
            total += m.P_INTERCONNECTOR_SOLUTION_LOSS[i] * (1 - m.P_INTERCONNECTOR_LOSS_SHARE[i])
        else:
            pass

    return total


def define_aggregate_power_expressions(m):
    """Compute aggregate demand and generation in each NEM region"""

    # Total generation dispatched in a given region
    m.E_REGION_GENERATION = pyo.Expression(m.S_REGIONS, rule=region_generation_rule)

    # Total load dispatched in a given region
    m.E_REGION_LOAD = pyo.Expression(m.S_REGIONS, rule=region_load_rule)

    # Net flow out of region
    m.E_REGION_NET_EXPORT_FLOW = pyo.Expression(m.S_REGIONS, rule=region_net_export_flow_rule)

    # Total initial scheduled load
    m.E_TOTAL_INITIALMW_SCHEDULED_LOAD = pyo.Expression(m.S_REGIONS, rule=total_initial_scheduled_load)

    # Total initial allocated losses
    m.E_TOTAL_INITIAL_ALLOCATED_LOSSES = pyo.Expression(m.S_REGIONS, rule=total_initial_allocated_losses)

    # Region Demand
    m.E_REGION_DEMAND = pyo.Expression(m.S_REGIONS, rule=region_demand_rule)

    # Fixed loss assigned to each region
    m.E_ALLOCATED_INTERCONNECTOR_LOSSES_OBSERVED = pyo.Expression(m.S_REGIONS,
                                                                  rule=allocated_interconnector_losses_observed_rule)

    return m
