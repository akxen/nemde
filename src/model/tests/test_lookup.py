"""Test case file lookup functionality"""

import os
import json
import unittest

from context import components

from components.lookup import CaseFileLookupJSON, CaseFileLookupXML
from components.utils.loader import load_dispatch_interval_json, load_dispatch_interval_xml


class TestCaseFileLookupJSON(unittest.TestCase):
    def setUp(self):
        # Object containing methods which must be tested
        self.lookup = CaseFileLookupJSON()

        # Load data used when running tests
        self.data = self.get_data()

    @staticmethod
    def get_data():
        """Get data"""

        # Data directory
        data_dir = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports',
                                'Data_Archive',
                                'NEMDE', 'zipped')

        # Load case data in json format and convert to dictionary
        case_data_json = load_dispatch_interval_json(data_dir, 2019, 10, 10, 1)

        # TODO: Tests depend on loaded data. Changing paths could break tests. Need to make this more robust.
        return json.loads(case_data_json)

    def test_get_generic_constraint_attribute(self):
        """High-level generic constraint information. E.g. constraint type, violation price, etc."""

        value = self.lookup.get_generic_constraint_attribute(self.data, '#CLERMSF1_E', 'ViolationPrice')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_generic_constraint_solution_attribute(self):
        """Get generic constraint solution information. E.g. marginal value."""
        pass

    def test_get_trader_attribute(self):
        """Test trader attribute lookup"""

        value = self.lookup.get_trader_attribute(self.data, 'HDWF1', 'TraderID')

        self.assertEqual(value, 'HDWF1', 'Trader attribute does not match')

    def test_get_trader_initial_condition_attribute(self):
        """Test trader initial condition attribute lookup"""

        value = self.lookup.get_trader_initial_condition_attribute(self.data, 'HDWF1', 'InitialMW')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_period_attribute(self):
        """Test trader period attribute lookup"""

        value = self.lookup.get_trader_period_attribute(self.data, 'HDWF1', 'RegionID')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_price_band_attribute(self):
        """Test trader price band attribute lookup"""

        value = self.lookup.get_trader_price_band_attribute(self.data, 'HDWF1', 'ENOF', 'PriceBand1')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_quantity_band_attribute(self):
        """Test trader quantity band attribute lookup"""

        value = self.lookup.get_trader_quantity_band_attribute(self.data, 'HDWF1', 'ENOF', 'BandAvail1')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_solution_attribute(self):
        """Test trader solution attribute lookup"""

        value = self.lookup.get_trader_solution_attribute(self.data, 'HDWF1', 'EnergyTarget')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_attribute(self):
        """Test interconnector attribute lookup"""

        value = self.lookup.get_interconnector_attribute(self.data, 'V-SA', 'InterconnectorID')

        self.assertIsNotNone(value, 'Value should not be None')
        self.assertEqual(value, 'V-SA', 'Interconnector IDs do not match')

    def test_get_interconnector_initial_condition_attribute(self):
        """Test interconnector initial condition lookup"""

        value = self.lookup.get_interconnector_initial_condition_attribute(self.data, 'V-SA', 'InitialMW')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_loss_model_attribute(self):
        """Test interconnector loss model attribute lookup"""

        value = self.lookup.get_interconnector_loss_model_attribute(self.data, 'V-SA', 'LossLowerLimit')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_period_attribute(self):
        """Test interconnector period attribute lookup"""

        value = self.lookup.get_interconnector_period_attribute(self.data, 'V-SA', 'FromRegion')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_solution_attribute(self):
        """Test interconnector solution attribute lookup"""

        value = self.lookup.get_interconnector_solution_attribute(self.data, 'V-SA', 'Flow')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_mnsp_price_band_attribute(self):
        """Test MNSP price band attribute lookup"""

        value = self.lookup.get_mnsp_price_band_attribute(self.data, 'T-V-MNSP1', 'TAS1', 'PriceBand1')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_mnsp_quantity_band_attribute(self):
        """Test MNSP quantity band lookup"""

        value = self.lookup.get_mnsp_quantity_band_attribute(self.data, 'T-V-MNSP1', 'TAS1', 'RampUpRate')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_case_attribute(self):
        """Test case attribute lookup"""

        value = self.lookup.get_case_attribute(self.data, 'EnergyDeficitPrice')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_case_solution_attribute(self):
        """Test case solution attribute lookup"""

        value = self.lookup.get_case_solution_attribute(self.data, 'Terminal')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_period_solution_attribute(self):
        """Test region period solution attribute"""

        value = self.lookup.get_period_solution_attribute(self.data, 'TotalObjective')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_region_period_attribute(self):
        """Test region period attribute"""

        value = self.lookup.get_region_period_attribute(self.data, 'SA1', 'DemandForecast')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_region_initial_condition_attribute(self):
        """Test region initial condition attribute"""

        value = self.lookup.get_region_initial_condition_attribute(self.data, 'SA1', 'ADE')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_region_solution_attribute(self):
        """Test region solution attribute"""

        value = self.lookup.get_region_solution_attribute(self.data, 'SA1', 'DispatchedGeneration')

        self.assertIsNotNone(value, 'Value should not be None')


