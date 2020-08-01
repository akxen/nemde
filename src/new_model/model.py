"""Model used to construct and solve NEMDE approximation"""

import os
import json

import pyomo.environ as pyo

from utils.data import parse_case_data_json
from utils.loaders import load_dispatch_interval_json


class NEMDEModel:
    def __init__(self):
        pass

    @staticmethod
    def define_sets(m, data):
        """Define sets"""

        # NEM regions
        m.S_REGIONS = pyo.Set(initialize=data['S_REGIONS'])

        # Market participants (generators and loads)
        m.S_TRADERS = pyo.Set(initialize=data['S_TRADERS'])

        # Trader offer types
        m.S_TRADER_OFFERS = pyo.Set(initialize=data['S_TRADER_OFFERS'])

        # Generic constraints
        m.S_GENERIC_CONSTRAINTS = pyo.Set(initialize=data['S_GENERIC_CONSTRAINTS'])

        # Generic constraints trader variables
        m.S_GC_TRADER_VARS = pyo.Set(initialize=data['S_GC_TRADER_VARS'])

        # Generic constraint interconnector variables
        m.S_GC_INTERCONNECTOR_VARS = pyo.Set(initialize=data['S_GC_INTERCONNECTOR_VARS'])

        # Generic constraint region variables
        m.S_GC_REGION_VARS = pyo.Set(initialize=data['S_GC_REGION_VARS'])

        # Price / quantity band index
        m.S_BANDS = pyo.RangeSet(1, 10, 1)

        # Market Network Service Providers (interconnectors that bid into the market)
        m.S_MNSPS = pyo.Set(initialize=data['S_MNSPS'])

        # MNSP offer types
        m.S_MNSP_OFFERS = pyo.Set(initialize=data['S_MNSP_OFFERS'])

        # All interconnectors (interconnector_id)
        m.S_INTERCONNECTORS = pyo.Set(initialize=data['S_INTERCONNECTORS'])

        # # Loss model breakpoints
        # m.S_INTERCONNECTOR_BREAKPOINTS = pyo.Set(m.S_INTERCONNECTORS, initialize=data['S_INTERCONNECTOR_BREAKPOINTS'])
        #
        # # Loss model intervals
        # m.S_INTERCONNECTOR_INTERVALS = pyo.Set(m.S_INTERCONNECTORS, initialize=data['S_INTERCONNECTOR_INTERVALS'])
        #
        # # All interconnector
        # m.S_BREAKPOINTS = pyo.Set(initialize=data['S_BREAKPOINTS'])
        #
        # # All interconnector
        # m.S_INTERVALS = pyo.Set(initialize=data['S_INTERVALS'])

        return m

    @staticmethod
    def define_parameters(m, data):
        """Define model parameters"""

        # Price bands for traders (generators / loads)
        m.P_TRADER_PRICE_BANDS = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS, initialize=data['P_TRADER_PRICE_BANDS'])

        # Quantity bands for traders (generators / loads)
        m.P_TRADER_QUANTITY_BANDS = pyo.Param(m.S_TRADER_OFFERS, m.S_BANDS, initialize=data['P_TRADER_QUANTITY_BANDS'])

        # Max available output for given trader
        m.P_TRADER_MAX_AVAILABLE = pyo.Param(m.S_TRADER_OFFERS, initialize=data['P_TRADER_MAX_AVAILABLE'])

        # Initial MW output for generators / loads
        m.P_TRADER_INITIAL_MW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_INITIAL_MW'])

        # Trader HMW and LMW
        m.P_TRADER_HMW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_HMW'])
        m.P_TRADER_LMW = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_LMW'])

        # Trader AGC status
        m.P_TRADER_AGC_STATUS = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_AGC_STATUS'])

        # Trader region
        m.P_TRADER_REGIONS = pyo.Param(m.S_TRADERS, initialize=data['P_TRADER_REGIONS'])

        # Price bands for MNSPs
        m.P_MNSP_PRICE_BANDS = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, initialize=data['P_MNSP_PRICE_BANDS'])

        # Quantity bands for MNSPs
        m.P_MNSP_QUANTITY_BANDS = pyo.Param(m.S_MNSP_OFFERS, m.S_BANDS, initialize=data['P_MNSP_QUANTITY_BANDS'])

        # def mnsp_max_available_rule(m, i, j):
        #     """Max available energy output from given MNSP"""
        #
        #     return self.data.get_mnsp_quantity_band_attribute(i, j, 'MaxAvail')
        #
        # Max available output for given MNSP
        m.P_MNSP_MAX_AVAILABLE = pyo.Param(m.S_MNSP_OFFERS, initialize=data['P_MNSP_MAX_AVAILABLE'])

        # def generic_constraint_rhs_rule(m, c):
        #     """RHS value for given generic constraint"""
        #
        #     return self.data.get_generic_constraint_solution_attribute(c, 'RHS')
        #
        # # Generic constraint RHS
        # m.P_RHS = Param(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_rhs_rule)
        #
        # def generic_constraint_violation_factor_rule(m, c):
        #     """Constraint violation penalty for given generic constraint"""
        #
        #     return self.data.get_generic_constraint_attribute(c, 'ViolationPrice')
        #
        # # Constraint violation factors
        # m.P_CVF_GC = Param(m.S_GENERIC_CONSTRAINTS, rule=generic_constraint_violation_factor_rule)
        #
        # # Value of lost load
        # m.P_CVF_VOLL = Param(initialize=self.data.get_case_attribute('VoLL'))
        #
        # # Energy deficit price
        # m.P_CVF_ENERGY_DEFICIT_PRICE = Param(initialize=self.data.get_case_attribute('EnergyDeficitPrice'))
        #
        # # Energy surplus price
        # m.P_CVF_ENERGY_SURPLUS_PRICE = Param(initialize=self.data.get_case_attribute('EnergySurplusPrice'))
        #
        # # Ramp-rate constraint violation factor
        # m.P_CVF_RAMP_RATE_PRICE = Param(initialize=self.data.get_case_attribute('RampRatePrice'))
        #
        # # Capacity price (assume for constraint ensuring max available capacity not exceeded)
        # m.P_CVF_CAPACITY_PRICE = Param(initialize=self.data.get_case_attribute('CapacityPrice'))
        #
        # # Offer price (assume for constraint ensuring band offer amounts are not exceeded)
        # m.P_CVF_OFFER_PRICE = Param(initialize=self.data.get_case_attribute('OfferPrice'))
        #
        # # MNSP offer price (assumed for constraint ensuring MNSP band offers are not exceeded)
        # m.P_CVF_MNSP_OFFER_PRICE = Param(initialize=self.data.get_case_attribute('MNSPOfferPrice'))
        #
        # # MNSP ramp rate price (not sure what this applies to - unclear what MNSP ramp rates are)
        # m.P_CVF_MNSP_RAMP_RATE_PRICE = Param(initialize=self.data.get_case_attribute('MNSPRampRatePrice'))
        #
        # # MNSP capacity price (assume for constraint ensuring max available capacity not exceeded)
        # m.P_CVF_MNSP_CAPACITY_PRICE = Param(initialize=self.data.get_case_attribute('MNSPCapacityPrice'))
        #
        # # Ancillary services profile price (assume for constraint ensure FCAS trapezium not violated)
        # m.P_CVF_AS_PROFILE_PRICE = Param(initialize=self.data.get_case_attribute('ASProfilePrice'))
        #
        # # Ancillary services max available price (assume for constraint ensure max available amount not exceeded)
        # m.P_CVF_AS_MAX_AVAIL_PRICE = Param(initialize=self.data.get_case_attribute('ASMaxAvailPrice'))
        #
        # # Ancillary services enablement min price (assume for constraint ensure FCAS > enablement min if active)
        # m.P_CVF_AS_ENABLEMENT_MIN_PRICE = Param(initialize=self.data.get_case_attribute('ASEnablementMinPrice'))
        #
        # # Ancillary services enablement max price (assume for constraint ensure FCAS < enablement max if active)
        # m.P_CVF_AS_ENABLEMENT_MAX_PRICE = Param(initialize=self.data.get_case_attribute('ASEnablementMaxPrice'))
        #
        # # Interconnector power flow violation price
        # m.P_CVF_INTERCONNECTOR_PRICE = Param(initialize=self.data.get_case_attribute('InterconnectorPrice'))
        #
        # # Interconnector loss model segments
        # loss_segments = {i: self.data.get_interconnector_absolute_loss_segments(i) for i in m.S_INTERCONNECTORS}
        #
        # def loss_model_breakpoint_x_rule(m, i, j):
        #     """Loss model breakpoints"""
        #
        #     return loss_segments[i][j - 1][0]
        #
        # # Loss model breakpoints
        # m.P_LOSS_MODEL_BREAKPOINTS_X = Param(m.S_BREAKPOINTS, rule=loss_model_breakpoint_x_rule)
        #
        # def loss_model_breakpoint_y_rule(m, i, j):
        #     """Loss model breakpoints"""
        #
        #     return loss_segments[i][j - 1][1]
        #
        # # Loss model breakpoints
        # m.P_LOSS_MODEL_BREAKPOINTS_Y = Param(m.S_BREAKPOINTS, rule=loss_model_breakpoint_y_rule)
        #
        # # MNSP loss price
        # m.P_MNSP_LOSS_PRICE = Param(initialize=self.data.get_case_attribute('MNSPLossesPrice'))

        return m

    def construct_model(self, data):
        """Create model object"""

        # Initialise model
        m = pyo.ConcreteModel()

        # Define model components
        m = self.define_sets(m, data)
        m = self.define_parameters(m, data)

        return m

    def solve_model(self):
        """Solve model"""
        pass


if __name__ == '__main__':
    # Directory containing case data
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive', 'NEMDE',
                                  'zipped')

    # NEMDE model object
    nemde = NEMDEModel()

    # Case data in json format
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Get NEMDE model data as a Python dictionary
    cdata = json.loads(case_data_json)
    # with open('example.json', 'w') as f:
    #     json.dump(cdata, f)

    cased_data = parse_case_data_json(case_data_json)

    # Construct model
    nemde_model = nemde.construct_model(cased_data)

    # # Solve model
    # nemde_model, status = nemde.solve_model(nemde_model)
