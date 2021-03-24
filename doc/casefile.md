# Casefile format
The structure of a NEMDE casefile is discussed in the following sections. Summaries for each component are by no means exhaustive, rather they seek to provide a high-level overview of the components most likely to be modified when undertaking scenario analyses. Users can refer to the JSON schema for a more precise overview of casefile structure and allowed data types.

### NEMSPDCaseFile.NemSpdInputs.Case
Most of the following parameters pertain to constraint violation penalty factors. The price ceiling is given by `@VoLL` - formerly referred to as the 'value of lost load', while the price floor is represented by `@MPF`. The `@Intervention` flag indicates if an intervention pricing run occured for the given interval.

```
{
    "@CaseID": "20201101001",
    "@CaseType": "DS",
    "@Intervention": "False",
    "@VoLL": "15000",
    "@MPF": "-1000",
    "@EnergyDeficitPrice": "2250000",
    "@EnergySurplusPrice": "2250000",
    "@RampRatePrice": "17325000",
    "@InterconnectorPrice": "17250000",
    "@CapacityPrice": "5550000",
    "@OfferPrice": "17025000",
    "@TieBreakPrice": "1E-6",
    "@GenericConstraintPrice": "450000",
    "@NPLThreshold": "0.1",
    "@MNSPLossesPrice": "5475000",
    "@MNSPOfferPrice": "17025000",
    "@MNSPRampRatePrice": "17325000",
    "@MNSPCapacityPrice": "5475000",
    "@FastStartPrice": "16950000",
    "@Satisfactory_Network_Price": "5400000",
    "@FastStartThreshold": "0.005",
    "@SwitchRunInitialStatus": "1",
    "@UIGFSurplusPrice": "5775000",
    "@UIGF_ATime": "20201101040500",
    "@UseSOS2LossModel": "True",
    "@ASProfilePrice": "2325000",
    "@ASMaxAvailPrice": "2325000",
    "@ASEnablementMinPrice": "1050000",
    "@ASEnablementMaxPrice": "1050000"
}
```

### NEMSPDCaseFile.NemSpdInputs.RegionCollection.Region
Array describing intial conditions for each region.

```
[
    {
        "@RegionID": "NSW1",
        "RegionInitialConditionCollection": {
            "RegionInitialCondition": [
                {
                    "@InitialConditionID": "ADE",
                    "@Value": "0"
                },
                {
                    "@InitialConditionID": "InitialDemand",
                    "@Value": "5668.345703125"
                }
            ]
        }
    },
    ...,
]
```

| Parameter | Description|
|---|---|
|`ADE`| Aggregate dispatch error at start of dispatch interval|
|`InitialDemand`| Region demand at start of dispatch interval |

### NEMSPDCaseFile.NemSpdInputs.TraderCollection.Trader
Array describing trader price bands and initial conditions at the start of a given dispatch interval.

```
[
    {
        "@TraderID": "AGLHAL",
        "@TraderType": "GENERATOR",
        "@FastStart": "1",
        "@MinLoadingMW": "2",
        "@CurrentMode": "0",
        "@CurrentModeTime": "0",
        "@T1": "10",
        "@T2": "2",
        "@T3": "10",
        "@T4": "2",
        "@SemiDispatch": "0",
        "TraderInitialConditionCollection": {
            "TraderInitialCondition": [
                {
                    "@InitialConditionID": "AGCStatus",
                    "@Value": "0"
                },
                {
                    "@InitialConditionID": "HMW",
                    "@Value": "0"
                },
                {
                    "@InitialConditionID": "InitialMW",
                    "@Value": "0"
                },
                {
                    "@InitialConditionID": "LMW",
                    "@Value": "0"
                },
                {
                    "@InitialConditionID": "WhatIfInitialMW",
                    "@Value": "0"
                }
            ]
        },
        "TradePriceStructureCollection": {
            "TradePriceStructure":
                {
                    "@TradePriceStructureID": "20201101001",
                    "TradeTypePriceStructureCollection": {
                        "TradeTypePriceStructure": [
                            {
                                "@TradeType": "ENOF",
                                "@PriceBand1": "-1000",
                                "@PriceBand2": "0",
                                "@PriceBand3": "278.81",
                                "@PriceBand4": "368.81",
                                "@PriceBand5": "418.81",
                                "@PriceBand6": "498.81",
                                "@PriceBand7": "578.81",
                                "@PriceBand8": "1365.56",
                                "@PriceBand9": "10578.87",
                                "@PriceBand10": "15000",
                                "@Offer_SettlementDate": "2020-11-01T00:00:00+10:00",
                                "@Offer_EffectiveDate": "2020-10-16T12:01:01+10:00",
                                "@Offer_VersionNo": "1"
                            }
                        ]
                    }
                }
        }
    },
    ...,
]
```

