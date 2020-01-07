"""Classes used to extract data from NEMDE output files and extract and format relevant information for NEMDE model"""

import os
import io
import zipfile

import xmltodict
import xml.etree.ElementTree as ET

import pandas as pd


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

    def get_unit_quantity_bands(self):
        """Get quantity bands for each DUID"""

        # Path to elements containing quantity band information
        path = './/NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod'

        # Quantity bands from all generators / loads
        units = self.interval_data.findall(path)

        # Format data {DUID: {energy type: {offer details}}}
        q_bands = {u.get('TraderID'): {trade.get('TradeType'): trade.attrib for trade in u.findall('.//Trade')}
                   for u in units}
        return q_bands

    def get_interconnector_quantity_bands(self):
        """Get quantity bands for each interconnector that bids into the market"""

        # Path to elements containing interconnector quantity band information
        path = (r".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                r"InterconnectorPeriod[@MNSPPriceStructureID]")

        # Interconnectors that submit offers into the market
        interconnectors = self.interval_data.findall(path)

        # Format data {interconnector ID: {region: {offer details}}}
        q_bands = {i.get('InterconnectorID'): {o.get('RegionID'): o.attrib for o in i.findall('.//MNSPOffer')}
                   for i in interconnectors}

        return q_bands

    def get_quantity_bands(self):
        """Get quantity band offers for each generator / load and offer type"""

        # Get all quantity bands from units and interconnectors and combine into single dictionary
        unit_q_bands = self.get_unit_quantity_bands()
        interconnector_q_bands = self.get_interconnector_quantity_bands()

        return {**unit_q_bands, **interconnector_q_bands}

    def get_lhs_factor_collection_categories(self):
        """Get LHS factor categories for generic constraints"""

        # All generic constraints
        constraints = self.interval_data.findall('.//NemSpdInputs/GenericConstraintCollection/GenericConstraint')

        # LHS factor collection categories
        categories = set([f.tag for c in constraints for f in list(c.find('.//LHSFactorCollection'))])

        return categories

    def get_trader_factor_variables(self):
        """Get variable IDs associated with trader factors in Generic Constraints"""

        # Extract all trader factor elements from generic constraints
        factors = self.interval_data.findall(
            './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/TraderFactor')

        # Construct ID for trader factor variables
        var_ids = list(set([(f.get('TraderID'), f.get('TradeType')) for f in factors]))

        return var_ids

    def get_interconnector_factor_variables(self):
        """Get variable IDs associated with interconnector factors in Generic Constraints"""

        # Extract all interconnector factor elements from generic constraints
        factors = self.interval_data.findall(
            './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/InterconnectorFactor')

        # Construct ID for trader factor variables
        var_ids = list(set(f.get('InterconnectorID') for f in factors))

        return var_ids

    def get_region_factor_variables(self):
        """Get variable IDs associated with region factors in Generic Constraints"""

        # Extract all interconnector factor elements from generic constraints
        factors = self.interval_data.findall(
            './/NemSpdInputs/GenericConstraintCollection/GenericConstraint/LHSFactorCollection/RegionFactor')

        # Construct ID for trader factor variables
        var_ids = list(set([(f.get('RegionID'), f.get('TradeType')) for f in factors]))

        return var_ids

    def get_participant_unit_index(self):
        """Get index for market participant units based on price band information"""

        # All market units that are market participants
        units = self.interval_data.findall('.//NemSpdInputs/TraderCollection/Trader')

        # Construct index based on element attributes
        unit_ids = [(u.get('TraderType'), u.get('TraderID'), t.get('TradeType')) for u in units
                    for t in u.findall('.//TradeTypePriceStructure')]

        return unit_ids

    def get_participant_interconnector_index(self):
        """Get index for interconnectors that submit offers into the market using price band information"""

        # All market interconnectors
        interconnectors = self.interval_data.findall(
            './/NemSpdInputs/InterconnectorCollection/Interconnector[MNSPPriceStructureCollection]')

        # Construct interconnector index based on interconnector ID and region name (price bands for each region)
        interconnector_ids = [('INTERCONNECTOR', u.get('InterconnectorID'), t.get('RegionID')) for u in interconnectors
                              for t in u.findall('.//MNSPRegionPriceStructure')]

        return interconnector_ids

    def get_generic_constraint_index(self):
        """Get index for each generic constraint"""

        # All generic constraints. Only consider no intervention case for now.
        # constraints = self.interval_data.findall('.//NemSpdInputs/GenericConstraintCollection/GenericConstraint')
        constraints = self.interval_data.findall(".//NemSpdOutputs/ConstraintSolution/[@Intervention='0']")

        # Extract constraint IDs
        constraint_ids = [c.get('ConstraintID') for c in constraints]

        return constraint_ids

    def get_trader_price_band_value(self, duid, offer_type, band):
        """Get price band value for given unit, offer type, and price band"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{duid}']/TradePriceStructureCollection/"
                f"TradePriceStructure/TradeTypePriceStructureCollection/"
                f"TradeTypePriceStructure[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'PriceBand{band}'))

    def get_trader_quantity_band_value(self, duid, offer_type, band):
        """Get quantity band value for given unit, offer type, and quantity band"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{duid}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get(f'BandAvail{band}'))

    def get_trader_max_available_value(self, duid, offer_type):
        """Get maximum amount that can be dispatch for a given generator and offer type"""

        # Path to element containing quantity band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{duid}']"
                f"/TradeCollection/Trade[@TradeType='{offer_type}']")

        return float(self.interval_data.find(path).get('MaxAvail'))

    def get_interconnector_price_band_value(self, interconnector, region, band):
        """Get price band value for given interconnector, and price band"""

        # Path to element containing price band information for given interconnector and region
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector}']/"
                f"MNSPPriceStructureCollection/MNSPPriceStructure/MNSPRegionPriceStructureCollection/"
                f"MNSPRegionPriceStructure[@RegionID='{region}']")

        return float(self.interval_data.find(path).get(f'PriceBand{band}'))

    def get_interconnector_quantity_band_value(self, interconnector, region, band):
        """Get quantity band value for given interconnector, and quantity band"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region}']")

        return float(self.interval_data.find(path).get(f'BandAvail{band}'))

    def get_interconnector_max_available_value(self, interconnector, region):
        """Get price band value for given interconnector, and price band"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region}']")

        return float(self.interval_data.find(path).get(f'MaxAvail'))

    def get_generic_constraint_rhs_value(self, constraint_id):
        """Get RHS value for generic constraint"""

        # Path to element containing generic constraint information for a given constraint ID
        # Note: only consider no intervention case for now
        # path = f".//NemSpdInputs/GenericConstraintCollection/GenericConstraint[@ConstraintID='{constraint_id}']"
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

    def get_trader_observed_dispatch_dataframe(self):
        """Get observed dispatch for each trader and display in a Pandas DataFrame"""

        # Path to elements containing energy target information (only consider no intervention case for now)
        path = f".//NemSpdOutputs/TraderSolution[@Intervention='0']"

        # Construct DataFrame
        df = pd.DataFrame([i.attrib for i in self.interval_data.findall(path)]).set_index(['TraderID'])

        # Try and make all values floats if possible
        for c in df.columns:
            df[c] = df[c].astype(float, errors='ignore')

        return df


