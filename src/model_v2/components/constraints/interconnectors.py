"""Interconnector constraints"""

import pyomo.environ as pyo


def interconnector_forward_flow_rule(m, i):
    """Constrain forward power flow over interconnector"""

    return m.V_GC_INTERCONNECTOR[i] <= m.P_INTERCONNECTOR_UPPER_LIMIT[i] + m.V_CV_INTERCONNECTOR_FORWARD[i]


def interconnector_reverse_flow_rule(m, i):
    """Constrain reverse power flow over interconnector"""

    return m.V_GC_INTERCONNECTOR[i] + m.V_CV_INTERCONNECTOR_REVERSE[i] >= - m.P_INTERCONNECTOR_LOWER_LIMIT[i]


def from_node_connection_point_balance_rule(m, i):
    """Power balance at from node connection point"""

    return m.V_FLOW_FROM_CP[i] - (m.P_INTERCONNECTOR_LOSS_SHARE[i] * m.V_LOSS[i]) - m.V_GC_INTERCONNECTOR[i] == 0


def to_node_connection_point_balance_rule(m, i):
    """Power balance at to node connection point"""

    # Loss share applied to from node connection point
    loss_share = 1 - m.P_INTERCONNECTOR_LOSS_SHARE[i]

    return m.V_GC_INTERCONNECTOR[i] - (loss_share * m.V_LOSS[i]) - m.V_FLOW_TO_CP[i] == 0


def define_interconnector_constraints(m):
    """Define power flow limits on interconnectors"""

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_FORWARD_FLOW = pyo.Constraint(m.S_INTERCONNECTORS, rule=interconnector_forward_flow_rule)

    # Forward power flow limit for interconnector
    m.C_INTERCONNECTOR_REVERSE_FLOW = pyo.Constraint(m.S_INTERCONNECTORS, rule=interconnector_reverse_flow_rule)

    # From node connection point power balance
    m.C_FROM_NODE_CP_POWER_BALANCE = pyo.Constraint(m.S_INTERCONNECTORS, rule=from_node_connection_point_balance_rule)

    # To node connection point power balance
    m.C_TO_NODE_CP_POWER_BALANCE = pyo.Constraint(m.S_INTERCONNECTORS, rule=to_node_connection_point_balance_rule)

    return m
