

def get_trader_solution(data, intervention) -> dict:
    """Get trader solution"""

    traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@TraderID', '@PeriodID', '@Intervention',
                '@FSTargetMode', '@SemiDispatchCap']

    # Container for extracted values
    solutions = {}
    for i in traders:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@TraderID']
                      ] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_interconnector_solution(data, intervention) -> dict:
    """Get interconnector solution"""

    # All interconnectors
    interconnectors = data.get('NEMSPDCaseFile').get(
        'NemSpdOutputs').get('InterconnectorSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@InterconnectorID', '@PeriodID', '@Intervention', '@NPLExists']

    # Container for extracted interconnector solutions
    solutions = {}
    for i in interconnectors:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@InterconnectorID']
                      ] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_region_solution(data, intervention) -> dict:
    """Get region solution"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@RegionID', '@PeriodID', '@Intervention']

    # Container for extracted region solutions
    solutions = {}
    for i in regions:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@RegionID']
                      ] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_region_solution_attribute(data, attribute, func, intervention) -> dict:
    """Get given solution attribute for all regions"""

    # All regions
    regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')

    return {i['@RegionID']: func(i[attribute]) for i in regions if i['@Intervention'] == intervention}


def get_constraint_solution(data, intervention) -> dict:
    """Get constraint solution"""

    # All constraints
    constraints = data.get('NEMSPDCaseFile').get(
        'NemSpdOutputs').get('ConstraintSolution')

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@ConstraintID', '@Version', '@PeriodID', '@Intervention']

    # Container for extracted region solutions
    solutions = {}
    for i in constraints:
        # Parse values - only consider no intervention case
        if i['@Intervention'] == intervention:
            solutions[i['@ConstraintID']
                      ] = {k: str(v) if k in str_keys else float(v) for k, v in i.items()}

    return solutions


def get_case_solution(data) -> dict:
    """Get case solution"""

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@SolverStatus', '@Terminal', '@InterventionStatus', '@SolverVersion', '@NPLStatus', '@OCD_Status',
                '@CaseSubType']

    return {k: str(v) if k in str_keys else float(v)
            for k, v in data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('CaseSolution').items()}


def get_period_solution(data, intervention) -> dict:
    """Get period solution"""

    # Keys that should be converted to type string. All other keys to be converted to type float.
    str_keys = ['@PeriodID', '@Intervention',
                '@SwitchRunBestStatus', '@SolverStatus', '@NPLStatus']

    return {k: str(v) if k in str_keys else float(v)
            for i in convert_to_list(data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('PeriodSolution'))
            for k, v in i.items() if i['@Intervention'] == intervention}
