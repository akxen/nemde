"""Solver-free unit tests for the FCAS trapezium/availability maths in inputs.py.

Everything here is a pure function of hand-built inputs: no LP solve, no CBC, no
gitignored casefile data, so this module runs in a clean checkout in well under a
second and can gate every commit. The existing test_fcas_availability.py checks
the same logic against a month of real casefiles; this one pins the *boundaries*,
which real data exercises only by luck.
"""

import pytest

from nemde.inputs import (
    BidBand,
    BidDirection,
    FCASTrapezium,
    Line,
    TraderType,
    TradeType,
    apply_agc_enablement_limit_scaling,
    apply_agc_ramp_rate_scaling,
    apply_uigf_scaling,
    fcas_flag_condition_3,
    fcas_flag_condition_5,
    get_intersection,
    get_trader_effective_ramp_dn_rate,
    get_trader_effective_ramp_up_rate,
    is_fcas_available,
)
from tests.factories import make_bid, make_trader


def trapezium(
    enablement_min=20.0,
    low_breakpoint=40.0,
    high_breakpoint=80.0,
    enablement_max=100.0,
    max_avail=20.0,
    trade_type=TradeType.R6SE,
    direction=None,
):
    """A symmetric reference trapezium: slopes of 1.0 on both sides.

    max_avail 20 is reached at 40 MW rising from enablement_min 20, and held to
    80 MW before falling to zero at enablement_max 100.
    """
    return FCASTrapezium(
        trade_type=trade_type,
        direction=direction,
        enablement_min=enablement_min,
        enablement_max=enablement_max,
        low_breakpoint=low_breakpoint,
        high_breakpoint=high_breakpoint,
        max_avail=max_avail,
    )


class TestGetIntersection:
    def test_two_sloped_lines(self):
        # y = x and y = -x + 10 meet at (5, 5)
        assert get_intersection(Line(1.0, 0.0, 0.0), Line(-1.0, 10.0, 10.0)) == (5.0, 5.0)

    def test_both_horizontal_returns_none(self):
        assert get_intersection(Line(0, 0.0, None), Line(0, 5.0, None)) is None

    def test_both_vertical_returns_none(self):
        assert get_intersection(Line(None, None, 3.0), Line(None, None, 7.0)) is None

    def test_first_line_vertical(self):
        # x = 3 crosses y = 2x + 1 at (3, 7)
        assert get_intersection(Line(None, None, 3.0), Line(2.0, 1.0, -0.5)) == (3.0, 7.0)

    def test_second_line_vertical(self):
        assert get_intersection(Line(2.0, 1.0, -0.5), Line(None, None, 3.0)) == (3.0, 7.0)


class TestAgcEnablementLimitScaling:
    def test_none_limits_leave_trapezium_unchanged(self):
        original = trapezium()
        assert apply_agc_enablement_limit_scaling(original, None, None) == original

    def test_wider_agc_limits_do_not_widen_the_trapezium(self):
        # AGC limits outside the bid's own limits must not relax them: the result
        # keeps the bid's narrower enablement window.
        scaled = apply_agc_enablement_limit_scaling(trapezium(), 0.0, 200.0)
        assert (scaled.enablement_min, scaled.enablement_max) == (20.0, 100.0)
        assert scaled.max_avail == 20.0

    def test_narrower_agc_limits_pull_the_window_in(self):
        scaled = apply_agc_enablement_limit_scaling(trapezium(), 30.0, 90.0)
        assert (scaled.enablement_min, scaled.enablement_max) == (30.0, 90.0)
        # Slopes are preserved, so the breakpoints move with the limits.
        assert scaled.low_breakpoint == pytest.approx(50.0)
        assert scaled.high_breakpoint == pytest.approx(70.0)
        assert scaled.max_avail == 20.0

    def test_limits_narrow_enough_to_clip_the_peak(self):
        # Enablement window of 20 MW with slopes of 1.0 -- the two slopes now meet
        # at 10 MW, below the bid's 20 MW max avail, so the peak is clipped.
        scaled = apply_agc_enablement_limit_scaling(trapezium(), 40.0, 60.0)
        assert scaled.max_avail == pytest.approx(10.0)
        assert scaled.low_breakpoint == pytest.approx(50.0)
        assert scaled.high_breakpoint == pytest.approx(50.0)