**Fast-start parameters**

These parameters are only defined for fast-start units.

| Parameter | Description |
| --------- | ----------- |
| @FastStart | Flag indicating fast start capability |
| @MinLoadingMW | Min loading when in mode 3 over fast-start inflexibility profile |
| @CurrentMode | Inflexibility profile mode at start of dispatch interval |
| @CurrentModeTime | Time unit has operated in its current inflexibility profile mode |
| @T1 | Minutes unit must operate in mode 1 |
| @T2 | Minutes unit must operate in mode 2 |
| @T1 | Minutes unit must operate in mode 3 |
| @T1 | Minutes unit must operate in mode 4 |

**Price bands**

Price bands corresponding to each offer type are contained within the array corresponding to `TradeTypePriceStructure`. Each element of the array corresponds to a trade type. Possible trade types are as follows:

| Trade type | Description |
| ---------- | ----------- |
| `ENOF` | Generator energy offer |
| `LDOF` | Load energy offer |
| `R6SE` | Raise 6 second FCAS market |
| `R60S` | Raise 60 second FCAS market |
| `R5MI` | Raise 5 min FCAS market |
| `R5RE` | Raise regulation FCAS market |
| `L6SE` | Lower 6 second FCAS market |
| `L60S` | Lower 60 second FCAS market |
| `L5MI` | Lower 5 min FCAS market |
| `L5RE` | Lower regulation FCAS market |


### NEMSPDCaseFile.NemSpdInputs.InterconnectorCollection.Interconnector
Array describing initial conditions for each interconnector at the start of a given dispatch interval, along with a description of the interconector's loss model.

```
[
    {
        "@InterconnectorID": "N-Q-MNSP1",
        "InterconnectorInitialConditionCollection": {
            "InterconnectorInitialCondition": [
                {
                    "@InitialConditionID": "InitialMW",
                    "@Value": "-32.7999992370605"
                },
                {
                    "@InitialConditionID": "WhatIfInitialMW",
                    "@Value": "-32.7999992370605"
                }
            ]
        },
        "LossModelCollection": {
            "LossModel": {
                "@LossModelID": "637398003000000000",
                "@LossLowerLimit": "265",
                "@LossShare": "0.48",
                "@NPLRange": "10000",
                "SegmentCollection": {
                    "Segment": [
                        {
                            "@Limit": "-257",
                            "@Factor": "-0.538797000"
                        },
                        {
                            "@Limit": "-249",
                            "@Factor": "-0.520581000"
                        },
                        {
                            "@Limit": "-241",
                            "@Factor": "-0.502365000"
                        },...
                    ]
                }
            }
        }
    },
    ...,
]
```
**Interconnector initial conditions**

| Parameter | Description |
| - | - | 
| `InitialMW` | Initial MW flow over interconnector at start of dispatch interval |
| `WhatIfInitialMW` | Initial MW value to use for an intervention pricing run |

**Loss model**

Loss model segments are used to describe the relationship between interconnector flow and total losses over the interconnector. For each segment `@Factor` describes the marginal loss over a given loss model segment. The endpoints for each segment are given by `@Limit`. Each interconnector has a `@FromRegion` and `@ToRegion` (defined in TODO: add link). Positive flow corresponds to power flowing from an interconnector's `@FromRegion` to its `@ToRegion`, while negative values denote power flowing in the opposite direction. This is explains why `@Limit` takes negative values (the net transfer is from the interconnector's `@ToRegion` to its `@FromRegion`). The loss over a given loss model segment is simply the MW flow over the segment multiplied by `@Factor`. Integrating losses over each segment yields the total loss over the interconnector.

