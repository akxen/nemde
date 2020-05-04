"""
Processing data for NEMDE approximation

Note: major speed-up observed when using 'find' instead of 'findall'. First method is less robust though (may have have
duplicate values). Using 'find' for now though.
"""

import os
import io
import zipfile

import xmltodict
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt


class MMSDMDataHandler:
    def __init__(self, data_dir):
        # Root folder containing MMSDM and NEMDE output files
        self.data_dir = data_dir

        # Loader containing NEMDE files
        self.mmsdm_dir = os.path.join(data_dir, 'MMSDM', 'zipped')

        # Summary of DUIDs (contains marginal loss factor information)
        self.dudetailsummary = None

    def load_file(self, year, month, name):
        """Load NEMDE input / output file"""

        z_1_name = f'MMSDM_{year}_{month:02}.zip'

        print(os.listdir(self.mmsdm_dir))

        with zipfile.ZipFile(os.path.join(self.mmsdm_dir, z_1_name)) as z_1:
            z_2_name = f'MMSDM_{year}_{month:02}/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_DVD_{name}_{year}{month:02}010000.zip'
            with z_1.open(z_2_name) as z_2:
                z_2_data = io.BytesIO(z_2.read())

                with zipfile.ZipFile(z_2_data) as z_3:
                    z_3_name = f'PUBLIC_DVD_{name}_{year}{month:02}010000.CSV'

                    # Read into DataFrame. Skip first and last rows.
                    df = pd.read_csv(z_3.open(z_3_name), skiprows=1)
                    df = df.iloc[:-1]

                    return df

    def load_interval(self, year, month):
        """Load data and bind to class attribute"""

        # Summary of DUID details (contains marginal loss factor information)
        self.dudetailsummary = self.load_file(year, month, 'DUDETAILSUMMARY')

    def get_marginal_loss_factor(self, trader_id):
        """Get marginal loss factor for a given trader"""

        # Remove duplicates - keep the latest record
        # TODO: May need to adjust this
        df = self.dudetailsummary.drop_duplicates(subset=['DUID'], keep='last')

        # Extract the transmission loss factor (Marginal Loss Factor) for given trader
        return float(df.loc[df['DUID'] == trader_id, 'TRANSMISSIONLOSSFACTOR'])


