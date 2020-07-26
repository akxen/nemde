"""
Processing data for NEMDE approximation

Note: major speed-up observed when using 'find' instead of 'findall'. First method is less robust though (may have have
duplicate values). Using 'find' for now though.
"""

import os
import io
import json
import math
import zipfile
import collections

import xmltodict
import xml.etree.ElementTree as ET

from scipy import integrate
import numpy as np
import pandas as pd

import matplotlib

matplotlib.use('TkAgg')

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

        with zipfile.ZipFile(os.path.join(self.nemde_dir, z_1_name)) as z_1:
            if f'NEMDE_{year}_{month:02}/NEMDE_Market_Data/' in z_1.namelist():
                z_2_name = f'NEMDE_{year}_{month:02}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{year}{month:02}{day:02}_loaded.zip'
            elif f'{month:02}/' in z_1.namelist():
                z_2_name = f'{month:02}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{year}{month:02}{day:02}_loaded.zip'
            else:
                raise Exception('Unexpected NEMDE directory structure')

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

    def get_nemde_json(self, year, month, day, interval):
        """Get NEMDE input / output file in dictionary format"""

        # Load NEMDE inputs / outputs
        data = self.load_file(year, month, day, interval)

        # Convert to dictionary
        info = xmltodict.parse(data)

        return json.dumps(info)

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
        """Get interconnector initial condition information"""

        # Path to interconnector elements
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"InterconnectorInitialConditionCollection/"
                f"InterconnectorInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, 'Value')

    def get_interconnector_loss_model_attribute(self, interconnector_id, attribute):
        """Get interconnector loss model attributes"""

        # Path to interconnector elements
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"LossModelCollection/LossModel")

        # Matching elements
        elements = self.interval_data.findall(path)

        return self.parse_single_attribute(elements, attribute)

    def get_interconnector_loss_model_segments(self, interconnector_id):
        """Get segments corresponding to interconnector loss model"""

        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"LossModelCollection/LossModel/SegmentCollection/Segment")

        # Matching elements
        elements = self.interval_data.findall(path)

        segments = []
        for e in elements:
            segment = {i: int(j) if i == 'Limit' else float(j) for i, j in e.attrib.items()}
            segments.append(segment)

        return segments

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

    def get_total_scheduled_load_initial_mw(self):
        """Get total initial MW for loads"""

        total = 0
        for i, j in self.get_trader_offer_index():
            # Get semi-dispatch status
            semi_dispatch = self.get_trader_attribute(i, 'SemiDispatch')

            # Get initial MW for loads (scheduled loads)
            if (j == 'LDOF') and (semi_dispatch == 0):
                total += self.get_trader_initial_condition_attribute(i, 'InitialMW')

        return total

    def get_total_scheduled_load_target_mw(self):
        """Get total initial MW for loads"""

        total = 0
        for i, j in self.get_trader_offer_index():
            # Get semi-dispatch status
            semi_dispatch = self.get_trader_attribute(i, 'SemiDispatch')

            # Get initial MW for loads (scheduled loads)
            if (j == 'LDOF') and (semi_dispatch == 0):
                total += self.get_trader_solution_attribute(i, 'EnergyTarget')

        return total

    def get_total_demand_forecast(self):
        """Total demand forecast increment across all regions"""

        total = 0
        for i in self.get_region_index():
            total += self.get_region_period_attribute(i, 'DF')

        return total

    def get_total_ade(self):
        """Get total aggregate dispatch error"""

        total = 0
        for i in self.get_region_index():
            total += self.get_region_initial_condition_attribute(i, 'ADE')

        return total

    def get_region_generator_initial_mw(self, region_id):
        """Total initial MW for a given region"""

        total = 0
        for i, j in self.get_trader_offer_index():
            # Get region
            trader_region_id = self.get_trader_period_attribute(i, 'RegionID')

            # Get initial MW for generators
            if (j == 'ENOF') and (trader_region_id == region_id):
                total += self.get_trader_initial_condition_attribute(i, 'InitialMW')
                # value = self.get_trader_initial_condition_attribute(i, 'InitialMW')
                # if value > 0:
                #     total += value

        return total

    def get_region_scheduled_load_initial_mw(self, region_id):
        """Total initial MW for a given region"""

        total = 0
        for i, j in self.get_trader_offer_index():
            # Get region
            trader_region_id = self.get_trader_period_attribute(i, 'RegionID')

            # Get semi-dispatch status
            semi_dispatch = self.get_trader_attribute(i, 'SemiDispatch')

            # Get initial MW for generators
            if (j == 'LDOF') and (trader_region_id == region_id) and (semi_dispatch == 0):
                total += self.get_trader_initial_condition_attribute(i, 'InitialMW')

        return total

    def get_region_scheduled_load_target_mw(self, region_id):
        """Total target MW for a given region"""

        total = 0
        for i, j in self.get_trader_offer_index():
            # Get region
            trader_region_id = self.get_trader_period_attribute(i, 'RegionID')

            # Get semi-dispatch status
            semi_dispatch = self.get_trader_attribute(i, 'SemiDispatch')

            # Get initial MW for generators
            if (j == 'LDOF') and (trader_region_id == region_id) and (semi_dispatch == 0):
                total += self.get_trader_solution_attribute(i, 'EnergyTarget')

        return total

    def get_region_initial_net_import(self, region_id):
        """Compute net import into region from interconnectors"""

        total = 0
        for i in self.get_interconnector_index():
            from_region = self.get_interconnector_period_attribute(i, 'FromRegion')
            to_region = self.get_interconnector_period_attribute(i, 'ToRegion')

            if region_id == from_region:
                total -= self.get_interconnector_initial_condition_attribute(i, 'InitialMW')
            elif region_id == to_region:
                total += self.get_interconnector_initial_condition_attribute(i, 'InitialMW')
            else:
                pass

        return total

    def get_region_target_net_import(self, region_id):
        """Compute net import into region from interconnectors"""

        total = 0
        for i in self.get_interconnector_index():
            from_region = self.get_interconnector_period_attribute(i, 'FromRegion')
            to_region = self.get_interconnector_period_attribute(i, 'ToRegion')

            if region_id == from_region:
                total -= self.get_interconnector_solution_attribute(i, 'Flow')
            elif region_id == to_region:
                total += self.get_interconnector_solution_attribute(i, 'Flow')
            else:
                pass

        return total

    def get_region_initial_net_allocated_losses(self, region_id):
        """Compute net import into region from interconnectors"""

        total = 0
        for i in self.get_interconnector_index():
            from_region = self.get_interconnector_period_attribute(i, 'FromRegion')
            to_region = self.get_interconnector_period_attribute(i, 'ToRegion')
            loss_share = self.get_interconnector_loss_model_attribute(i, 'LossShare')
            initial_flow = self.get_interconnector_initial_condition_attribute(i, 'InitialMW')
            estimated_losses = self.get_interconnector_loss_estimate(i, initial_flow)

            if region_id == from_region:
                total += estimated_losses * loss_share

            elif region_id == to_region:
                total += estimated_losses * (1 - loss_share)
            else:
                pass

        return total

    def get_region_target_net_allocated_losses(self, region_id):
        """Compute net import into region from interconnectors"""

        total = 0
        for i in self.get_interconnector_index():
            from_region = self.get_interconnector_period_attribute(i, 'FromRegion')
            to_region = self.get_interconnector_period_attribute(i, 'ToRegion')
            loss_share = nemde_data.get_interconnector_loss_model_attribute(i, 'LossShare')

            if region_id == from_region:
                total += self.get_interconnector_solution_attribute(i, 'Losses') * loss_share
            elif region_id == to_region:
                total += self.get_interconnector_solution_attribute(i, 'Losses') * (1 - loss_share)
            else:
                pass

        return total

    def get_region_summary(self, region_id):
        """Summarise region information"""

        values = {
            'region id': region_id,
            'generator initial MW': self.get_region_generator_initial_mw(region_id),
            'scheduled load initial MW': self.get_region_scheduled_load_initial_mw(region_id),
            'DF': self.get_region_period_attribute(region_id, 'DF'),
            'ADE': self.get_region_initial_condition_attribute(region_id, 'ADE'),
            'initial net import': self.get_region_initial_net_import(region_id),
            'initial allocated losses': self.get_region_initial_net_allocated_losses(region_id),
            'target net import': self.get_region_target_net_import(region_id),
            'target allocated losses': self.get_region_target_net_allocated_losses(region_id),
            'fixed demand': self.get_region_solution_attribute(region_id, 'FixedDemand'),
            'cleared demand': self.get_region_solution_attribute(region_id, 'ClearedDemand'),
            'target scheduled load': self.get_region_scheduled_load_target_mw(region_id),
        }

        total_demand = (
                values['generator initial MW'] - values['scheduled load initial MW'] + values['initial net import']
                - values['initial allocated losses'] + values['DF'] + values['ADE']
        )

        # Adjust for Basslink MLF between Loy Yang and RRN
        if region_id == 'VIC1':
            # Flow over Basslink
            basslink_flow = self.get_interconnector_initial_condition_attribute('T-V-MNSP1', 'InitialMW')

            # Import into VIC
            if basslink_flow > 40:
                mlf = self.get_interconnector_attribute('T-V-MNSP1', 'ToRegionLFImport')
            elif basslink_flow < -40:
                mlf = self.get_interconnector_attribute('T-V-MNSP1', 'ToRegionLFExport')
            else:
                raise Exception('No go zone for Basslink')

            if basslink_flow > 0:
                demand_adjustment = (basslink_flow - self.get_interconnector_loss_estimate('T-V-MNSP1',
                                                                                           basslink_flow)) * (1 - mlf)
            else:
                demand_adjustment = (basslink_flow + self.get_interconnector_loss_estimate('T-V-MNSP1',
                                                                                           basslink_flow)) * (1 - mlf)

            total_demand -= demand_adjustment

        values['total demand'] = total_demand
        values['total demand - fixed demand'] = values['total demand'] - values['fixed demand']

        return values

    def get_interconnector_summary(self, interconnector_id):
        """Summary of interconnector information"""

        # Extract interconnector information
        initial = self.get_interconnector_initial_condition_attribute(interconnector_id, 'InitialMW')
        target = self.get_interconnector_solution_attribute(interconnector_id, 'Flow')
        target_losses = self.get_interconnector_solution_attribute(interconnector_id, 'Losses')
        estimated_initial_losses = self.get_interconnector_loss_estimate(interconnector_id, initial)
        estimated_target_losses = self.get_interconnector_loss_estimate(interconnector_id, target)

        # Summarise values in a single dictionary
        values = {
            'interconnector id': interconnector_id,
            'initial MW': initial,
            'target MW': target,
            'difference': initial - target,
            'estimated initial loss': estimated_initial_losses,
            'target loss': target_losses,
            'estimated target loss': estimated_target_losses,
        }

        return values

    def get_nem_summary(self):
        """Summary statistics for entire NEM"""

        # Summarise values in single dictionary
        values = {'total fixed demand': sum(self.get_region_solution_attribute(i, 'FixedDemand')
                                            for i in nemde_data.get_region_index()),
                  'total cleared demand': sum(self.get_region_solution_attribute(i, 'ClearedDemand')
                                              for i in self.get_region_index()),
                  'total generation': sum(self.get_trader_solution_attribute(i, 'EnergyTarget')
                                          for i, j in nemde_data.get_trader_offer_index()
                                          if j == 'ENOF'),
                  'total scheduled load': sum(self.get_trader_solution_attribute(i, 'EnergyTarget')
                                              for i, j in nemde_data.get_trader_offer_index()
                                              if (j == 'LDOF') and (self.get_trader_attribute(i, 'SemiDispatch') == 0)),
                  'total losses': nemde_data.get_total_losses(),
                  }

        return values

    def get_dispatch_interval_summary(self, region_id, interconnector_ids):
        """Used to interrogate demand discrepancy for QLD"""

        # Extract interconnector information
        i_values = {}
        for i in interconnector_ids:
            initial = self.get_interconnector_initial_condition_attribute(i, 'InitialMW')
            target = self.get_interconnector_solution_attribute(i, 'Flow')
            target_losses = self.get_interconnector_solution_attribute(i, 'Losses')
            estimated_initial_losses = self.get_interconnector_loss_estimate(i, initial)
            estimated_target_losses = self.get_interconnector_loss_estimate(i, target)

            # Summarise values in a single dictionary
            i_v = {
                f'{i} InitialMW': initial,
                f'{i} target MW': target,
                f'{i} InitialMW - target MW ': initial - target,
                f'{i} estimated initial loss': estimated_initial_losses,
                f'{i} target loss': target_losses,
                f'{i} estimated target loss': estimated_target_losses,
                f'{i} loss share': self.get_interconnector_loss_model_attribute(i, 'LossShare'),
                f'{i} LossDemandConstant': self.get_interconnector_period_attribute(i, 'LossDemandConstant'),
            }
            i_values = {**i_v, **i_values}

        # Region summary
        r_values = {
            'region id': region_id,
            'generator InitialMW': self.get_region_generator_initial_mw(region_id),
            'scheduled load InitialMW': self.get_region_scheduled_load_initial_mw(region_id),
            'DF': self.get_region_period_attribute(region_id, 'DF'),
            'ADE': self.get_region_initial_condition_attribute(region_id, 'ADE'),
            'InitialDemand': self.get_region_initial_condition_attribute(region_id, 'InitialDemand'),
            'initial net import': self.get_region_initial_net_import(region_id),
            'initial total allocated losses': self.get_region_initial_net_allocated_losses(region_id),
            'target net import': self.get_region_target_net_import(region_id),
            'target allocated losses': self.get_region_target_net_allocated_losses(region_id),
            'fixed demand': self.get_region_solution_attribute(region_id, 'FixedDemand'),
            'cleared demand': self.get_region_solution_attribute(region_id, 'ClearedDemand'),
            'target scheduled load': self.get_region_scheduled_load_target_mw(region_id),
        }

        # Compute total demand
        total_demand = (
                r_values['generator InitialMW'] - r_values['scheduled load InitialMW'] + r_values['initial net import']
                - r_values['initial total allocated losses'] + r_values['DF'] + r_values['ADE']
        )
        r_values['total demand'] = total_demand

        # Difference between total demand and fixed demand (should be 0)
        r_values['total demand - fixed demand'] = r_values['total demand'] - r_values['fixed demand']

        # Total demand based on initial demand values
        r_values['total demand (calc 2)'] = (r_values['InitialDemand']
                                             + r_values['DF'] + r_values['ADE']
                                             - r_values['scheduled load InitialMW']
                                             - r_values['initial total allocated losses']
                                             - r_values['fixed demand'])

        # Combine into single dictionary
        values = {**r_values, **i_values}

        return values

    @staticmethod
    def get_nsw_qld_mlf(nsw_qld_flow, qld_demand, nsw_demand):
        """
        Compute inter-regional loss factor for NSW1-QLD1 from function

        Parameters
        ----------
            nsw_qld_flow : Flow over NSW1-QLD1
            qld_demand : Queensland demand
            nsw_demand : New South Wales demand

        Returns
        -------
            mlf : Inter-regional loss factor

        """

        # Inter regional loss factor
        mlf = 0.9529 + (1.9617E-04 * nsw_qld_flow) + (1.0044E-05 * qld_demand) + (-3.5146E-07 * nsw_demand)

        return mlf

    @staticmethod
    def get_nsw_qld_loss(nsw_qld_flow, qld_demand, nsw_demand):
        """
        Compute total loss over NSW1-QLD1 interconnector

        Parameters
        ----------
            nsw_qld_flow : Flow over NSW1-QLD1
            qld_demand : Queensland demand
            nsw_demand : New South Wales demand

        Returns
        -------
            loss : Total loss over interconnector
        """

        # Total loss over interconnector for given flow + region loading
        loss = (((-0.0471 + 1.0044E-05 * qld_demand + -3.5146E-07 * nsw_demand) * nsw_qld_flow)
                + (9.8083E-05 * (nsw_qld_flow ** 2)))

        return loss

    @staticmethod
    def get_estimated_loss(nsw_qld_flow, qld_demand, nsw_demand):
        """Estimated loss for initial MW"""

        # Coefficients for quadratic equation
        a = 9.8083E-05
        b = (1 - 0.0471) + (1.0044E-05 * qld_demand) + (-3.5146E-07 * nsw_demand)
        c = -nsw_qld_flow

        x_up = (-b + math.sqrt((b ** 2) - (4 * a * c))) / (2 * a)
        x_dn = (-b - math.sqrt((b ** 2) - (4 * a * c))) / (2 * a)

        return x_up, x_dn

    def check_dispatch_interval_results(self):
        """Extract results from several dispatch intervals and print relevant statistics"""

        results = {}
        for d_id in range(1, 289):
            nemde_data.load_interval(2019, 10, 10, d_id)
            print('d_id', d_id)
            results[d_id] = {}

            # Get summary for given dispatch interval
            sa_results = self.get_dispatch_interval_summary('SA1', ['V-SA', 'V-S-MNSP1'])
            results[d_id]['SA1'] = sa_results

            vic_results = self.get_dispatch_interval_summary('SA1', ['V-SA', 'V-S-MNSP1', 'T-V-MNSP1', 'VIC1-NSW1'])
            results[d_id]['VIC1'] = vic_results

            tas_results = self.get_dispatch_interval_summary('TAS1', ['T-V-MNSP1'])
            results[d_id]['TAS1'] = tas_results

            nsw_results = self.get_dispatch_interval_summary('NSW1', ['VIC1-NSW1', 'N-Q-MNSP1', 'NSW1-QLD1'])
            results[d_id]['NSW1'] = nsw_results

            qld_results = self.get_dispatch_interval_summary('QLD1', ['NSW1-QLD1', 'N-Q-MNSP1'])
            results[d_id]['QLD1'] = qld_results

            print(json.dumps(results, indent=4))

        return results

    def get_segments(self, interconnector_id):
        """Use breakpoints and segment factors to construct a new start-end representation for the MLF curve"""

        # Check loss model
        segments = self.get_interconnector_loss_model_segments(interconnector_id)

        # First segment
        start = -self.get_interconnector_loss_model_attribute(interconnector_id, 'LossLowerLimit')

        # Format segments with start, end, and factor
        new_segments = []
        for s in segments:
            segment = {'start': start, 'end': s['Limit'], 'factor': s['Factor']}
            start = s['Limit']
            new_segments.append(segment)

        return new_segments

    def get_interconnector_loss_estimate(self, interconnector_id, flow):
        """Estimate interconnector loss - numerically integrating loss model segments"""

        # Construct segments based on loss model
        segments = self.get_segments(interconnector_id)

        if flow == 9:
            q = 100

        # Initialise total in
        total_area = 0
        for s in segments:
            if flow > 0:
                # Only want segments to right of origin
                if s['end'] <= 0:
                    proportion = 0

                # Only want segments that are less than or equal to flow
                elif s['start'] > flow:
                    proportion = 0

                # Take positive part of segment if segment crosses origin
                elif (s['start'] < 0) and (s['end'] > 0):
                    # Part of segment that is positive
                    positive_proportion = s['end'] / (s['end'] - s['start'])

                    # Flow proportion (if flow close to zero)
                    flow_proportion = flow / (s['end'] - s['start'])

                    # Take min value
                    proportion = min(positive_proportion, flow_proportion)

                # If flow within segment
                elif (flow >= s['start']) and (flow <= s['end']):
                    # Segment proportion
                    proportion = (flow - s['start']) / (s['end'] - s['start'])

                # Use full segment if flow greater than end of segment - use full segment
                elif flow > s['end']:
                    proportion = 1

                else:
                    raise Exception('Unhandled case')

                # Compute block area
                area = (s['end'] - s['start']) * s['factor'] * proportion

                # Update total area
                total_area += area

            # Flow is <= 0
            else:
                # Only want segments to left of origin
                if s['start'] >= 0:
                    proportion = 0

                # Only want segments that are >= flow
                elif s['end'] < flow:
                    proportion = 0

                # Take negative part of segment if segment crosses origin
                elif (s['start'] < 0) and (s['end'] > 0):
                    # Part of segment that is negative
                    negative_proportion = - s['start'] / (s['end'] - s['start'])

                    # Flow proportion (if flow close to zero)
                    flow_proportion = -flow / (s['end'] - s['start'])

                    # Take min value
                    proportion = min(negative_proportion, flow_proportion)

                # If flow within segment
                elif (flow >= s['start']) and (flow <= s['end']):
                    # Segment proportion
                    proportion = -1 * (flow - s['end']) / (s['end'] - s['start'])

                # Use full segment if flow less than start of segment - use full segment
                elif flow <= s['start']:
                    proportion = 1

                else:
                    raise Exception('Unhandled case')

                # Compute block area
                area = -1 * (s['end'] - s['start']) * s['factor'] * proportion

                # Update total area
                total_area += area

        return total_area

    def check_qld_demand(self):
        """Check QLD total demand calculation inputs"""

        generator_initial_mws = []
        generator_target_mws = []
        scheduled_load_initial_mws = []
        scheduled_load_target_mws = []

        for i, j in self.get_trader_offer_index():
            region_id = self.get_trader_period_attribute(i, 'RegionID')

            if (j == 'ENOF') and (region_id == 'QLD1'):
                initial_mw = nemde_data.get_trader_initial_condition_attribute(i, 'InitialMW')
                generator_initial_mws.append((i, j, initial_mw))

                target_mw = nemde_data.get_trader_solution_attribute(i, 'EnergyTarget')
                generator_target_mws.append((i, j, target_mw))

            if (j == 'LDOF') and (region_id == 'QLD1'):
                initial_mw = nemde_data.get_trader_initial_condition_attribute(i, 'InitialMW')
                scheduled_load_initial_mws.append((i, j, initial_mw))

                target_mw = nemde_data.get_trader_solution_attribute(i, 'EnergyTarget')
                scheduled_load_target_mws.append((i, j, target_mw))

        terranora_initialmw = self.get_interconnector_initial_condition_attribute('N-Q-MNSP1', 'InitialMW')
        nsw_qld_initialmw = self.get_interconnector_initial_condition_attribute('NSW1-QLD1', 'InitialMW')

        # Demand forecast and aggregate dispatch error
        values = {
            'DF': self.get_region_period_attribute('QLD1', 'DF'),
            'ADE': self.get_region_initial_condition_attribute('QLD1', 'ADE'),
            'N-Q-MNSP1 InitialMW': terranora_initialmw,
            'NSW1-QLD1 InitialMW': nsw_qld_initialmw,
            'N-Q-MNSP1 initial loss': self.get_interconnector_loss_estimate('N-Q-MNSP1', terranora_initialmw),
            'NSW1-QLD1 initial loss': self.get_interconnector_loss_estimate('NSW1-QLD1', nsw_qld_initialmw),
            'N-Q-MNSP1 initial LossShare': self.get_interconnector_loss_model_attribute('N-Q-MNSP1', 'LossShare'),
            'NSW1-QLD1 initial LossShare': self.get_interconnector_loss_model_attribute('NSW1-QLD1', 'LossShare'),
            'QLD1 FixedDemand': self.get_region_solution_attribute('QLD1', 'FixedDemand'),
            'QLD1 NetExport': self.get_region_solution_attribute('QLD1', 'NetExport'),
            'QLD1 ClearedDemand': self.get_region_solution_attribute('QLD1', 'ClearedDemand'),
            'N-Q-MNSP1 target Flow': self.get_interconnector_solution_attribute('N-Q-MNSP1', 'Flow'),
            'N-Q-MNSP1 target Losses': self.get_interconnector_solution_attribute('N-Q-MNSP1', 'Losses'),
            'NSW1-QLD1 target Flow': self.get_interconnector_solution_attribute('NSW1-QLD1', 'Flow'),
            'NSW1-QLD1 target Losses': self.get_interconnector_solution_attribute('NSW1-QLD1', 'Losses'),
            'N-Q-MNSP1 LossDemandConstant': self.get_interconnector_period_attribute('N-Q-MNSP1', 'LossDemandConstant'),
            'NSW1-QLD1 LossDemandConstant': self.get_interconnector_period_attribute('NSW1-QLD1', 'LossDemandConstant'),
            'QLD1 InitialDemand': self.get_region_initial_condition_attribute('QLD1', 'InitialDemand'),
        }

        # Save to csv
        (pd.DataFrame(generator_initial_mws, columns=['TraderID', 'TradeType', 'InitialMW']).set_index('TraderID')
         .to_csv('output/qld_check/generator_initial_mw.csv'))

        (pd.DataFrame(scheduled_load_initial_mws, columns=['TraderID', 'TradeType', 'InitialMW']).set_index('TraderID')
         .to_csv('output/qld_check/scheduled_load_initial_mw.csv'))

        (pd.DataFrame(generator_target_mws, columns=['TraderID', 'TradeType', 'EnergyTarget']).set_index('TraderID')
         .to_csv('output/qld_check/generator_target_mw.csv'))

        (pd.DataFrame(scheduled_load_target_mws, columns=['TraderID', 'TradeType', 'EnergyTarget']).set_index(
            'TraderID')
         .to_csv('output/qld_check/scheduled_load_target_mw.csv'))

        pd.DataFrame.from_dict(values, orient='index').to_csv('output/qld_check/inputs.csv')

    def check_loss_model(self, interconnector_id):
        """Plot interconnector loss model segments"""

        # Construct segments
        segments = self.get_segments(interconnector_id)

        fig, ax = plt.subplots()
        for s in segments:
            ax.plot([s['start'], s['end']], [s['factor'], s['factor']])

        ax.plot([segments[0]['start'], segments[-1]['end']], [0, 0], linewidth=0.7, alpha=0.7, linestyle=':')
        ax.plot([0, 0], [segments[0]['factor'], segments[-1]['factor']], linewidth=0.7, alpha=0.7,
                linestyle=':')

        plt.show()

    def get_interconnector_absolute_loss_segments(self, interconnector_id):
        """Compute absolute loss at each breakpoint"""

        # Absolute loss for each level of flow
        absolute_loss = [(i['Limit'], self.get_interconnector_loss_estimate(interconnector_id, i['Limit'])) for i in
                         self.get_interconnector_loss_model_segments(interconnector_id)]

        # First grid point
        loss_lower_limit = self.get_interconnector_loss_model_attribute(interconnector_id, 'LossLowerLimit')
        loss_lower_limit_value = self.get_interconnector_loss_estimate(interconnector_id, -loss_lower_limit)

        # Append to loss model
        absolute_loss = [(-loss_lower_limit, loss_lower_limit_value)] + absolute_loss

        return absolute_loss


