"""Check NEMDE solution"""


class NEMDESolution:
    def __init__(self, data_dir):
        # Important directories
        self.data_dir = data_dir

        # Object used to parse NEMDE data
        self.data = NEMDEDataHandler(data_dir)

        # Object used to check FCAS solution
        self.fcas = FCASHandler(data_dir)

    @staticmethod
    def get_variable_values(m, v):
        """Extract pyo.Variable values from model object"""

        # Extract values into dictionary
        values = {k: v.value for k, v in m.__getattribute__(v).items()}

        return values

    def get_scheduled_traders(self):
        """Get all scheduled traders"""

        # All traders
        all_traders = self.data.get_trader_index()

        # Get scheduled generators / loads
        scheduled = [i for i in all_traders if self.data.get_trader_attribute(i, 'SemiDispatch') == 0]

        return scheduled

    def get_model_energy_output(self, m, var_name):
        """Extract energy output"""

        # Energy output values
        values = self.get_variable_values(m, var_name)

        # Wrap values in list - makes parsing DataFrame easier
        values_in_list = {k: [v] for k, v in values.items()}

        # Convert to DataFrame
        df = pd.DataFrame(values_in_list).T
        df.index.rename(['TRADER_ID', 'OFFER_TYPE'], inplace=True)
        df = df.rename(columns={0: 'output'})

        # Model output
        df_m = df.pivot_table(index='TRADER_ID', columns='OFFER_TYPE', values='output').astype(float, errors='ignore')

        return df_m

    def check_energy_solution(self, m, model_variable_name, model_key, observed_key):
        """Check model solution"""

        # Model energy output
        df_m = self.get_model_energy_output(m, model_variable_name)

        # Actual NEMDE output
        df_o = self.data.get_trader_solution_dataframe()

        # Combine into single DataFrame
        df_c = pd.concat([df_m[model_key], df_o[observed_key]], axis=1, sort=True)

        # Compute difference between model and target
        df_c['difference'] = df_c[model_key].subtract(df_c[observed_key])
        df_c['abs_difference'] = df_c['difference'].abs()
        df_c = df_c.sort_values(by='abs_difference', ascending=False)

        # Get scheduled loads
        scheduled = [i for i in df_c.index if self.data.get_trader_attribute(i, 'SemiDispatch') == 0]

        # Mean squared error (squared difference between NEMDE target values and model values)
        mse = df_c.loc[scheduled, :].apply(lambda x: (x[model_key] - x[observed_key]) ** 2, axis=1).mean()
        print(f'{model_key} MSE =', mse)

        # Compare model and observed energy output
        ax = df_c.loc[scheduled, :].plot(x=model_key, y=observed_key, kind='scatter')

        # Max value
        max_value = df_c.loc[scheduled, [model_key, observed_key]].max().max()
        ax.plot([0, max_value], [0, max_value], color='r', alpha=0.8, linestyle='--')

        plt.show()

        return df_c

    def check_trader_solution(self, m, trader_id):
        """Compare model results with actual solution"""

        # Name map between model and solution pyo.Variables
        name_map = {'R6SE': 'R6Target', 'R60S': 'R60Target', 'R5MI': 'R5Target', 'R5RE': 'R5RegTarget',
                    'L6SE': 'L6Target', 'L60S': 'L60Target', 'L5MI': 'L5Target', 'L5RE': 'L5RegTarget',
                    'ENOF': 'EnergyTarget', 'LDOF': 'EnergyTarget'}

        fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8), (ax9, ax10)) = plt.subplots(nrows=5, ncols=2)

        for i, j in [(ax1, 'ENOF'), (ax2, 'LDOF')]:
            # Plot energy solution
            try:
                i.set_title(j)
                model_energy_target = m.V_TRADER_TOTAL_OFFER[trader_id, j].value
                true_energy_target = self.data.get_trader_solution_attribute(trader_id, name_map[j])
                i.scatter([model_energy_target], [true_energy_target], color='cyan')
                max_value = max([model_energy_target, true_energy_target])
                i.plot([0, max_value + 1], [0, max_value + 1], linestyle='--', linewidth=0.9, alpha=0.7)
                i.set_xlim([0, max_value + 1])
                i.set_xlim([0, max_value + 1])
            except:
                pass

        # Plot FCAS solution
        for i, j in [(ax3, 'L5RE'), (ax4, 'R5RE'), (ax5, 'L5MI'), (ax6, 'R5MI'), (ax7, 'L60S'), (ax8, 'R60S'),
                     (ax9, 'L6SE'), (ax10, 'R6SE')]:
            try:
                i.set_title(j)
                i = self.fcas.plot_fcas_solution(trader_id, j, i)
                model_target = m.V_TRADER_TOTAL_OFFER[trader_id, j].value
                i.scatter([model_energy_target], [model_target], color='cyan')
            except Exception as e:
                print(e, j)

        fig.set_size_inches(6, 12)

        plt.show()

    @staticmethod
    def print_fcas_constraints(m, trader_id):
        """Print all FCAS constraints applying to a given trader"""

        # Types of FCAS offers
        fcas_types = ['L6SE', 'L60S', 'L5MI', 'L5RE', 'R6SE', 'R60S', 'R5MI', 'R5RE']

        # Types of FCAS constraints
        fcas_constraints = ['JOINT_RAMP_UP', 'JOINT_RAMP_DOWN', 'JOINT_CAPACITY_UP', 'JOINT_CAPACITY_DOWN',
                            'JOINT_REGULATING_UP', 'JOINT_REGULATING_DOWN']

        for c in fcas_constraints:
            print('\n--------------------')
            print(c)
            print('--------------------')
            for t in fcas_types:
                try:
                    print(m.__getattribute__(c)[trader_id, t].expr)
                except:
                    pass

    def check_interconnector_solution(self, m):
        """Fix interconnector solution to observed values"""

        fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(nrows=3, ncols=2)

        # Fix solution for each interconnector
        for i, j in zip(m.S_INTERCONNECTORS, [ax1, ax2, ax3, ax4, ax5, ax6]):
            observed_flow = self.data.get_interconnector_solution_attribute(i, 'Flow')
            model_flow = m.V_GC_INTERCONNECTOR[i].value

            # Interconnector limits
            min_flow = self.data.get_interconnector_period_attribute(i, 'LowerLimit')
            max_flow = self.data.get_interconnector_period_attribute(i, 'UpperLimit')

            j.scatter([model_flow], [observed_flow])
            j.plot([-min_flow, max_flow], [-min_flow, max_flow], linewidth=0.9, linestyle='--', alpha=0.8)
            j.set_title(i)

        plt.show()

        return m


