"""Visualise FCAS constraints and use methods to abstract constraint generation process"""

import os

import numpy as np

import matplotlib.pyplot as plt

from data import NEMDEDataHandler
from data import MMSDMDataHandler


class FCASHandler:
    def __init__(self, data_dir):
        # Object used to extract NEMDE input information
        self.data = NEMDEDataHandler(data_dir)

    def get_fcas_trapezium_offer(self, trader_id, trade_type):
        """Get FCAS trapezium offer for a given trader and trade type"""

        # Trapezium information
        enablement_min = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMin')
        enablement_max = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMax')
        low_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'LowBreakpoint')
        high_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'HighBreakpoint')
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

        # Store FCAS trapezium information in a dictionary
        trapezium = {'enablement_min': enablement_min, 'enablement_max': enablement_max, 'max_available': max_available,
                     'low_breakpoint': low_breakpoint, 'high_breakpoint': high_breakpoint}

        return trapezium

    @staticmethod
    def get_new_breakpoint(slope, x_intercept, max_available):
        """Compute new (lower/upper) breakpoint"""

        # Y-axis intercept
        y_intercept = -slope * x_intercept

        return (max_available - y_intercept) / slope

    def get_scaled_fcas_trapezium_agc_enablement_limits(self, trader_id, trapezium):
        """Compute scaled FCAS trapezium - taking into account AGC enablement limits"""

        # Input FCAS trapezium
        trap = dict(trapezium)

        # AGC enablement limits
        try:
            agc_enablement_min = self.data.get_trader_initial_condition_attribute(trader_id, 'LMW')
        except:
            agc_enablement_min = None

        try:
            agc_enablement_max = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')
        except:
            agc_enablement_max = None

        if (agc_enablement_min is not None) and (agc_enablement_min > trap['enablement_min']):
            try:
                slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
                trap['low_breakpoint'] = self.get_new_breakpoint(slope, agc_enablement_min, trap['max_available'])
            except ZeroDivisionError:
                trap['low_breakpoint'] = agc_enablement_min
            trap['enablement_min'] = agc_enablement_min

        if (agc_enablement_max is not None) and (agc_enablement_max < trap['enablement_max']):
            try:
                slope = -trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
                trap['high_breakpoint'] = self.get_new_breakpoint(slope, agc_enablement_max, trap['max_available'])
            except ZeroDivisionError:
                trap['high_breakpoint'] = agc_enablement_max
            trap['enablement_max'] = agc_enablement_max

        return trap

    def get_scaled_fcas_trapezium_agc_ramp_rates(self, trader_id, trade_type, trapezium):
        """FCAS trapezium taking into account AGC ramp rates"""

        # Input FCAS trapezium
        trap = dict(trapezium)

        # AGC up and down ramp rates
        if trade_type == 'R5RE':
            try:
                agc_ramp = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate')
            except:
                return trap
        elif trade_type == 'L5RE':
            try:
                agc_ramp = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampDnRate')
            except:
                return trap
        else:
            raise Exception(f'Unexpected trade type: {trade_type}')

        # Max available
        max_available = min(trap['max_available'], agc_ramp / 12)

        if max_available < trap['max_available']:
            # Low breakpoint calculation
            try:
                slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
                trap['low_breakpoint'] = self.get_new_breakpoint(slope, trap['enablement_min'], max_available)
            except ZeroDivisionError:
                pass

            # High breakpoint calculation
            try:
                slope = -trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
                trap['high_breakpoint'] = self.get_new_breakpoint(slope, trap['enablement_max'], max_available)
            except ZeroDivisionError:
                pass

        # Update max available
        trap['max_available'] = max_available

        return trap

    def get_scaled_fcas_trapezium_uigf(self, trader_id, trapezium):
        """Trapezium scaling for semi-scheduled units"""

        # Input FCAS trapezium
        trap = dict(trapezium)

        # Try and get UIGF value if it exists for a given unit (only will exist for semi-scheduled units)
        try:
            uigf = self.data.get_trader_period_attribute(trader_id, 'UIGF')
        except TypeError:
            return trap

        if uigf < trap['enablement_max']:
            # High breakpoint calculation
            try:
                slope = -trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
                trap['high_breakpoint'] = self.get_new_breakpoint(slope, trap['enablement_max'], uigf)
            except ZeroDivisionError:
                pass

            # Update enablement max
            trap['enablement_max'] = uigf

        return trap

    def get_energy_target_solution(self, trader_id):
        """Get energy target from SPD outputs"""

        return self.data.get_trader_solution_attribute(trader_id, 'EnergyTarget')

    def get_fcas_solution(self, trader_id, trade_type):
        """Get FCAS solution"""

        # Map between names used in trader period to define offers and solution output
        name_map = {'R6SE': 'R6Target', 'R5RE': 'R5RegTarget'}

        return self.data.get_trader_solution_attribute(trader_id, name_map[trade_type])

    def plot_fcas_solution(self, trader_id, trade_type):
        """Plot FCAS solution"""

        # FCAS trapezium
        offer = fcas.get_fcas_trapezium_offer(trader_id, trade_type)

        # Energy and FCAS targets
        energy_target = self.get_energy_target_solution(trader_id)
        fcas_target = self.get_fcas_solution(trader_id, trade_type)

        # Initialise figure
        fig, ax = plt.subplots()

        # FCAS offer trapezium
        x = [offer['enablement_min'], offer['low_breakpoint'], offer['high_breakpoint'], offer['enablement_max']]
        y = [0, offer['max_available'], offer['max_available'], 0]
        ax.plot(x, y)

        # Energy target
        ax.plot([energy_target, energy_target], [0, offer['max_available']], color='r')

        # FCAS target
        ax.plot([offer['enablement_min'], offer['enablement_max']], [fcas_target, fcas_target], color='k',
                linestyle='--')

        # Joint capacity constraint
        # ax.plot([offer['high_breakpoint'] - 5, offer['enablement_max'] - 5], [offer['max_available'], 0], color='g')

        return ax

    @staticmethod
    def plot_fcas(*args):
        """Plot FCAS trapeziums"""

        # Initialise figure
        fig, ax = plt.subplots()

        for arg in args:
            # FCAS offer trapezium
            x = [arg['enablement_min'], arg['low_breakpoint'], arg['high_breakpoint'], arg['enablement_max']]
            y = [0, arg['max_available'], arg['max_available'], 0]
            ax.plot(x, y)

        return ax


