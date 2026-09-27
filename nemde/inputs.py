"""Casefile parsing: turns a raw NEMDE casefile dict into the model's input objects.

Section index. Line ranges are approximate and drift with edits.

    27-40         xmltodict single-element normalisation
    41-87         scalar coercion helpers (to_float, to_int, zero_if_null)
    88-520        data model: TradeType/TraderType/BidDirection enums and the
                 Trader/Region/Interconnector/GenericConstraint/Line NamedTuples
    521-916       casefile -> object parsing (parse_trader, parse_region, parse_interconnector,
                 parse_generic_constraint, get_*_objects)
    917-1218      bid/price-band lookups and price-tie helpers
    1219-1746     FCAS trapezium scaling and availability logic (AGC/UIGF scaling,
                 apply_fcas_trapezium_scaling, fcas_flag_condition_3/4/5, is_fcas_available) --
                 the live FCAS implementation, consumed by model.define_fcas_constraints
    1747-2176     ramp-rate math (composite/effective ramp rates) and interconnector loss-model
                 math (loss estimate, MNSP region loss indicator)
    2177-3157     top-level entry point assembling the full model input dict from a casefile;
                 this dict is the whole contract between parsing and modelling
"""

from enum import Enum
from itertools import groupby
from operator import itemgetter
from typing import Literal, NamedTuple


def convert_to_list(list_or_dict):
    """Wrap a single xmltodict element in a list, or pass a list through.

    xmltodict collapses a one-element collection to a bare dict, so anything not
    covered by casefile_io.FORCE_LIST has to be normalised at the point of use.
    """

    if isinstance(list_or_dict, dict):
        return [list_or_dict]
    if isinstance(list_or_dict, list):
        return list_or_dict
    raise TypeError(f"Input should be a list or dict. Received {type(list_or_dict)}")


def to_float(value):
    """Convert value to float if possible, otherwise return original value.

    Args:
        value: Value to convert to float

    Returns:
        Float representation of value, or original value if conversion fails
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return value


def to_int(value):
    """Convert value to int if possible, otherwise return original value.

    Args:
        value: Value to convert to int

    Returns:
        Int representation of value, or original value if conversion fails
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return value


def zero_if_null(x):
    """Return 0 if value is None, otherwise return the value unchanged.

    Args:
        x: Value to check for None

    Returns:
        0 if x is None, otherwise x
    """
    return 0 if x is None else x


# =============================================================================
# CONSTANTS AND TYPE DEFINITIONS
# =============================================================================


class TradeType(str, Enum):
    BDOF = "BDOF"
    ENOF = "ENOF"
    LDOF = "LDOF"
    DROF = "DROF"
    L1SE = "L1SE"
    L6SE = "L6SE"
    L60S = "L60S"
    L5MI = "L5MI"
    L5RE = "L5RE"
    R1SE = "R1SE"
    R6SE = "R6SE"
    R60S = "R60S"
    R5MI = "R5MI"
    R5RE = "R5RE"


TRADE_TYPES = [i.value for i in TradeType]

FCAS_TRADE_TYPES = [
    TradeType.L1SE,
    TradeType.L6SE,
    TradeType.L60S,
    TradeType.L5MI,
    TradeType.L5RE,
    TradeType.R1SE,
    TradeType.R6SE,
    TradeType.R60S,
    TradeType.R5MI,
    TradeType.R5RE,
]

FCASTradeType = Literal[
    TradeType.L1SE,
    TradeType.L6SE,
    TradeType.L60S,
    TradeType.L5MI,
    TradeType.L5RE,
    TradeType.R1SE,
    TradeType.R6SE,
    TradeType.R60S,
    TradeType.R5MI,
    TradeType.R5RE,
]


REGULATION_FCAS_TRADE_TYPES = [TradeType.L5RE, TradeType.R5RE]

RegulationFCASTradeType = Literal[TradeType.L5RE, TradeType.R5RE]

CONTINGENCY_FCAS_TRADE_TYPES = [
    TradeType.L1SE,
    TradeType.L6SE,
    TradeType.L60S,
    TradeType.L5MI,
    TradeType.R1SE,
    TradeType.R6SE,
    TradeType.R60S,
    TradeType.R5MI,
]

CONTINGENCY_RAISE_FCAS_TRADE_TYPES = [
    TradeType.R1SE,
    TradeType.R6SE,
    TradeType.R60S,
    TradeType.R5MI,
]

CONTINGENCY_LOWER_FCAS_TRADE_TYPES = [
    TradeType.L1SE,
    TradeType.L6SE,
    TradeType.L60S,
    TradeType.L5MI,
]


ContingencyFCASTradeType = Literal[
    TradeType.L1SE,
    TradeType.L6SE,
    TradeType.L60S,
    TradeType.L5MI,
    TradeType.R1SE,
    TradeType.R6SE,
    TradeType.R60S,
    TradeType.R5MI,
]


REGION_IDS = [
    "SA1",
    "VIC1",
    "NSW1",
    "TAS1",
    "QLD1",
]

RegionId = Literal["SA1", "VIC1", "NSW1", "TAS1", "QLD1"]


class TraderType(str, Enum):
    Generator = "GENERATOR"
    Load = "LOAD"
    NormallyOnLoad = "NORMALLY_ON_LOAD"
    Bidirectional = "BIDIRECTIONAL"
    Wdr = "WDR"


TRADER_TYPES = [t.value for t in TraderType]


class BidDirection(str, Enum):
    Load = "LOAD"
    Gen = "GEN"


TRADE_TYPE_DIRECTIONS = [d.value for d in BidDirection] + [None]

TradeTypeDirection = BidDirection | None

FCAS_FLAG_MAP = {
    "@R1Flags": TradeType.R1SE,
    "@R6Flags": TradeType.R6SE,
    "@R60Flags": TradeType.R60S,
    "@R5Flags": TradeType.R5MI,
    "@R5RegFlags": TradeType.R5RE,
    "@L1Flags": TradeType.L1SE,
    "@L6Flags": TradeType.L6SE,
    "@L60Flags": TradeType.L60S,
    "@L5Flags": TradeType.L5MI,
    "@L5RegFlags": TradeType.L5RE,
}


class FCASTrapezium(NamedTuple):
    trade_type: TradeType
    direction: TradeTypeDirection
    enablement_min: float
    enablement_max: float
    low_breakpoint: float
    high_breakpoint: float
    max_avail: float


class BidBand(NamedTuple):
    index: int
    price: float
    quantity: float


class Bid(NamedTuple):
    trade_type: TradeType
    direction: TradeTypeDirection
    ramp_up_rate: float | None
    ramp_dn_rate: float | None
    max_avail: float
    enablement_min: float | None
    enablement_max: float | None
    low_breakpoint: float | None
    high_breakpoint: float | None
    bid_bands: list[BidBand]
    scaled_fcas_trapezium: FCASTrapezium | None


class NEMDETraderSolution(NamedTuple):
    intervention: str
    energy_target: float
    r1_target: float
    r6_target: float
    r60_target: float
    r5_target: float
    r5_reg_target: float
    l1_target: float
    l6_target: float
    l60_target: float
    l5_target: float
    l5_reg_target: float
    ramp_up_rate: float
    ramp_dn_rate: float
    r1_flags: int
    r6_flags: int
    r60_flags: int
    r5_flags: int
    r5_reg_flags: int
    l1_flags: int
    l6_flags: int
    l60_flags: int
    l5_flags: int
    l5_reg_flags: int


class Trader(NamedTuple):
    trader_id: str
    trader_type: TraderType
    region_id: RegionId
    semi_dispatch: str
    agc_status: str
    hmw: float | None
    initial_energy_storage: float | None
    initial_mw: float
    lmw: float | None
    uigf: float | None
    scada_ramp_dn_rate: float | None
    scada_ramp_up_rate: float | None
    what_if_initial_energy_storage: float | None
    what_if_initial_mw: float | None
    import_efficiency_factor: float | None
    export_efficiency_factor: float | None
    min_energy_limit: float | None
    max_energy_limit: float | None
    max_storage_capacity: float | None
    bids: list[Bid]
    fast_start: int | None
    min_loading_mw: float | None
    current_mode: int | None
    current_mode_time: int | None
    t1: int | None
    t2: int | None
    t3: int | None
    t4: int | None
    # Used for backtesting and development (e.g. pinning solutions)
    nemde_solution: list[NEMDETraderSolution] | None


class Region(NamedTuple):
    region_id: str
    ade: float
    initial_demand: float
    df: float


class InterconnectorBid(NamedTuple):
    region_id: str
    max_avail: float
    ramp_up_rate: float
    ramp_dn_rate: float
    bid_bands: list[BidBand]


class LossModelSegment(NamedTuple):
    index: int
    limit: float
    factor: float


class NEMDEInterconnectorSolution(NamedTuple):
    intervention: str
    flow: float
    losses: float
    deficit: float
    price: float
    ideal_losses: float


class Interconnector(NamedTuple):
    interconnector_id: str
    from_region: str
    to_region: str
    initial_mw: float
    what_if_initial_mw: float | None
    lower_limit: float
    upper_limit: float
    mnsp_status: str
    loss_share: float
    loss_lower_limit: float
    loss_model_segments: list[LossModelSegment]
    bids: list[InterconnectorBid]
    # Only applicable for MNSP interconnectors
    to_region_lf: float | None
    to_region_lf_import: float | None
    to_region_lf_export: float | None
    from_region_lf: float | None
    from_region_lf_import: float | None
    from_region_lf_export: float | None
    # NEMDE solution used for backtesting and development (e.g. pinning solutions)
    nemde_solution: list[NEMDEInterconnectorSolution] | None


class TraderFactor(NamedTuple):
    trader_id: str
    trade_type: str
    factor: float


class InterconnectorFactor(NamedTuple):
    interconnector_id: str
    factor: float


class RegionFactor(NamedTuple):
    region_id: str
    trade_type: str
    factor: float


class LHSFactorCollection(NamedTuple):
    trader_factors: list[TraderFactor]
    interconnector_factors: list[InterconnectorFactor]
    region_factors: list[RegionFactor]


class NEMDEConstraintSolution(NamedTuple):
    marginal_value: float
    deficit: float
    rhs_solution: float


class GenericConstraint(NamedTuple):
    constraint_id: str
    intervention: str
    constraint_type: str
    violation_price: float
    lhs_factor_collection: LHSFactorCollection
    rhs: float
    nemde_solution: NEMDEConstraintSolution


class CaseParameters(NamedTuple):
    case_id: str
    case_type: str
    intervention: str
    voll: float
    mpf: float
    energy_deficit_price: float
    energy_surplus_price: float
    ramp_rate_price: float
    interconnector_price: float
    capacity_price: float
    min_energy_limit_price: float
    max_energy_limit_price: float
    offer_price: float
    tie_break_price: float
    generic_constraint_price: float
    npl_threshold: float
    mnsp_losses_price: float
    mnsp_offer_price: float
    mnsp_ramp_rate_price: float
    mnsp_capacity_price: float
    fast_start_price: float
    satisfactory_network_price: float
    fast_start_threshold: float
    switch_run_initial_status: int
    uigf_surplus_price: float
    uigf_atime: str
    use_sos2_loss_model: int
    energy_limit_price: float
    as_profile_price: float
    as_max_avail_price: float
    as_enablement_min_price: float
    as_enablement_max_price: float


class Line(NamedTuple):
    slope: float
    y_intercept: float | None
    x_intercept: float | None


# =============================================================================
# TRADER PARSING
# =============================================================================


def _create_bid_bands(band_data: dict) -> list[BidBand]:
    """Extract bid bands from raw band data.

    Args:
        band_data: Dictionary containing price and quantity band data

    Returns:
        List of 10 BidBand objects with price and quantity information
    """
    return [
        BidBand(
            index=j,
            price=to_float(band_data.get(f"@PriceBand{j}")),
            quantity=to_float(band_data.get(f"@BandAvail{j}")),
        )
        for j in range(1, 11)
    ]


def _create_fcas_trapezium(band_data: dict) -> FCASTrapezium:
    """Create FCASTrapezium from raw band data.

    Args:
        band_data: Dictionary containing FCAS trapezium parameters

    Returns:
        FCASTrapezium with enablement limits, breakpoints, and max availability
    """
    return FCASTrapezium(
        trade_type=band_data["@TradeType"],
        direction=band_data.get("@Direction"),
        enablement_min=to_float(band_data.get("@EnablementMin")),
        enablement_max=to_float(band_data.get("@EnablementMax")),
        low_breakpoint=to_float(band_data.get("@LowBreakpoint")),
        high_breakpoint=to_float(band_data.get("@HighBreakpoint")),
        max_avail=to_float(band_data["@MaxAvail"]),
    )


