"""Classes used to extract data from NEMDE output files and extract and format relevant information for NEMDE model"""

import os
import io
import zipfile

import xmltodict
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt


class NEMDEData:
    def __init__(self, data_dir):
        # Root folder containing MMSDM and NEMDE output files
        self.data_dir = data_dir

        # Loader containing NEMDE files
        self.nemde_dir = os.path.join(data_dir, 'NEMDE', 'zipped')

        # NEMDE interval data
        self.interval_data = None

    def load_file(self, year, month, day, interval):
        """Load NEMDE input / output file"""

        z_1_name = f'NEMDE_{year}_{month:02}.zip'

        print(os.listdir(self.nemde_dir))

        with zipfile.ZipFile(os.path.join(self.nemde_dir, z_1_name)) as z_1:
            z_2_name = f'NEMDE_2019_{month:02}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{year}{month:02}{day:02}_loaded.zip'
            with z_1.open(z_2_name) as z_2:
                z_2_data = io.BytesIO(z_2.read())

                with zipfile.ZipFile(z_2_data) as z_3:
                    z_3_name = f'NEMSPDOutputs_{year}{month:02}{day:02}{interval:03}00.loaded'
                    return z_3.open(z_3_name).read()

    def get_nemde_xml(self, year, month, day, interval):
        """Get NEMDE input / output file in XML format"""

        # Load NEMDE inputs / outputs
        data = self.load_file(year, month, day, interval)

        # Parse XML and construct tree
        tree = ET.fromstring(data)

        return tree

    def get_nemde_dict(self, year, month, day, interval):
        """Get NEMDE input / output file in dictionary format"""

        # Load NEMDE inputs / outputs
        data = self.load_file(year, month, day, interval)

        # Convert to dictionary
        info = xmltodict.parse(data)

        return info

    def load_interval(self, year, month, day, interval):
        """Load xml data for a given interval"""

        self.interval_data = self.get_nemde_xml(year, month, day, interval)

    def get_trader_ids(self):
        """Get index for market participant units based on price band information"""

        # Path to trader elements
        path = ".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod"

        # All traders
        traders = self.interval_data.findall(path)

        # Construct index based on element attributes
        trader_ids = [t.get('TraderID') for t in traders]

        return trader_ids

    def get_trader_offer_index(self):
        """Get index for market participant units based on price band information"""

        # Path to trader elements
        path = ".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod"

        # All market units that are market participants
        traders = self.interval_data.findall(path)

        # Construct index based on element attributes
        trader_offer_ids = [(t.get('TraderID'), o.get('TradeType')) for t in traders for o in t.findall('.//Trade')]

        return trader_offer_ids

    def get_mnsp_ids(self):
        """Get IDs of all Market Network Service Providers (interconnectors that bid into the market)"""

        # Path to MNSP elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod[@MNSP='1']"

        # Get MNSP elements
        mnsps = self.interval_data.findall(path)

        # Extract MNSP IDs
        mnsp_ids = [i.get('InterconnectorID') for i in mnsps]

        return mnsp_ids

    def get_interconnector_ids(self):
        """Get all interconnector IDs"""

        # Path to interconnector elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod"

        # Get MNSP elements
        interconnectors = self.interval_data.findall(path)

        # Extract interconnector IDs
        interconnector_ids = [i.get('InterconnectorID') for i in interconnectors]

        return interconnector_ids

    def get_mnsp_offer_index(self):
        """Get index for interconnectors that submit offers into the market. Using price band information."""

        # Path to MNSP elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod[@MNSP='1']"

        # Get MNSP elements
        mnsps = self.interval_data.findall(path)

        # Construct MNSP offer index based on interconnector ID and region name (price bands for each region)
        mnsp_offer_index = [(i.get('InterconnectorID'), o.get('RegionID'))
                            for i in mnsps for o in i.findall('.//MNSPOffer')]

        return mnsp_offer_index

    def get_generic_constraint_index(self):
        """Get index for each generic constraint"""

        # All generic constraints. Only consider no intervention case for now.
        constraints = self.interval_data.findall(".//NemSpdOutputs/ConstraintSolution/[@Intervention='0']")

        # Extract constraint IDs
        constraint_ids = [c.get('ConstraintID') for c in constraints]

        return constraint_ids

    def get_generic_constraint_trader_variables(self):
        """Get variable IDs associated with trader elements in Generic Constraints"""

        # Path to trader factor elements within generic constraints
        # TODO: May need to consider intervention
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/TraderFactor'

        # Extract all trader factor elements from generic constraints
        factors = self.interval_data.findall(path)

        # Construct ID for trader factor variables
        var_ids = list(set([(f.get('TraderID'), f.get('TradeType')) for f in factors]))

        return var_ids

    def get_generic_constraint_interconnector_variables(self):
        """Get variable IDs associated with interconnector factors in Generic Constraints"""

        # Path to interconnector elements
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/InterconnectorFactor'

        # Extract all interconnector factor elements from generic constraints
        factors = self.interval_data.findall(path)

        # Construct ID for trader factor variables
        var_ids = list(set(f.get('InterconnectorID') for f in factors))

        return var_ids

    def get_generic_constraint_region_variables(self):
        """Get variable IDs associated with region factors in Generic Constraints"""

        # Path to region elements
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/RegionFactor'

        # Extract all interconnector factor elements from generic constraints
        factors = self.interval_data.findall(path)

        # Construct ID for trader factor variables
        var_ids = list(set([(f.get('RegionID'), f.get('TradeType')) for f in factors]))

        return var_ids

    def get_trader_price_band_value(self, trader_id, offer_type, band):
        """Get price band value for given unit, offer type, and price band"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TradePriceStructureCollection/"
                f"TradePriceStructure/TradeTypePriceStructureCollection/"
                f"TradeTypePriceStructure[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'PriceBand{band}'))

    def get_trader_quantity_band_value(self, trader_id, offer_type, band):
        """Get quantity band value for given unit, offer type, and quantity band"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'BandAvail{band}'))

    def get_trader_max_available_value(self, trader_id, offer_type):
        """Get maximum amount that can be dispatch for a given generator and offer type"""

        # Path to element containing quantity band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get('MaxAvail'))

    def get_mnsp_price_band_value(self, interconnector_id, region, band):
        """Get price band value for given MNSP and price band"""

        # Path to element containing price band information for given interconnector and region
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"MNSPPriceStructureCollection/MNSPPriceStructure/MNSPRegionPriceStructureCollection/"
                f"MNSPRegionPriceStructure[@RegionID='{region}']")

        return float(self.interval_data.find(path).get(f'PriceBand{band}'))

    def get_mnsp_quantity_band_value(self, interconnector_id, region, band):
        """Get quantity band value for given MNSP and quantity band"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector_id}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region}']")

        return float(self.interval_data.find(path).get(f'BandAvail{band}'))

    def get_mnsp_max_available_value(self, interconnector, region):
        """Get price band value for given MNSP and price band"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region}']")

        return float(self.interval_data.find(path).get(f'MaxAvail'))

    def get_generic_constraint_rhs_value(self, constraint_id):
        """Get RHS value for generic constraint. Note: using constraint solution elements to extract this value."""

        # Path to element containing generic constraint information for a given constraint ID
        # Note: only consider no intervention case for now
        path = f".//NemSpdOutputs/ConstraintSolution[@ConstraintID='{constraint_id}'][@Intervention='0']"

        return float(self.interval_data.find(path).get('RHS'))

    def get_generic_constraint_cvf_value(self, constraint_id):
        """Get Constraint Violation Factor for generic constraint"""

        # Path to element containing generic constraint information for a given constraint ID
        path = f".//NemSpdInputs/GenericConstraintCollection/GenericConstraint[@ConstraintID='{constraint_id}']"

        return float(self.interval_data.find(path).get('ViolationPrice'))

    def get_trader_types(self):
        """Get types of traders"""

        # Path to elements containing price band information. Also contains trader type for each unit.
        path = './/NemSpdInputs/TraderCollection/Trader'

        return list(set([u.get('TraderType') for u in self.interval_data.findall(path)]))

    def get_trader_type(self, trader_id):
        """Get type of trader for given trader ID"""

        # Path to elements containing price band information. Also contains trader type for each unit.
        path = f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']"

        return self.interval_data.find(path).get('TraderType')

    @staticmethod
    def get_interconnector_types():
        """Assuming only one type of interconnector trader."""

        return ['INTERCONNECTOR']

    def get_participant_types(self):
        """Get all trader and interconnector types"""

        # All interconnector and participant types. Used to differentiate generators, loads, and interconnectors.
        participant_types = self.get_trader_types() + self.get_interconnector_types()

        return participant_types

    def get_generic_constraint_types(self):
        """Get types of generic constraints (GE, LE, EQ) e.g. an inequality or equality constraint"""

        # Path to elements containing Generic Constraint information
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint'

        return list(set([c.get('Type') for c in self.interval_data.findall(path)]))

    def get_generic_constraint_type(self, constraint_id):
        """Get type of generic constraint (GE, LE, EQ) e.g. an inequality or equality constraint"""

        # Path to elements containing Generic Constraint information
        path = f".//NemSpdInputs/GenericConstraintCollection/GenericConstraint[@ConstraintID='{constraint_id}']"

        return self.interval_data.find(path).get('Type')

    def get_interconnector_from_region(self, interconnector):
        """Get interconnector 'from' region"""

        # Path to elements containing interconnector information
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector}']")

        return self.interval_data.find(path).get('FromRegion')

    def get_interconnector_to_region(self, interconnector):
        """Get interconnector 'to' region"""

        # Path to elements containing interconnector information
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector}']")

        return self.interval_data.find(path).get('ToRegion')

    def get_lhs_terms(self, constraint_id):
        """Get trader, interconnector, and region terms along with associated factors for a given constraint ID"""

        # Path to generic constraint
        path = f".//NemSpdInputs/GenericConstraintCollection/GenericConstraint[@ConstraintID='{constraint_id}']"

        # Extract constraint information
        constraint = self.interval_data.find(path)

        # Get trader factors
        trader_factors = {(i.get('TraderID'), i.get('TradeType')): float(i.get('Factor')) for i in
                          constraint.findall('.//LHSFactorCollection/TraderFactor')}

        # Get interconnector factors
        interconnector_factors = {(i.get('InterconnectorID')): float(i.get('Factor')) for i in
                                  constraint.findall('.//LHSFactorCollection/InterconnectorFactor')}

        # Get region factors
        region_factors = {(i.get('RegionID'), i.get('TradeType')): float(i.get('Factor')) for i in
                          constraint.findall('.//LHSFactorCollection/RegionFactor')}

        # Combine terms into a single dictionary
        terms = {'trader_factors': trader_factors, 'interconnector_factors': interconnector_factors,
                 'region_factors': region_factors}

        return terms

    def get_trader_observed_dispatch(self, trader_id):
        """Get observed dispatch for each trader"""

        # Path to elements containing energy target information (only consider no intervention case for now)
        path = f".//NemSpdOutputs/TraderSolution[@Intervention='0'][@TraderID='{trader_id}']"

        # Target energy output for a given unit
        unit_target = self.interval_data.find(path)

        return unit_target.attrib

    def get_trader_solution_dataframe(self):
        """Get observed dispatch for each trader and display in a Pandas DataFrame"""

        # Path to elements containing energy target information (only consider no intervention case for now)
        path = f".//NemSpdOutputs/TraderSolution[@Intervention='0']"

        # Construct DataFrame
        df = pd.DataFrame([i.attrib for i in self.interval_data.findall(path)]).set_index(['TraderID'])

        # Try and make all values floats if possible
        for c in df.columns:
            df[c] = df[c].astype(float, errors='ignore')

        return df

    def get_trader_initial_condition_mw(self, trader_id):
        """Get initial MW output for given trader"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition[@InitialConditionID='InitialMW']")

        # Get initial MW value
        initial_mw = float(self.interval_data.find(path).get('Value'))

        # If value is less than 0, return 0
        if initial_mw < 0:
            return 0
        else:
            return initial_mw

    def get_trader_ramp_up_rate(self, trader_id):
        """Get ramp rate up (MW/h) for given trader"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='ENOF']")

        return float(self.interval_data.find(path).get('RampUpRate'))

    def get_trader_ramp_down_rate(self, trader_id):
        """Get ramp rate down (MW/h) for given trader"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='ENOF']")

        return float(self.interval_data.find(path).get('RampDnRate'))

    def get_trader_initial_condition_ramp_rate_down(self, trader_id):
        """Get ramp rate up (MW/h) for given trader"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='ENOF']")

        return float(self.interval_data.find(path).get('RampDnRate'))

    def get_trader_initial_condition_max_mw(self, trader_id):
        """Get ramp rate up (MW/h) for given trader"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition[@InitialConditionID='HMW']")

        return float(self.interval_data.find(path).get('Value'))

    def get_trader_initial_condition_min_mw(self, trader_id):
        """Get ramp rate up (MW/h) for given trader"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition[@InitialConditionID='LMW']")

        return float(self.interval_data.find(path).get('Value'))

    def get_interconnector_initial_condition_mw(self, interconnector_id):
        """Get initial flow over given interconnector"""

        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"InterconnectorInitialConditionCollection"
                f"/InterconnectorInitialCondition[@InitialConditionID='InitialMW']")

        return float(self.interval_data.find(path).get('Value'))

    def get_trader_semi_dispatch_value(self, trader_id):
        """Check if trader is semi dispatchable (1=is semi dispatchable, 0=not semi-dispatchable)"""

        # Path to trader information elements
        path = f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']"

        return int(self.interval_data.find(path).get('SemiDispatch'))

    def get_constraint_violation_ramp_rate_penalty(self):
        """Get penalty factor associated with violating ramp-rate"""

        # Path to general case information
        path = './/NemSpdInputs/Case'

        return float(self.interval_data.find(path).get('RampRatePrice'))

    def get_interconnector_observed_flow_value(self, interconnector_id):
        """Get observed flow over a given interconnector"""

        # Path to interconnector element
        path = f".//NemSpdOutputs/InterconnectorSolution[@InterconnectorID='{interconnector_id}']"

        return float(self.interval_data.find(path).get('Flow'))

    def get_interconnector_solution_dataframe(self):
        """Get interconnector solution in DataFrame format"""

        # Path to interconnector solution elements. Only consider no intervention case for now.
        path = f".//NemSpdOutputs/InterconnectorSolution[@Intervention='0']"

        # All interconnectors
        interconnectors = self.interval_data.findall(path)

        # Extract solution information
        df = pd.DataFrame([i.attrib for i in interconnectors]).set_index('InterconnectorID')

        # Attempt to convert all columns to float
        for c in df.columns:
            df[c] = df[c].astype(float, errors='ignore')

        return df

    def get_trader_cost_function(self, trader_id, offer_type):
        """Extract price and quantity band information for given trader and offer type and visualise bids"""

        # Extract prices and quantities
        prices = [self.get_trader_price_band_value(trader_id, offer_type, b) for b in range(1, 11)]
        quantities = [self.get_trader_quantity_band_value(trader_id, offer_type, b) for b in range(1, 11)]

        # Combine into single object
        cost = list(zip(prices, quantities))

        # Extract non-zero offers. Duplicate first price (for plotting step function)
        y_price = [i[0] for i in cost if i[1] != 0]
        y_price = [y_price[0]] + y_price

        x_quantity = [i[1] for i in cost if i[1] != 0]
        x_quantity = [0] + x_quantity
        x_quantity = list(np.cumsum(x_quantity))

        fig, ax = plt.subplots()
        ax.step(x_quantity, y_price, where='pre')
        ax.set_ylabel('Price ($/MWh)')
        ax.set_xlabel('Offer (MW)')
        ax.set_title(f'{trader_id} {offer_type}')
        plt.show()

        return prices, quantities

    def get_region_initial_demand_value(self, region_id):
        """Get region initial demand"""

        # Path to elements containing region information
        path = (f".//NemSpdInputs/RegionCollection/Region[@RegionID='{region_id}']/RegionInitialConditionCollection/"
                f"RegionInitialCondition[@InitialConditionID='InitialDemand']")

        return float(self.interval_data.find(path).get('Value'))

    def get_region_demand_forecast_value(self, region_id):
        """Get forecast demand for a given region"""

        # Path to region information elements
        path = f".//NemSpdInputs/PeriodCollection/Period/RegionPeriodCollection/RegionPeriod[@RegionID='{region_id}']"

        return float(self.interval_data.find(path).get('DemandForecast'))

    def get_region_ids(self):
        """Get NEM region IDs"""

        # Path to region information elements
        path = f'.//NemSpdInputs/PeriodCollection/Period/RegionPeriodCollection/RegionPeriod'

        return [i.get('RegionID') for i in self.interval_data.findall(path)]

    def get_trader_region_id(self, trader_id):
        """Get the NEM region to which a given trader belongs"""

        # Path to trader elements
        path = f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"

        return self.interval_data.find(path).get('RegionID')

    def get_trader_fcas_enablement_min_value(self, trader_id, offer_type):
        """Get FCAS trapezium min enablement value"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'EnablementMin'))

    def get_trader_fcas_enablement_max_value(self, trader_id, offer_type):
        """Get FCAS trapezium max enablement value"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'EnablementMax'))

    def get_trader_fcas_low_breakpoint_value(self, trader_id, offer_type):
        """Get FCAS trapezium low breakpoint value"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'LowBreakpoint'))

    def get_trader_fcas_high_breakpoint_value(self, trader_id, offer_type):
        """Get FCAS trapezium high breakpoint value"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'HighBreakpoint'))

    def get_trader_scada_ramp_up_rate_value(self, trader_id):
        """Get AGC ramp-up capability"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition/[@InitialConditionID='SCADARampUpRate']")

        return float(self.interval_data.find(path).get('Value'))

    def get_trader_scada_ramp_down_rate_value(self, trader_id):
        """Get AGC ramp-down capability"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition/[@InitialConditionID='SCADARampDnRate']")

        return float(self.interval_data.find(path).get('Value'))

    def get_trader_scada_agc_status_value(self, trader_id):
        """Get AGC status"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition/[@InitialConditionID='AGCStatus']")

        return int(self.interval_data.find(path).get('Value'))

    def get_trader_scada_agc_upper_limit_value(self, trader_id):
        """Get AGC upper MW limit"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition/[@InitialConditionID='HMW']")

        return float(self.interval_data.find(path).get('Value'))

    def get_trader_scada_agc_lower_limit_value(self, trader_id):
        """Get AGC lower MW limit"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition/[@InitialConditionID='LMW']")

        return float(self.interval_data.find(path).get('Value'))


if __name__ == '__main__':
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    nemde = NEMDEData(data_directory)

    yr, mt, dy, iv = 2019, 10, 10, 1
    nemde.load_interval(yr, mt, dy, iv)

    trd_ids = nemde.get_trader_ids()
    trd_offer_index = nemde.get_trader_offer_index()
    mp_id = nemde.get_mnsp_ids()
    int_id = nemde.get_interconnector_ids()
    mp_o_index = nemde.get_mnsp_offer_index()
    sd = nemde.get_trader_semi_dispatch_value('AGLHAL')

    d = nemde.get_interconnector_solution_dataframe()

    p, q = nemde.get_trader_cost_function('DALNTHL1', 'L6SE')

    demand = [nemde.get_region_initial_demand_value(r) for r in ['SA1', 'VIC1', 'NSW1', 'QLD1', 'TAS1']]

    ru = nemde.get_trader_scada_ramp_up_rate_value('VP6')
    rd = nemde.get_trader_scada_ramp_down_rate_value('VP6')
    agc = nemde.get_trader_scada_agc_status_value('VP6')

    agc_u = nemde.get_trader_scada_agc_upper_limit_value('VP6')
    agc_l = nemde.get_trader_scada_agc_lower_limit_value('VP6')
