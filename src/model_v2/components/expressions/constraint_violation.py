"""Constraint violation penalty expressions"""

import pyomo.environ as pyo


def generic_constraint_violation_rule(m, i):
    """Constraint violation penalty for generic constraint which is an inequality"""

    return m.P_CVF_GC[i] * m.V_CV[i]


def generic_constraint_lhs_violation_rule(m, i):
    """Constraint violation penalty for equality constraint"""

    return m.P_CVF_GC[i] * m.V_CV_LHS[i]


def generic_constraint_rhs_violation_rule(m, i):
    """Constraint violation penalty for equality constraint"""

    return m.P_CVF_GC[i] * m.V_CV_RHS[i]


def trader_offer_penalty_rule(m, i, j, k):
    """Penalty for band amount exceeding band bid amount"""

    return m.P_CVF_OFFER_PRICE * m.V_CV_TRADER_OFFER[i, j, k]


def trader_capacity_penalty_rule(m, i, j):
    """Penalty for total band amount exceeding max available amount"""

    return m.P_CVF_CAPACITY_PRICE * m.V_CV_TRADER_CAPACITY[i, j]


def trader_ramp_up_penalty_rule(m, i):
    """Penalty for violating ramp down constraint"""

    return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_UP[i]


def trader_ramp_down_penalty_rule(m, i):
    """Penalty for violating ramp down constraint"""

    return m.P_CVF_RAMP_RATE_PRICE * m.V_CV_TRADER_RAMP_DOWN[i]


def trader_trapezium_penalty_rule(m, i, j):
    """Penalty for violating FCAS trapezium bounds"""

    return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_TRAPEZIUM[i, j]


def trader_fcas_trapezium_penalty_rule(m, i, j):
    """Penalty for violating FCAS trapezium bounds"""

    return m.P_CVF_AS_PROFILE_PRICE * (m.V_CV_TRADER_FCAS_AS_PROFILE_1[i, j]
                                       + m.V_CV_TRADER_FCAS_AS_PROFILE_2[i, j]
                                       + m.V_CV_TRADER_FCAS_AS_PROFILE_3[i, j]
                                       )


def trader_joint_ramping_raise_generator_penalty_rule(m, i, j):
    """Penalty for FCAS joint capacity constraint up violation"""

    return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR[i, j]


def trader_joint_ramping_lower_generator_penalty_rule(m, i, j):
    """Penalty for FCAS joint ramping constraint down violation"""

    return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR[i, j]


def trader_joint_capacity_raise_generator_penalty_rule(m, i, j):
    """Penalty for FCAS joint capacity constraint raise violation"""

    return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_RAISE_GENERATOR[i, j]


def trader_joint_capacity_lower_generator_penalty_rule(m, i, j):
    """Penalty for FCAS joint capacity constraint lower violation"""

    return m.P_CVF_AS_PROFILE_PRICE * m.V_CV_TRADER_FCAS_JOINT_CAPACITY_LOWER_GENERATOR[i, j]


def trader_fcas_energy_regulating_raise_generator_penalty_rule(m, i, j):
    """Penalty for FCAS joint capacity constraint up violation"""

    return m.P_CVF_AS_ENABLEMENT_MAX_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR[i, j]


def trader_fcas_energy_regulating_lower_generator_penalty_rule(m, i, j):
    """Penalty for FCAS joint capacity constraint down violation"""

    return m.P_CVF_AS_ENABLEMENT_MIN_PRICE * m.V_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR[i, j]


def mnsp_offer_penalty_rule(m, i, j, k):
    """Penalty for band amount exceeding band bid amount"""

    return m.P_CVF_MNSP_OFFER_PRICE * m.V_CV_MNSP_OFFER[i, j, k]


def mnsp_capacity_penalty_rule(m, i, j):
    """Penalty for total band amount exceeding max available amount"""

    return m.P_CVF_MNSP_CAPACITY_PRICE * m.V_CV_MNSP_CAPACITY[i, j]


def interconnector_forward_penalty_rule(m, i):
    """Penalty for forward power flow exceeding max allowable flow"""

    return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_FORWARD[i]


