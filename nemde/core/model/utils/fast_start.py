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


def get_inflexibility_profile_cumulative_time(current_mode, current_mode_time, t1, t2, t3):
    """Get number of minutes from start of inflexibility profile"""

    if current_mode == 0:
        return current_mode_time
    elif current_mode == 1:
        return current_mode_time
    elif current_mode == 2:
        return t1 + current_mode_time
    elif current_mode == 3:
        return t1 + t2 + current_mode_time
    elif current_mode == 4:
        return t1 + t2 + t3 + current_mode_time
    else:
        raise Exception('Unhandled case:', current_mode, current_mode_time, t1, t2, t3)


def get_mode_endpoints(t1, t2, t3, t4):
    """Compute cumulative time in inflexibility profile for each mode endpoint"""

    # Time interval endpoints
    t1_end = t1
    t2_end = t1 + t2
    t3_end = t1 + t2 + t3
    t4_end = t1 + t2 + t3 + t4

    return t1_end, t2_end, t3_end, t4_end


def get_target_mode(current_mode, current_mode_time, t1, t2, t3, t4):
    """Get target fast start mode at END of interval"""

    # Get cumulative time corresponding to point at end of dispatch interval
    minutes = get_inflexibility_profile_cumulative_time(
        current_mode=current_mode, current_mode_time=current_mode_time + 5,
        t1=t1, t2=t2, t3=t3)

    # Fast start mode time endpoints
    t1_end, t2_end, t3_end, t4_end = get_mode_endpoints(t1=t1, t2=t2, t3=t3, t4=t4)

    if current_mode == 0:
        return 0
    elif minutes <= t1_end:
        return 1
    elif (minutes > t1_end) and (minutes <= t2_end):
        return 2
    elif (minutes > t2_end) and (minutes <= t3_end):
        return 3
    elif (minutes > t3_end) and (minutes <= t4_end):
        return 4
    elif minutes > t4_end:
        return 4
    else:
        raise Exception('Unhandled case:', minutes, t1_end, t2_end, t3_end, t4_end)


def get_target_mode_time(current_mode, current_mode_time, t1, t2, t3, t4):
    """Get target mode time"""

    # Compute target mode
    target_mode = get_target_mode(
        current_mode=current_mode, current_mode_time=current_mode_time,
        t1=t1, t2=t2, t3=t3, t4=t4)

    # Cumulative minutes unit on inflexibility profile at end of interval
    cumulative_minutes = get_inflexibility_profile_cumulative_time(
        current_mode=current_mode, current_mode_time=current_mode_time + 5,
        t1=t1, t2=t2, t3=t3)

    # Interval endpoints
    t1_end, t2_end, t3_end, t4_end = get_mode_endpoints(t1=t1, t2=t2, t3=t3, t4=t4)

    # Get effective time based on target mode and time interval endpoints
    if target_mode == 0:
        return current_mode_time
    elif target_mode == 1:
        return cumulative_minutes
    elif target_mode == 2:
        return cumulative_minutes - t1_end
    elif target_mode == 3:
        return cumulative_minutes - t2_end
    elif target_mode == 4:
        return cumulative_minutes - t3_end
    else:
        raise Exception('Unhandled case:', target_mode)
