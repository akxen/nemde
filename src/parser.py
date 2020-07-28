"""Parse NEMDE case file"""

import os
import json
from abc import ABC, abstractmethod

from data import NEMDEDataHandler


class CaseFileAbstractClass(ABC):
    def __init__(self):
        pass

    @staticmethod
    @abstractmethod
    def get_trader_index(data):
        """Get trader index"""
        pass

    @staticmethod
    @abstractmethod
    def get_non_scheduled_generators(data):
        """Get non-scheduled generators"""
        pass

    @staticmethod
    @abstractmethod
    def get_mnsp_index(data):
        """MNSP index"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_index(data):
        """Interconnector index"""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_offer_index(data):
        """Get trader offer index"""
        pass

    @staticmethod
    @abstractmethod
    def get_mnsp_offer_index(data):
        """MNSP offer index"""
        pass

    @staticmethod
    @abstractmethod
    def get_generic_constraint_index(data):
        """
        Get index for all generic constraints. Note: using constraint solution to identify constraints that were used
        """
        pass

    @staticmethod
    @abstractmethod
    def get_region_index(data):
        """Get index for all NEM regions"""
        pass

    @staticmethod
    @abstractmethod
    def get_generic_constraint_trader_variable_index(data):
        """Get index of all trader variables within generic constraints"""
        pass

    @staticmethod
    @abstractmethod
    def get_generic_constraint_interconnector_variable_index(self):
        """Get index of all interconnector variables within generic constraints"""
        pass

    @staticmethod
    @abstractmethod
    def get_generic_constraint_region_variable_index(data):
        """Get index of all region variables within generic constraints"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_loss_model_breakpoints_index(data):
        """Get index for interconnector loss model breakpoints"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_loss_model_intervals_index(data):
        """Get index for interconnector loss model segments"""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_collection_summary(data):
        """
        Summary of trader collection data - facilitates quick access of price band attributes which are otherwise nested
        """
        pass

    @staticmethod
    @abstractmethod
    def get_trader_period_summary(data):
        """Get summary of trader period data - enables quick quantity band access"""
        pass


class CaseFileJSONParser(CaseFileAbstractClass):
    def __init__(self):
        pass

    @staticmethod
    def get_trader_index(data):
        """Get trader index"""

        # Trader period attribute
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('TraderPeriodCollection').get('TraderPeriod'))

        return [i.get('@TraderID') for i in elements]

    @staticmethod
    def get_non_scheduled_generators(data):
        """Get non-scheduled generators"""

        # Non-scheduled generator attribute
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('Non_Scheduled_Generator_Collection').get('Non_Scheduled_Generator'))

        return [i.get('@DUID') for i in elements]

    @staticmethod
    def get_mnsp_index(data):
        """MNSP index"""

        # Get MNSP elements
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        return [i.get('@InterconnectorID') for i in elements if i.get('@MNSP') == '1']

    @staticmethod
    def get_interconnector_index(data):
        """Interconnector index"""

        # Get MNSP elements
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        return [i.get('@InterconnectorID') for i in elements]

    @staticmethod
    def get_trader_offer_index(data):
        """Get trader offer index"""

        # Trader offer index
        elements = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                    .get('TraderPeriodCollection').get('TraderPeriod'))

        # Container for trader offer index
        trader_offer_index = []

        for trader in elements:
            # Extract offer info
            offer_info = trader.get('TradeCollection').get('Trade')

            # Case when trader has only one offer
            if type(offer_info) == dict:
                trader_offer_index.append((trader.get('@TraderID'), offer_info.get('@TradeType')))

            # Case when trader has multiple offers
            elif type(offer_info) == list:
                for offer in offer_info:
                    trader_offer_index.append((trader.get('@TraderID'), offer.get('@TradeType')))
            else:
                raise Exception(f'Unexpected type: {type(offer_info)}')

        return trader_offer_index

    @staticmethod
    def get_mnsp_offer_index(data):
        """MNSP offer index"""

        # Container for MNSP offer index
        mnsp_offer = []

        # Get MNSP offer information
        mnsps = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                 .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        for i in mnsps:
            # Identify MNSPs
            if i.get('@MNSP') == '1':
                # Extract regions corresponding to each offer
                for j in i.get('MNSPOfferCollection').get('MNSPOffer'):
                    mnsp_offer.append((i.get('@InterconnectorID'), j.get('@RegionID')))

        return mnsp_offer

    @staticmethod
    def get_generic_constraint_index(data):
        """Get index for all generic constraints. Assuming no intervention"""

        # Generic constraint information
        constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                       .get('GenericConstraint'))

        # Container for constraint IDs
        constraint_ids = []

        for i in constraints:
            # Ensure LHS is non-empty
            if i.get('LHSFactorCollection'):

                # If not an intervention period constraint, append to container
                if i.get('s:ConstraintTrkCollection').get('ConstraintTrkItem').get('@Intervention') == 'False':
                    constraint_ids.append(i.get('@ConstraintID'))

        return constraint_ids

    @staticmethod
    def get_region_index(data):
        """Get index for all NEM regions"""

        # Region information
        regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('RegionPeriodCollection').get('RegionPeriod'))

        # Extract region IDs
        region_ids = [i.get('@RegionID') for i in regions]

        return region_ids

    @staticmethod
    def get_generic_constraint_trader_variable_index(data):
        """Get index of all trader variables within generic constraints"""

        # All generic constraints
        constraints = (
            data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection').get('GenericConstraint')
        )

        # Container for trader variables
        trader_variables = []

        for i in constraints:
            # Proceed to next constraint if no LHS factors
            if i.get('LHSFactorCollection') is None:
                continue

            # Extract trader factors
            factors = i.get('LHSFactorCollection').get('TraderFactor', None)

            # Proceed to next constraint if no trader variables in constraint
            if factors is None:
                continue

            # Case where only one trader variable is in constraint
            elif type(factors) == dict:
                trader_variables.append((factors.get('@TraderID'), factors.get('@TradeType')))

            # Case where multiple trader variables in constraint
            elif type(factors) == list:
                for j in factors:
                    trader_variables.append((j.get('@TraderID'), j.get('@TradeType')))

            else:
                raise Exception(f'Unexpected type: {factors}')

        # Get unique trader variables
        return list(set(trader_variables))

    @staticmethod
    def get_generic_constraint_interconnector_variable_index(data):
        """Get index of all interconnector variables within generic constraints"""

        # All generic constraints
        constraints = (
            data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection').get('GenericConstraint')
        )

        # Container for interconnector variables
        interconnector_variables = []

        for i in constraints:
            # Proceed to next constraint if no LHS factors
            if i.get('LHSFactorCollection') is None:
                continue

            # Extract trader factors
            factors = i.get('LHSFactorCollection').get('InterconnectorFactor', None)

            # Proceed to next constraint if no interconnector variables in constraint
            if factors is None:
                continue

            # Case where only one interconnector variable is in constraint
            elif type(factors) == dict:
                interconnector_variables.append(factors.get('@InterconnectorID'))

            # Case where multiple interconnector variables in constraint
            elif type(factors) == list:
                for j in factors:
                    interconnector_variables.append(j.get('@InterconnectorID'))

            else:
                raise Exception(f'Unexpected type: {factors}')

        # Get unique interconnector variables
        return list(set(interconnector_variables))

    @staticmethod
    def get_generic_constraint_region_variable_index(data):
        """Get index of all region variables within generic constraints"""

        # All generic constraints
        constraints = (
            data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection').get('GenericConstraint')
        )

        # Container for region variables
        region_variables = []

        for i in constraints:
            # Proceed to next constraint if no LHS factors
            if i.get('LHSFactorCollection') is None:
                continue

            # Extract region factors
            factors = i.get('LHSFactorCollection').get('RegionFactor', None)

            # Proceed to next constraint if no region variables in constraint
            if factors is None:
                continue

            # Case where only one region variable is in constraint
            elif type(factors) == dict:
                region_variables.append((factors.get('@RegionID'), factors.get('@TradeType')))

            # Case where multiple region variables in constraint
            elif type(factors) == list:
                for j in factors:
                    region_variables.append((j.get('@RegionID'), j.get('@TradeType')))

            else:
                raise Exception(f'Unexpected type: {factors}')

        # Get unique region variables
        return list(set(region_variables))

    @staticmethod
    def get_interconnector_loss_model_breakpoints_index(data):
        """Index for interconnector loss model breakpoints"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        # Container for breakpoint index
        breakpoint_index = {}

        for i in interconnectors:
            # Loss model intervals
            n_intervals = len(i.get('LossModelCollection').get('LossModel').get('SegmentCollection').get('Segment'))

            # Breakpoints = intervals + 1
            n_breakpoints = n_intervals + 1

            # Create index and append to container
            breakpoint_index[i.get('@InterconnectorID')] = range(1, n_breakpoints + 1)

        return breakpoint_index

    @staticmethod
    def get_interconnector_loss_model_intervals_index(data):
        """Index for interconnector loss model breakpoints"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        # Container for segments index
        segments_index = {}

        for i in interconnectors:
            # Loss model intervals
            n_intervals = len(i.get('LossModelCollection').get('LossModel').get('SegmentCollection').get('Segment'))

            # Create index and append to container
            segments_index[i.get('@InterconnectorID')] = range(1, n_intervals + 1)

        return segments_index

    @staticmethod
    def get_trader_collection_summary(data):
        """
        Summary of trader collection data - facilitates quick access of price band attributes which are otherwise nested
        """

        # All traders
        traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

        # Container for trader collection summary
        trader_collection = {}

        for i in traders:
            trader_collection[i.get('@TraderID')] = i

            # Container for summary data
            trader_collection[i.get('@TraderID')]['summary'] = {}

            # All offers for a given trader
            offers = (i.get('TradePriceStructureCollection').get('TradePriceStructure')
                      .get('TradeTypePriceStructureCollection').get('TradeTypePriceStructure'))

            # Extract price bands
            if type(offers) == list:
                trader_collection[i.get('@TraderID')]['summary']['trade_types'] = {j.get('@TradeType'): j for j in
                                                                                   offers}
            elif type(offers) == dict:
                trader_collection[i.get('@TraderID')]['summary']['trade_types'] = {offers.get('@TradeType'): offers}
            else:
                raise Exception(f'Unexpected type: {offers}')

        return trader_collection

    @staticmethod
    def get_trader_period_summary(data):
        """Get summary of trader period data - enables quick quantity band access"""

        traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('TraderPeriodCollection').get('TraderPeriod'))

        # Container for trader period data
        trader_period = {}

        for i in traders:
            trader_period[i.get('@TraderID')] = i
            trader_period[i.get('@TraderID')]['summary'] = {}

            # All offers for given trader
            offers = i.get('TradeCollection').get('Trade')

            if type(offers) == list:
                trader_period[i.get('@TraderID')]['summary']['trade_types'] = {j.get('@TradeType'): j for j in offers}

            elif type(offers) == dict:
                trader_period[i.get('@TraderID')]['summary']['trade_types'] = {offers.get('@TradeType'): offers}

            else:
                raise Exception(f'Unexpected type: {offers}')

        return trader_period

    @staticmethod
    def get_trader_initial_condition_attribute(trader_initial_conditions, attribute):
        """Extract desired initial condition attribute value given generators initial conditions"""

        for i in trader_initial_conditions:
            if i.get('@InitialConditionID') == attribute:
                return i.get('@Value')
        raise Exception(f'Attribute not found: {trader_initial_conditions, attribute}')

    @staticmethod
    def get_mnsp_price_band_attribute(data, interconnector_id, region_id, attribute):
        """MNSP price band attribute"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        for i in interconnectors:
            if i.get('@InterconnectorID') != interconnector_id:
                continue

            # Offer for each region
            offers = (i.get('MNSPPriceStructureCollection').get('MNSPPriceStructure')
                      .get('MNSPRegionPriceStructureCollection').get('MNSPRegionPriceStructure'))

            for j in offers:
                if j.get('@RegionID') == region_id:
                    return j.get(attribute)

            raise Exception(f'Attribute not found: {attribute}')

    @staticmethod
    def get_mnsp_quantity_band_attribute(data, interconnector_id, region_id, attribute):
        """Get quantity band information for given MNSP for a bids in a given region"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{mnsp_id}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region_id}']")

        # Matching elements
        elements = self.interval_data.findall(path)

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                           .get('Period').get('InterconnectorPeriodCollection'))

        for i in interconnectors:
            if i.get('@InterconnectorID') != interconnector_id:
                continue





        return self.parse_single_attribute(elements, attribute)


if __name__ == '__main__':
    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to get case data
    nemde_data = NEMDEDataHandler(data_directory)

    # Object used to parse case data and extract model parameters
    json_parser = CaseFileJSONParser()

    # Get case data for a given dispatch interval
    case_data = nemde_data.get_nemde_json(2019, 10, 10, 1)
    d = json.loads(case_data)

    trader_period = json_parser.get_trader_period_summary(d)
    trader_collection = json_parser.get_trader_collection_summary(d)