if __name__ == '__main__':
    data_directory = 'C:/Users/eee/Desktop/nemweb/Reports/Data_Archive'

    nemde = NEMDEData(data_directory)

    y, m, d, i = 2019, 11, 1, 1
    # x = nemde.get_nemde_xml(y, m, d, i)
    nemde.load_interval(y, m, d, i)

    r_f = nemde.get_region_factor_variables()
    i_f = nemde.get_interconnector_factor_variables()
    t_f = nemde.get_trader_factor_variables()

    u_ids = nemde.get_participant_unit_index()
    i_ids = nemde.get_participant_interconnector_index()

    nemde.interval_data.findall('.//NemSpdInputs/TraderCollection/Trader')

    b1 = nemde.get_trader_price_band_value('YWPS4', 'ENOF', 1)
    p1 = nemde.get_trader_quantity_band_value('YWPS4', 'ENOF', 1)
    pi1 = nemde.get_interconnector_price_band_value('T-V-MNSP1', 'TAS1', 1)
    bi1 = nemde.get_interconnector_quantity_band_value('T-V-MNSP1', 'TAS1', 1)

    tmx = nemde.get_trader_max_available_value('YWPS4', 'ENOF')
    imx = nemde.get_interconnector_max_available_value('T-V-MNSP1', 'TAS1')

    rhs = nemde.get_generic_constraint_rhs_value('#BNGSF2_E')
    cvf = nemde.get_generic_constraint_cvf_value('#BNGSF2_E')

    g_types = nemde.get_generic_constraint_types()
    tt = nemde.get_trader_type('AGLHAL')

    lhs_terms = nemde.get_lhs_terms('F_I+LREG_0210')
    od = nemde.get_trader_observed_dispatch('AGLHAL')
    df = nemde.get_trader_observed_dispatch_dataframe()
