"""Builders for inputs.py's NamedTuples, for solver-free tests.

Trader and Bid have 20 and 11 fields respectively, almost all irrelevant to any
one assertion. These builders supply a plausible default for every field so a
test can name only what it is actually about -- which is what makes the test read
as a statement about the rule rather than about the data model.
"""

from nemde.inputs import Bid, BidBand, FCASTrapezium, TraderType, TradeType


def make_bid_bands(quantity: float = 10.0) -> list[BidBand]:
    return [BidBand(index=i, price=10.0 * i, quantity=quantity) for i in range(1, 11)]


def make_trapezium(
    trade_type: TradeType = TradeType.R6SE,
    direction=None,
    enablement_min: float = 20.0,
    enablement_max: float = 100.0,
    low_breakpoint: float = 40.0,
    high_breakpoint: float = 80.0,
    max_avail: float = 20.0,
) -> FCASTrapezium:
    return FCASTrapezium(
        trade_type=trade_type,
        direction=direction,
        enablement_min=enablement_min,
        enablement_max=enablement_max,
        low_breakpoint=low_breakpoint,
        high_breakpoint=high_breakpoint,
        max_avail=max_avail,
    )


def make_bid(
    trade_type: TradeType = TradeType.R6SE,
    direction=None,
    ramp_up_rate: float | None = 240.0,
    ramp_dn_rate: float | None = 240.0,
    max_avail: float = 20.0,
    enablement_min: float | None = 20.0,
    enablement_max: float | None = 100.0,
    low_breakpoint: float | None = 40.0,
    high_breakpoint: float | None = 80.0,
    bid_bands: list[BidBand] | None = None,
    scaled_fcas_trapezium: FCASTrapezium | None = None,
) -> Bid:
    return Bid(
        trade_type=trade_type,
        direction=direction,
        ramp_up_rate=ramp_up_rate,
        ramp_dn_rate=ramp_dn_rate,
        max_avail=max_avail,
        enablement_min=enablement_min,
        enablement_max=enablement_max,
        low_breakpoint=low_breakpoint,
        high_breakpoint=high_breakpoint,
        bid_bands=make_bid_bands() if bid_bands is None else bid_bands,
        scaled_fcas_trapezium=scaled_fcas_trapezium,
    )


def make_trader(**overrides):
    """A scheduled generator, AGC-enabled, with one ENOF bid. Override any field.

    Built lazily against Trader._fields so a new field on the NamedTuple shows up
    as an explicit failure here rather than a silent positional shift.
    """
    from nemde.inputs import Trader

    defaults = {
        "trader_id": "TRADER1",
        "trader_type": TraderType.Generator,
        "region_id": "SA1",
        "semi_dispatch": "0",
        "agc_status": "1",
        "hmw": None,
        "initial_energy_storage": None,
        "initial_mw": 50.0,
        "lmw": None,
        "uigf": None,
        "scada_ramp_dn_rate": 240.0,
        "scada_ramp_up_rate": 240.0,
        "what_if_initial_energy_storage": None,
        "what_if_initial_mw": None,
        "import_efficiency_factor": None,
        "export_efficiency_factor": None,
        "min_energy_limit": None,
        "max_energy_limit": None,
        "max_storage_capacity": None,
        "bids": None,
        "fast_start": None,
        "min_loading_mw": None,
        "current_mode": None,
        "current_mode_time": None,
        "t1": None,
        "t2": None,
        "t3": None,
        "t4": None,
        "nemde_solution": None,
    }
    unknown = set(overrides) - set(Trader._fields)
    if unknown:
        raise TypeError(f"Trader has no field(s) {sorted(unknown)}")
    missing = set(Trader._fields) - set(defaults)
    if missing:
        raise TypeError(
            f"tests/factories.py is missing a default for Trader field(s) {sorted(missing)}"
        )

    values = {**defaults, **overrides}
    if values["bids"] is None:
        values["bids"] = [make_bid(trade_type=TradeType.ENOF, max_avail=200.0)]
    return Trader(**values)
