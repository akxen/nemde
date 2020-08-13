"""Visualise FCAS constraints and use methods to abstract constraint generation process"""

import os

import numpy as np

import matplotlib.pyplot as plt

try:
    from data import NEMDEDataHandler
    from data import MMSDMDataHandler
except ImportError:
    from .data import NEMDEDataHandler
    from .data import MMSDMDataHandler


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
        try:
            y_intercept = -slope * x_intercept
            return (max_available - y_intercept) / slope

        # If line is vertical or horizontal, return original x-intercept
        except (TypeError, ZeroDivisionError):
            return x_intercept

    @staticmethod
    def get_line_from_points(p_1, p_2):
        """Compute slope and intercept given two points"""

        try:
            slope = (p_2[1] - p_1[1]) / (p_2[0] - p_1[0])
            y_intercept = p_1[1] - (slope * p_1[0])
        except ZeroDivisionError:
            slope = None
            y_intercept = None

        # Compute intercept using slope and point 1
        try:
            x_intercept = (p_1[1] - y_intercept) / slope
        except TypeError:
            x_intercept = p_1[0]

        return {'slope': slope, 'y_intercept': y_intercept, 'x_intercept': x_intercept}

    @staticmethod
    def get_line_from_slope_and_x_intercept(slope, x_intercept):
        """Define line by its slope and x-intercept"""

        # y-intercept - set to None if slope undefined
        try:
            y_intercept = -slope * x_intercept
        except TypeError:
            y_intercept = None

        return {'slope': slope, 'y_intercept': y_intercept, 'x_intercept': x_intercept}

    @staticmethod
    def get_intersection(line_1, line_2):
        """Get point of intersection between two lines"""

        # Case 0 - both lines are horizontal
        if (line_1['slope'] == 0) and (line_2['slope'] == 0):
            return None

        # Case 1 - both slopes are defined
        if (line_1['slope'] is not None) and (line_2['slope'] is not None):
            x = (line_2['y_intercept'] - line_1['y_intercept']) / (line_1['slope'] - line_2['slope'])
            y = (line_1['slope'] * x) + line_1['y_intercept']
            return x, y

        # Case 2 - line 1's slope is undefined, line 2's slope is defined
        elif (line_1['slope'] is None) and (line_2['slope'] is not None):
            x = line_1['x_intercept']
            y = (line_2['slope'] * x) + line_2['y_intercept']
            return x, y

        # Case 3 - line 1's slope is defined, line 2's slope is undefined
        elif (line_1['slope'] is not None) and (line_2['slope'] is None):
            x = line_2['x_intercept']
            y = (line_1['slope'] * x) + line_1['y_intercept']
            return x, y

        # Case 4 - both lines have undefined slopes - lines are either coincident or never intersect
        elif (line_1['slope'] is None) and (line_2['slope'] is None):
            return None

        else:
            raise Exception('Unhandled case')

    def get_scaled_fcas_trapezium_agc_enablement_limits_lhs(self, trader_id, trapezium):
        """Compute scaled FCAS trapezium - taking into account minimum AGC enablement limit"""

        # Input FCAS trapezium
        trap = dict(trapezium)

        # AGC enablement limits
        try:
            agc_enablement_min = self.data.get_trader_initial_condition_attribute(trader_id, 'LMW')
        except:
            agc_enablement_min = None

        if (agc_enablement_min is not None) and (agc_enablement_min > trap['enablement_min']):
            # Compute slope between enablement min and lower breakpoint
            try:
                lhs_slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
            except ZeroDivisionError:
                lhs_slope = None

            # Compute slope between high breakpoint and enablement max
            try:
                rhs_slope = - trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
            except ZeroDivisionError:
                rhs_slope = None

            # LHS line with new min enablement limit
            lhs_line = self.get_line_from_slope_and_x_intercept(lhs_slope, agc_enablement_min)

            # RHS line (original)
            rhs_line = self.get_line_from_slope_and_x_intercept(rhs_slope, trap['enablement_max'])

            # Intersection between LHS and RHS lines
            intersection = self.get_intersection(lhs_line, rhs_line)

            # Update max available if required
            if intersection[1] < trap['max_available']:
                trap['max_available'] = intersection[1]

            # New low breakpoint
            trap['low_breakpoint'] = self.get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'],
                                                             trap['max_available'])

            # New high breakpoint
            trap['high_breakpoint'] = self.get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'],
                                                              trap['max_available'])

            # Update enablement min
            trap['enablement_min'] = agc_enablement_min

        return trap

    def get_scaled_fcas_trapezium_agc_enablement_limits_rhs(self, trader_id, trapezium):
        """Compute scaled FCAS trapezium - taking into account minimum AGC enablement limit"""

        # Input FCAS trapezium
        trap = dict(trapezium)

        # AGC enablement limits
        try:
            agc_enablement_max = self.data.get_trader_initial_condition_attribute(trader_id, 'HMW')
        except:
            agc_enablement_max = None

        if (agc_enablement_max is not None) and (agc_enablement_max < trap['enablement_max']):
            # Compute slope between enablement min and lower breakpoint
            try:
                lhs_slope = trap['max_available'] / (trap['low_breakpoint'] - trap['enablement_min'])
            except ZeroDivisionError:
                lhs_slope = None

            # Compute slope between high breakpoint and enablement max
            try:
                rhs_slope = - trap['max_available'] / (trap['enablement_max'] - trap['high_breakpoint'])
            except ZeroDivisionError:
                rhs_slope = None

            # LHS line (original)
            lhs_line = self.get_line_from_slope_and_x_intercept(lhs_slope, trap['enablement_min'])

            # RHS line with new min enablement limit
            rhs_line = self.get_line_from_slope_and_x_intercept(rhs_slope, agc_enablement_max)

            # Intersection between LHS and RHS lines
            intersection = self.get_intersection(lhs_line, rhs_line)

            # Update max available if required
            if (intersection is not None) and (intersection[1] < trap['max_available']):
                trap['max_available'] = intersection[1]

            # New low breakpoint
            trap['low_breakpoint'] = self.get_new_breakpoint(lhs_line['slope'], lhs_line['x_intercept'],
                                                             trap['max_available'])

            # New high breakpoint
            trap['high_breakpoint'] = self.get_new_breakpoint(rhs_line['slope'], rhs_line['x_intercept'],
                                                              trap['max_available'])

            # Update enablement min
            trap['enablement_max'] = agc_enablement_max

        return trap

    def get_scaled_fcas_trapezium_agc_enablement_limits(self, trader_id, trapezium):
        """Compute scaled FCAS trapezium - taking into account AGC enablement limits"""

        # Input FCAS trapezium
        trap = dict(trapezium)

        # Scale trapezium LHS and RHS
        trap = self.get_scaled_fcas_trapezium_agc_enablement_limits_lhs(trader_id, trap)
        trap = self.get_scaled_fcas_trapezium_agc_enablement_limits_rhs(trader_id, trap)

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
        # name_map = {'R6SE': 'R6Target', 'R5RE': 'R5RegTarget', 'L5RE': 'L5RegTarget'}
        name_map = {'R6SE': 'R6Target', 'R60S': 'R60Target', 'R5MI': 'R5Target', 'R5RE': 'R5RegTarget',
                    'L6SE': 'L6Target', 'L60S': 'L60Target', 'L5MI': 'L5Target', 'L5RE': 'L5RegTarget',
                    'ENOF': 'EnergyTarget', 'LDOF': 'EnergyTarget'}

        return self.data.get_trader_solution_attribute(trader_id, name_map[trade_type])

    def plot_fcas_solution(self, trader_id, trade_type, ax=None):
        """Plot FCAS solution"""

        # FCAS trapezium
        if trade_type in ['R5RE', 'L5RE']:
            offer = self.get_scaled_fcas_trapezium(trader_id, trade_type)
        else:
            offer = self.get_fcas_trapezium_offer(trader_id, trade_type)

        # Energy and FCAS targets
        energy_target = self.get_energy_target_solution(trader_id)
        fcas_target = self.get_fcas_solution(trader_id, trade_type)

        # Initialise figure
        if ax is None:
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

    def plot_fcas_solution2(self, trader_id, trade_type, ax):
        """Plot FCAS solution over FCAS trapezium"""

        # FCAS trapezium
        trapezium = self.get_fcas_trapezium_offer(trader_id, trade_type)

        # FCAS and energy targets
        fcas_target = self.get_fcas_solution(trader_id, trade_type)
        energy_target = self.get_energy_target_solution(trader_id)

        x_min, x_max = trapezium['enablement_min'], trapezium['enablement_max']
        y_min, y_max = 0, trapezium['max_available'] + 1

        # Plot energy and FCAS target
        ax.plot([x_min, x_max], [fcas_target, fcas_target], color='r', linestyle='--')
        ax.plot([energy_target, energy_target], [y_min, y_max], color='b', linestyle='--')

        return ax

    def get_scaled_fcas_trapezium(self, trader_id, trade_type):
        """Get scaled FCAS trapezium"""

        # Get unscaled FCAS offer
        trapezium_1 = dict(self.get_fcas_trapezium_offer(trader_id, trade_type))

        assert trade_type in ['R5RE', 'L5RE'], Exception(f'{trade_type}: can only scale regulating FCAS trapeziums')

        # Only scale regulating FCAS offers
        trapezium_2 = self.get_scaled_fcas_trapezium_agc_enablement_limits(trader_id, trapezium_1)
        trapezium_3 = self.get_scaled_fcas_trapezium_agc_ramp_rates(trader_id, trade_type, trapezium_2)
        trapezium_4 = self.get_scaled_fcas_trapezium_uigf(trader_id, trapezium_3)

        return trapezium_4

    def check_regulating_fcas(self, trader_id, trade_type):
        """Check regulating FCAS plot"""
        
        if trade_type not in ['L5RE', 'R5RE']:
            raise Exception('Can only check regulating FCAS offer')

        # Scale FCAS trapezium
        t1 = self.get_fcas_trapezium_offer(trader_id, trade_type)
        t2 = self.get_scaled_fcas_trapezium_agc_enablement_limits(trader_id, t1)
        t3 = self.get_scaled_fcas_trapezium_agc_ramp_rates(trader_id, trade_type, t2)
        t4 = self.get_scaled_fcas_trapezium_uigf(trader_id, t3)

        # Create plot
        ax = self.plot_fcas(t1, t2, t3, t4)
        ax = self.plot_fcas_solution2(trader_id, trade_type, ax)
        ax.set_title(f'{trader_id} - {trade_type}')
        plt.show()

    def check_regulating_fcas_plots(self):
        """Check FCAS trapezium scaling and corresponding energy / FCAS target solutions"""

        for i, j in self.data.get_trader_offer_index():
            try:
                if j in ['R5RE', 'L5RE']:
                # if (j in ['R5RE']) and (i in ['DEVILS_G']):
                    t1 = self.get_fcas_trapezium_offer(i, j)
                    t2 = self.get_scaled_fcas_trapezium_agc_enablement_limits(i, t1)
                    t3 = self.get_scaled_fcas_trapezium_agc_ramp_rates(i, j, t2)
                    t4 = self.get_scaled_fcas_trapezium_uigf(i, t3)

                    ax = self.plot_fcas(t1, t2, t3, t4)
                    ax = self.plot_fcas_solution2(i, j, ax)
                    ax.set_title(f'{i} - {j}')
                    plt.show()
            except Exception as e:
                print(i, j, e)


if __name__ == '__main__':
    # Root directory containing NEMDE and MMSDM files
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to parse NEMDE file
    nemde_data = NEMDEDataHandler(data_directory)
    mmsdm_data = MMSDMDataHandler(data_directory)
    fcas = FCASHandler(data_directory)

    # Load interval
    fcas.data.load_interval(2019, 10, 10, 1)

    # Scaled FCAS trapezium
    scaled_trapezium = fcas.get_scaled_fcas_trapezium('BW01', 'R5RE')

    # Check regulated FCAS plots (evaluate scaling procedure)
    # fcas.check_regulating_fcas_plots()

    # fcas.check_regulating_fcas('POAT220', 'R5RE')
    fcas.check_regulating_fcas('TORRA4', 'R5RE')