def _scale_fcas_trapezium_if_applicable(
    band_data: dict,
    trader_data: dict,
    initial_conditions: dict,
) -> FCASTrapezium | None:
    """Create and scale FCAS trapezium if trade type is FCAS.

    Args:
        band_data: Dictionary containing bid band data
        trader_data: Dictionary containing trader information
        initial_conditions: Dictionary containing trader initial conditions

    Returns:
        Scaled FCASTrapezium if trade type is FCAS, None otherwise
    """
    if band_data["@TradeType"] not in FCAS_TRADE_TYPES:
        return None

    trapezium = _create_fcas_trapezium(band_data)

    return apply_fcas_trapezium_scaling(
        trapezium=trapezium,
        trader_type=trader_data["@TraderType"],
        trade_type=band_data["@TradeType"],
        agc_enablement_min=to_float(initial_conditions.get("LMW")),
        agc_enablement_max=to_float(initial_conditions.get("HMW")),
        scada_ramp_dn_rate=to_float(initial_conditions.get("SCADARampDnRate")),
        scada_ramp_up_rate=to_float(initial_conditions.get("SCADARampUpRate")),
        uigf=to_float(trader_data.get("@UIGF")),
    )


def parse_trader(trader_data: dict) -> Trader:
    """Consolidate trader data into a Trader object.

    Parses raw trader data from casefile format and constructs a Trader object
    with all bids, initial conditions, and scaled FCAS trapeziums.

    Args:
        trader_data: Dictionary containing trader information, bids, and initial conditions

    Returns:
        Trader object with parsed bids and trader attributes
    """

    initial_conditions = {
        i["@InitialConditionID"]: to_float(i["@Value"])
        for i in trader_data["TraderInitialConditionCollection"]["TraderInitialCondition"]
    }

    price_bands = {
        (
            i["@TradeType"] + "_" + i["@Direction"] if i.get("@Direction") else i["@TradeType"]
        ): to_float(i)
        for i in trader_data["TradePriceStructureCollection"]["TradePriceStructure"][
            "TradeTypePriceStructureCollection"
        ]["TradeTypePriceStructure"]
    }

    quantity_bands = {
        (
            i["@TradeType"] + "_" + i["@Direction"] if i.get("@Direction") else i["@TradeType"]
        ): to_float(i)
        for i in trader_data["TradeCollection"]["Trade"]
    }

    bands = {k: {**v, **price_bands[k]} for k, v in quantity_bands.items()}

    bids = [
        Bid(
            trade_type=i["@TradeType"],
            direction=i.get("@Direction"),
            ramp_up_rate=to_float(i.get("@RampUpRate")),
            ramp_dn_rate=to_float(i.get("@RampDnRate")),
            max_avail=to_float(i["@MaxAvail"]),
            enablement_min=to_float(i.get("@EnablementMin")),
            enablement_max=to_float(i.get("@EnablementMax")),
            low_breakpoint=to_float(i.get("@LowBreakpoint")),
            high_breakpoint=to_float(i.get("@HighBreakpoint")),
            bid_bands=_create_bid_bands(band_data=i),
            scaled_fcas_trapezium=_scale_fcas_trapezium_if_applicable(
                band_data=i,
                trader_data=trader_data,
                initial_conditions=initial_conditions,
            ),
        )
        for i in bands.values()
    ]

    # Only considering the no intervention solution for now
    # TODO: Extend to handle intervention solutions
    nemde_solution = [i for i in trader_data["nemde_solution"] if i["@Intervention"] == "0"][0]

    trader = Trader(
        trader_id=trader_data["@TraderID"],
        trader_type=trader_data["@TraderType"],
        region_id=trader_data["@RegionID"],
        semi_dispatch=str(trader_data["@SemiDispatch"]),
        agc_status=str(to_int(initial_conditions.get("AGCStatus"))),
        hmw=to_float(initial_conditions.get("HMW")),
        initial_energy_storage=to_float(initial_conditions.get("InitialEnergyStorage")),
        initial_mw=to_float(initial_conditions.get("InitialMW")),
        lmw=to_float(initial_conditions.get("LMW")),
        uigf=to_float(trader_data.get("@UIGF")),
        scada_ramp_dn_rate=to_float(initial_conditions.get("SCADARampDnRate")),
        scada_ramp_up_rate=to_float(initial_conditions.get("SCADARampUpRate")),
        what_if_initial_energy_storage=to_float(
            initial_conditions.get("WhatIfInitialEnergyStorage")
        ),
        what_if_initial_mw=to_float(initial_conditions.get("WhatIfInitialMW")),
        # Bidirectional units
        import_efficiency_factor=to_float(trader_data.get("@ImportEfficiencyFactor")),
        export_efficiency_factor=to_float(trader_data.get("@ExportEfficiencyFactor")),
        min_energy_limit=to_float(trader_data.get("@MinEnergyLimit")),
        max_energy_limit=to_float(trader_data.get("@MaxEnergyLimit")),
        max_storage_capacity=to_float(trader_data.get("@MaxStorageCapacity")),
        bids=bids,
        # Fast start parameters
        fast_start=to_float(trader_data.get("@FastStart")),
        min_loading_mw=to_float(trader_data.get("@MinLoadingMW")),
        current_mode=to_int(trader_data.get("@CurrentMode")),
        current_mode_time=to_float(trader_data.get("@CurrentModeTime")),
        t1=to_float(trader_data.get("@T1")),
        t2=to_float(trader_data.get("@T2")),
        t3=to_float(trader_data.get("@T3")),
        t4=to_float(trader_data.get("@T4")),
        nemde_solution=[
            NEMDETraderSolution(
                intervention=str(nemde_solution["@Intervention"]),
                energy_target=to_float(nemde_solution["@EnergyTarget"]),
                r1_target=to_float(nemde_solution.get("@R1Target", 0)),
                r6_target=to_float(nemde_solution["@R6Target"]),
                r60_target=to_float(nemde_solution["@R60Target"]),
                r5_target=to_float(nemde_solution["@R5Target"]),
                r5_reg_target=to_float(nemde_solution["@R5RegTarget"]),
                l1_target=to_float(nemde_solution.get("@L1Target", 0)),
                l6_target=to_float(nemde_solution["@L6Target"]),
                l60_target=to_float(nemde_solution["@L60Target"]),
                l5_target=to_float(nemde_solution["@L5Target"]),
                l5_reg_target=to_float(nemde_solution["@L5RegTarget"]),
                ramp_up_rate=to_float(nemde_solution.get("@RampUpRate")),
                ramp_dn_rate=to_float(nemde_solution.get("@RampDnRate")),
                r1_flags=to_float(nemde_solution.get("@R1Flags")),
                r6_flags=to_float(nemde_solution.get("@R6Flags")),
                r60_flags=to_float(nemde_solution.get("@R60Flags")),
                r5_flags=to_float(nemde_solution.get("@R5Flags")),
                r5_reg_flags=to_float(nemde_solution.get("@R5RegFlags")),
                l1_flags=to_float(nemde_solution.get("@L1Flags")),
                l6_flags=to_float(nemde_solution.get("@L6Flags")),
                l60_flags=to_float(nemde_solution.get("@L60Flags")),
                l5_flags=to_float(nemde_solution.get("@L5Flags")),
                l5_reg_flags=to_float(nemde_solution.get("@L5RegFlags")),
            )
        ],
    )

    return trader