class TestAgcRampRateScaling:
    @pytest.mark.parametrize("rate", [None, 0])
    def test_absent_or_zero_scada_rate_is_a_no_op(self, rate):
        # Documented behaviour: a missing or zero SCADA ramp rate means "no
        # information", not "no ramping capability".
        original = trapezium()
        assert apply_agc_ramp_rate_scaling(original, rate) is original

    def test_generous_ramp_rate_leaves_trapezium_unchanged(self):
        # 20 MW max avail needs 240 MW/h over the 5-minute interval; anything more
        # is not binding.
        original = trapezium()
        assert apply_agc_ramp_rate_scaling(original, 600.0) == original

    def test_binding_ramp_rate_caps_max_avail_and_moves_breakpoints(self):
        # 120 MW/h over 5 minutes = 10 MW of capability, half the bid's 20 MW.
        scaled = apply_agc_ramp_rate_scaling(trapezium(), 120.0)
        assert scaled.max_avail == pytest.approx(10.0)
        assert scaled.low_breakpoint == pytest.approx(30.0)
        assert scaled.high_breakpoint == pytest.approx(90.0)
        # Enablement limits are untouched by ramp-rate scaling.
        assert (scaled.enablement_min, scaled.enablement_max) == (20.0, 100.0)

    def test_exactly_equal_capability_is_not_scaled(self):
        # 240 MW/h / 12 == the 20 MW max avail exactly: the >= guard means no change.
        original = trapezium()
        assert apply_agc_ramp_rate_scaling(original, 240.0) == original


class TestUigfScaling:
    def test_none_uigf_is_a_no_op(self):
        original = trapezium()
        assert apply_uigf_scaling(original, None) is original

    def test_uigf_above_enablement_max_is_not_binding(self):
        scaled = apply_uigf_scaling(trapezium(), 150.0)
        assert scaled.enablement_max == 100.0
        assert scaled.high_breakpoint == 80.0

    def test_uigf_below_enablement_max_pulls_the_upper_slope_in(self):
        scaled = apply_uigf_scaling(trapezium(), 90.0)
        assert scaled.enablement_max == 90.0
        # Upper slope of -1.0 preserved, so the high breakpoint moves with it.
        assert scaled.high_breakpoint == pytest.approx(70.0)
        # UIGF scaling never touches max avail or the lower slope.
        assert scaled.max_avail == 20.0
        assert (scaled.enablement_min, scaled.low_breakpoint) == (20.0, 40.0)

    def test_vertical_upper_slope_keeps_its_breakpoint(self):
        # high_breakpoint == enablement_max means the upper slope is vertical;
        # there is no finite slope to move the breakpoint along.
        vertical = trapezium(high_breakpoint=100.0, enablement_max=100.0)
        scaled = apply_uigf_scaling(vertical, 90.0)
        assert scaled.enablement_max == 90.0
        assert scaled.high_breakpoint == 100.0


class TestFcasFlagCondition3:
    def test_contingency_bids_are_exempt(self):
        # Condition 3 only applies to regulation services.
        bid = make_bid(trade_type=TradeType.R6SE, enablement_max=-5.0)
        assert fcas_flag_condition_3(make_trader(), bid) is True

    @pytest.mark.parametrize(
        ("enablement_max", "expected"), [(0.0, True), (10.0, True), (-0.1, False)]
    )
    def test_generator_regulation_needs_non_negative_enablement_max(self, enablement_max, expected):
        bid = make_bid(trade_type=TradeType.R5RE, enablement_max=enablement_max)
        assert fcas_flag_condition_3(make_trader(), bid) is expected

    @pytest.mark.parametrize(
        ("enablement_min", "expected"), [(0.0, True), (-10.0, True), (0.1, False)]
    )
    def test_bdu_load_side_regulation_needs_non_positive_enablement_min(
        self, enablement_min, expected
    ):
        trader = make_trader(trader_type=TraderType.Bidirectional)
        bid = make_bid(
            trade_type=TradeType.L5RE,
            direction=BidDirection.Load,
            enablement_min=enablement_min,
        )
        assert fcas_flag_condition_3(trader, bid) is expected


