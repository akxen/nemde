"""Offer constraints"""

import pyomo.environ as pyo


def trader_total_offer_rule(m, i, j):
    """Link quantity band offers to total offer made by trader for each offer type"""

    return m.V_TRADER_TOTAL_OFFER[i, j] == sum(m.V_TRADER_OFFER[i, j, k] for k in m.S_BANDS)


def trader_offer_rule(m, i, j, k):
    """Band output must be non-negative and less than the max offered amount for that band"""

    return m.V_TRADER_OFFER[i, j, k] <= m.P_TRADER_QUANTITY_BAND[i, j, k] + m.V_CV_TRADER_OFFER[i, j, k]


def trader_capacity_rule(m, i, j):
    """Constrain max available output"""

    # UIGF constrains max output for semi-dispatchable plant
    if i in m.S_TRADERS_SEMI_DISPATCH:
        return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_UIGF[i] + m.V_CV_TRADER_CAPACITY[i, j]
    else:
        return m.V_TRADER_TOTAL_OFFER[i, j] <= m.P_TRADER_MAX_AVAILABLE[i, j] + m.V_CV_TRADER_CAPACITY[i, j]


def mnsp_total_offer_rule(m, i, j):
    """Link quantity band offers to total offer made by MNSP for each offer type"""

    return m.V_MNSP_TOTAL_OFFER[i, j] == sum(m.V_MNSP_OFFER[i, j, k] for k in m.S_BANDS)


def mnsp_offer_rule(m, i, j, k):
    """Band output must be non-negative and less than the max offered amount for that band"""

    return m.V_MNSP_OFFER[i, j, k] <= m.P_MNSP_QUANTITY_BAND[i, j, k] + m.V_CV_MNSP_OFFER[i, j, k]


def mnsp_capacity_rule(m, i, j):
    """Constrain max available output"""

    return m.V_MNSP_TOTAL_OFFER[i, j] <= m.P_MNSP_MAX_AVAILABLE[i, j] + m.V_CV_MNSP_CAPACITY[i, j]


def define_offer_constraints(m):
    """Ensure trader and MNSP bids don't exceed their specified bid bands"""

    # Linking individual quantity band offers to total amount offered by trader
    m.C_TRADER_TOTAL_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_total_offer_rule)

    # Bounds on quantity band variables for traders
    m.C_TRADER_OFFER = pyo.Constraint(m.S_TRADER_OFFERS, m.S_BANDS, rule=trader_offer_rule)

    # Ensure dispatch is constrained by max available offer amount
    m.C_TRADER_CAPACITY = pyo.Constraint(m.S_TRADER_OFFERS, rule=trader_capacity_rule)

    # Linking individual quantity band offers to total amount offered by MNSP
    m.C_MNSP_TOTAL_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_total_offer_rule)

    # Bounds on quantity band variables for MNSPs
    m.C_MNSP_OFFER = pyo.Constraint(m.S_MNSP_OFFERS, m.S_BANDS, rule=mnsp_offer_rule)

    # Ensure dispatch is constrained by max available offer amount
    m.C_MNSP_CAPACITY = pyo.Constraint(m.S_MNSP_OFFERS, rule=mnsp_capacity_rule)

    return m