if __name__ == '__main__':
    # Root directory containing NEMDE and MMSDM files
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to parse NEMDE file
    nemde_data = NEMDEDataHandler(data_directory)
    mmsdm_data = MMSDMDataHandler(data_directory)

    # Load interval
    nemde_data.load_interval(2019, 10, 10, 1)

    # for i in nemde_data.get_interconnector_index():
    for i in ['V-SA']:
        segments = nemde_data.get_interconnector_absolute_loss_segments(i)
        x, y = [i[0] for i in segments], [i[1] for i in segments]
        fig, ax = plt.subplots()
        ax.plot(x, y)
        ax.set_title(i)

        # Solution loss
        solution_loss = nemde_data.get_interconnector_solution_attribute(i, 'Losses')
        flow_min, flow_max = segments[0][0], segments[-1][0]

        # Min and max flow
        ax.plot([flow_min, flow_max], [solution_loss, solution_loss], linewidth=1.2, alpha=0.7, linestyle=':')

        # Solution flow
        solution_flow = nemde_data.get_interconnector_solution_attribute(i, 'Flow')
        loss_max = max([i[1] for i in segments]) + 10
        loss_min = min([i[1] for i in segments]) - 10
        ax.plot([solution_flow, solution_flow], [loss_min, loss_max], linewidth=1.2, alpha=0.7, linestyle=':')

        plt.show()
