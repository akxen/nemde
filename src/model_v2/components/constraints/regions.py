"""Region constraints"""

import pyomo.environ as pyo


def power_balance_rule(m, r):
    """Power balance for each region"""

    return (m.E_REGION_GENERATION[r]
            ==
            m.E_REGION_DEMAND[r]
            + m.E_REGION_LOAD[r]
            + m.E_REGION_NET_EXPORT_FLOW[r]
            )


def define_region_constraints(m):
    """Define power balance constraint for each region, and constrain flows on interconnectors"""

    # Power balance in each region
    m.C_POWER_BALANCE = pyo.Constraint(m.S_REGIONS, rule=power_balance_rule)

    return m
