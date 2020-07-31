"""Visualise NEMDE solution, in particulat FCAS constraints"""


class Visualisation:
    def __init__(self):
        pass

    def plot_fcas_trapezium_offer(self, trader_id, trade_type):
        """Plot offered FCAS trapezium"""
        pass

    @staticmethod
    def add_line(ax, m, c, inequality):
        """Plot a line given the slope and intercept. Add shaded area to indicate infeasible region."""
        pass

    def get_joint_capacity_constraint_up(self):
        """Plot joint capacity up constraint"""
        pass

    def get_joint_capacity_constraint_down(self):
        """Get joint capacity down constraint"""
        pass

    def get_joint_energy_regulating_constraint_up(self):
        """Get joint energy and regulating FCAS constraint (up)"""
        pass

    def get_joint_energy_regulating_constraint_down(self):
        """Get joint energy and regulating FCAS constraint (up)"""
        pass

    def plot_feasible_area(self):
        """Plot the FCAS offer trapezium. Scale it"""