def interconnector_reverse_penalty_rule(m, i):
    """Penalty for reverse power flow exceeding max allowable flow"""

    return m.P_CVF_INTERCONNECTOR_PRICE * m.V_CV_INTERCONNECTOR_REVERSE[i]


def define_constraint_violation_penalty_expressions(m):
    """Define expressions relating constraint violation penalties"""

    # Constraint violation penalty for inequality constraints
    m.E_CV_GC_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_rule)

    # Constraint violation penalty for equality constraints
    m.E_CV_GC_LHS_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_lhs_violation_rule)

    # Constraint violation penalty for equality constraints
    m.E_CV_GC_RHS_PENALTY = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_violation_rule)

    # Constraint violation penalty for trader dispatched band amount exceeding bid amount
    m.E_CV_TRADER_OFFER_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_penalty_rule)

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_TRADER_CAPACITY_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_capacity_penalty_rule)

    # Penalty factor for ramp up rate violation
    m.E_CV_TRADER_RAMP_UP_PENALTY = pyo.Expression(m.S_TRADERS, rule=trader_ramp_up_penalty_rule)

    # Penalty factor for ramp down rate violation
    m.E_CV_TRADER_RAMP_DOWN_PENALTY = pyo.Expression(m.S_TRADERS, rule=trader_ramp_down_penalty_rule)

    # FCAS trapezium violation penalty
    m.E_CV_TRADER_TRAPEZIUM_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_trapezium_penalty_rule)

    # FCAS trapezium penalty
    m.E_CV_TRADER_FCAS_TRAPEZIUM_PENALTY = pyo.Expression(m.S_TRADER_OFFERS, rule=trader_fcas_trapezium_penalty_rule)

    # FCAS joint ramping constraint down violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_RAISE_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_ramping_raise_generator_penalty_rule)

    # FCAS joint ramping constraint down violation penalty
    m.E_CV_TRADER_JOINT_RAMPING_LOWER_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_ramping_lower_generator_penalty_rule)

    # FCAS joint capacity constraint up violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_RAISE_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_raise_generator_penalty_rule)

    # FCAS joint capacity constraint down violation penalty
    m.E_CV_TRADER_JOINT_CAPACITY_LOWER_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_joint_capacity_lower_generator_penalty_rule)

    # FCAS joint capacity constraint down violation penalty
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_energy_regulating_raise_generator_penalty_rule)

    # FCAS joint capacity constraint down violation penalty
    m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_PENALTY = pyo.Expression(
        m.S_TRADER_OFFERS, rule=trader_fcas_energy_regulating_lower_generator_penalty_rule)

    # Constraint violation penalty for MNSP dispatched band amount exceeding bid amount
    m.E_CV_MNSP_OFFER_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_penalty_rule)

    # Constraint violation penalty for total offer amount exceeding max available
    m.E_CV_MNSP_CAPACITY_PENALTY = pyo.Expression(m.S_MNSP_OFFERS, rule=mnsp_capacity_penalty_rule)

    # Constraint violation penalty for forward interconnector limit being violated
    m.E_CV_INTERCONNECTOR_FORWARD_PENALTY = pyo.Expression(m.S_INTERCONNECTORS,
                                                           rule=interconnector_forward_penalty_rule)

    # Constraint violation penalty for forward interconnector limit being violated
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
             + sum(m.E_CV_TRADER_JOINT_RAMPING_RAISE_GENERATOR_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_RAMPING_LOWER_GENERATOR_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_RAISE_GENERATOR_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_JOINT_CAPACITY_LOWER_GENERATOR_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_RAISE_GENERATOR_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_TRADER_FCAS_ENERGY_REGULATING_LOWER_GENERATOR_PENALTY[i] for i in m.S_TRADER_OFFERS)
             + sum(m.E_CV_MNSP_OFFER_PENALTY[i, j, k] for i, j in m.S_MNSP_OFFERS for k in m.S_BANDS)
             + sum(m.E_CV_MNSP_CAPACITY_PENALTY[i] for i in m.S_MNSP_OFFERS)
             + sum(m.E_CV_INTERCONNECTOR_FORWARD_PENALTY[i] for i in m.S_INTERCONNECTORS)
             + sum(m.E_CV_INTERCONNECTOR_REVERSE_PENALTY[i] for i in m.S_INTERCONNECTORS)
    )

    return m
