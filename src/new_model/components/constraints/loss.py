"""Loss model constraints"""

import pyomo.environ as pyo


def approximated_loss_rule(m, i):
    """Approximate interconnector loss"""

    return (m.V_LOSS[i] == sum(m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y[i, k] * m.V_LOSS_LAMBDA[i, k]
                               for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i))


def sos2_condition_1_rule(m, i):
    """SOS2 condition 1"""

    return (m.V_GC_INTERCONNECTOR[i] == sum(m.P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X[i, k] * m.V_LOSS_LAMBDA[i, k]
                                            for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i))


def sos2_condition_2_rule(m, i):
    """SOS2 condition 2"""

    return sum(m.V_LOSS_LAMBDA[i, k] for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS if j == i) == 1


def sos2_condition_3_rule(m, i):
    """SOS2 condition 3"""

    return sum(m.V_LOSS_Y[i, k] for j, k in m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS if j == i) == 1


def sos2_condition_4_rule(m, i, j):
    """SOS2 condition 4"""

    # Last interconnector breakpoint index
    end = max(segment_id for interconnector_id, segment_id in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
              if interconnector_id == i)

    if (j >= 2) and (j <= end - 1):
        return (sum(m.V_LOSS_Y[i, z] for z in range(j + 1, end))
                <= sum(m.V_LOSS_LAMBDA[i, z] for z in range(j + 1, end + 1)))
    else:
        return pyo.Constraint.Skip


def sos2_condition_5_rule(m, i, j):
    """SOS2 condition 5"""

    # Last interconnector breakpoint index
    end = max(segment_id for interconnector_id, segment_id in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
              if interconnector_id == i)

    if (j >= 2) and (j <= end - 1):
        return (sum(m.V_LOSS_LAMBDA[i, z] for z in range(j + 1, end + 1))
                <= sum(m.V_LOSS_Y[i, z] for z in range(j, end)))
    else:
        return pyo.Constraint.Skip


def sos2_condition_6_rule(m, i, j):
    """SOS2 condition 6"""

    # Last interconnector breakpoint index
    end = max(segment_id for interconnector_id, segment_id in m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS
              if interconnector_id == i)

    if j == 1:
        return m.V_LOSS_LAMBDA[i, j] <= m.V_LOSS_Y[i, j]
    elif j == end:
        return m.V_LOSS_LAMBDA[i, j] <= m.V_LOSS_Y[i, j - 1]
    else:
        return pyo.Constraint.Skip


def define_loss_model_constraints(m):
    """Interconnector loss model constraints"""

    # Approximate loss over interconnector
    m.C_APPROXIMATED_LOSS = pyo.Constraint(m.S_INTERCONNECTORS, rule=approximated_loss_rule)

    # SOS2 condition 1
    m.C_SOS2_CONDITION_1 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_1_rule)

    # SOS2 condition 2
    m.C_SOS2_CONDITION_2 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_2_rule)

    # SOS2 condition 3
    m.C_SOS2_CONDITION_3 = pyo.Constraint(m.S_INTERCONNECTORS, rule=sos2_condition_3_rule)

    # SOS2 condition 4
    m.C_SOS2_CONDITION_4 = pyo.Constraint(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, rule=sos2_condition_4_rule)

    # SOS2 condition 5
    m.C_SOS2_CONDITION_5 = pyo.Constraint(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, rule=sos2_condition_5_rule)

    # SOS2 condition 6
    m.C_SOS2_CONDITION_6 = pyo.Constraint(m.S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS, rule=sos2_condition_6_rule)

    return m