if __name__ == '__main__':
    # Root directory containing NEMDE and MMSDM files
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to parse NEMDE file
    nemde_data = NEMDEDataHandler(data_directory)
    mmsdm_data = MMSDMDataHandler(data_directory)
    fcas = FCASHandler(data_directory)

    # Load interval
    fcas.data.load_interval(2019, 10, 10, 1)

    # # g, o = 'BW01', 'R5RE'
    # # g, o = 'GSTONE2', 'R5RE'
    # g, o = 'HPRG1', 'R5RE'
    #
    # # Plot FCAS solution
    # t1 = fcas.get_fcas_trapezium_offer(g, o)
    # t2 = fcas.get_scaled_fcas_trapezium_agc_enablement_limits(g, t1)
    # t3 = fcas.get_scaled_fcas_trapezium_agc_ramp_rates(g, o, t2)
    # t4 = fcas.get_scaled_fcas_trapezium_uigf(g, t3)
    #
    # fcas.plot_fcas(t1, t2, t3, t4)
    # plt.show()

    for i, j in fcas.data.get_trader_offer_index():
        try:
            if j in ['R5RE', 'L5RE']:
                t1 = fcas.get_fcas_trapezium_offer(i, j)
                t2 = fcas.get_scaled_fcas_trapezium_agc_enablement_limits(i, t1)
                t3 = fcas.get_scaled_fcas_trapezium_agc_ramp_rates(i, j, t2)
                t4 = fcas.get_scaled_fcas_trapezium_uigf(i, t3)

                ax = fcas.plot_fcas(t1, t2, t3, t4)
                ax.set_title(f'{i} - {j}')
                plt.show()
        except Exception as e:
            print(i, j, e)

# BW01 R5RE
# HPRG1 - R5RE
