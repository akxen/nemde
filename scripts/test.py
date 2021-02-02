import pyomo.environ as pyo

m = pyo.ConcreteModel()

m.s = pyo.Set(initialize=range(1, 10000))

m.x = pyo.Var(m.s, within=pyo.NonNegativeReals)


def c_1_rule(m, i):
    return m.x[i] == i


m.c_1 = pyo.Constraint(m.s, rule=c_1_rule)


def c_2_rule(m, i):
    return m.x[i] <= 2000000


m.c_2 = pyo.Constraint(m.s, rule=c_2_rule)


m.c_2.deactivate()

m.obj = pyo.Objective(expr=sum(m.x[i] for i in m.s), sense=pyo.maximize)

opt = pyo.SolverFactory('cbc', solver_io='lp')


m.c_1.deactivate()
opt.solve(m)
print(m.x[1].value)