(TODO: figure of loss model factors)

(TODO: figure of integrated loss model segments)

### NEMSPDCaseFile.NemSpdInputs.ConstraintScadaDataCollection.ConstraintScadaData
SCADA telemetry data used when computing RHS values for constraints.

**Note: these data are not currently used when implenting the approximated version of NEMDE. See RHS limitations for more information. (TODO: write caveats section for RHS values)**

```
[
    {
        "@SpdType": "A",
        "ScadaValuesCollection": {
            "ScadaValues": [
                {
                    "@SpdID": "220_GEN_INERTIA",
                    "@Value": "38.1619987487793",
                    "@EMS_ID": "INER",
                    "@EMS_Key": "YPS.SUMM.BASE.INER",
                    "@Grouping_ID": "VIC1",
                    "@Can_Use_Last_Good": "True",
                    "@Can_Use_Value": "True",
                    "@EMS_Good": "True",
                    "@EMS_Replaced": "False",
                    "@Data_Flags": "1075904512",
                    "@Site_ID": "EMS_PROD2",
                    "@Good_Input_Count": "2",
                    "@EMS_TimeStamp": "2020-11-01T03:31:35+10:00",
                    "@Est_Value": "0",
                    "@Est_Flags": "0",
                    "@Can_Use_Est_Value": "False",
                    "@IsReferenced": "True"
                },
                ...,
            ]
    },
    ...,
]
```

### NEMSPDCaseFile.NemSpdInputs.GenericEquationCollection.GenericEquation
Equation used to compute the RHS value for generic constraints with a dynamic RHS.

**Note: these data are not currently used when implenting the approximated version of NEMDE. See RHS limitations for more information. (TODO: write caveats section for RHS values)**

```
[
    {
        "@EquationID": "BA-HO_66-LNK_STATUS",
        "@EffectiveDate": "2014-01-06T00:00:00+10:00",
        "@VersionNo": "1",
        "RHSTermCollection": {
            "RHSTerm": [
                {
                    "@TermID": "1",
                    "@Multiplier": "0.0001",
                    "@Operation": "PUSH",
                    "@SpdID": "Constant",
                    "@SpdType": "C",
                    "@Default": "1"
                },
                {
                    "@TermID": "2",
                    "@Multiplier": "9999",
                    "@Operation": "PUSH",
                    "@SpdID": "Constant",
                    "@SpdType": "C",
                    "@Default": "1"
                },
                {
                    "@TermID": "3",
                    "@Multiplier": "1",
                    "@Operation": "PUSH",
                    "@SpdID": "ART_CB_B_STAT",
                    "@SpdType": "S",
                    "@Default": "1"
                },
                ...,
            ]
        }
    },
    ...,
]
```


### NEMSPDCaseFile.NemSpdInputs.GenericConstraintCollection.GenericConstraint
Array describing generic constraint components.

```
[
    {
        "@ConstraintID": "DATASNAP",
        "@Version": "20180413000000_1",
        "@EffectiveDate": "2018-04-13T00:00:00+10:00",
        "@VersionNo": "1",
        "@Type": "LE",
        "@ViolationPrice": "60000",
        "@RHS": "10000",
        "@Force_SCADA": "False",
        "LHSFactorCollection": {
            "InterconnectorFactor": {
                "@Factor": "1",
                "@InterconnectorID": "N-Q-MNSP1"
            }
        },
        "RHSTermCollection": {
            "RHSTerm": [
                {
                    "@TermID": "1",
                    "@Multiplier": "10000",
                    "@SpdID": "BIG",
                    "@SpdType": "C",
                    "@Default": "10000"
                },
                {
                    "@TermID": "2",
                    "@Multiplier": "1",
                    "@SpdID": "TAS_INERTIA",
                    "@SpdType": "A",
                    "@Default": "0"
                }
            ]
        },
        "s:ConstraintTrkCollection": {
            "@xmlns:s": "http://www.w3.org/2001/XMLSchema-instance",
            "ConstraintTrkItem": {
                "@Invocation_ID": "50177",
                "@Start_Interval_DateTime": "2020-11-01T04:05:00+10:00",
                "@End_Interval_DateTime": "2020-11-01T04:05:00+10:00",
                "@DynamicRHS": "1",
                "@GenConSetID": "I*DATASNAP",
                "@Intervention": "False",
                "@ASConstraintType": "ICONNECT",
                "@SystemNormal": "True",
                "@Invocation_Group_ID": "50177",
                "@LimitType": "Other"
            }
        }
    },
    ...,
]
```

### NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.RegionPeriodCollection.RegionPeriod
Array describing demand forecast for upcoming interval.

```
[
    {
        "@RegionID": "NSW1",
        "@DF": "-6.88232421875",
        "@DemandForecast": "5661.46337890625",
        "@Suspension_Schedule_Energy_Price": "35.88",
        "@Suspension_Schedule_R6_Price": "2.13",
        "@Suspension_Schedule_R60_Price": "2.79",
        "@Suspension_Schedule_R5_Price": "0.88",
        "@Suspension_Schedule_RReg_Price": "7.18",
        "@Suspension_Schedule_L6_Price": "3.41",
        "@Suspension_Schedule_L60_Price": "6.04",
        "@Suspension_Schedule_L5_Price": "4.38",
        "@Suspension_Schedule_LReg_Price": "9.02"
    },
    ...,
]
```

| Parameter | Description |
| --------- | ----------- |
| `@DF` | Delta forecast. The amount by which demand is expected over the dispatch interval. |
| `@DemandForecast` | Demand forecast at end of a given dispatch interval |


### NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.TraderPeriodCollection.TraderPeriod
Array describing trader quantity band parameters. 

```
[
    {
        "@TraderID": "BW01",
        "@RegionID": "NSW1",
        "@TradePriceStructureID": "20201101001",
        "TradeCollection": {
            "Trade": [
                {
                    "@TradeType": "ENOF",
                    "@RampUpRate": "240",
                    "@RampDnRate": "180",
                    "@MaxAvail": "600",
                    "@BandAvail1": "330",
                    "@BandAvail2": "100",
                    "@BandAvail3": "60",
                    "@BandAvail4": "0",
                    "@BandAvail5": "20",
                    "@BandAvail6": "20",
                    "@BandAvail7": "20",
                    "@BandAvail8": "0",
                    "@BandAvail9": "50",
                    "@BandAvail10": "100"
                },
                {
                    "@TradeType": "L5MI",
                    "@MaxAvail": "66",
                    "@EnablementMin": "240",
                    "@EnablementMax": "640",
                    "@LowBreakpoint": "306",
                    "@HighBreakpoint": "640",
                    "@BandAvail1": "0",
                    "@BandAvail2": "0",
                    "@BandAvail3": "5",
                    "@BandAvail4": "5",
                    "@BandAvail5": "5",
                    "@BandAvail6": "5",
                    "@BandAvail7": "0",
                    "@BandAvail8": "0",
                    "@BandAvail9": "0",
                    "@BandAvail10": "46"
                },
                ...,
            ]
        }
    },
    ...,
]
```

Each element of the `Trade` array describes quantity bands for a given trade type. 

When determining a scheduled unit's availability it is important to examine the `@MaxAvail` parameter. Simply summing band availabilities will give misleading results.

FCAS offers contain additional parameters describing a given trade type's FCAS trapezium.

(TODO figure of FCAS trapezium)

### NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.InterconnectorPeriodCollection.InterconnectorPeriod
Array describing interconnector power flow limits and 'from' and 'to' region definitions.

```
[
    {
        "@InterconnectorID": "N-Q-MNSP1",
        "@MNSP": "0",
        "@LossModelID": "637398003000000000",
        "@FromRegion": "NSW1",
        "@ToRegion": "QLD1",
        "@LowerLimit": "264",
        "@UpperLimit": "264",
        "@LossDemandConstant": "0"
    },
    ...,
]
```

