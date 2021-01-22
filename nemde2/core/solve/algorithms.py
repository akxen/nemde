def fix_binary_variables(m):
    """Fix all binary variables"""

    for i in m.S_INTERCONNECTOR_LOSS_MODEL_INTERVALS:
        m.V_LOSS_Y[i].fix()

    return m


def fix_interconnector_flow_solution(m, data, intervention):
    """Fix interconnector solution to observed values"""

    for i in m.S_GC_INTERCONNECTOR_VARS:
        observed_flow = utils.lookup.get_interconnector_solution_attribute(
            data, i, '@Flow', float, intervention)
        m.V_GC_INTERCONNECTOR[i].fix(observed_flow)

    return m


def unfix_interconnector_flow_solution(m):
    """Fix interconnector solution to observed values"""

    for i in m.S_GC_INTERCONNECTOR_VARS:
        m.V_GC_INTERCONNECTOR[i].unfix()

    return m


def fix_trader_solution(m, data, intervention, offers=None):
    """Fix FCAS solution"""

    # Map between NEMDE output keys and keys used in solution dictionary
    key_map = {'ENOF': '@EnergyTarget', 'LDOF': '@EnergyTarget',
               'R6SE': '@R6Target', 'R60S': '@R60Target', 'R5MI': '@R5Target', 'R5RE': '@R5RegTarget',
               'L6SE': '@L6Target', 'L60S': '@L60Target', 'L5MI': '@L5Target', 'L5RE': '@L5RegTarget'}

    # Use all offers by default
    if offers is None:
        trader_offers = ['ENOF', 'LDOF', 'R6SE', 'R60S',
                         'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']
    else:
        trader_offers = offers

    for i, j in m.S_TRADER_OFFERS:
        if j in trader_offers:
            target = utils.lookup.get_trader_solution_attribute(
                data, i, key_map[j], float, intervention)
            m.V_TRADER_TOTAL_OFFER[(i, j)].fix(target)

    return m


def solve_model(m):
    """Solve model"""

    # Setup solver
    solver_options = {
        # 'mip tolerances mipgap': 1e-50,
        # 'mip tolerances absmipgap': 1,
        # 'mip tolerances mipgap': 1e-20,
    }

    # solver_options = {
    #     'MIPGapAbs': 1e-20,
    #     'MIPGap': 1e-20,
    # }

    # solver_options = {}

    # solver_options = {}
    opt = pyo.SolverFactory('cbc', solver_io='lp')

    # Solve model
    t0 = time.time()

    print('Starting MILP solve:', time.time() - t0)
    solve_status_1 = opt.solve(
        m, tee=True, options=solver_options, keepfiles=False)
    print('Finished MILP solve:', time.time() - t0)
    print('Objective value - 1:', m.OBJECTIVE.expr())

    # # Fix binary variables
    # m = fix_binary_variables(m)
    #
    # # Unfix interconnector solution
    # # m = unfix_interconnector_flow_solution(m)
    #
    # solve_status_2 = opt.solve(m, tee=True, options=solver_options, keepfiles=False)
    # print('Finished MILP solve:', time.time() - t0)
    # print('Objective value - 2:', m.OBJECTIVE.expr())

    return m


def solve_model_online(user_data):
    """Construct model for online applications"""

    # Extract case ID
    case_id = user_data['CaseID']

    # Load case data
    base_case = nemde.core.utils.database.get_preprocessed_case_data(
        os.environ['MYSQL_DATABASE'], case_id)

    # Update case with user parameters
    updated_case = update(base_case, user_data)

    # Pre-process case file to be ingested by model
    transformed_case = nemde.core.utils.transforms.simplified.data.parse_case_data(
        updated_case, 'physical')
    preprocessed_case = nemde.core.utils.preprocessing.get_preprocessed_case_file(
        transformed_case)

    # Construct and solve model
    m = construct_model(preprocessed_case)
    m = solve_model(m)

    # Extract solution
    m_solution = nemde.core.utils.solution.get_model_solution(m)

    return m_solution


def get_case_ids(year, month, n, seed=10):
    """Get random collection of dispatch interval case IDs"""

    # Get days in specified month
    _, days_in_month = calendar.monthrange(year, month)

    # Seed random number generator for reproducable results
    np.random.seed(seed)

    # Population of dispatch intervals for a given month
    population = [f'{year}{month:02}{i:02}{j:03}' for i in range(
        1, days_in_month + 1) for j in range(1, 289)]

    # Shuffle list to randomise sample (should be reproducible though because seed is set)
    np.random.shuffle(population)

    # Return Sample of case IDs
    return population[:n]


def save_case_json(data_dir, output_dir, year, month, day, interval, overwrite=True):
    """Save casefile in JSON format for inspection"""

    # Case data in json format
    data_json = utils.loaders.load_dispatch_interval_json(
        data_dir, year, month, day, interval)

    # Get NEMDE model data as a Python dictionary
    data = json.loads(data_json)

    # Filename for JSON data
    filename = f'case-{year}-{month:02}-{day:02}-{interval:03}.json'

    if filename in os.listdir(output_dir) and not overwrite:
        pass
    else:
        with open(os.path.join(output_dir, filename), 'w') as f:
            json.dump(data, f)


def get_positive_variables(obj):
    """Get all variables that are > 0"""

    return [(i, obj[i].value) for i in obj.keys() if obj[i].value > 0]


def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def get_model_data_online(case_id):
    """Get data for a given case"""

    # Load case data
    base_case = utils.database.get_preprocessed_case_data(
        os.environ['MYSQL_DATABASE'], case_id)

    return base_case
