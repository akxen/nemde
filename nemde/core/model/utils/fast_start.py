"""
Fast start unit calculations
"""


def get_mode_one_ramping_capability(t1, t2, min_loading, current_mode_time, effective_ramp_rate):
    """
    Determine max ramping capability for fast start unit if it is initially
    in mode 1
    """

    # Output fixed to 0 for this amount of time over dispatch interval
    t1_time_remaining = t1 - current_mode_time

    # Time unit follows fixed startup trajectory over interval
    t2_time = max(0, min(t2, 5 - t1_time_remaining))

    # Time unit above min loading over interval
    min_loading_time = max([0, 5 - t1_time_remaining - t2_time])

    # Unit immediately transitions to mode 2
    if t2 == 0:
        t2_ramp_capability = min_loading

    # Unit must follow fixed startup trajectory if T2 > 0
    else:
        t2_ramp_capability = (min_loading / t2) * t2_time

    # Ramping capability for T3 and beyond
    t3_ramp_capability = (effective_ramp_rate / 60) * min_loading_time

    # Total ramp up capability over the dispatch interval
    ramp_up_capability = t2_ramp_capability + t3_ramp_capability

    return ramp_up_capability


def get_mode_two_ramping_capability(t2, min_loading, current_mode_time, effective_ramp_rate):
    """Get ramping capability when @CurrentMode = 2"""

    # Amount of time remaining in T2
    t2_time_remaining = t2 - current_mode_time

    # Time unit is above min loading level over the dispatch interval
    min_loading_time = max([0, 5 - t2_time_remaining])

    # If T2=0 then unit immediately operates at min loading after synchronisation complete
    if t2 == 0:
        t2_ramp_capability = min_loading

    # Else unit must follow fixed startup trajectory
    else:
        t2_ramp_capability = (min_loading / t2) * t2_time_remaining

    # Ramping capability for T3 and beyond
    t3_ramp_capability = (effective_ramp_rate / 60) * min_loading_time

    # Total ramp up capability
    ramp_up_capability = t2_ramp_capability + t3_ramp_capability

    return ramp_up_capability


def get_mode_two_initial_mw(t2, min_loading, current_mode_time):
    """
    Get initial MW when unit is in mode two and on fixed startup trajectory

    Note: InitialMW is based on trader's position within the fixed startup
    trajectory for fast-start units. This may differ from the InitialMW
    value reported by SCADA telemetry.
    """

    return (min_loading / t2) * current_mode_time