def get_trader_objects(casefile: dict) -> list[Trader]:
    """Construct trader objects from casefile data.

    Extracts trader information from NEMDE casefile and creates Trader objects
    by combining trader collection data with trader period data.

    Args:
        casefile: Dictionary containing NEMDE casefile with trader and period information

    Returns:
        List of Trader objects with parsed bids and attributes
    """

    trader_collection = {
        i["@TraderID"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["TraderCollection"]["Trader"]
    }

    trader_period_collection = {
        i["@TraderID"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["PeriodCollection"]["Period"][
            "TraderPeriodCollection"
        ]["TraderPeriod"]
    }

    trader_solution = casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["TraderSolution"]

    trader_solution_grouped = {
        k: {"nemde_solution": list(v)}
        for k, v in groupby(
            sorted(trader_solution, key=itemgetter("@TraderID")),
            key=itemgetter("@TraderID"),
        )
    }

    # Combine trader and period data and transform into Trader objects
    traders = [
        parse_trader(
            trader_data={
                **v,
                **trader_period_collection[k],
                **trader_solution_grouped[k],
            }
        )
        for k, v in trader_collection.items()
    ]

    return traders


def parse_region(region_data: dict) -> Region:
    """Consolidate region data into a Region object.

    Parses raw region data from casefile format and constructs a Region object
    with ADE and initial demand.

    Args:
        region_data: Dictionary containing region information

    Returns:
        Region object with parsed attributes
    """

    initial_conditions = {
        i["@InitialConditionID"]: to_float(i["@Value"])
        for i in region_data["RegionInitialConditionCollection"]["RegionInitialCondition"]
    }

    region = Region(
        region_id=region_data["@RegionID"],
        ade=initial_conditions["ADE"],
        initial_demand=initial_conditions["InitialDemand"],
        df=to_float(region_data["@DF"]),
    )

    return region


def get_region_objects(casefile: dict) -> list[Region]:
    """Construct region objects from casefile data.

    Extracts region information from NEMDE casefile and creates Region objects
    by combining region collection data with region period data.

    Args:
        casefile: Dictionary containing NEMDE casefile with region and period information

    Returns:
        List of Region objects with parsed attributes
    """

    region_collection = {
        i["@RegionID"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["RegionCollection"]["Region"]
    }

    region_period_collection = {
        i["@RegionID"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["PeriodCollection"]["Period"][
            "RegionPeriodCollection"
        ]["RegionPeriod"]
    }

    # Combine trader and period data and transform into Trader objects
    regions = [
        parse_region(region_data={**v, **region_period_collection[k]})
        for k, v in region_collection.items()
    ]
    return regions


def parse_interconnector(interconnector_data: dict) -> Interconnector:
    """Consolidate interconnector data into an Interconnector object.

    Parses raw interconnector data from casefile format and constructs an Interconnector object
    with all attributes.

    Args:
        interconnector_data: Dictionary containing interconnector information

    Returns:
        Interconnector object with parsed attributes
    """

    initial_conditions = {
        i["@InitialConditionID"]: to_float(i["@Value"])
        for i in interconnector_data["InterconnectorInitialConditionCollection"][
            "InterconnectorInitialCondition"
        ]
    }

    loss_model_segments = [
        LossModelSegment(
            index=index,
            limit=to_float(segment["@Limit"]),
            factor=to_float(segment["@Factor"]),
        )
        for index, segment in enumerate(
            interconnector_data["LossModelCollection"]["LossModel"]["SegmentCollection"]["Segment"]
        )
    ]

    bids = []
    if interconnector_data["@MNSP"] == "1":
        price_bands = {
            i["@RegionID"]: i
            for i in interconnector_data["MNSPPriceStructureCollection"]["MNSPPriceStructure"][
                "MNSPRegionPriceStructureCollection"
            ]["MNSPRegionPriceStructure"]
        }

        quantity_bands = {
            i["@RegionID"]: i for i in interconnector_data["MNSPOfferCollection"]["MNSPOffer"]
        }

        bands = {k: {**v, **price_bands[k]} for k, v in quantity_bands.items()}

        bids = [
            InterconnectorBid(
                region_id=i["@RegionID"],
                max_avail=to_float(i["@MaxAvail"]),
                ramp_up_rate=to_float(i["@RampUpRate"]),
                ramp_dn_rate=to_float(i["@RampDnRate"]),
                bid_bands=_create_bid_bands(band_data=i),
            )
            for i in bands.values()
        ]

    nemde_solution = [
        NEMDEInterconnectorSolution(
            intervention=str(i["@Intervention"]),
            flow=to_float(i["@Flow"]),
            losses=to_float(i["@Losses"]),
            deficit=to_float(i["@Deficit"]),
            price=to_float(i["@Price"]),
            ideal_losses=to_float(i["@IdealLosses"]),
        )
        for i in interconnector_data["nemde_solution"]
    ]

    interconnector = Interconnector(
        interconnector_id=interconnector_data["@InterconnectorID"],
        from_region=interconnector_data["@FromRegion"],
        to_region=interconnector_data["@ToRegion"],
        initial_mw=to_float(initial_conditions["InitialMW"]),
        what_if_initial_mw=to_float(initial_conditions.get("WhatIfInitialMW")),
        lower_limit=to_float(interconnector_data["@LowerLimit"]),
        upper_limit=to_float(interconnector_data["@UpperLimit"]),
        mnsp_status=str(interconnector_data["@MNSP"]),
        loss_share=to_float(interconnector_data["LossModelCollection"]["LossModel"]["@LossShare"]),
        loss_lower_limit=to_float(
            interconnector_data["LossModelCollection"]["LossModel"]["@LossLowerLimit"]
        ),
        loss_model_segments=loss_model_segments,
        bids=bids,
        # Only applicable for MNSP interconnectors
        to_region_lf=to_float(interconnector_data.get("@ToRegionLF")),
        to_region_lf_import=to_float(interconnector_data.get("@ToRegionLFImport")),
        to_region_lf_export=to_float(interconnector_data.get("@ToRegionLFExport")),
        from_region_lf=to_float(interconnector_data.get("@FromRegionLF")),
        from_region_lf_import=to_float(interconnector_data.get("@FromRegionLFImport")),
        from_region_lf_export=to_float(interconnector_data.get("@FromRegionLFExport")),
        nemde_solution=nemde_solution,
    )

    return interconnector


def get_interconnector_objects(casefile: dict) -> list[Interconnector]:
    """Construct interconnector objects from casefile data.

    Extracts interconnector information from NEMDE casefile and creates Interconnector objects.

    Args:
        casefile: Dictionary containing NEMDE casefile with interconnector information

    Returns:
        List of Interconnector objects with parsed attributes
    """

    interconnector_collection = {
        i["@InterconnectorID"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["InterconnectorCollection"][
            "Interconnector"
        ]
    }

    interconnector_period_collection = {
        i["@InterconnectorID"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["PeriodCollection"]["Period"][
            "InterconnectorPeriodCollection"
        ]["InterconnectorPeriod"]
    }

    interconnector_solution = casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["InterconnectorSolution"]

    interconnector_solution_grouped = {
        k: {"nemde_solution": list(v)}
        for k, v in groupby(
            sorted(interconnector_solution, key=itemgetter("@InterconnectorID")),
            key=itemgetter("@InterconnectorID"),
        )
    }

    # Combine trader and period data and transform into Trader objects
    interconnectors = [
        parse_interconnector(
            interconnector_data={
                **v,
                **interconnector_period_collection[k],
                **interconnector_solution_grouped[k],
            }
        )
        for k, v in interconnector_collection.items()
    ]
    return interconnectors


def to_list(x):
    """Convert input to list if it is not already a list.

    Args:
        x: Input value to convert
    Returns:
        List containing the input value(s)
    """
    return x if isinstance(x, list) else [x]


def get_trader_price_bands(data) -> dict:
    """Trader price bands"""

    traders = data.get("NEMSPDCaseFile").get("NemSpdInputs").get("TraderCollection").get("Trader")

    # Container for all price bands
    price_bands = {}
    for i in traders:
        # All trade types for a given trader
        trade_types = (
            i.get("TradePriceStructureCollection")
            .get("TradePriceStructure")
            .get("TradeTypePriceStructureCollection")
            .get("TradeTypePriceStructure")
        )

        for j in convert_to_list(trade_types):
            # Price bands
            for k in range(1, 11):
                key = (i["@TraderID"], j["@TradeType"], j.get("@Direction"), k)
                price_bands[key] = float(j.get(f"@PriceBand{k}"))

    return price_bands


def get_trader_quantity_bands(data) -> dict:
    """Get trader quantity bands"""

    traders = (
        data.get("NEMSPDCaseFile")
        .get("NemSpdInputs")
        .get("PeriodCollection")
        .get("Period")
        .get("TraderPeriodCollection")
        .get("TraderPeriod")
    )

    # Container for quantity bands
    quantity_bands = {}
    for i in traders:
        for j in convert_to_list(i.get("TradeCollection").get("Trade")):
            # Quantity bands
            for k in range(1, 11):
                key = (i["@TraderID"], j["@TradeType"], j.get("@Direction"), k)
                quantity_bands[key] = float(j[f"@BandAvail{k}"])

    return quantity_bands


def get_trader_period_attribute(data, attribute, func) -> dict:
    """Get trader period attribute"""

    return {
        i["@TraderID"]: func(i[attribute])
        for i in (
            data.get("NEMSPDCaseFile")
            .get("NemSpdInputs")
            .get("PeriodCollection")
            .get("Period")
            .get("TraderPeriodCollection")
            .get("TraderPeriod")
        )
        if i.get(attribute) is not None
    }


def reorder_tuple(input_tuple) -> tuple:
    """Sort tuples alphabetically"""

    if input_tuple[0][0] > input_tuple[1][0]:
        return tuple((input_tuple[1], input_tuple[0]))
    else:
        return tuple((input_tuple[0], input_tuple[1]))


def get_price_tied_bands(data, trade_type):
    """
    Get price-tied generators and loads. 'trade_type'=ENOF for generators,
    'trade_type'=LDOF for loads.
    """

    # Price and quantity bands
    price_bands = get_trader_price_bands(data)
    quantity_bands = get_trader_quantity_bands(data)

    # Generator energy offer price bands
    filtered_price_bands = {k: v for k, v in price_bands.items() if k[1] == trade_type}

    # Trader region
    trader_region = get_trader_period_attribute(data, "@RegionID", str)

    # Container for price tied bands
    price_tied = []

    # For each price band
    for i, j in filtered_price_bands.items():
        # Compare it to every other price band
        for m, n in filtered_price_bands.items():
            # Price bands must be in same region (also ignore the input trader,
            # which will of course match)
            if (m == i) or (trader_region[i[0]] != trader_region[m[0]]):
                continue

            # Price-tied if the prices match to within a threshold and both offers
            # actually have quantity to reallocate between them.
            if (
                abs(j - n) < 1e-6
                and quantity_bands[m[0], m[1], m[2], m[3]] != 0
                and quantity_bands[i[0], i[1], i[2], i[3]] != 0
            ):
                price_tied.append((i, m))

    # Re-order tuples, get unique price-tied combinations, and sort alphabetically
    price_tied_reordered = [reorder_tuple(i) for i in price_tied]
    price_tied_unique = list(set(price_tied_reordered))
    price_tied_unique.sort()

    # Flatten to produce one tuple for a given pair of price-tied generators
    price_tied_flattened = [
        (i[0][0], i[0][1], i[0][2], i[0][3], i[1][0], i[1][1], i[1][2], i[1][3])
        for i in price_tied_unique
    ]

    return price_tied_flattened


def parse_generic_constraint(generic_constraint_data: dict) -> GenericConstraint:
    """Consolidate generic constraint data into a GenericConstraint object.

    Parses raw generic constraint data from casefile format and constructs a
    GenericConstraint object with all attributes.

    Args:
        generic_constraint_data: Dictionary containing generic constraint information

    Returns:
        GenericConstraint object with parsed attributes
    """

    return GenericConstraint(
        constraint_id=generic_constraint_data["@ConstraintID"],
        intervention=str(generic_constraint_data["@Intervention"]),
        constraint_type=generic_constraint_data["@Type"],
        violation_price=to_float(generic_constraint_data["@ViolationPrice"]),
        lhs_factor_collection=LHSFactorCollection(
            trader_factors=[
                TraderFactor(
                    trader_id=i["@TraderID"],
                    trade_type=i["@TradeType"],
                    factor=to_float(i["@Factor"]),
                )
                for i in to_list(
                    generic_constraint_data["LHSFactorCollection"].get("TraderFactor", [])
                )
            ],
            interconnector_factors=[
                InterconnectorFactor(
                    interconnector_id=i["@InterconnectorID"],
                    factor=to_float(i["@Factor"]),
                )
                for i in to_list(
                    generic_constraint_data["LHSFactorCollection"].get("InterconnectorFactor", [])
                )
            ],
            region_factors=[
                RegionFactor(
                    region_id=i["@RegionID"],
                    trade_type=i["@TradeType"],
                    factor=to_float(i["@Factor"]),
                )
                for i in to_list(
                    generic_constraint_data["LHSFactorCollection"].get("RegionFactor", [])
                )
            ],
        ),
        rhs=to_float(generic_constraint_data["@RHS"]),
        nemde_solution=NEMDEConstraintSolution(
            marginal_value=to_float(generic_constraint_data["@MarginalValue"]),
            deficit=to_float(generic_constraint_data["@Deficit"]),
            rhs_solution=to_float(generic_constraint_data["@RHSSolution"]),
        ),
    )


def get_generic_constraint_objects(casefile: dict) -> list[GenericConstraint]:
    """Construct generic constraint objects from casefile data.

    Extracts generic constraint information from a NEMDE casefile and creates
    GenericConstraint objects.

    Args:
        casefile: Dictionary containing NEMDE casefile with generic constraint information

    Returns:
        List of GenericConstraint objects with parsed attributes
    """
    generic_constraint_period_collection = {
        i["@ConstraintID"] + "__" + i["@Version"] + "__" + i["@Intervention"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["PeriodCollection"]["Period"][
            "GenericConstraintPeriodCollection"
        ]["GenericConstraintPeriod"]
    }

    # Defines constraints applying for current period. Includes intervention status.
    generic_constraint_collection = {
        i["@ConstraintID"] + "__" + i["@Version"]: i
        for i in casefile["NEMSPDCaseFile"]["NemSpdInputs"]["GenericConstraintCollection"][
            "GenericConstraint"
        ]
    }

    generic_constraint_solution = {
        i["@ConstraintID"] + "__" + i["@Version"] + "__" + i["@Intervention"]: {
            "@MarginalValue": i["@MarginalValue"],
            "@Deficit": i["@Deficit"],
            "@RHSSolution": i["@RHS"],
        }
        for i in casefile["NEMSPDCaseFile"]["NemSpdOutputs"]["ConstraintSolution"]
    }

    generic_constraints = [
        parse_generic_constraint(
            generic_constraint_data={
                **v,
                **generic_constraint_collection["__".join(k.split("__")[:-1])],
                **generic_constraint_solution[k],
            }
        )
        for k, v in generic_constraint_period_collection.items()
    ]

    return generic_constraints


# =============================================================================
# GEOMETRY UTILITIES
# =============================================================================


def get_line_from_slope_and_x_intercept(slope: float, x_intercept: float) -> Line:
    """Define line by its slope and x-intercept"""

    # y-intercept - set to None if slope undefined
    try:
        y_intercept = -slope * x_intercept
    except TypeError:
        y_intercept = None

    return Line(slope=slope, y_intercept=y_intercept, x_intercept=x_intercept)


def get_intersection(line_1: Line, line_2: Line) -> tuple:
    """Get point of intersection between two lines"""

    # Case 0 - both lines are horizontal
    if (line_1.slope == 0) and (line_2.slope == 0):
        return None

    # Case 1 - both slopes are defined
    if (line_1.slope is not None) and (line_2.slope is not None):
        x = (line_2.y_intercept - line_1.y_intercept) / (line_1.slope - line_2.slope)
        y = (line_1.slope * x) + line_1.y_intercept
        return x, y

    # Case 2 - line 1's slope is undefined, line 2's slope is defined
    elif (line_1.slope is None) and (line_2.slope is not None):
        x = line_1.x_intercept
        y = (line_2.slope * x) + line_2.y_intercept
        return x, y

    # Case 3 - line 1's slope is defined, line 2's slope is undefined
    elif (line_1.slope is not None) and (line_2.slope is None):
        x = line_2.x_intercept
        y = (line_1.slope * x) + line_1.y_intercept
        return x, y

    # Case 4 - both lines have undefined slopes - lines are either coincident or never intersect
    elif (line_1.slope is None) and (line_2.slope is None):
        return None

    else:
        raise Exception("Unhandled case")


def get_new_breakpoint(slope, x_intercept, max_available) -> float:
    """Compute new (lower/upper) breakpoint"""

    # Y-axis intercept
    try:
        y_intercept = -slope * x_intercept
        return (max_available - y_intercept) / slope

    # If line is vertical or horizontal, return original x-intercept
    except (TypeError, ZeroDivisionError):
        return x_intercept


# =============================================================================
# FCAS TRAPEZIUM SCALING
# =============================================================================


def apply_agc_enablement_limit_scaling(
    trapezium: FCASTrapezium, agc_enablement_min: float, agc_enablement_max: float
) -> FCASTrapezium:

    # New enablement min and max
    new_enablement_min = (
        trapezium.enablement_min
        if (agc_enablement_min is None)
        else max(trapezium.enablement_min, agc_enablement_min)
    )

    new_enablement_max = (
        trapezium.enablement_max
        if (agc_enablement_max is None)
        else min(trapezium.enablement_max, agc_enablement_max)
    )

    # Get lower slope of FCAS trapezium
    low_breakpoint_minus_enablement_min = trapezium.low_breakpoint - trapezium.enablement_min
    lower_slope = (
        None
        if low_breakpoint_minus_enablement_min == 0
        else trapezium.max_avail / low_breakpoint_minus_enablement_min
    )
    lower_slope_line = get_line_from_slope_and_x_intercept(
        slope=lower_slope, x_intercept=new_enablement_min
    )

    # Get upper slope of FCAS trapezium
    high_breakpoint_minus_enablement_max = trapezium.high_breakpoint - trapezium.enablement_max
    upper_slope = (
        None
        if high_breakpoint_minus_enablement_max == 0
        else trapezium.max_avail / high_breakpoint_minus_enablement_max
    )
    upper_slope_line = get_line_from_slope_and_x_intercept(
        slope=upper_slope, x_intercept=new_enablement_max
    )

    # Intersection between LHS and RHS lines
    intersection = get_intersection(line_1=lower_slope_line, line_2=upper_slope_line)

    new_max_avail = (
        min(intersection[1], trapezium.max_avail)
        if intersection is not None
        else trapezium.max_avail
    )

    # Calculate new low and high breakpoints
    new_low_breakpoint = get_new_breakpoint(
        slope=lower_slope_line.slope,
        x_intercept=lower_slope_line.x_intercept,
        max_available=new_max_avail,
    )

    new_high_breakpoint = get_new_breakpoint(
        slope=upper_slope_line.slope,
        x_intercept=upper_slope_line.x_intercept,
        max_available=new_max_avail,
    )

    new_trapezium = FCASTrapezium(
        trade_type=trapezium.trade_type,
        direction=trapezium.direction,
        enablement_min=new_enablement_min,
        enablement_max=new_enablement_max,
        low_breakpoint=new_low_breakpoint,
        high_breakpoint=new_high_breakpoint,
        max_avail=new_max_avail,
    )

    return new_trapezium


def apply_agc_ramp_rate_scaling(
    trapezium: FCASTrapezium,
    scada_ramp_rate: float | None,
) -> FCASTrapezium:
    """Apply AGC ramp rate scaling to trapezium"""

    # Return input trapezium if scada_ramp_rate is None or 0 (from docs)
    if (scada_ramp_rate is None) or (scada_ramp_rate == 0):
        return trapezium

    new_max_avail = min([trapezium.max_avail, scada_ramp_rate / 12])

    # No scaling applied if max available is greater than or equal to the original max available
    if new_max_avail >= trapezium.max_avail:
        return trapezium

    # Low breakpoint calculation
    low_breakpoint_minus_enablement_min = trapezium.low_breakpoint - trapezium.enablement_min
    new_low_breakpoint = (
        get_new_breakpoint(
            slope=trapezium.max_avail / low_breakpoint_minus_enablement_min,
            x_intercept=trapezium.enablement_min,
            max_available=new_max_avail,
        )
        if low_breakpoint_minus_enablement_min != 0
        else trapezium.low_breakpoint
    )

    high_breakpoint_minus_enablement_max = trapezium.high_breakpoint - trapezium.enablement_max
    new_high_breakpoint = (
        get_new_breakpoint(
            slope=trapezium.max_avail / high_breakpoint_minus_enablement_max,
            x_intercept=trapezium.enablement_max,
            max_available=new_max_avail,
        )
        if high_breakpoint_minus_enablement_max != 0
        else trapezium.high_breakpoint
    )

    new_trapezium = FCASTrapezium(
        trade_type=trapezium.trade_type,
        direction=trapezium.direction,
        enablement_min=trapezium.enablement_min,
        enablement_max=trapezium.enablement_max,
        low_breakpoint=new_low_breakpoint,
        high_breakpoint=new_high_breakpoint,
        max_avail=new_max_avail,
    )

    return new_trapezium


def apply_uigf_scaling(trapezium: FCASTrapezium, uigf: float | None) -> FCASTrapezium:

    # No scaling applied if UIGF is absent
    if uigf is None:
        return trapezium

    new_enablement_max = min(trapezium.enablement_max, uigf)

    high_breakpoint_minus_enablement_max = trapezium.high_breakpoint - trapezium.enablement_max

    new_high_breakpoint = (
        get_new_breakpoint(
            slope=trapezium.max_avail / high_breakpoint_minus_enablement_max,
            x_intercept=new_enablement_max,
            max_available=trapezium.max_avail,
        )
        if high_breakpoint_minus_enablement_max != 0
        else trapezium.high_breakpoint
    )

    new_trapezium = FCASTrapezium(
        trade_type=trapezium.trade_type,
        direction=trapezium.direction,
        enablement_min=trapezium.enablement_min,
        enablement_max=new_enablement_max,
        low_breakpoint=trapezium.low_breakpoint,
        high_breakpoint=new_high_breakpoint,
        max_avail=trapezium.max_avail,
    )

    return new_trapezium


def apply_fcas_trapezium_scaling(
    trapezium: FCASTrapezium,
    trader_type: TraderType,
    trade_type: TradeType,
    agc_enablement_min: float | None,
    agc_enablement_max: float | None,
    scada_ramp_up_rate: float | None,
    scada_ramp_dn_rate: float | None,
    uigf: float | None,
) -> FCASTrapezium:
    """Apply scaling to trapezium based on AGC enablement limits and UIGF"""

    # Apply scaling for regulation offers
    if trade_type in [TradeType.L5RE, TradeType.R5RE]:
        trapezium = apply_agc_enablement_limit_scaling(
            trapezium=trapezium,
            agc_enablement_min=agc_enablement_min,
            agc_enablement_max=agc_enablement_max,
        )

        # AGC ramp rate for generators, bi-diretional units, and wholesale
        # demand response units. Increasing generation increases frequency,
        # and reducing load increases frequency.
        if (trader_type in [TraderType.Generator, TraderType.Bidirectional, TraderType.Wdr]) and (
            trapezium.trade_type == TradeType.R5RE
        ):
            trapezium = apply_agc_ramp_rate_scaling(
                trapezium=trapezium, scada_ramp_rate=scada_ramp_up_rate
            )

        elif (
            (trader_type in [TraderType.Generator, TraderType.Bidirectional, TraderType.Wdr])
            and (trapezium.trade_type == TradeType.L5RE)
            or (trader_type in [TraderType.Load, TraderType.NormallyOnLoad])
            and (trapezium.trade_type == TradeType.R5RE)
        ):
            trapezium = apply_agc_ramp_rate_scaling(
                trapezium=trapezium, scada_ramp_rate=scada_ramp_dn_rate
            )

        elif (trader_type in [TraderType.Load, TraderType.NormallyOnLoad]) and (
            trapezium.trade_type == TradeType.L5RE
        ):
            trapezium = apply_agc_ramp_rate_scaling(
                trapezium=trapezium, scada_ramp_rate=scada_ramp_up_rate
            )

    # Apply UIGF scaling for both regulation and contingency offers
    trapezium = apply_uigf_scaling(trapezium=trapezium, uigf=uigf)

    return trapezium


# =============================================================================
# FCAS AVAILABILITY LOGIC
# =============================================================================


def _get_energy_bid(trader: Trader) -> Bid | None:
    """Get the energy max availability bid for a trader.

    Args:
        trader: Trader object containing bids

    Returns:
        Energy max availability bid (ENOF or LDOF) if found, None otherwise

    Raises:
        Exception: If multiple energy max availability bids are found
    """
    energy_bids = [
        i for i in trader.bids if i.trade_type in [TradeType.ENOF, TradeType.LDOF, TradeType.DROF]
    ]

    if len(energy_bids) > 1:
        raise Exception("Multiple energy max availability bids found")

    return energy_bids[0] if energy_bids else None


def _get_bidirectional_energy_bid(trader: Trader, direction: BidDirection) -> Bid:
    """Get the BDOF bid for a specific direction from a bidirectional trader.

    Args:
        trader: Bidirectional trader object
        direction: Bid direction (Load or Gen)

    Returns:
        BDOF bid for the specified direction

    Raises:
        Exception: If no BDOF bid found for the specified direction
    """
    bids = [i for i in trader.bids if i.trade_type == TradeType.BDOF and i.direction == direction]

    if not bids:
        raise Exception(f"No BDOF bid found for direction {direction}")

    if len(bids) > 1:
        raise Exception(f"Multiple BDOF bids found for direction {direction}")

    return bids[0]


def _check_energy_availability_constraint(trader: Trader, bid: Bid, use_uigf: bool = False) -> bool:
    """Check if energy max availability meets FCAS enablement requirement.

    For semi-scheduled generators, considers UIGF constraint. For other units,
    checks if energy max availability is sufficient for FCAS enablement.

    Args:
        trader: Trader object with energy and FCAS bids
        bid: FCAS bid to check
        use_uigf: Whether to apply UIGF constraint (for semi-scheduled generators)

    Returns:
        True if energy availability constraint is satisfied, False otherwise
    """
    energy_bid = _get_energy_bid(trader=trader)

    # Unit only has FCAS bids, no energy max availability bid
    if energy_bid is None:
        return True

    if use_uigf:
        effective_max_avail = min(energy_bid.max_avail, zero_if_null(x=trader.uigf))
    else:
        effective_max_avail = energy_bid.max_avail

    return effective_max_avail >= bid.scaled_fcas_trapezium.enablement_min


def _get_regulation_fcas_bid(trader: Trader, trade_type: TradeType, direction: BidDirection) -> Bid:
    """Get regulation FCAS bid for a specific direction and trade type.

    Args:
        trader: Trader object containing regulation FCAS bids
        trade_type: FCAS trade type (e.g., L5RE, R5RE)
        direction: Bid direction (Load or Gen)

    Returns:
        Regulation FCAS bid matching trade type and direction

    Raises:
        Exception: If multiple matching bids found or no bid found
    """
    bids = [i for i in trader.bids if i.direction == direction and i.trade_type == trade_type]

    if len(bids) > 1:
        raise Exception(f"Multiple {direction} bids found for trade type {trade_type}")

    if not bids:
        raise Exception(f"No {direction} bid found for trade type {trade_type}")

    return bids[0]


def fcas_flag_condition_3(trader: Trader, bid: Bid) -> bool:
    """Condition 3 for FCAS flag determination.

    Checks if the FCAS trapezium straddles zero MW for regulation FCAS services.
    For bidirectional units, applies direction-specific constraints.

    Args:
        trader: Trader object with trader type information
        bid: FCAS bid to evaluate

    Returns:
        True if condition 3 is satisfied, False otherwise
    """

    if bid.trade_type not in REGULATION_FCAS_TRADE_TYPES:
        return True

    # For regulation FCAS bids on the load side of bi-directional units
    # - FCAS EnablementMin (load) <= 0
    if trader.trader_type == TraderType.Bidirectional and bid.direction == BidDirection.Load:
        return bid.enablement_min <= 0

    # For regulation FCAS bids on the generation side of bidirectional units,
    # and for all FCAS bids from non-bidirectional units
    # - FCAS EnablementMax >= 0
    if trader.trader_type == TraderType.Bidirectional and bid.direction == BidDirection.Gen:
        return bid.enablement_max >= 0

    if trader.trader_type != TraderType.Bidirectional:
        return bid.enablement_max >= 0

    # For regulation FCAS bids on the generation side from bidirectional units,
    # FCAS EnablementMin and FCAS EnablementMax may be negative, positive, or zero.
    raise Exception("Unhandled case")


def fcas_flag_condition_4(trader: Trader, bid: Bid) -> bool:
    """Condition 4 for FCAS flag determination.

    Checks if energy max availability allows the unit to operate within the FCAS
    trapezium for the service. For semi-scheduled generators, considers UIGF constraint.
    For bidirectional units, checks both load and generation side constraints.

    Args:
        trader: Trader object with energy bids and trader attributes
        bid: FCAS bid to evaluate

    Returns:
        True if condition 4 is satisfied, False otherwise
    """

    # Unit must be AGC enabled to be eligible for regulation FCAS
    if (trader.agc_status == "0") and (bid.trade_type in REGULATION_FCAS_TRADE_TYPES):
        return False

    # For scheduled generating units, scheduled loads, and wholesale demand response units:
    # - Energy Max Availability >= FCAS EnablementMin
    # For semi-scheduled generating units:
    # - min(Energy Max Availability, UIGF) >= FCAS EnablementMin
    if trader.trader_type in [
        TraderType.Generator,
        TraderType.Load,
        TraderType.NormallyOnLoad,
        TraderType.Wdr,
    ]:
        # Semi-scheduled generators need UIGF consideration
        use_uigf = trader.trader_type == TraderType.Generator and trader.semi_dispatch == "1"
        return _check_energy_availability_constraint(trader=trader, bid=bid, use_uigf=use_uigf)

    # For bidirectional units offering regulation FCAS on the load side:
    # - Energy Max Availability (load) <= FCAS Enablement Max (load)
    # For bidirectional units offering regulation FCAS on the generation side:
    # - Energy Max Availability (generation) >= FCAS Enablement Min (generation)
    if (
        trader.trader_type == TraderType.Bidirectional
        and bid.trade_type in REGULATION_FCAS_TRADE_TYPES
    ):
        if bid.direction == BidDirection.Load:
            load_bid = _get_bidirectional_energy_bid(trader=trader, direction=BidDirection.Load)
            return -load_bid.max_avail <= bid.scaled_fcas_trapezium.enablement_max
        else:  # GEN
            gen_bid = _get_bidirectional_energy_bid(trader=trader, direction=BidDirection.Gen)
            return gen_bid.max_avail >= bid.scaled_fcas_trapezium.enablement_min

    # For bidirectional units offering contingency FCAS:
    # - Energy Max Availability (load) <= FCAS Enablement Max
    # - Energy Max Availability (generation) >= FCAS Enablement Min
    if (
        trader.trader_type == TraderType.Bidirectional
        and bid.trade_type in CONTINGENCY_FCAS_TRADE_TYPES
    ):
        load_bid = _get_bidirectional_energy_bid(trader=trader, direction=BidDirection.Load)
        gen_bid = _get_bidirectional_energy_bid(trader=trader, direction=BidDirection.Gen)

        return (
            -load_bid.max_avail <= bid.scaled_fcas_trapezium.enablement_max
            and gen_bid.max_avail >= bid.scaled_fcas_trapezium.enablement_min
        )

    raise Exception("Unhandled case")


def fcas_flag_condition_5(trader: Trader, bid: Bid) -> bool:
    """Condition 5 for FCAS flag determination.

    Checks if the unit is operating between FCAS enablement min and max at the
    start of the interval. Units "stranded outside" the FCAS trapezium cannot
    be enabled for FCAS.

    Args:
        trader: Trader object with initial MW
        bid: FCAS bid to evaluate

    Returns:
        True if condition 5 is satisfied, False otherwise
    """

    # The unit is operating between FCAS enablement min and max at the start of the interval.

    # For scheduled and semi-scheduled generating units, scheduled loads, and wholesale
    # demand response units:
    # - FCAS Enablement Min <= Max(Initial MW, 0) <= FCAS Enablement Max
    if trader.trader_type in [TraderType.Generator, TraderType.Load, TraderType.Wdr]:
        return (
            bid.scaled_fcas_trapezium.enablement_min
            <= max(trader.initial_mw, 0)
            <= bid.scaled_fcas_trapezium.enablement_max
        )

    # For bidirectional units offering regulation FCAS on both the generation and load sides:
    # - FCAS Enablement Min (load) <= InitialMW <= FCAS Enablement Max (generation)
    if (
        trader.trader_type == TraderType.Bidirectional
        and bid.trade_type in REGULATION_FCAS_TRADE_TYPES
    ):
        load_bid = _get_regulation_fcas_bid(
            trader=trader, trade_type=bid.trade_type, direction=BidDirection.Load
        )
        gen_bid = _get_regulation_fcas_bid(
            trader=trader, trade_type=bid.trade_type, direction=BidDirection.Gen
        )

        if (
            gen_bid.scaled_fcas_trapezium.max_avail > 0
            and load_bid.scaled_fcas_trapezium.max_avail > 0
        ):
            return (
                load_bid.scaled_fcas_trapezium.enablement_min
                <= trader.initial_mw
                <= gen_bid.scaled_fcas_trapezium.enablement_max
            )

    # For all other types of FCAS bids from bidirectional units:
    # - FCAS Enablement Min <= InitialMW <= FCAS Enablement Max

    # If the unit is operating at energy level outside the Enablement Min and Enablement Max
    # of an FCAS trapezium at the start of an interval cannot be enabled for FCAS. This is
    # referred to as being "stranded outside" the FCAS trapezium.
    return (
        bid.scaled_fcas_trapezium.enablement_min
        <= trader.initial_mw
        <= bid.scaled_fcas_trapezium.enablement_max
    )


def is_fcas_available(trader: Trader, bid: Bid) -> int:
    """Determine if FCAS service is available for a trader's bid.

    Evaluates all five NEMDE FCAS flag conditions to determine if the trader
    can be enabled for the specified FCAS service. Returns the logical AND of
    all five conditions.

    The five conditions are:
    1. Maximum availability > 0
    2. At least one bid band has capacity > 0
    3. FCAS trapezium straddles zero MW (for regulation services)
    4. Energy max availability allows operation within FCAS trapezium
    5. Unit is operating within FCAS trapezium at interval start

    Args:
        trader: Trader object with bids and attributes
        bid: Bid to evaluate for FCAS availability

    Returns:
        True if FCAS is available, False otherwise, or None if not an FCAS trade type
    """

    if bid.trade_type not in FCAS_TRADE_TYPES:
        return None

    # After FCAS trapezium scaling, a scheduled or semi-scheduled generating unit,
    # scheduled bidirectional unit, scheduled load, or wholesale demand response unit
    # is considered for enablement for a particular FCAS service if the following
    # conditions are met:

    # Condition 1
    # Maximum availability is greater than zero
    condition_1 = bid.max_avail > 0

    # Condition 2
    # At least one of the bid price bands has capacity greater than zero
    condition_2 = any(band.quantity > 0 for band in bid.bid_bands)

    condition_3 = fcas_flag_condition_3(trader=trader, bid=bid)

    condition_4 = fcas_flag_condition_4(trader=trader, bid=bid)

    condition_5 = fcas_flag_condition_5(trader=trader, bid=bid)

    return condition_1 and condition_2 and condition_3 and condition_4 and condition_5


def get_case_parameters(casefile: dict) -> CaseParameters:
    """Extract case parameters from casefile data.

    Args:
        casefile: NEMDE casefile dictionary
    Returns:
        Dictionary of case parameters
    """
    parameters = casefile["NEMSPDCaseFile"]["NemSpdInputs"]["Case"]

    return CaseParameters(
        case_id=parameters["@CaseID"],
        case_type=parameters["@CaseType"],
        intervention="0" if parameters["@Intervention"] == "False" else "1",
        voll=to_float(parameters["@VoLL"]),
        mpf=to_float(parameters["@MPF"]),
        energy_deficit_price=to_float(parameters["@EnergyDeficitPrice"]),
        energy_surplus_price=to_float(parameters["@EnergySurplusPrice"]),
        ramp_rate_price=to_float(parameters["@RampRatePrice"]),
        interconnector_price=to_float(parameters["@InterconnectorPrice"]),
        capacity_price=to_float(parameters["@CapacityPrice"]),
        min_energy_limit_price=to_float(parameters.get("@MinEnergyLimitPrice", 0)),
        max_energy_limit_price=to_float(parameters.get("@MaxEnergyLimitPrice", 0)),
        offer_price=to_float(parameters["@OfferPrice"]),
        tie_break_price=to_float(parameters["@TieBreakPrice"]),
        generic_constraint_price=to_float(parameters["@GenericConstraintPrice"]),
        npl_threshold=to_float(parameters["@NPLThreshold"]),
        mnsp_losses_price=to_float(parameters["@MNSPLossesPrice"]),
        mnsp_offer_price=to_float(parameters["@MNSPOfferPrice"]),
        mnsp_ramp_rate_price=to_float(parameters["@MNSPRampRatePrice"]),
        mnsp_capacity_price=to_float(parameters["@MNSPCapacityPrice"]),
        fast_start_price=to_float(parameters["@FastStartPrice"]),
        satisfactory_network_price=to_float(parameters["@Satisfactory_Network_Price"]),
        fast_start_threshold=to_float(parameters["@FastStartThreshold"]),
        switch_run_initial_status=to_float(parameters["@SwitchRunInitialStatus"]),
        uigf_surplus_price=to_float(parameters["@UIGFSurplusPrice"]),
        uigf_atime=to_float(parameters["@UIGF_ATime"]),
        use_sos2_loss_model=to_float(parameters["@UseSOS2LossModel"]),
        energy_limit_price=to_float(parameters.get("@EnergyLimitPrice", 0)),
        as_profile_price=to_float(parameters["@ASProfilePrice"]),
        as_max_avail_price=to_float(parameters["@ASMaxAvailPrice"]),
        as_enablement_min_price=to_float(parameters["@ASEnablementMinPrice"]),
        as_enablement_max_price=to_float(parameters["@ASEnablementMaxPrice"]),
    )


# =============================================================================
# COMPOSITE RAMP RATES FOR BIDIRECTIONAL UNITS
# =============================================================================


def get_composite_up_ramp_rate(
    initial_mw: float,
    gen_bid_ramp_up_rate: float,
    load_bid_ramp_down_rate: float,
    dispatch_period: float = 5.0,
) -> float:
    """Calculate composite up ramp rate for bidirectional units.

    Bidirectional units can submit different ramp rates for generation and consumption sides.
    NEMDE uses a composite ramp rate when the unit may move between generation and consumption
    during a trading interval.

    Args:
        initial_mw: Initial MW output (positive for generation, negative for consumption)
        gen_bid_ramp_up_rate: Generation side ramp up rate (MW/min)
        load_bid_ramp_down_rate: Load side ramp down rate (MW/min)
        dispatch_period: Dispatch period in hours (default: 5 min)

    Returns:
        Composite up ramp rate (MW/min)
    """
    if initial_mw >= 0:
        return gen_bid_ramp_up_rate
    elif load_bid_ramp_down_rate == 0:
        return 0
    elif abs(initial_mw / load_bid_ramp_down_rate) >= dispatch_period:
        return load_bid_ramp_down_rate
    else:
        return (
            (dispatch_period - abs(initial_mw / load_bid_ramp_down_rate)) * gen_bid_ramp_up_rate
            - initial_mw
        ) / dispatch_period


def get_composite_down_ramp_rate(
    initial_mw: float,
    gen_bid_ramp_down_rate: float,
    load_bid_ramp_up_rate: float,
    dispatch_period: float = 5.0,
) -> float:
    """Calculate composite down ramp rate for bidirectional units.

    Bidirectional units can submit different ramp rates for generation and consumption sides.
    NEMDE uses a composite ramp rate when the unit may move between generation and consumption
    during a trading interval.

    Args:
        initial_mw: Initial MW output (positive for generation, negative for consumption)
        gen_bid_ramp_down_rate: Generation side ramp down rate (MW/min)
        load_bid_ramp_up_rate: Load side ramp up rate (MW/min)
        dispatch_period: Dispatch period in minutes (default: 5.0)

    Returns:
        Composite down ramp rate (MW/min)
    """
    if initial_mw <= 0:
        return load_bid_ramp_up_rate
    elif gen_bid_ramp_down_rate == 0:
        return 0
    elif abs(initial_mw / gen_bid_ramp_down_rate) >= dispatch_period:
        return gen_bid_ramp_down_rate
    else:
        return (
            (dispatch_period - abs(initial_mw / gen_bid_ramp_down_rate)) * load_bid_ramp_up_rate
            + initial_mw
        ) / dispatch_period


def get_trader_effective_ramp_up_rate(trader: Trader) -> dict:
    """
    Compute effective ramp-up rate. Min of energy offer ramp rate and SCADA
    ramp rate. Some traders do not have ramp rates specified and have None
    corresponding to their ramp rate.
    """

    if trader.trader_type == TraderType.Bidirectional:
        gen_offer = [
            i
            for i in trader.bids
            if i.trade_type == TradeType.BDOF and i.direction == BidDirection.Gen
        ][0]
        load_offer = [
            i
            for i in trader.bids
            if i.trade_type == TradeType.BDOF and i.direction == BidDirection.Load
        ][0]

        composite_ramp_up_rate = get_composite_up_ramp_rate(
            initial_mw=trader.initial_mw,
            gen_bid_ramp_up_rate=gen_offer.ramp_up_rate,
            load_bid_ramp_down_rate=load_offer.ramp_dn_rate,
        )
        return min(r for r in [composite_ramp_up_rate, trader.scada_ramp_up_rate] if r is not None)

    if trader.trader_type in [
        TraderType.Generator,
        TraderType.Load,
        TraderType.NormallyOnLoad,
        TraderType.Wdr,
    ]:
        energy_bid = _get_energy_bid(trader=trader)
        ramp_rates = [
            i
            for i in [
                energy_bid.ramp_up_rate if energy_bid else None,
                trader.scada_ramp_up_rate,
            ]
            if i is not None
        ]

        return min(ramp_rates) if ramp_rates else None

    raise Exception("Unhandled trader type")


def get_trader_effective_ramp_dn_rate(trader: Trader) -> dict:
    """
    Compute effective ramp-down rate. Min of energy offer ramp rate and SCADA
    ramp rate. Some traders do not have ramp rates specified and have None
    corresponding to their ramp rate.
    """

    if trader.trader_type == TraderType.Bidirectional:
        gen_offer = [
            i
            for i in trader.bids
            if i.trade_type == TradeType.BDOF and i.direction == BidDirection.Gen
        ][0]
        load_offer = [
            i
            for i in trader.bids
            if i.trade_type == TradeType.BDOF and i.direction == BidDirection.Load
        ][0]

        composite_ramp_down_rate = get_composite_down_ramp_rate(
            initial_mw=trader.initial_mw,
            gen_bid_ramp_down_rate=gen_offer.ramp_dn_rate,
            load_bid_ramp_up_rate=load_offer.ramp_up_rate,
        )
        return min(
            r for r in [composite_ramp_down_rate, trader.scada_ramp_dn_rate] if r is not None
        )

    if trader.trader_type in [
        TraderType.Generator,
        TraderType.Load,
        TraderType.NormallyOnLoad,
        TraderType.Wdr,
    ]:
        energy_bid = _get_energy_bid(trader=trader)
        ramp_rates = [
            i
            for i in [
                energy_bid.ramp_dn_rate if energy_bid else None,
                trader.scada_ramp_dn_rate,
            ]
            if i is not None
        ]

        return min(ramp_rates) if ramp_rates else None

    raise Exception("Unhandled trader type")


def get_parsed_interconnector_loss_model_segments(
    interconnector: Interconnector,
) -> list:
    """
    Use breakpoints and segment factors to construct a new start-end-factor
    representation for a given interconnector's MLF curve segments

    Parameters
    ----------
    data : dict
        NEMDE casefile

    interconnector_id : str
        Interconnector ID

    Returns
    -------
    new_segments : list
        Loss model segments in a start-end-factor representation
        E.g. [{'start': float, 'end': float, 'factor': float}, ...]
    """

    # Lower bound for loss model
    loss_lower_limit = interconnector.loss_lower_limit
    segments = interconnector.loss_model_segments

    # First segment set equal to loss lower limit
    start = -loss_lower_limit

    # Format segments with start, end, and factor
    new_segments = []
    for s in segments:
        segment = {"start": start, "end": s.limit, "factor": s.factor}
        start = s.limit
        new_segments.append(segment)

    return new_segments


def get_interconnector_loss_estimate(interconnector: Interconnector, flow: float) -> float:
    """
    Estimate interconnector loss by numerically integrating loss model segments

    Parameters
    ----------
    data : dict
        NEMDE casefile

    interconnector_id : str
        Interconnector ID

    flow : float
        Flow over interconnector (MW)

    Returns
    -------
    total_area : float
        Total area under MLF curve corresponds to total loss (MW)
    """

    # Only considering the non-intervention pricing scenario for now; an
    # intervention case would use what-if initial MW.
    # Construct segments based on loss model
    segments = get_parsed_interconnector_loss_model_segments(interconnector=interconnector)

    # Initialise total area
    total_area = 0
    for s in segments:
        if flow > 0:
            # Only want segments to right of origin
            if s["end"] <= 0 or s["start"] > flow:
                proportion = 0

            # Take positive part of segment if segment crosses origin
            elif (s["start"] < 0) and (s["end"] > 0):
                # Part of segment that is positive
                positive_proportion = s["end"] / (s["end"] - s["start"])

                # Flow proportion (if flow close to zero)
                flow_proportion = flow / (s["end"] - s["start"])

                # Take min value
                proportion = min(positive_proportion, flow_proportion)

            # If flow within segment
            elif (flow >= s["start"]) and (flow <= s["end"]):
                # Segment proportion
                proportion = (flow - s["start"]) / (s["end"] - s["start"])

            # Use full segment if flow greater than end of segment - use full segment
            elif flow > s["end"]:
                proportion = 1

            else:
                raise Exception("Unhandled case")

            # Compute block area
            area = (s["end"] - s["start"]) * s["factor"] * proportion

            # Update total area
            total_area += area

        # Flow is <= 0
        else:
            # Only want segments to left of origin
            if s["start"] >= 0 or s["end"] < flow:
                proportion = 0

            # Take negative part of segment if segment crosses origin
            elif (s["start"] < 0) and (s["end"] > 0):
                # Part of segment that is negative
                negative_proportion = -s["start"] / (s["end"] - s["start"])

                # Flow proportion (if flow close to zero)
                flow_proportion = -flow / (s["end"] - s["start"])

                # Take min value
                proportion = min(negative_proportion, flow_proportion)

            # If flow within segment
            elif (flow >= s["start"]) and (flow <= s["end"]):
                # Segment proportion
                proportion = -1 * (flow - s["end"]) / (s["end"] - s["start"])

            # Use full segment if flow less than start of segment - use full segment
            elif flow <= s["start"]:
                proportion = 1

            else:
                raise Exception("Unhandled case")

            # Compute block area
            area = -1 * (s["end"] - s["start"]) * s["factor"] * proportion

            # Update total area
            total_area += area

    return total_area


def get_mnsp_region_loss_indicator(
    interconnector: Interconnector, region_id: RegionId, intervention: str
) -> int:
    """
    Get region loss indicator. =1 if FromRegion and InitialMW >= 0,
    or if ToRegion and InitialMW < 0, else =0
    """

    if interconnector.mnsp_status != "1":
        raise Exception("Interconnector is not MNSP")

    # Only considering non-intervention pricing scenario for now.
    # Use what-if initial MW if intervention case.
    # TODO: need to update to handle intervention scenario
    initial_mw = (
        interconnector.initial_mw if intervention == "0" else interconnector.what_if_initial_mw
    )

    # Loss applied to FromRegion
    if (
        (region_id == interconnector.from_region)
        and (initial_mw >= 0)
        or (region_id == interconnector.to_region)
        and (initial_mw < 0)
    ):
        return 1

    else:
        return 0


def get_trader_target(trader: Trader) -> list:
    # Only handling non-intervention scenario for now
    # TODO: need to update to handle intervention scenario
    solution = [i for i in trader.nemde_solution if i.intervention == "0"][0]
    return {
        (trader.trader_id, "ENERGY_TARGET"): solution.energy_target,
        (trader.trader_id, "R1SE"): solution.r1_target,
        (trader.trader_id, "R6SE"): solution.r6_target,
        (trader.trader_id, "R60S"): solution.r60_target,
        (trader.trader_id, "R5MI"): solution.r5_target,
        (trader.trader_id, "R5RE"): solution.r5_reg_target,
        (trader.trader_id, "L1SE"): solution.l1_target,
        (trader.trader_id, "L6SE"): solution.l6_target,
        (trader.trader_id, "L60S"): solution.l60_target,
        (trader.trader_id, "L5MI"): solution.l5_target,
        (trader.trader_id, "L5RE"): solution.l5_reg_target,
    }


def fcas_is_available_and_has_energy_offer(trader: Trader, bid: Bid) -> bool:
    """
    Check if trader has an energy offer and FCAS is available for the given bid.
    """

    if trader.trader_type == TraderType.Generator:
        energy_offer_trade_type = TradeType.ENOF
    elif trader.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]:
        energy_offer_trade_type = TradeType.LDOF
    elif trader.trader_type == TraderType.Bidirectional:
        energy_offer_trade_type = TradeType.BDOF
    else:
        raise Exception("Unhandled trader type")

    has_energy_offer = len([b for b in trader.bids if b.trade_type == energy_offer_trade_type]) > 0
    fcas_available = is_fcas_available(trader=trader, bid=bid)
    return has_energy_offer and fcas_available


def has_trade_type(trader: Trader, trade_type: TradeType, direction: BidDirection) -> bool:
    return (
        len([b for b in trader.bids if b.trade_type == trade_type and b.direction == direction]) > 0
    )


def construct_case(data, mode) -> dict:  # noqa: ARG001 -- `mode` is reserved, see docstring
    """Assemble the model's input dict from a NEMDE casefile.

    The returned dict is the entire contract between this module and model.py,
    which reads it by string key. model.py never uses `data.get(...)`, so a key
    that goes missing here raises there rather than degrading into an empty Set.

    Parameters
    ----------
    data : dict
        NEMDE casefile, xmltodict-shaped (see casefile_io.normalize_casefile).
    mode : str
        Reserved for intervention handling. Only the non-intervention pricing
        scenario is built today -- every comprehension below filters on
        `intervention == "0"` -- so this argument is currently unused.

    Returns
    -------
    case : dict
        Dictionary containing case data to be read into model
    """

    case_parameters = get_case_parameters(casefile=data)
    regions = get_region_objects(casefile=data)
    traders = get_trader_objects(casefile=data)
    interconnectors = get_interconnector_objects(casefile=data)
    generic_constraints = get_generic_constraint_objects(casefile=data)

    case = {
        "S_REGIONS": [i.region_id for i in regions],
        "S_TRADERS": [trader.trader_id for trader in traders],
        "S_TRADERS_SEMI_DISPATCH": [
            trader.trader_id for trader in traders if trader.semi_dispatch == "1"
        ],
        "S_TRADER_OFFERS": [
            (trader.trader_id, bid.trade_type, bid.direction)
            for trader in traders
            for bid in trader.bids
        ],
        "S_TRADER_TOTAL_OFFERS": [
            (trader.trader_id, bid.trade_type) for trader in traders for bid in trader.bids
        ],
        "S_TRADER_ENERGY_OFFERS": [
            (trader.trader_id, bid.trade_type, bid.direction)
            for trader in traders
            for bid in trader.bids
            if bid.trade_type in [TradeType.ENOF, TradeType.LDOF, TradeType.DROF, TradeType.BDOF]
        ],
        "S_TRADER_FCAS_OFFERS": [
            (trader.trader_id, bid.trade_type, bid.direction)
            for trader in traders
            for bid in trader.bids
            if bid.trade_type in FCAS_TRADE_TYPES
        ],
        "S_TRADER_FAST_START": [
            trader.trader_id for trader in traders if trader.fast_start is not None
        ],
        "S_TRADERS_BIDIRECTIONAL": [
            trader.trader_id for trader in traders if trader.trader_type == TraderType.Bidirectional
        ],
        # FCAS joint ramping
        # AEMO fcas-model-in-nemde.pdf s6.1: joint ramping constraints are only
        # applied "if a unit has an energy bid, is enabled for regulating
        # services, and the AGC ramp up or down rate is greater than zero" --
        # traders missing (or with a non-positive) SCADA ramp rate for the
        # constraint's relevant direction must be excluded, otherwise
        # P_TRADER_SCADA_RAMP_UP/DN_RATE[i] is undefined at constraint build
        # time (that param dict only contains traders with a value).
        "S_TRADER_FCAS_JOINT_RAMPING_RAISE_GENERATOR_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type == TradeType.R5RE
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_up_rate is not None
            and i.scada_ramp_up_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_RAISE_LOAD_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Load
            and b.trade_type == TradeType.R5RE
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_dn_rate is not None
            and i.scada_ramp_dn_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_GEN_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type == TradeType.R5RE
            and b.direction == BidDirection.Gen
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_up_rate is not None
            and i.scada_ramp_up_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_RAISE_BIDIRECTIONAL_LOAD_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type == TradeType.R5RE
            and b.direction == BidDirection.Load
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_dn_rate is not None
            and i.scada_ramp_dn_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_LOWER_GENERATOR_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type == TradeType.L5RE
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_dn_rate is not None
            and i.scada_ramp_dn_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_LOWER_LOAD_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Load
            and b.trade_type == TradeType.L5RE
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_up_rate is not None
            and i.scada_ramp_up_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_GEN_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.direction == BidDirection.Gen
            and b.trade_type == TradeType.L5RE
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_dn_rate is not None
            and i.scada_ramp_dn_rate > 0
        ],
        "S_TRADER_FCAS_JOINT_RAMPING_LOWER_BIDIRECTIONAL_LOAD_INDEX": [
            i.trader_id
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.direction == BidDirection.Load
            and b.trade_type == TradeType.L5RE
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
            and i.scada_ramp_dn_rate is not None
            and i.scada_ramp_dn_rate > 0
        ],
        # FCAS joint capacity constraints (upper slope)
        "S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITH_R5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in CONTINGENCY_RAISE_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.ENOF, direction=None)
            and has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_GENERATOR_WITHOUT_R5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in CONTINGENCY_RAISE_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.ENOF, direction=None)
            and not has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITH_L5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in CONTINGENCY_LOWER_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.LDOF, direction=None)
            and has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_LOAD_WITHOUT_L5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in CONTINGENCY_LOWER_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.LDOF, direction=None)
            and not has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITH_R5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type in CONTINGENCY_RAISE_FCAS_TRADE_TYPES
            and (
                has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Load)
            )
            and (
                has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=BidDirection.Load)
            )
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_UPPER_SLOPE_BIDIRECTIONAL_WITHOUT_R5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type in CONTINGENCY_RAISE_FCAS_TRADE_TYPES
            and (
                has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Load)
            )
            and not (
                has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=BidDirection.Load)
            )
            and is_fcas_available(trader=i, bid=b)
        ],
        # FCAS joint capacity constraints (lower slope)
        "S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITH_L5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in CONTINGENCY_LOWER_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.ENOF, direction=None)
            and has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_GENERATOR_WITHOUT_L5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in CONTINGENCY_LOWER_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.ENOF, direction=None)
            and not has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        # A LOAD's energy bid is LDOF, never ENOF -- these two tested for ENOF and so
        # were unconditionally empty, silently generating no lower-slope joint-capacity
        # constraints for any load. The upper-slope pair above is the correct template.
        "S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITH_R5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in CONTINGENCY_RAISE_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.LDOF, direction=None)
            and has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_LOAD_WITHOUT_R5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in CONTINGENCY_RAISE_FCAS_TRADE_TYPES
            and has_trade_type(trader=i, trade_type=TradeType.LDOF, direction=None)
            and not has_trade_type(trader=i, trade_type=TradeType.R5RE, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITH_L5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type in CONTINGENCY_LOWER_FCAS_TRADE_TYPES
            and (
                has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Load)
            )
            and (
                has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=BidDirection.Load)
            )
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_JOINT_CAPACITY_LOWER_SLOPE_BIDIRECTIONAL_WITHOUT_L5RE_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type in CONTINGENCY_LOWER_FCAS_TRADE_TYPES
            and (
                has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Load)
            )
            and not (
                has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=BidDirection.Gen)
                or has_trade_type(trader=i, trade_type=TradeType.L5RE, direction=BidDirection.Load)
            )
            and is_fcas_available(trader=i, bid=b)
        ],
        # Energy and regulating FCAS capacity constraints
        "S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_GENERATOR_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in [TradeType.R5RE, TradeType.L5RE]
            and has_trade_type(trader=i, trade_type=TradeType.ENOF, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENERGY_AND_REGULATING_UPPER_SLOPE_LOAD_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in [TradeType.R5RE, TradeType.L5RE]
            and has_trade_type(trader=i, trade_type=TradeType.LDOF, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_GENERATOR_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in [TradeType.R5RE, TradeType.L5RE]
            and has_trade_type(trader=i, trade_type=TradeType.ENOF, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENERGY_AND_REGULATING_LOWER_SLOPE_LOAD_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in [TradeType.R5RE, TradeType.L5RE]
            and has_trade_type(trader=i, trade_type=TradeType.LDOF, direction=None)
            and is_fcas_available(trader=i, bid=b)
        ],
        # BDU energy and regulating FCAS capacity constraints
        "S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_GEN_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type in [TradeType.R5RE, TradeType.L5RE]
            and b.direction == BidDirection.Gen
            and has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Gen)
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENERGY_AND_REGULATING_BDU_LOAD_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.trade_type in [TradeType.R5RE, TradeType.L5RE]
            and b.direction == BidDirection.Load
            and has_trade_type(trader=i, trade_type=TradeType.BDOF, direction=BidDirection.Load)
            and is_fcas_available(trader=i, bid=b)
        ],
        # BDU regulating FCAS SCADA capacity constraints
        "S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_UP_INDEX": list(
            set(
                i.trader_id
                for i in traders
                for b in i.bids
                if i.trader_type == TraderType.Bidirectional
                and b.trade_type == TradeType.R5RE
                # TODO: check whether an energy offer is required here. The FCAS
                # docs say yes, but it is not obvious that it should be.
                and is_fcas_available(trader=i, bid=b)
            )
        ),
        "S_TRADER_FCAS_BIDIRECTIONAL_SCADA_RAMPING_DOWN_INDEX": list(
            set(
                i.trader_id
                for i in traders
                for b in i.bids
                if i.trader_type == TraderType.Bidirectional
                and b.trade_type == TradeType.L5RE
                # TODO: check whether an energy offer is required here. The FCAS
                # docs say yes, but it is not obvious that it should be.
                and is_fcas_available(trader=i, bid=b)
            )
        ),
        # Enablement min and max
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_REGULATION_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in REGULATION_FCAS_TRADE_TYPES
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_GENERATOR_CONTINGENCY_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in CONTINGENCY_FCAS_TRADE_TYPES
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_REGULATION_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in REGULATION_FCAS_TRADE_TYPES
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_LOAD_CONTINGENCY_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in CONTINGENCY_FCAS_TRADE_TYPES
            and fcas_is_available_and_has_energy_offer(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_GEN_REGULATION_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.direction == BidDirection.Gen
            and b.trade_type in REGULATION_FCAS_TRADE_TYPES
            and is_fcas_available(trader=i, bid=b)
        ],
        # A BDU's contingency FCAS bid is "a bid for the entire unit"
        # (fcas-model-in-nemde.txt s2.4, Figure 5): one undirected trapezium whose
        # enablement limits sit on the unit's *net* energy axis, so the bid carries
        # no @Direction. Only regulation FCAS is split GEN/LOAD. Filtering these on
        # b.direction == GEN/LOAD (as this and its LOAD sibling used to) therefore
        # matched nothing, and BDU contingency offers got no enablement constraints
        # at all -- see C_FCAS_ENABLEMENT_{MIN,MAX}_BIDIRECTIONAL_CONTINGENCY.
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_CONTINGENCY_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.direction is None
            and b.trade_type in CONTINGENCY_FCAS_TRADE_TYPES
            and is_fcas_available(trader=i, bid=b)
        ],
        "S_TRADER_FCAS_ENABLEMENT_MIN_AND_MAX_BIDIRECTIONAL_LOAD_REGULATION_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Bidirectional
            and b.direction == BidDirection.Load
            and b.trade_type in REGULATION_FCAS_TRADE_TYPES
            and is_fcas_available(trader=i, bid=b)
        ],
        # Max available FCAS
        "S_TRADER_FCAS_MAX_AVAIL_GENERATOR_REGULATION_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator and b.trade_type in REGULATION_FCAS_TRADE_TYPES
        ],
        "S_TRADER_FCAS_MAX_AVAIL_GENERATOR_CONTINGENCY_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type == TraderType.Generator
            and b.trade_type in CONTINGENCY_FCAS_TRADE_TYPES
        ],
        "S_TRADER_FCAS_MAX_AVAIL_LOAD_REGULATION_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in REGULATION_FCAS_TRADE_TYPES
        ],
        "S_TRADER_FCAS_MAX_AVAIL_LOAD_CONTINGENCY_INDEX": [
            (i.trader_id, b.trade_type)
            for i in traders
            for b in i.bids
            if i.trader_type in [TraderType.Load, TraderType.NormallyOnLoad]
            and b.trade_type in CONTINGENCY_FCAS_TRADE_TYPES
        ],
        "S_TRADER_PRICE_TIED_GENERATORS": get_price_tied_bands(data, trade_type="ENOF"),
        "S_TRADER_PRICE_TIED_LOADS": get_price_tied_bands(data, trade_type="LDOF"),
        # TODO: Only handles the non-intervention scenario; needs updating to
        # handle the intervention scenario.
        "S_GENERIC_CONSTRAINTS": [
            gc.constraint_id for gc in generic_constraints if gc.intervention == "0"
        ],
        "S_GC_TRADER_VARS": list(
            set(
                (trader.trader_id, trader.trade_type)
                for gc in generic_constraints
                for trader in gc.lhs_factor_collection.trader_factors
                if gc.intervention == "0"
            )
        ),
        "S_GC_INTERCONNECTOR_VARS": list(
            set(
                interconnector.interconnector_id
                for gc in generic_constraints
                for interconnector in gc.lhs_factor_collection.interconnector_factors
                if gc.intervention == "0"
            )
        ),
        "S_GC_REGION_VARS": list(
            set(
                (region.region_id, region.trade_type)
                for gc in generic_constraints
                for region in gc.lhs_factor_collection.region_factors
                if gc.intervention == "0"
            )
        ),
        "S_INTERCONNECTORS": [
            interconnector.interconnector_id for interconnector in interconnectors
        ],
        "S_INTERCONNECTOR_LOSS_MODEL_BREAKPOINTS": [
            (interconnector.interconnector_id, index)
            for interconnector in interconnectors
            for index in range(len(interconnector.loss_model_segments) + 1)
        ],
        "S_INTERCONNECTOR_LOSS_MODEL_INTERVALS": [
            (interconnector.interconnector_id, index)
            for interconnector in interconnectors
            for index, _ in enumerate(interconnector.loss_model_segments)
        ],
        "S_MNSPS": [
            interconnector.interconnector_id
            for interconnector in interconnectors
            if interconnector.mnsp_status == "1"
        ],
        "S_MNSP_OFFERS": [
            (interconnector.interconnector_id, bid.region_id)
            for interconnector in interconnectors
            for bid in interconnector.bids
            if interconnector.mnsp_status == "1"
        ],
        "P_CASE_ID": case_parameters.case_id,
        "P_INTERVENTION_STATUS": case_parameters.intervention,
        "P_TRADER_PRICE_BAND": {
            (trader.trader_id, bid.trade_type, bid.direction, band.index): band.price
            for trader in traders
            for bid in trader.bids
            for band in bid.bid_bands
        },
        "P_TRADER_QUANTITY_BAND": {
            (trader.trader_id, bid.trade_type, bid.direction, band.index): band.quantity
            for trader in traders
            for bid in trader.bids
            for band in bid.bid_bands
        },
        # NOTE: for some reason DROF does not have a cost factor = -1
        "P_TRADER_OFFER_COST_FACTOR": {
            (trader.trader_id, bid.trade_type, bid.direction): (
                -1
                if (bid.trade_type in [TradeType.LDOF])
                or (bid.trade_type == TradeType.BDOF and bid.direction == BidDirection.Load)
                else 1
            )
            for trader in traders
            for bid in trader.bids
        },
        "P_TRADER_MAX_AVAIL": {
            (t.trader_id, i.trade_type, i.direction): i.max_avail for t in traders for i in t.bids
        },
        "P_TRADER_UIGF": {i.trader_id: i.uigf for i in traders if i.uigf is not None},
        "P_TRADER_INITIAL_MW": {i.trader_id: i.initial_mw for i in traders},
        "P_TRADER_WHAT_IF_INITIAL_MW": {
            i.trader_id: i.what_if_initial_mw for i in traders if i.what_if_initial_mw is not None
        },
        "P_TRADER_HMW": {i.trader_id: i.hmw for i in traders if i.hmw is not None},
        "P_TRADER_LMW": {i.trader_id: i.lmw for i in traders if i.lmw is not None},
        "P_TRADER_AGC_STATUS": {i.trader_id: i.agc_status for i in traders},
        "P_TRADER_SEMI_DISPATCH_STATUS": {i.trader_id: i.semi_dispatch for i in traders},
        "P_TRADER_REGION": {i.trader_id: i.region_id for i in traders},
        "P_TRADER_PERIOD_RAMP_UP_RATE": {
            (t.trader_id, i.trade_type, i.direction): i.ramp_up_rate
            for t in traders
            for i in t.bids
            if i.ramp_up_rate is not None
        },
        "P_TRADER_PERIOD_RAMP_DN_RATE": {
            (t.trader_id, i.trade_type, i.direction): i.ramp_dn_rate
            for t in traders
            for i in t.bids
            if i.ramp_dn_rate is not None
        },
        "P_TRADER_TYPE": {i.trader_id: i.trader_type for i in traders},
        "P_TRADER_SCADA_RAMP_UP_RATE": {
            i.trader_id: i.scada_ramp_up_rate for i in traders if i.scada_ramp_up_rate is not None
        },
        "P_TRADER_SCADA_RAMP_DN_RATE": {
            i.trader_id: i.scada_ramp_dn_rate for i in traders if i.scada_ramp_dn_rate is not None
        },
        "P_TRADER_MIN_LOADING_MW": {
            i.trader_id: i.min_loading_mw for i in traders if i.min_loading_mw is not None
        },
        "P_TRADER_CURRENT_MODE": {
            i.trader_id: i.current_mode for i in traders if i.current_mode is not None
        },
        "P_TRADER_CURRENT_MODE_TIME": {
            i.trader_id: i.current_mode_time for i in traders if i.current_mode_time is not None
        },
        "P_TRADER_T1": {i.trader_id: i.t1 for i in traders if i.t1 is not None},
        "P_TRADER_T2": {i.trader_id: i.t2 for i in traders if i.t2 is not None},
        "P_TRADER_T3": {i.trader_id: i.t3 for i in traders if i.t3 is not None},
        "P_TRADER_T4": {i.trader_id: i.t4 for i in traders if i.t4 is not None},
        "P_TRADER_ENABLEMENT_MIN": {
            (t.trader_id, i.trade_type, i.direction): i.enablement_min
            for t in traders
            for i in t.bids
            if i.enablement_min is not None
        },
        "P_TRADER_EFFECTIVE_ENABLEMENT_MIN": {
            (
                t.trader_id,
                i.trade_type,
                i.direction,
            ): i.scaled_fcas_trapezium.enablement_min
            for t in traders
            for i in t.bids
            if i.scaled_fcas_trapezium is not None
        },
        "P_TRADER_LOW_BREAKPOINT": {
            (t.trader_id, i.trade_type, i.direction): i.low_breakpoint
            for t in traders
            for i in t.bids
            if i.low_breakpoint is not None
        },
        "P_TRADER_EFFECTIVE_LOW_BREAKPOINT": {
            (
                t.trader_id,
                i.trade_type,
                i.direction,
            ): i.scaled_fcas_trapezium.low_breakpoint
            for t in traders
            for i in t.bids
            if i.scaled_fcas_trapezium is not None
        },
        "P_TRADER_HIGH_BREAKPOINT": {
            (t.trader_id, i.trade_type, i.direction): i.high_breakpoint
            for t in traders
            for i in t.bids
            if i.high_breakpoint is not None
        },
        "P_TRADER_EFFECTIVE_HIGH_BREAKPOINT": {
            (
                t.trader_id,
                i.trade_type,
                i.direction,
            ): i.scaled_fcas_trapezium.high_breakpoint
            for t in traders
            for i in t.bids
            if i.scaled_fcas_trapezium is not None
        },
        "P_TRADER_ENABLEMENT_MAX": {
            (t.trader_id, i.trade_type, i.direction): i.enablement_max
            for t in traders
            for i in t.bids
            if i.enablement_max is not None
        },
        "P_TRADER_EFFECTIVE_ENABLEMENT_MAX": {
            (
                t.trader_id,
                i.trade_type,
                i.direction,
            ): i.scaled_fcas_trapezium.enablement_max
            for t in traders
            for i in t.bids
            if i.scaled_fcas_trapezium is not None
        },
        # Only considering pricing scenario. If intervention use what-if initial MW
        # TODO: handle physical targets scenario
        "P_TRADER_EFFECTIVE_INITIAL_MW": {
            t.trader_id: (
                t.what_if_initial_mw if case_parameters.intervention == "1" else t.initial_mw
            )
            for t in traders
        },
        "P_TRADER_FCAS_EFFECTIVE_MAX_AVAIL": {
            (t.trader_id, i.trade_type, i.direction): i.scaled_fcas_trapezium.max_avail
            for t in traders
            for i in t.bids
            if i.trade_type in FCAS_TRADE_TYPES
        },
        "P_TRADER_FCAS_AVAILABILITY_STATUS": {
            (t.trader_id, i.trade_type, i.direction): is_fcas_available(trader=t, bid=i)
            for t in traders
            for i in t.bids
            if i.trade_type in FCAS_TRADE_TYPES
        },
        "P_TRADER_FCAS_BDU_GEN_REGULATION_LOWER_ENERGY_BOUND": {
            (t.trader_id, b.trade_type): (
                load_bid.scaled_fcas_trapezium.enablement_min
                if (
                    load_bid := next(
                        (
                            lb
                            for lb in t.bids
                            if lb.direction == BidDirection.Load and lb.trade_type == b.trade_type
                        ),
                        None,
                    )
                )
                is not None
                else b.scaled_fcas_trapezium.enablement_min
            )
            for t in traders
            for b in t.bids
            if t.trader_type == TraderType.Bidirectional
            and b.direction == BidDirection.Gen
            and b.trade_type in REGULATION_FCAS_TRADE_TYPES
            and is_fcas_available(trader=t, bid=b)
        },
        "P_TRADER_EFFECTIVE_RAMP_UP_RATE": {
            k: v
            for k, v in {
                i.trader_id: get_trader_effective_ramp_up_rate(trader=i) for i in traders
            }.items()
            if v is not None
        },
        "P_TRADER_EFFECTIVE_RAMP_DN_RATE": {
            k: v
            for k, v in {
                i.trader_id: get_trader_effective_ramp_dn_rate(trader=i) for i in traders
            }.items()
            if v is not None
        },
        # Only considering pricing scenario. If intervention use what-if initial energy
        # TODO: handle physical targets scenario
        "P_TRADER_EFFECTIVE_INITIAL_ENERGY": {
            i.trader_id: (
                i.what_if_initial_energy_storage
                if case_parameters.intervention == "1"
                else i.initial_energy_storage
            )
            for i in traders
            if i.trader_type == TraderType.Bidirectional
        },
        "P_TRADER_BIDIRECTIONAL_MIN_ENERGY_LIMIT": {
            i.trader_id: i.min_energy_limit
            for i in traders
            if i.trader_type == TraderType.Bidirectional
        },
        "P_TRADER_BIDIRECTIONAL_MAX_ENERGY_LIMIT": {
            i.trader_id: i.max_energy_limit
            for i in traders
            if i.trader_type == TraderType.Bidirectional
        },
        "P_TRADER_BIDIRECTIONAL_MAX_STORAGE_CAPACITY": {
            i.trader_id: i.max_storage_capacity
            for i in traders
            if i.trader_type == TraderType.Bidirectional
        },
        "P_TRADER_BIDIRECTIONAL_IMPORT_EFFCIENCY_FACTOR": {
            i.trader_id: i.import_efficiency_factor
            for i in traders
            if i.trader_type == TraderType.Bidirectional
        },
        "P_TRADER_BIDIRECTIONAL_EXPORT_EFFCIENCY_FACTOR": {
            i.trader_id: i.export_efficiency_factor
            for i in traders
            if i.trader_type == TraderType.Bidirectional
        },
        "P_INTERCONNECTOR_INITIAL_MW": {i.interconnector_id: i.initial_mw for i in interconnectors},
        "P_INTERCONNECTOR_TO_REGION": {i.interconnector_id: i.to_region for i in interconnectors},
        "P_INTERCONNECTOR_FROM_REGION": {
            i.interconnector_id: i.from_region for i in interconnectors
        },
        "P_INTERCONNECTOR_LOWER_LIMIT": {
            i.interconnector_id: i.lower_limit for i in interconnectors
        },
        "P_INTERCONNECTOR_UPPER_LIMIT": {
            i.interconnector_id: i.upper_limit for i in interconnectors
        },
        "P_INTERCONNECTOR_MNSP_STATUS": {
            i.interconnector_id: i.mnsp_status for i in interconnectors
        },
        "P_INTERCONNECTOR_LOSS_SHARE": {i.interconnector_id: i.loss_share for i in interconnectors},
        "P_INTERCONNECTOR_LOSS_LOWER_LIMIT": {
            i.interconnector_id: i.loss_lower_limit for i in interconnectors
        },
        "P_INTERCONNECTOR_LOSS_SEGMENT_LIMIT": {
            (i.interconnector_id, s.index): s.limit
            for i in interconnectors
            for s in i.loss_model_segments
        },
        "P_INTERCONNECTOR_LOSS_SEGMENT_FACTOR": {
            (i.interconnector_id, s.index): s.factor
            for i in interconnectors
            for s in i.loss_model_segments
        },
        # Only considering pricing scenario. If intervention use what-if initial MW
        # TODO: handle physical targets scenario
        "P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW": {
            i.interconnector_id: (
                i.what_if_initial_mw if case_parameters.intervention == "1" else i.initial_mw
            )
            for i in interconnectors
        },
        "P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE": {
            i.interconnector_id: get_interconnector_loss_estimate(
                interconnector=i,
                flow=(
                    i.what_if_initial_mw if case_parameters.intervention == "1" else i.initial_mw
                ),
            )
            for i in interconnectors
        },
        "P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y": {
            # First segment corresponds to loss lower limit
            **{
                (i.interconnector_id, 0): get_interconnector_loss_estimate(
                    interconnector=i, flow=-i.loss_lower_limit
                )
                for i in interconnectors
            },
            # Subsequent segments used limits defined in loss model
            **{
                (i.interconnector_id, s.index + 1): get_interconnector_loss_estimate(
                    interconnector=i, flow=s.limit
                )
                for i in interconnectors
                for s in i.loss_model_segments
            },
        },
        "P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X": {
            # First segment corresponds to loss lower limit
            **{(i.interconnector_id, 0): -i.loss_lower_limit for i in interconnectors},
            # Subsequent segments used limits defined in loss model
            **{
                (i.interconnector_id, s.index + 1): s.limit
                for i in interconnectors
                for s in i.loss_model_segments
            },
        },
        "P_MNSP_PRICE_BAND": {
            (i.interconnector_id, bid.region_id, band.index): band.price
            for i in interconnectors
            for bid in i.bids
            for band in bid.bid_bands
            if i.mnsp_status == "1"
        },
        "P_MNSP_QUANTITY_BAND": {
            (i.interconnector_id, bid.region_id, band.index): band.quantity
            for i in interconnectors
            for bid in i.bids
            for band in bid.bid_bands
            if i.mnsp_status == "1"
        },
        "P_MNSP_MAX_AVAILABLE": {
            (i.interconnector_id, bid.region_id): bid.max_avail
            for i in interconnectors
            for bid in i.bids
            if i.mnsp_status == "1"
        },
        "P_MNSP_TO_REGION_LF": {
            i.interconnector_id: i.to_region_lf for i in interconnectors if i.mnsp_status == "1"
        },
        "P_MNSP_TO_REGION_LF_EXPORT": {
            i.interconnector_id: i.to_region_lf_export
            for i in interconnectors
            if i.mnsp_status == "1"
        },
        "P_MNSP_TO_REGION_LF_IMPORT": {
            i.interconnector_id: i.to_region_lf_import
            for i in interconnectors
            if i.mnsp_status == "1"
        },
        "P_MNSP_FROM_REGION_LF": {
            i.interconnector_id: i.from_region_lf for i in interconnectors if i.mnsp_status == "1"
        },
        "P_MNSP_FROM_REGION_LF_EXPORT": {
            i.interconnector_id: i.from_region_lf_export
            for i in interconnectors
            if i.mnsp_status == "1"
        },
        "P_MNSP_FROM_REGION_LF_IMPORT": {
            i.interconnector_id: i.from_region_lf_import
            for i in interconnectors
            if i.mnsp_status == "1"
        },
        "P_MNSP_RAMP_UP_RATE": {
            (i.interconnector_id, bid.region_id): bid.ramp_up_rate
            for i in interconnectors
            for bid in i.bids
            if i.mnsp_status == "1"
        },
        "P_MNSP_RAMP_DOWN_RATE": {
            (i.interconnector_id, bid.region_id): bid.ramp_dn_rate
            for i in interconnectors
            for bid in i.bids
            if i.mnsp_status == "1"
        },
        "P_MNSP_REGION_LOSS_INDICATOR": {
            (i.interconnector_id, region.region_id): get_mnsp_region_loss_indicator(
                interconnector=i,
                region_id=region.region_id,
                intervention=case_parameters.intervention,
            )
            for i in interconnectors
            for region in regions
            if i.mnsp_status == "1"
        },
        "P_MNSP_LOSS_PRICE": case_parameters.mnsp_losses_price,
        "P_REGION_INITIAL_DEMAND": {i.region_id: i.initial_demand for i in regions},
        "P_REGION_ADE": {i.region_id: i.ade for i in regions},
        "P_REGION_DF": {i.region_id: i.df for i in regions},
        # Only considering non-intervention scenario for now
        # TODO: handle intervention scenario
        # RHS value comes from NEMDE solution
        # TODO: use reverse polish notation to compute RHS directly from inputs
        "P_GC_RHS": {
            i.constraint_id: i.nemde_solution.rhs_solution
            for i in generic_constraints
            if i.intervention == "0"
        },
        "P_GC_TYPE": {
            i.constraint_id: i.constraint_type for i in generic_constraints if i.intervention == "0"
        },
        "P_CVF_GC": {
            i.constraint_id: i.violation_price for i in generic_constraints if i.intervention == "0"
        },
        "P_CVF_VOLL": case_parameters.voll,
        "P_CVF_ENERGY_DEFICIT_PRICE": case_parameters.energy_deficit_price,
        "P_CVF_ENERGY_SURPLUS_PRICE": case_parameters.energy_surplus_price,
        "P_CVF_UIGF_SURPLUS_PRICE": case_parameters.uigf_surplus_price,
        "P_CVF_RAMP_RATE_PRICE": case_parameters.ramp_rate_price,
        "P_CVF_CAPACITY_PRICE": case_parameters.capacity_price,
        "P_CVF_OFFER_PRICE": case_parameters.offer_price,
        "P_CVF_MNSP_OFFER_PRICE": case_parameters.mnsp_offer_price,
        "P_CVF_MNSP_RAMP_RATE_PRICE": case_parameters.mnsp_ramp_rate_price,
        "P_CVF_MNSP_CAPACITY_PRICE": case_parameters.mnsp_capacity_price,
        "P_CVF_AS_PROFILE_PRICE": case_parameters.as_profile_price,
        "P_CVF_AS_MAX_AVAIL_PRICE": case_parameters.as_max_avail_price,
        "P_CVF_AS_ENABLEMENT_MIN_PRICE": case_parameters.as_enablement_min_price,
        "P_CVF_AS_ENABLEMENT_MAX_PRICE": case_parameters.as_enablement_max_price,
        "P_CVF_INTERCONNECTOR_PRICE": case_parameters.interconnector_price,
        "P_CVF_FAST_START_PRICE": case_parameters.fast_start_price,
        "P_CVF_GENERIC_CONSTRAINT_PRICE": case_parameters.generic_constraint_price,
        "P_CVF_SATISFACTORY_NETWORK_PRICE": case_parameters.satisfactory_network_price,
        "P_TIE_BREAK_PRICE": case_parameters.tie_break_price,
        "P_CVF_BDU_MIN_ENERGY_PRICE": case_parameters.min_energy_limit_price,
        "P_CVF_BDU_MAX_ENERGY_PRICE": case_parameters.max_energy_limit_price,
        "P_FAST_START_THRESHOLD": case_parameters.fast_start_threshold,
        # Only considering non-intervention scenario for now
        # TODO: handle intervention scenario
        "intermediate": {
            "generic_constraint_lhs_terms": {
                c.constraint_id: {
                    "traders": {
                        (t.trader_id, t.trade_type): t.factor
                        for t in c.lhs_factor_collection.trader_factors
                    },
                    "interconnectors": {
                        i.interconnector_id: i.factor
                        for i in c.lhs_factor_collection.interconnector_factors
                    },
                    "regions": {
                        (r.region_id, r.trade_type): r.factor
                        for r in c.lhs_factor_collection.region_factors
                    },
                }
                for c in generic_constraints
                if c.intervention == "0"
            },
            "loss_model_segments": {
                i.interconnector_id: get_parsed_interconnector_loss_model_segments(interconnector=i)
                for i in interconnectors
            },
        },
        # NEMDE solution outputs. Used for backtesting and development
        "P_TRADER_TARGET": {
            k: v for t in [get_trader_target(trader=i) for i in traders] for k, v in t.items()
        },
        "P_INTERCONNECTOR_FLOW": {
            i.interconnector_id: j.flow
            for i in interconnectors
            for j in i.nemde_solution
            if j.intervention == "0"
        },
    }

    return case
