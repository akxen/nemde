"""Solver-free tests for the fast-start inflexibility-profile maths.

fast_start.py is pure arithmetic over the AEMO inflexibility profile (T1-T4), with
no model coupling, so every case here is a hand-computed expectation.

The profile: a unit spends T1 minutes synchronising at zero output, T2 minutes on
a fixed ramp to its minimum loading level, T3 minutes at or above min loading, and
T4 minutes shutting down. Dispatch intervals are 5 minutes.
"""

import pytest

from nemde.fast_start import (
    get_inflexibility_profile_cumulative_time,
    get_mode_endpoints,
    get_mode_one_ramping_capability,
    get_mode_two_initial_mw,
    get_mode_two_ramping_capability,
    get_target_mode,
    get_target_mode_time,
)

# A representative profile: 2 min synchronising, 4 min to min loading, then 3 and 2.
T1, T2, T3, T4 = 2, 4, 3, 2
MIN_LOADING = 40.0
RAMP_RATE = 120.0  # MW/h -> 2 MW/min


class TestModeEndpoints:
    def test_endpoints_are_cumulative(self):
        assert get_mode_endpoints(T1, T2, T3, T4) == (2, 6, 9, 11)

    def test_zero_length_modes_collapse(self):
        assert get_mode_endpoints(0, 0, 0, 0) == (0, 0, 0, 0)


class TestCumulativeTime:
    @pytest.mark.parametrize(
        ("mode", "mode_time", "expected"),
        [
            (0, 3, 3),  # mode 0: not yet on the profile, time passes through
            (1, 1, 1),  # mode 1: still within T1
            (2, 1, 3),  # mode 2: T1 elapsed, plus 1 minute into T2
            (3, 2, 8),  # mode 3: T1 + T2 elapsed, plus 2
            (4, 1, 10),  # mode 4: T1 + T2 + T3 elapsed, plus 1
        ],
    )
    def test_offsets_by_the_preceding_modes(self, mode, mode_time, expected):
        assert get_inflexibility_profile_cumulative_time(mode, mode_time, T1, T2, T3) == expected

    def test_unknown_mode_raises(self):
        with pytest.raises(Exception, match="Unhandled case"):
            get_inflexibility_profile_cumulative_time(5, 0, T1, T2, T3)


class TestModeOneRampingCapability:
    def test_whole_interval_spent_synchronising_gives_no_capability(self):
        # current_mode_time=0 with T1=5: the unit is at zero output for the whole
        # 5-minute interval, so it can reach nothing.
        assert get_mode_one_ramping_capability(5, T2, MIN_LOADING, 0, RAMP_RATE) == 0.0

    def test_partial_t1_then_fixed_trajectory(self):
        # 1 minute of T1 left, so 4 minutes on the T2 trajectory. T2 is 4 minutes
        # long, so the unit reaches exactly min loading and no further.
        assert get_mode_one_ramping_capability(T1, T2, MIN_LOADING, 1, RAMP_RATE) == pytest.approx(
            MIN_LOADING
        )

    def test_time_above_min_loading_ramps_at_the_effective_rate(self):
        # T1=1 (already elapsed), T2=2: 1 min of trajectory... then 2 min free ramping.
        # trajectory: (40/2)*2 = 40; free ramp: (120/60)*2 = 4 MW.
        assert get_mode_one_ramping_capability(1, 2, MIN_LOADING, 0, RAMP_RATE) == pytest.approx(
            44.0
        )

    def test_zero_t2_jumps_straight_to_min_loading(self):
        # T2=0 means no fixed trajectory: the unit is at min loading as soon as
        # synchronisation completes, then ramps freely for the rest of the interval.
        assert get_mode_one_ramping_capability(1, 0, MIN_LOADING, 0, RAMP_RATE) == pytest.approx(
            MIN_LOADING + (RAMP_RATE / 60) * 4
        )


class TestModeTwoRampingCapability:
    def test_remaining_trajectory_plus_free_ramp(self):
        # 2 of T2's 4 minutes elapsed: 2 minutes of trajectory reaching (40/4)*2 = 20 MW,
        # then 3 minutes of free ramping at 2 MW/min = 6 MW.
        assert get_mode_two_ramping_capability(T2, MIN_LOADING, 2, RAMP_RATE) == pytest.approx(26.0)

    def test_trajectory_longer_than_the_interval(self):
        # T2=10 with 0 elapsed: the whole 5-minute interval is on the trajectory,
        # reaching (40/10)*10 = 40 -- the formula uses time *remaining*, not elapsed.
        assert get_mode_two_ramping_capability(10, MIN_LOADING, 0, RAMP_RATE) == pytest.approx(40.0)

    def test_zero_t2_is_min_loading_plus_a_full_interval_of_ramping(self):
        assert get_mode_two_ramping_capability(0, MIN_LOADING, 0, RAMP_RATE) == pytest.approx(
            MIN_LOADING + (RAMP_RATE / 60) * 5
        )


class TestModeTwoInitialMw:
    def test_position_on_the_fixed_trajectory(self):
        # Halfway through a 4-minute T2 means halfway to min loading.
        assert get_mode_two_initial_mw(T2, MIN_LOADING, 2) == pytest.approx(20.0)

    def test_start_of_trajectory_is_zero(self):
        assert get_mode_two_initial_mw(T2, MIN_LOADING, 0) == 0.0

    def test_end_of_trajectory_is_min_loading(self):
        assert get_mode_two_initial_mw(T2, MIN_LOADING, T2) == pytest.approx(MIN_LOADING)


class TestTargetMode:
    def test_mode_zero_stays_zero(self):
        # A unit not on the profile does not join it just because time passed.
        assert get_target_mode(0, 0, T1, T2, T3, T4) == 0

    @pytest.mark.parametrize(
        ("mode", "mode_time", "expected"),
        [
            (1, 0, 2),  # 0 + 5 = 5 minutes: past T1 (2), inside T2 (6)
            (2, 0, 3),  # 2 + 5 = 7: past T2 (6), inside T3 (9)
            (3, 0, 4),  # 6 + 5 = 11: past T3 (9), at T4 end (11)
            (4, 0, 4),  # 9 + 5 = 14: beyond the profile, stays in mode 4
        ],
    )
    def test_advances_five_minutes_along_the_profile(self, mode, mode_time, expected):
        assert get_target_mode(mode, mode_time, T1, T2, T3, T4) == expected

    def test_long_t1_keeps_the_unit_in_mode_one(self):
        assert get_target_mode(1, 0, 10, T2, T3, T4) == 1


class TestTargetModeTime:
    def test_mode_zero_time_passes_through(self):
        assert get_target_mode_time(0, 3, T1, T2, T3, T4) == 3

    def test_time_is_measured_from_the_start_of_the_target_mode(self):
        # From mode 1 t=0, the interval ends 5 minutes in: past T1's end at 2,
        # so mode 2 with 5 - 2 = 3 minutes elapsed in that mode.
        assert get_target_mode(1, 0, T1, T2, T3, T4) == 2
        assert get_target_mode_time(1, 0, T1, T2, T3, T4) == 3

    def test_staying_within_mode_one_just_adds_the_interval(self):
        assert get_target_mode_time(1, 1, 10, T2, T3, T4) == 6

    def test_beyond_the_profile_keeps_counting_from_t3_end(self):
        # mode 4, t=0 -> cumulative 9 + 5 = 14, measured from T3's end (9) = 5.
        assert get_target_mode_time(4, 0, T1, T2, T3, T4) == 5
