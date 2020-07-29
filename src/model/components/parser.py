"""Parse NEMDE case file"""

import os
import json
from abc import ABC, abstractmethod

from data import NEMDEDataHandler


class ModelComponentConstructorAbstract:
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
        """Get index for all generic constraints. Assuming no intervention"""
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
    def get_generic_constraint_interconnector_variable_index(data):
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
        """Index for interconnector loss model breakpoints"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_loss_model_intervals_index(data):
        """Index for interconnector loss model breakpoints"""
        pass


class ModelComponentConstructorJSON(ModelComponentConstructorAbstract):
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
            data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection').get(
                'GenericConstraint')
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
            data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection').get(
                'GenericConstraint')
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
            data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection').get(
                'GenericConstraint')
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


if __name__ == '__main__':
    # Data directory
    output_directory = os.path.join(os.path.dirname(__file__), 'output')
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, 'nemweb', 'Reports', 'Data_Archive')

    # Object used to get case data
    nemde_data = NEMDEDataHandler(data_directory)

    # Object used to parse case data and extract model parameters
    json_parser = CaseFileLookupJSONParser()

    # Get case data for a given dispatch interval
    case_data = nemde_data.get_nemde_json(2019, 10, 10, 1)
    d = json.loads(case_data)

