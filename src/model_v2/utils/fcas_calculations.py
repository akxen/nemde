"""Compute max availability for each service"""


def get_effective_rreg_max_available(data, trader_id):
    """Get effective R5RE max available"""
    pass


def get_effective_rreg_enablement_max(data, trader_id):
    """Get effective R5RE enablement max"""
    pass


def get_effective_rreg_enablement_min(data, trader_id):
    """Get effective R5RE enablement min"""
    pass


def get_effective_lreg_max_available(data, trader_id):
    """Get effective L5RE max available"""
    pass


def get_effective_lreg_enablement_max(data, trader_id):
    """Get effective L5RE enablement max"""
    pass


def get_effective_lreg_enablement_min(data, trader_id):
    """Get effective L5RE enablement min"""
    pass


def get_joint_ramp_raise_max(data, trader_id):
    """Get joint ramp raise max term"""
    pass


def get_joint_ramp_lower_min(data, trader_id):
    """Get joint ramp lower min term"""
    pass


def get_lower_slope_coefficient(data, trader_id, trade_type):
    """Get lower slope coefficient"""
    pass


def get_upper_slope_coefficient(data, trader_id, trade_type):
    """Get upper slope coefficient"""
    pass


def get_regulating_raise_availability(data, trader_id):
    """Get regulating raise availability R5RE"""

    max_avail = get_effective_rreg_max_available(data, trader_id)
    enablement_max = get_effective_rreg_enablement_max(data, trader_id)
    enablement_min = get_effective_rreg_enablement_min(data, trader_id)
    upper_slope_coefficient = get_upper_slope_coefficient(data, trader_id, 'R5RE')
    lower_slope_coefficient = get_lower_slope_coefficient(data, trader_id, 'L5RE')
    joint_ramp_raise_max = get_joint_ramp_raise_max(data, trader_id)
    enablement_max_r6 = get_trader_quantity_band_attribute(data, trader_id, '@R6SE')