def check_solution(model):
    """Check model solution"""

    # Check solution
    enof = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'ENOF', 'EnergyTarget')
    ldof = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'LDOF', 'EnergyTarget')

    r6se = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R6SE', 'R6Target')
    r60s = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R60S', 'R60Target')
    r5mi = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R5MI', 'R5Target')
    r5reg = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'R5RE', 'R5RegTarget')

    l6se = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L6SE', 'L6Target')
    l60s = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L60S', 'L60Target')
    l5mi = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L5MI', 'L5Target')
    l5reg = analysis.check_energy_solution(model, 'V_TRADER_TOTAL_OFFER', 'L5RE', 'L5RegTarget')

    # Scheduled units
    scheduled_traders = analysis.get_scheduled_traders()

    # Filter scheduled generators and loads
    enof_scheduled = enof.loc[enof.index.intersection(scheduled_traders), :]
    ldof_scheduled = ldof.loc[ldof.index.intersection(scheduled_traders), :]

    # Write generic constraints
    nemde.save_generic_constraints(model)

    # Combine into single DataFrame
    duid = 'JBUTTERS'
    analysis.check_trader_solution(model, duid)
    analysis.print_fcas_constraints(model, duid)

    # Check interconnector solution
    analysis.check_interconnector_solution(model)

    def sa_v_loss(flow):
        """Loss equation for V-SA interconnector"""
        vic_demand = nemde.data.get_region_period_attribute('VIC1', 'DemandForecast')
        sa_demand = nemde.data.get_region_period_attribute('SA1', 'DemandForecast')
        return (0.0138 + (1.3598E-06 * vic_demand) + (-1.3290E-05 * sa_demand)) * flow + (1.4761E-04 * (flow ** 2))

    interconnectors = ['N-Q-MNSP1', 'NSW1-QLD1', 'T-V-MNSP1', 'V-S-MNSP1', 'V-SA', 'VIC1-NSW1']
    total_loss = sum(nemde.data.get_interconnector_solution_attribute(i, 'Losses') for i in interconnectors)

    gen_surplus = enof['difference'].sum()
    load_surplus = ldof['difference'].sum()

    x = [i[1] for i in model.P_LOSS_MODEL_BREAKPOINTS_X.items() if i[0][0] == 'V-S-MNSP1']
    y = [i[1] for i in model.P_LOSS_MODEL_BREAKPOINTS_Y.items() if i[0][0] == 'V-S-MNSP1']

    print('V-S-MNSP1 solution loss', nemde.data.get_interconnector_solution_attribute('V-S-MNSP1', 'Losses'))
    print('V-S-MNSP1 model loss', model.V_LOSS['V-S-MNSP1'].value)

    print('V-S-MNSP1 solution flow', nemde.data.get_interconnector_solution_attribute('V-S-MNSP1', 'Flow'))
    print('V-S-MNSP1 model flow', model.V_GC_INTERCONNECTOR['V-S-MNSP1'].value)

    fig, ax = plt.subplots()
    ax.plot(x, y)
    plt.show()

    interconnector_loss_solution = {i: nemde.data.get_interconnector_solution_attribute(i, 'Losses')
                                    for i in model.S_INTERCONNECTORS}

    interconnector_flow_solution = {i: nemde.data.get_interconnector_solution_attribute(i, 'Flow')
                                    for i in model.S_INTERCONNECTORS}