class NEMDEDataHandler:
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
            z_2_name = f'NEMDE_{year}_{month:02}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{year}{month:02}{day:02}_loaded.zip'
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

    @staticmethod
    def assert_single_value(data):
        """Check that only one value within list, else raise exception"""

        assert len(data) == 1, f'Length of list != 1. List has {len(data)} elements'

    @staticmethod
    def assert_no_duplicates(data):
        """Check no duplicates within list"""

        assert len(data) > 0, 'List is empty'

        assert (len(data) == len(set(data))), 'Duplicates within list'

    def parse_single_attribute(self, data, attribute):
        """Check that only one element exists. Extract attribute value and attempt float conversion."""

        # Check there is only one value returned
        self.assert_single_value(data)

        # Attribute value
        value = data[0].get(attribute)

        # Try and convert to float if possible
        try:
            return float(value)
        except ValueError:
            return value

    def get_region_index(self):
        """Get index for all NEM regions"""

        # Path to region information elements
        path = f'.//NemSpdInputs/PeriodCollection/Period/RegionPeriodCollection/RegionPeriod'

        # All region IDs
        region_ids = [i.get('RegionID') for i in self.interval_data.findall(path)]

        # Check for duplicate values
        self.assert_no_duplicates(region_ids)

        return region_ids

    def get_trader_index(self):
        """Get index used for all traders"""

        # Path to trader elements
        path = ".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod"

        # All traders
        traders = self.interval_data.findall(path)

        # Construct index based on element attributes
        trader_ids = [t.get('TraderID') for t in traders]

        # Check there are no duplicates
        self.assert_no_duplicates(trader_ids)

        return trader_ids

    def get_trader_offer_index(self):
        """Get index for all trader offers"""

        # Path to trader elements
        path = ".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod"

        # All market units that are market participants
        traders = self.interval_data.findall(path)

        # Construct index based on element attributes
        trader_offer_ids = [(t.get('TraderID'), o.get('TradeType')) for t in traders for o in t.findall('.//Trade')]

        # Check there are no duplicates
        self.assert_no_duplicates(trader_offer_ids)

        return trader_offer_ids

    def get_interconnector_index(self):
        """Get names for all interconnectors"""

        # Path to interconnector elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod"

        # Get MNSP elements
        interconnectors = self.interval_data.findall(path)

        # Extract interconnector IDs
        interconnector_ids = [i.get('InterconnectorID') for i in interconnectors]

        # Check there are no duplicates
        self.assert_no_duplicates(interconnector_ids)

        return interconnector_ids

    def get_mnsp_index(self):
        """Get index used for all Market Network Service Providers (MNSPs)"""

        # Path to MNSP elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod[@MNSP='1']"

        # Get MNSP elements
        mnsps = self.interval_data.findall(path)

        # Extract MNSP IDs
        mnsp_ids = [i.get('InterconnectorID') for i in mnsps]

        # Check there are no duplicates
        self.assert_no_duplicates(mnsp_ids)

        return mnsp_ids

    def get_mnsp_offer_index(self):
        """Get index for all MNSP offers"""

        # Path to MNSP elements
        path = ".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/InterconnectorPeriod[@MNSP='1']"

        # Get MNSP elements
        mnsps = self.interval_data.findall(path)

        # Construct MNSP offer index based on interconnector ID and region name (price bands for each region)
        mnsp_offer = [(i.get('InterconnectorID'), o.get('RegionID')) for i in mnsps for o in i.findall('.//MNSPOffer')]

        # Check there are no duplicates
        self.assert_no_duplicates(mnsp_offer)

        return mnsp_offer

    def get_generic_constraint_index(self, intervention=0):
        """
        Get index for all generic constraints. Note: using constraint solution to identify constraints that were used
        """

        # Path to generic constraint solution objects
        path = f".//NemSpdOutputs/ConstraintSolution/[@Intervention='{intervention}']"

        # All generic constraints. Only consider no intervention case for now.
        constraints = self.interval_data.findall(path)

        # Extract constraint IDs
        constraint_ids = [c.get('ConstraintID') for c in constraints]

        # Check there are no duplicates
        self.assert_no_duplicates(constraint_ids)

        return constraint_ids

    def get_generic_constraint_trader_variable_index(self):
        """Get index of all trader variables within generic constraints"""

        # Path to trader factor elements within generic constraints
        # TODO: May need to consider intervention. Could define variables with respect solution tags instead.
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/TraderFactor'

        # Extract all trader factor elements from generic constraints
        factors = self.interval_data.findall(path)

        # Construct ID for trader factor variables
        var_ids = list(set([(f.get('TraderID'), f.get('TradeType')) for f in factors]))

        # Check there are no duplicates
        self.assert_no_duplicates(var_ids)

        return var_ids

    def get_generic_constraint_interconnector_variable_index(self):
        """Get index of all interconnector variables within generic constraints"""

        # Path to interconnector elements
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/InterconnectorFactor'

        # Extract all interconnector factor elements from generic constraints
        factors = self.interval_data.findall(path)

        # Construct ID for trader factor variables
        var_ids = list(set(f.get('InterconnectorID') for f in factors))

        # Check there are no duplicates
        self.assert_no_duplicates(var_ids)

        return var_ids

    def get_generic_constraint_region_variable_index(self):
        """Get index of all region variables within generic constraints"""

        # Path to region elements
        path = './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/RegionFactor'

        # Extract all interconnector factor elements from generic constraints
        factors = self.interval_data.findall(path)

        # Construct ID for trader factor variables
        var_ids = list(set([(f.get('RegionID'), f.get('TradeType')) for f in factors]))

        return var_ids

    def get_generic_constraint_attribute(self, constraint_id, attribute):
        """High-level generic constraint information. E.g. constraint type, violation price, etc."""

        # Path to element containing generic constraint information for a given constraint ID
        path = f".//NemSpdInputs/GenericConstraintCollection/GenericConstraint[@ConstraintID='{constraint_id}']"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_generic_constraint_lhs_terms(self, constraint_id):
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
        terms = {'traders': trader_factors, 'interconnectors': interconnector_factors, 'regions': region_factors}

        return terms

    def get_generic_constraint_solution_attribute(self, constraint_id, attribute, intervention=0):
        """Get generic constraint solution information. E.g. marginal value."""

        # Path to element containing generic constraint information for a given constraint ID
        path = f".//NemSpdOutputs/ConstraintSolution[@ConstraintID='{constraint_id}'][@Intervention='{intervention}']"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_trader_attribute(self, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""

        # Path to elements containing price band information. Also contains trader type for each unit.
        path = f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']"

        # Trader elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_trader_period_attribute(self, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""

        # Path to elements containing price band information. Also contains trader type for each unit.
        path = f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"

        # Trader elements
        # TODO: May need to use findall in order to check no duplicates returned
        # elements = self.interval_data.findall(path)
        elements = [self.interval_data.find(path)]

        return self.parse_single_attribute(elements, attribute)

    def get_trader_initial_condition_attribute(self, trader_id, attribute):
        """Get trader initial condition information"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        # Check only one element
        self.assert_single_value(elements)

        # Return AGC status as an int if specified as the attribute
        if attribute == 'AGCStatus':
            return int(elements[0].get('Value'))
        else:
            return float(elements[0].get('Value'))

    def get_trader_price_band_attribute(self, trader_id, trade_type, attribute):
        """Get price band information"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TradePriceStructureCollection/"
                f"TradePriceStructure/TradeTypePriceStructureCollection/"
                f"TradeTypePriceStructure[@TradeType='{trade_type}']")

        # Matching elements
        # TODO: May need to replace find with findall (more robust when handling duplicates)
        # elements = self.interval_data.findall(path)
        elements = [self.interval_data.find(path)]

        return self.parse_single_attribute(elements, attribute)

    def get_trader_quantity_band_attribute(self, trader_id, trade_type, attribute):
        """Get trader quantity band information"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{trade_type}']")

        # Matching elements
        # elements = self.interval_data.findall(path)
        elements = [self.interval_data.find(path)]

        return self.parse_single_attribute(elements, attribute)

    def get_trader_solution_attribute(self, trader_id, attribute, intervention=0):
        """Get trader solution information (shows actual energy targets)"""

        # Path to elements containing energy target information (only consider no intervention case for now)
        path = f".//NemSpdOutputs/TraderSolution[@TraderID='{trader_id}'][@Intervention='{intervention}']"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_trader_solution_dataframe(self, intervention=0):
        """Get observed dispatch for each trader and display in a Pandas DataFrame"""

        # Path to elements containing energy target information (only consider no intervention case for now)
        path = f".//NemSpdOutputs/TraderSolution[@Intervention='{intervention}']"

        # Construct DataFrame
        df = pd.DataFrame([i.attrib for i in self.interval_data.findall(path)]).set_index(['TraderID'])

        # Try and make all values floats if possible
        for c in df.columns:
            df[c] = df[c].astype(float, errors='ignore')

        return df

    def get_interconnector_attribute(self, interconnector_id, attribute):
        """Get high-level attribute for given interconnector e.g. FromRegionLF, ToRegionLF, etc"""

        # Path to interconnector elements
        path = f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_interconnector_initial_condition_attribute(self, interconnector_id, attribute):
        """Get interconnection initial condition information"""

        # Path to interconnector elements
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"InterconnectorInitialConditionCollection/"
                f"InterconnectorInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, 'Value')

    def get_interconnector_period_attribute(self, interconnector_id, attribute):
        """High-level attribute giving access to interconnector limits and 'from' and 'to' regions"""

        # Path to MNSP elements
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector_id}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_interconnector_solution_attribute(self, interconnector_id, attribute, intervention=0):
        """Get interconnector solution information"""

        # Path to interconnector solution elements. Only consider no intervention case for now.
        path = (f".//NemSpdOutputs/"
                f"InterconnectorSolution[@InterconnectorID='{interconnector_id}'][@Intervention='{intervention}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_mnsp_price_band_attribute(self, mnsp_id, region_id, attribute):
        """Get price band information for given MNSP for a bids in a given region"""

        # Path to element containing price band information for given interconnector and region
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{mnsp_id}']/"
                f"MNSPPriceStructureCollection/MNSPPriceStructure/MNSPRegionPriceStructureCollection/"
                f"MNSPRegionPriceStructure[@RegionID='{region_id}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_mnsp_quantity_band_attribute(self, mnsp_id, region_id, attribute):
        """Get price band information for given MNSP for a bids in a given region"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{mnsp_id}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region_id}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_case_attribute(self, attribute):
        """Get case input attributes"""

        # Path to element containing case information
        path = f".//NemSpdInputs/Case"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_case_solution_attribute(self, attribute):
        """Get case solution information"""

        # Path to element containing case solution information
        path = f".//NemSpdOutputs/CaseSolution"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_period_solution_attribute(self, attribute):
        """High-level period solution information"""

        # Path to element containing period solution information
        path = f".//NemSpdOutputs/PeriodSolution"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_region_period_attribute(self, region_id, attribute):
        """Get region period attributes e.g. demand forecast"""

        # Path to element containing region period information
        path = f".//NemSpdInputs/PeriodCollection/Period/RegionPeriodCollection/RegionPeriod[@RegionID='{region_id}']"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_region_initial_condition_attribute(self, region_id, attribute):
        """Get region attributes"""

        # Path to element containing case information
        path = (f".//NemSpdInputs/RegionCollection/Region[@RegionID='{region_id}']/RegionInitialConditionCollection/"
                f"RegionInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, 'Value')

    def get_region_solution_attribute(self, region_id, attribute, intervention=0):
        """Get region solution information"""

        # Path to element containing region solution information
        path = f".//NemSpdOutputs/RegionSolution[@RegionID='{region_id}'][@Intervention='{intervention}']"

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_constraint_scada_attribute_partial_id(self, spd_type, ems_id, spd_id_start, attribute):
        """Get constraint SCADA attribute"""

        # Path to element containing SCADA information
        path = (f".//NemSpdInputs/ConstraintScadaDataCollection/ConstraintScadaData[@SpdType='{spd_type}']"
                f"/ScadaValuesCollection/ScadaValues")

        # Matching elements
        elements = self.interval_data.findall(path)

        # Get elements
        print(spd_type, ems_id, spd_id_start, attribute)
        els = [i for i in elements if (i.get('EMS_ID') == ems_id) and (i.get('SpdID').startswith(spd_id_start))]

        return self.parse_single_attribute(els, attribute)

    def get_non_scheduled_generators(self):
        """Get non-scheduled generators"""

        # Path to elements
        path = f".//NemSpdInputs/PeriodCollection/Period/Non_Scheduled_Generator_Collection/Non_Scheduled_Generator"

        # Matching elements
        elements = self.interval_data.findall(path)

        return [i.get('DUID') for i in elements]

    def get_non_scheduled_generator_dispatch(self, duid, attribute):
        """Get non-scheduled generator dispatch"""

        # Path to elements
        path = (f".//NemSpdInputs/PeriodCollection/Period/Non_Scheduled_Generator_Collection"
                f"/Non_Scheduled_Generator[@DUID='{duid}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    # TODO: can delete this method
    def get_trader_solutions(self):
        """Get trader solution"""

        # Path to elements
        path = f".//NemSpdOutputs/TraderSolution"

        # Matching elements
        elements = self.interval_data.findall(path)

        return elements

    def get_total_generation(self):
        """Compute total generation based on energy target for each trader"""

        total = 0
        for i, j in self.get_trader_offer_index():
            if j == 'ENOF':
                total += self.get_trader_solution_attribute(i, 'EnergyTarget')

        return total

    def get_total_load(self):
        """Compute total load based on energy target for each trader"""

        total = 0
        for i, j in self.get_trader_offer_index():
            if j == 'LDOF':
                total += self.get_trader_solution_attribute(i, 'EnergyTarget')

        return total

    def get_total_losses(self):
        """Get total losses for each interconnector"""

        total = 0
        for i in self.get_interconnector_index():
            total += self.get_interconnector_solution_attribute(i, 'Losses')

        return total

    def get_total_cleared_demand(self):
        """Total cleared demand from region solution"""

        total = 0
        for i in self.get_region_index():
            total += self.get_region_solution_attribute(i, 'ClearedDemand')

        return total

    def get_total_forecast_demand(self):
        """Total forecast demand for each regions"""

        total = 0
        for i in self.get_region_index():
            total += self.get_region_period_attribute(i, 'DemandForecast')

        return total

    def get_total_generator_initial_mw(self):
        """Get total initial MW for generators"""

        total = 0
        for i, j in self.get_trader_offer_index():
            if j == 'ENOF':
                total += self.get_trader_initial_condition_attribute(i, 'InitialMW')

        return total

    def get_total_load_initial_mw(self):
        """Get total initial MW for loads"""

        total = 0
        for i, j in self.get_trader_offer_index():
            if j == 'LDOF':
                total += self.get_trader_initial_condition_attribute(i, 'InitialMW')

        return total

    def get_sa_demand(self):
        """Get interconnector ID"""

        total_generator_initial_mw = 0
        for i, j in self.get_trader_offer_index():
            # Get region
            generator_region_id = self.get_trader_period_attribute(i, 'RegionID')

            # Get initial MW for generators
            if (j == 'ENOF') and (generator_region_id == 'SA1'):
                total_generator_initial_mw += self.get_trader_initial_condition_attribute(i, 'InitialMW')

        total_load_initial_mw = 0
        for i, j in self.get_trader_offer_index():
            # Get region
            load_region_id = self.get_trader_period_attribute(i, 'RegionID')

            # Get semi-dispatch status
            semi_dispatch = self.get_trader_attribute(i, 'SemiDispatch')

            # Get initial MW for loads (scheduled loads)
            if (j == 'LDOF') and (load_region_id == 'SA1') and (semi_dispatch == 0):
                total_load_initial_mw += self.get_trader_initial_condition_attribute(i, 'InitialMW')

        # Flow into region
        v_sa_flow = self.get_interconnector_solution_attribute('V-SA', 'Flow')
        v_mnsp_flow = self.get_interconnector_solution_attribute('V-S-MNSP1', 'Flow')

        # Losses
        v_sa_losses = self.get_interconnector_solution_attribute('V-SA', 'Losses')
        sa_v_sa_losses = abs(v_sa_losses) * (1 - 0.73)

        v_mnsp_losses = self.get_interconnector_solution_attribute('V-S-MNSP1', 'Losses')
        sa_v_mnsp_losses = abs(v_mnsp_losses) * (1 - 0.73)

        # Demand forecast
        demand_forecast = self.get_region_period_attribute('SA1', 'DF')

        # Aggregate dispatch error
        ade = self.get_region_initial_condition_attribute('SA1', 'ADE')

        total_demand = (total_generator_initial_mw - total_load_initial_mw + v_sa_flow + v_mnsp_flow - sa_v_sa_losses
                        - sa_v_mnsp_losses + demand_forecast + ade)

        return total_demand


if __name__ == '__main__':
    # Root directory containing NEMDE and MMSDM files
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to parse NEMDE file
    nemde_data = NEMDEDataHandler(data_directory)
    mmsdm_data = MMSDMDataHandler(data_directory)

    # Load interval
    nemde_data.load_interval(2019, 10, 10, 1)

    sa_total_demand = nemde_data.get_sa_demand()
    sa_cleared_demand = nemde_data.get_region_solution_attribute('SA1', 'ClearedDemand')
    sa_initial_demand = nemde_data.get_region_initial_condition_attribute('SA1', 'InitialDemand')
    sa_demand_forecast = nemde_data.get_region_period_attribute('SA1', 'DemandForecast')
    sa_ade = nemde_data.get_region_initial_condition_attribute('SA1', 'ADE')

    # total_generation = nemde_data.get_total_generation()
    # total_load = nemde_data.get_total_load()
    # total_losses = nemde_data.get_total_losses()
    # total_cleared_demand = nemde_data.get_total_cleared_demand()
    # total_forecast_demand = nemde_data.get_total_forecast_demand()
    #
    # total_generator_initial_mw = nemde_data.get_total_generator_initial_mw()
    # total_load_initial_mw = nemde_data.get_total_load_initial_mw()



    # total_load + total_cleared_demand

    # a = nemde_data.get_trader_solutions()
    # len(set([i[0] for i in nemde_data.get_trader_offer_index()]))

    # a = nemde_data.get_non_scheduled_generators()
    # b = nemde_data.get_non_scheduled_generator_dispatch('BARCSF1', 'MW')

    # a = nemde_data.get_constraint_scada_attribute_partial_id('A', 'INER', '220_GEN_INERTIA', 'Value')
    # a = nemde_data.get_constraint_scada_attribute_partial_id('A', 'INER', '220_GEN_', 'Grouping_ID')

    # # Testing methods
    # region_index = nemde_data.get_region_index()
    # trader_index = nemde_data.get_trader_index()
    # trader_offer_index = nemde_data.get_trader_offer_index()
    # interconnector_index = nemde_data.get_interconnector_index()
    # mnsp_index = nemde_data.get_mnsp_index()
    # mnsp_offer_index = nemde_data.get_mnsp_offer_index()
    # generic_constraint_index = nemde_data.get_generic_constraint_index()
    # generic_constraint_trader_variable_index = nemde_data.get_generic_constraint_trader_variable_index()
    # generic_constraint_interconnector_variable_index = nemde_data.get_generic_constraint_interconnector_variable_index()
    # generic_constraint_region_variable_index = nemde_data.get_generic_constraint_region_variable_index()
    #
    # constraint_attribute_value = nemde_data.get_generic_constraint_attribute('V_WEMENSF_19INV', 'Type')
    # constraint_lhs_terms = nemde_data.get_generic_constraint_lhs_terms('V_WEMENSF_19INV')
    # constraint_rhs = nemde_data.get_generic_constraint_solution_attribute('V_WEMENSF_19INV', 'RHS')
    #
    # trader_initial_mw = nemde_data.get_trader_initial_condition_attribute('AGLHAL', 'InitialMW')
    #
    # price_1 = nemde_data.get_trader_price_band_attribute('AGLHAL', 'ENOF', 'PriceBand1')
    # quantity_1 = nemde_data.get_trader_quantity_band_attribute('AGLHAL', 'ENOF', 'BandAvail1')
    #
    # trader_r6 = nemde_data.get_trader_solution_attribute('AGLHAL', 'R6Target')
    # icon_id = nemde_data.get_interconnector_attribute('N-Q-MNSP1', 'InterconnectorID')
    # icon_initial_mw = nemde_data.get_interconnector_initial_condition_attribute('N-Q-MNSP1', 'InitialMW')
    #
    # icon_from_region = nemde_data.get_interconnector_period_attribute('N-Q-MNSP1', 'FromRegion')
    # mnsp_p1 = nemde_data.get_mnsp_price_band_attribute('T-V-MNSP1', 'TAS1', 'PriceBand1')
    # mnsp_q1 = nemde_data.get_mnsp_quantity_band_attribute('T-V-MNSP1', 'TAS1', 'BandAvail1')
    #
    # case_price = nemde_data.get_case_attribute('EnergyDeficitPrice')
    # case_solution = nemde_data.get_case_solution_attribute('TotalObjective')
    # period_solution = nemde_data.get_period_solution_attribute('TotalASProfileViolation')
    #
    region_initial = nemde_data.get_region_initial_condition_attribute('NSW1', 'InitialDemand')
    # region_solution = nemde_data.get_region_solution_attribute('NSW1', 'EnergyPrice')

    # Get all marginal loss factors
    # mmsdm_data.load_interval(2019, 10)
