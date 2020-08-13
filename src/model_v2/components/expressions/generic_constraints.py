"""Expressions used in generic constraints"""

import pyomo.environ as pyo


def define_generic_constraint_expressions(m, data):
    """Define generic constraint expressions"""

    # LHS terms in generic constraints
    terms = data['preprocessed']['GC_LHS_TERMS']

    def lhs_terms_rule(m, i):
        """Get LHS expression for a given Generic Constraint"""

        # LHS terms and associated factors
        # terms = self.data.get_generic_constraint_lhs_terms(i)

        # Trader terms
        t_terms = sum(m.V_GC_TRADER[index] * factor for index, factor in terms[i]['traders'].items())

        # Interconnector terms
        i_terms = sum(m.V_GC_INTERCONNECTOR[index] * factor for index, factor in terms[i]['interconnectors'].items())

        # Region terms
        r_terms = sum(m.V_GC_REGION[index] * factor for index, factor in terms[i]['regions'].items())

        return t_terms + i_terms + r_terms

    # Generic constraint LHS terms
    m.E_GC_LHS_TERMS = pyo.Expression(m.S_GENERIC_CONSTRAINTS, rule=lhs_terms_rule)

    return m


if __name__ == '__main__':
    pass
