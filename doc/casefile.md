# Casefile format
The following sections provide an overview of the structure of NEMDE casefiles and their constituent components.

## NEMSPDCaseFile/NemSpdInputs/Case
Case details and constraint violation penalty factors.

Example:
```
{
    "@CaseID": "20201130169",
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
    "@UIGF_ATime": "20201130180500",
    "@UseSOS2LossModel": "True",
    "@ASProfilePrice": "2325000",
    "@ASMaxAvailPrice": "2325000",
    "@ASEnablementMinPrice": "1050000",
    "@ASEnablementMaxPrice": "1050000"
}
```

## NEMSPDCaseFile/NemSpdInputs/RegionCollection/Region
Region initial conditions

Example:
```
"RegionCollection": {
    "Region": [
        {
            "@RegionID": "NSW1",
            "RegionInitialConditionCollection": {
                "RegionInitialCondition": [
                    {
                        "@InitialConditionID": "ADE",
                        "@Value": "16.9436740875244"
                    },
                    {
                        "@InitialConditionID": "InitialDemand",
                        "@Value": "8819.599609375"
                    }
                ]
            }
        },
        ... , 
    ]
```
Endpoints:

NEMSPDCaseFile/NemSpdInputs/RegionCollection/Region[]/@RegionID

NEMSPDCaseFile/NemSpdInputs/RegionCollection/Region[]/RegionInitialConditionCollection/RegionInitialCondition[]/@InitialConditionID

NEMSPDCaseFile/NemSpdInputs/RegionCollection/Region[]/RegionInitialConditionCollection/RegionInitialCondition[]/@Value


Possible values for `InitialConditionID`:

`"ADE"`: Aggregate dispatch error

`"InitialDemand"`: Region demand at start of dispatch interval