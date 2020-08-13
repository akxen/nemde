"""NEMDE FCAS calculations"""

import os

import numpy as np

from data2 import NEMDEDataHandler


class FCASCalculations:
    def __init__(self, data_dir):
        # Object used to extract NEMDE input information
        self.data = NEMDEDataHandler(data_dir)

    def get_effective_rreg_fcas_maxavail(self, trader_id):
        """Get effective raise regulation FCAS"""

        # Max available raise regulation FCAS
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, 'R5RE', 'MaxAvail')

        # AGC ramp rate
        agc_ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate') / 12

        return min(max_available, agc_ramp_rate)

    def get_effective_rreg_enablement_max(self, trader_id):
        """Get effective max enablement limit"""

        # Offer enablement max
        offer = self.data.get_trader_quantity_band_attribute(trader_id, 'R5RE', 'EnablementMax')

        # AGC limit
        agc = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')

        return min(offer, agc)

    def get_effective_rreg_enablement_min(self, trader_id):
        """Get effective min enablement limit"""

        # Offer enablement min
        offer = self.data.get_trader_quantity_band_attribute(trader_id, 'R5RE', 'EnablementMin')

        # AGC limit
        agc = self.data.get_trader_initial_condition_attribute(trader_id, 'LMW')

        return max(offer, agc)

    def get_effective_lreg_fcas_maxavail(self, trader_id):
        """Get effective raise regulation FCAS"""

        # Max available raise regulation FCAS
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, 'L5RE', 'MaxAvail')

        # AGC ramp rate
        agc_ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate') / 12

        return min(max_available, agc_ramp_rate)

    def get_effective_lreg_enablement_max(self, trader_id):
        """Get effective max enablement limit"""

        # Offer enablement max
        offer = self.data.get_trader_quantity_band_attribute(trader_id, 'L5RE', 'EnablementMax')

        # AGC limit
        agc = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')

        return min(offer, agc)

    def get_effective_lreg_enablement_min(self, trader_id):
        """Get effective min enablement limit"""

        # Offer enablement min
        offer = self.data.get_trader_quantity_band_attribute(trader_id, 'L5RE', 'EnablementMin')

        # AGC limit
        agc = self.data.get_trader_initial_condition_attribute(trader_id, 'LMW')

        return max(offer, agc)

    def get_joint_ramp_raise_max(self, trader_id):
        """Joint capacity raise limit"""

        # Initial MW at start of dispatch interval
        initial_mw = self.data.get_trader_initial_condition_attribute(trader_id, 'InitialMW')

        # AGC ramp rate
        agc_ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampUpRate') / 12

        return initial_mw + agc_ramp_rate

    def get_joint_ramp_lower_min(self, trader_id):
        """Joint capacity lower limit"""

        # Initial MW at start of dispatch interval
        initial_mw = self.data.get_trader_initial_condition_attribute(trader_id, 'InitialMW')

        # AGC ramp rate
        agc_ramp_rate = self.data.get_trader_initial_condition_attribute(trader_id, 'SCADARampDnRate') / 12

        return initial_mw - agc_ramp_rate

    def get_lower_slope_coefficient(self, trader_id, trade_type):
        """Lower slope coefficient"""

        low_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'LowBreakpoint')
        enablement_min = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMin')
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

        try:
            return (low_breakpoint - enablement_min) / max_available
        except ZeroDivisionError:
            return np.nan

    def get_upper_slope_coefficient(self, trader_id, trade_type):
        """Upper slope coefficient"""

        enablement_max = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'EnablementMax')
        high_breakpoint = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'HighBreakpoint')
        max_available = self.data.get_trader_quantity_band_attribute(trader_id, trade_type, 'MaxAvail')

        try:
            return (enablement_max - high_breakpoint) / max_available
        except ZeroDivisionError:
            return np.nan

    def get_regulating_raise_fcas_availability(self, trader_id):
        """Get max regulating raise FCAS available"""

        effective_rreg_fcas_maxavail = self.get_effective_rreg_fcas_maxavail(trader_id)
        effective_rreg_enablement_max = self.get_effective_rreg_enablement_max(trader_id)
        effective_rreg_enablement_min = self.get_effective_rreg_enablement_min(trader_id)
        rreg_upper_slope_coefficient = self.get_upper_slope_coefficient(trader_id, 'R5RE')
        rreg_lower_slope_coefficient = self.get_lower_slope_coefficient(trader_id, 'R5RE')




if __name__ == '__main__':
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to perform FCAS max availability calculations
    calculations = FCASCalculations(data_directory)
    calculations.data.load_interval(2019, 10, 10, 1)

    rreg_max_available = calculations.get_effective_rreg_fcas_maxavail('BALBG1')
    rreg_max_enablement = calculations.get_effective_rreg_enablement_max('BALBG1')
    rreg_min_enablement = calculations.get_effective_rreg_enablement_min('BALBG1')

    lreg_max_available = calculations.get_effective_lreg_fcas_maxavail('BALBG1')
    lreg_max_enablement = calculations.get_effective_lreg_enablement_max('BALBG1')
    lreg_min_enablement = calculations.get_effective_lreg_enablement_min('BALBG1')

    joint_ramp_raise_max = calculations.get_joint_ramp_raise_max('BALBG1')
    joint_ramp_lower_min = calculations.get_joint_ramp_lower_min('BALBG1')

    lower_slope = calculations.get_lower_slope_coefficient('BALBG1', 'R5RE')
    upper_slope = calculations.get_upper_slope_coefficient('BALBG1', 'R5RE')