class TestFcasFlagCondition5:
    @pytest.mark.parametrize(
        ("initial_mw", "expected"),
        [
            (20.0, True),  # exactly on enablement_min
            (100.0, True),  # exactly on enablement_max
            (60.0, True),
            (19.9, False),  # stranded below
            (100.1, False),  # stranded above
        ],
    )
    def test_generator_must_start_inside_the_trapezium(self, initial_mw, expected):
        trader = make_trader(initial_mw=initial_mw)
        bid = make_bid(scaled_fcas_trapezium=trapezium())
        assert fcas_flag_condition_5(trader, bid) is expected

    def test_negative_initial_mw_is_clamped_to_zero_for_a_generator(self):
        # Condition 5 uses max(initial_mw, 0) for generators/loads/WDR, so a
        # negative initial MW is treated as 0 -- outside a trapezium starting at 20.
        trader = make_trader(initial_mw=-50.0)
        bid = make_bid(scaled_fcas_trapezium=trapezium())
        assert fcas_flag_condition_5(trader, bid) is False

        # ... and inside one that starts at or below zero.
        bid_from_zero = make_bid(scaled_fcas_trapezium=trapezium(enablement_min=0.0))
        assert fcas_flag_condition_5(trader, bid_from_zero) is True


class TestIsFcasAvailable:
    def test_all_conditions_met(self):
        trader = make_trader(initial_mw=60.0)
        bid = make_bid(scaled_fcas_trapezium=trapezium())
        assert is_fcas_available(trader, bid)

    def test_zero_max_avail_makes_fcas_unavailable(self):
        # "Zero Max Availability means that no FCAS is available for enablement"
        # -- fcas-model-in-nemde.txt, footnote 4.
        trader = make_trader(initial_mw=60.0)
        bid = make_bid(max_avail=0.0, scaled_fcas_trapezium=trapezium(max_avail=0.0))
        assert not is_fcas_available(trader, bid)

    def test_no_bid_band_capacity_makes_fcas_unavailable(self):
        trader = make_trader(initial_mw=60.0)
        bid = make_bid(
            bid_bands=[BidBand(index=i, price=10.0 * i, quantity=0.0) for i in range(1, 11)],
            scaled_fcas_trapezium=trapezium(),
        )
        assert not is_fcas_available(trader, bid)

    def test_stranded_outside_the_trapezium_makes_fcas_unavailable(self):
        trader = make_trader(initial_mw=150.0)
        bid = make_bid(scaled_fcas_trapezium=trapezium())
        assert not is_fcas_available(trader, bid)


class TestEffectiveRampRates:
    def test_min_of_bid_and_scada_rate_is_taken(self):
        trader = make_trader(
            scada_ramp_up_rate=180.0,
            scada_ramp_dn_rate=90.0,
            bids=[make_bid(trade_type=TradeType.ENOF, ramp_up_rate=240.0, ramp_dn_rate=240.0)],
        )
        assert get_trader_effective_ramp_up_rate(trader) == 180.0
        assert get_trader_effective_ramp_dn_rate(trader) == 90.0

    def test_missing_scada_rate_falls_back_to_the_bid_rate(self):
        trader = make_trader(
            scada_ramp_up_rate=None,
            scada_ramp_dn_rate=None,
            bids=[make_bid(trade_type=TradeType.ENOF, ramp_up_rate=240.0, ramp_dn_rate=120.0)],
        )
        assert get_trader_effective_ramp_up_rate(trader) == 240.0
        assert get_trader_effective_ramp_dn_rate(trader) == 120.0

    def test_no_rate_from_either_source_is_none(self):
        # Traders with neither a SCADA nor a bid ramp rate must return None rather
        # than 0 -- inputs.py's index sets exclude them explicitly on that basis.
        trader = make_trader(
            scada_ramp_up_rate=None,
            scada_ramp_dn_rate=None,
            bids=[make_bid(trade_type=TradeType.ENOF, ramp_up_rate=None, ramp_dn_rate=None)],
        )
        assert get_trader_effective_ramp_up_rate(trader) is None
        assert get_trader_effective_ramp_dn_rate(trader) is None

    def test_zero_scada_rate_wins_over_a_positive_bid_rate(self):
        # Zero is a real value here (unlike in AGC ramp-rate scaling, where it
        # means "no information"), so it must not be filtered out as falsy.
        trader = make_trader(
            scada_ramp_up_rate=0.0,
            bids=[make_bid(trade_type=TradeType.ENOF, ramp_up_rate=240.0)],
        )
        assert get_trader_effective_ramp_up_rate(trader) == 0.0

    def test_unhandled_trader_type_raises(self):
        trader = make_trader(trader_type="SOMETHING_ELSE")
        with pytest.raises(Exception, match="Unhandled trader type"):
            get_trader_effective_ramp_up_rate(trader)