class TestCaseFileLookupXML(unittest.TestCase):
    def setUp(self):
        # Object containing methods which must be tested
        self.lookup = CaseFileLookupXML()

        # Load data used when running tests
        self.data = self.get_data()

    @staticmethod
    def get_data():
        """Get data"""

        # Data directory
        data_dir = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports',
                                'Data_Archive',
                                'NEMDE', 'zipped')

        # Load case data in json format and convert to dictionary
        case_data_xml = load_dispatch_interval_xml(data_dir, 2019, 10, 10, 1)

        # TODO: Tests depend on loaded data. Changing paths could break tests. Need to make this more robust.
        return case_data_xml

    def test_get_trader_attribute(self):
        """Test trader attribute lookup"""

        value = self.lookup.get_trader_attribute(self.data, 'HDWF1', 'TraderID')

        self.assertEqual(value, 'HDWF1', 'Trader attribute does not match')

    def test_get_trader_initial_condition_attribute(self):
        """Test trader initial condition attribute lookup"""

        value = self.lookup.get_trader_initial_condition_attribute(self.data, 'HDWF1', 'InitialMW')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_period_attribute(self):
        """Test trader period attribute lookup"""

        value = self.lookup.get_trader_period_attribute(self.data, 'HDWF1', 'RegionID')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_price_band_attribute(self):
        """Test trader price band attribute lookup"""

        value = self.lookup.get_trader_price_band_attribute(self.data, 'HDWF1', 'ENOF', 'PriceBand1')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_quantity_band_attribute(self):
        """Test trader quantity band attribute lookup"""

        value = self.lookup.get_trader_quantity_band_attribute(self.data, 'HDWF1', 'ENOF', 'BandAvail1')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_trader_solution_attribute(self):
        """Test trader solution attribute lookup"""

        value = self.lookup.get_trader_solution_attribute(self.data, 'HDWF1', 'EnergyTarget')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_attribute(self):
        """Test interconnector attribute lookup"""

        value = self.lookup.get_interconnector_attribute(self.data, 'V-SA', 'InterconnectorID')

        self.assertIsNotNone(value, 'Value should not be None')
        self.assertEqual(value, 'V-SA', 'Interconnector IDs do not match')

    def test_get_interconnector_initial_condition_attribute(self):
        """Test interconnector initial condition lookup"""

        value = self.lookup.get_interconnector_initial_condition_attribute(self.data, 'V-SA', 'InitialMW')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_loss_model_attribute(self):
        """Test interconnector loss model attribute lookup"""

        value = self.lookup.get_interconnector_loss_model_attribute(self.data, 'V-SA', 'LossLowerLimit')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_period_attribute(self):
        """Test interconnector period attribute lookup"""

        value = self.lookup.get_interconnector_period_attribute(self.data, 'V-SA', 'FromRegion')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_interconnector_solution_attribute(self):
        """Test interconnector solution attribute lookup"""

        value = self.lookup.get_interconnector_solution_attribute(self.data, 'V-SA', 'Flow')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_mnsp_price_band_attribute(self):
        """Test MNSP price band attribute lookup"""

        value = self.lookup.get_mnsp_price_band_attribute(self.data, 'T-V-MNSP1', 'TAS1', 'PriceBand1')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_mnsp_quantity_band_attribute(self):
        """Test MNSP quantity band lookup"""

        value = self.lookup.get_mnsp_quantity_band_attribute(self.data, 'T-V-MNSP1', 'TAS1', 'RampUpRate')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_case_attribute(self):
        """Test case attribute lookup"""

        value = self.lookup.get_case_attribute(self.data, 'EnergyDeficitPrice')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_case_solution_attribute(self):
        """Test case solution attribute lookup"""

        value = self.lookup.get_case_solution_attribute(self.data, 'Terminal')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_period_solution_attribute(self):
        """Test region period solution attribute"""

        value = self.lookup.get_period_solution_attribute(self.data, 'TotalObjective')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_region_period_attribute(self):
        """Test region period attribute"""

        value = self.lookup.get_region_period_attribute(self.data, 'SA1', 'DemandForecast')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_region_initial_condition_attribute(self):
        """Test region initial condition attribute"""

        value = self.lookup.get_region_initial_condition_attribute(self.data, 'SA1', 'ADE')

        self.assertIsNotNone(value, 'Value should not be None')

    def test_get_region_solution_attribute(self):
        """Test region solution attribute"""

        value = self.lookup.get_region_solution_attribute(self.data, 'SA1', 'DispatchedGeneration')

        self.assertIsNotNone(value, 'Value should not be None')


if __name__ == '__main__':
    unittest.main()