| Parameter | Description |
| --------- | ----------- |
| `@MNSP` | Flag indicating if unit is a Market Network Service Provider. These interconnectors can bid into the market and be dispatched in a similar way to traders |
| `@FromRegion` | Interconector's from region |
| `@ToRegion` | Interconector's to region |
| `@LowerLimit` | Max power flow when the net power transfer is from `@ToRegion` to `@FromRegion` |
| `@UpperLimit` | Max power flow when the net power transfer is from `@FromRegion` to `@ToRegion` |

### NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.GenericConstraintPeriodCollection.GenericConstraintPeriod
Array describing metadata for each generic constraint, including a flag denoting whether the constraint should be included when conducting an intervention pricing run. If market intervention occurs (e.g. AEMO directs a trader to produce above a minimum dispatch level) constraints corresponding to the market intervention will have their `@Intervention` flag set to 1. The first run of NEMDE is used to determine the dispatch targets for all traders, with all generic constraints included. A second run of NEMDE is then conducted with intervention constraints excluded. Pricing arising from this second 'intervention pricing' run set wholesale prices for the interval.

```
[
    {
        "@ConstraintID": "#BBTHREE3_E",
        "@Version": "20200817000000_1",
        "@Intervention": "0",
        "@Category": "1"
    },
    ...,
]
```

### NEMSPDCaseFile.NemSpdInputs.PeriodCollection.Period.Non_Scheduled_Generator_Collection.Non_Scheduled_Generator
Array describing power output for non-scheduled generators.

```
[
    {
        "@DUID": "BARCSF1",
        "@MW": "0"
    },
    ...,
]
```

### NEMSPDCaseFile.NemSpdOutputs.CaseSolution
High-level summary statistics for model solution. 

```
{
    "@SolverStatus": "0",
    "@Terminal": "NORREWMDS1A",
    "@InterventionStatus": "0",
    "@SolverVersion": "3.3.15",
    "@NPLStatus": "0",
    "@TotalObjective": "-42158401.095",
    "@TotalAreaGenViolation": "0",
    "@TotalInterconnectorViolation": "0",
    "@TotalGenericViolation": "0",
    "@TotalRampRateViolation": "0",
    "@TotalUnitMWCapacityViolation": "0",
    "@TotalEnergyConstrViolation": "0",
    "@TotalEnergyOfferViolation": "0",
    "@TotalASProfileViolation": "0",
    "@TotalFastStartViolation": "0",
    "@NumberOfDegenerateLPsSolved": "0",
    "@TotalUIGFViolation": "0",
    "@OCD_Status": "Not_OCD"
}
```

### NEMSPDCaseFile.NemSpdOutputs.PeriodSolution
Describes objective function value and aggregate violation statistics for a given interval.

```
{
    "@PeriodID": "2020-11-01T04:05:00+10:00",
    "@Intervention": "0",
    "@SwitchRunBestStatus": "1",
    "@TotalObjective": "-10540790.07213",
    "@SolverStatus": "0",
    "@NPLStatus": "0",
    "@TotalAreaGenViolation": "0",
    "@TotalInterconnectorViolation": "0",
    "@TotalGenericViolation": "0",
    "@TotalRampRateViolation": "0",
    "@TotalUnitMWCapacityViolation": "0",
    "@TotalEnergyConstrViolation": "0",
    "@TotalEnergyOfferViolation": "0",
    "@TotalASProfileViolation": "0",
    "@TotalFastStartViolation": "0",
    "@TotalMNSPRampRateViolation": "0",
    "@TotalMNSPOfferViolation": "0",
    "@TotalMNSPCapacityViolation": "0",
    "@TotalUIGFViolation": "0"
}
```

### NEMSPDCaseFile.NemSpdOutputs.RegionSolution
Array describing prices, demand, and net power flowing out of a given region.

