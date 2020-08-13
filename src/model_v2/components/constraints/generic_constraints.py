"""Define generic constraints"""

import pyomo.environ as pyo


def trader_variable_link_rule(m, i, j):
    """Link generic constraint trader variables to objective function variables"""

    return m.V_TRADER_TOTAL_OFFER[i, j] == m.V_GC_TRADER[i, j]


def region_variable_link_rule(m, i, j):
    """Link total offer amount for each bid type to region variables"""

    return (sum(m.V_TRADER_TOTAL_OFFER[q, r] for q, r in m.S_TRADER_OFFERS if (m.P_TRADER_REGION[q] == i) and (r == j))
            == m.V_GC_REGION[i, j])


def mnsp_variable_link_rule(m, i):
    """Link generic constraint MNSP variables to objective function variables"""

    # From and to regions for a given MNSP
    from_region = m.P_INTERCONNECTOR_FROM_REGION[i]
    to_region = m.P_INTERCONNECTOR_TO_REGION[i]

    # TODO: Taking difference between 'to' and 'from' region. Think this is correct.
    return m.V_GC_INTERCONNECTOR[i] == m.V_MNSP_TOTAL_OFFER[i, to_region] - m.V_MNSP_TOTAL_OFFER[i, from_region]


def generic_constraint_rule(m, c):
    """NEMDE Generic Constraints"""

    # Type of generic constraint (LE, GE, EQ)
    if m.P_GC_TYPE[c] == 'LE':
        return m.E_GC_LHS_TERMS[c] <= m.P_GC_RHS[c] + m.V_CV[c]
    elif m.P_GC_TYPE[c] == 'GE':
        return m.E_GC_LHS_TERMS[c] + m.V_CV[c] >= m.P_GC_RHS[c]
    elif m.P_GC_TYPE[c] == 'EQ':
        return m.E_GC_LHS_TERMS[c] + m.V_CV_LHS[c] == m.P_GC_RHS[c] + m.V_CV_RHS[c]
    else:
        raise Exception(f'Unexpected constraint type: {m.P_GC_TYPE[c]}')


def define_generic_constraints(m):
    """
    Construct generic constraints. Also include constraints linking variables in objective function to variables in
    Generic Constraints.
    """

    # Link between total power output and quantity band output
    m.C_TRADER_VARIABLE_LINK = pyo.Constraint(m.S_GC_TRADER_VARS, rule=trader_variable_link_rule)

    # Link between region variables and the trader components constituting those variables
    m.C_REGION_VARIABLE_LINK = pyo.Constraint(m.S_GC_REGION_VARS, rule=region_variable_link_rule)

    # Link between total power output and quantity band output
    m.C_MNSP_VARIABLE_LINK = pyo.Constraint(m.S_MNSPS, rule=mnsp_variable_link_rule)

    # Generic constraints
    m.C_GENERIC_CONSTRAINT = pyo.Constraint(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rule)

    return m
