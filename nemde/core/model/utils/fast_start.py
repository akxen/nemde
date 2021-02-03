"""
Fast start unit calculations
"""


def get_mode_one_ramping_capability(t1, t2, min_loading, current_mode_time, effective_ramp_rate):
    """
    Determine max ramping capability for fast start unit if it is initially
    in mode 1
    """

    # Output fixed to 0 for this amount of time over dispatch interval
    # t1_time_remaining = m.P_TRADER_T1[i] - \
    # m.P_TRADER_CURRENT_MODE_TIME[i]

    t1_time_remaining = t1 - current_mode_time

    # Time unit follows fixed startup trajectory over interval
    # t2_time = max(0, min(m.P_TRADER_T2[i], 5 - t1_time_remaining))
    t2_time = max(0, min(t2, 5 - t1_time_remaining))

    # Time unit above min loading over interval
    min_loading_time = max([0, 5 - t1_time_remaining - t2_time])

    # If T2=0 then unit immediately operates at min loading after synchronisation complete
    # if m.P_TRADER_T2[i] == 0:
    # t2_ramp_capability = m.P_TRADER_MIN_LOADING_MW[i]

    if t2 == 0:
        t2_ramp_capability = min_loading

    # Else unit must follow fixed startup trajectory for
    else:
        # t2_ramp_capability = (
        # m.P_TRADER_MIN_LOADING_MW[i] / m.P_TRADER_T2[i]) * t2_time

        t2_ramp_capability = (min_loading / t2) * t2_time

    # Ramping capability for T3 and beyond
    t3_ramp_capability = (effective_ramp_rate / 60) * min_loading_time

    # Total ramp up capability
    ramp_up_capability = t2_ramp_capability + t3_ramp_capability

    return ramp_up_capability