```
[
    {
        "@RegionID": "NSW1",
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@EnergyPrice": "41.69967",
        "@DispatchedGeneration": "5818.37",
        "@DispatchedLoad": "0",
        "@FixedDemand": "5654.29",
        "@NetExport": "164.08",
        "@SurplusGeneration": "0",
        "@R6Dispatch": "213",
        "@R60Dispatch": "196",
        "@R5Dispatch": "52",
        "@R5RegDispatch": "118.17",
        "@L6Dispatch": "112.35",
        "@L60Dispatch": "173",
        "@L5Dispatch": "78.97",
        "@L5RegDispatch": "34",
        "@R6Price": "1.49",
        "@R60Price": "1.73",
        "@R5Price": "0",
        "@R5RegPrice": "13.99",
        "@L6Price": "1.23",
        "@L60Price": "1.95",
        "@L5Price": "1.03",
        "@L5RegPrice": "3.75",
        "@AvailableGeneration": "8849",
        "@AvailableLoad": "0",
        "@ClearedDemand": "5660.54"
    },
    ...,
]
```

### NEMSPDCaseFile.NemSpdOutputs.InterconnectorSolution
Array describing power flow and total losses for each interconnector.

```
[
    {
        "@InterconnectorID": "N-Q-MNSP1",
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@Flow": "-33",
        "@Losses": "-0.59167",
        "@Deficit": "0",
        "@Price": "0",
        "@IdealLosses": "-0.59167",
        "@NPLExists": "0",
        "@InterRegionalLossFactor": "0.989524"
    },
    ...,
]
```

### NEMSPDCaseFile.NemSpdOutputs.TraderSolution
Array describing dispatch targets for each trader, and also additional parameters pertaining the unit's availability and ramp ramp rates.

```
[
    {
        "@TraderID": "BW01",
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@EnergyTarget": "490",
        "@R6Target": "25",
        "@R60Target": "30",
        "@R5Target": "5",
        "@R5RegTarget": "15",
        "@L6Target": "5",
        "@L60Target": "5",
        "@L5Target": "5",
        "@L5RegTarget": "0",
        "@R6Price": "0",
        "@R60Price": "0",
        "@R5Price": "0",
        "@R5RegPrice": "0",
        "@L6Price": "0",
        "@L60Price": "0",
        "@L5Price": "0",
        "@L5RegPrice": "0",
        "@R6Violation": "0",
        "@R60Violation": "0",
        "@R5Violation": "0",
        "@R5RegViolation": "0",
        "@L6Violation": "0",
        "@L60Violation": "0",
        "@L5Violation": "0",
        "@L5RegViolation": "0",
        "@RampUpRate": "240",
        "@RampDnRate": "180",
        "@RampPrice": "0",
        "@RampDeficit": "0",
        "@R6Flags": "1",
        "@R60Flags": "1",
        "@R5Flags": "1",
        "@R5RegFlags": "1",
        "@L6Flags": "1",
        "@L60Flags": "1",
        "@L5Flags": "1",
        "@L5RegFlags": "1",
        "@EnergyR5RegPrice": "0",
        "@EnergyR5RegViolation": "0",
        "@EnergyL5RegPrice": "0",
        "@EnergyL5RegViolation": "0"
    },
    ...,
]
```

Note `@EnergyTarget` describes a trader's power target (in MW) in the market for energy. While generators and loads have differing trade types for this market (`ENOF` for generators and `LDOF` for loads) there is no distinction with respect to the dispatch solution - both trader categories use `@EnergyTarget` to power target set for generators and loads at the end of a given dispatch interval.

### NEMSPDCaseFile.NemSpdOutputs.ConstraintSolution
Array describing generic constraint solution. 

```
[
    {
        "@ConstraintID": "#BBTHREE3_E",
        "@Version": "20200817000000_1",
        "@PeriodID": "2020-11-01T04:05:00+10:00",
        "@Intervention": "0",
        "@RHS": "25",
        "@MarginalValue": "0",
        "@Deficit": "0"
    },
    ...,
]
```

| Parameter | Description |
| --------- | ----------- |
| `@RHS` | Right-hand side value for constraint |
| `@MarginalValue` | Value of the dual variable corresponding to constraint. This value represents a sensitivity, describing how the objective function value would change for an incremental tightenting of the constraint. |
| `@Deficit` | The amount by which the RHS has been violated |
