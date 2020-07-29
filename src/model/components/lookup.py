"""Parse NEMDE case file"""

import os
import json
from abc import ABC, abstractmethod

try:
    from .utils.loader import load_dispatch_interval_json, load_dispatch_interval_xml
    from .utils.convert import parse_single_attribute
    from .utils.decorators import str_to_float
except ImportError:
    from utils.loader import load_dispatch_interval_json, load_dispatch_interval_xml
    from utils.convert import parse_single_attribute
    from utils.decorators import str_to_float


class CaseFileLookupAbstractClass(ABC):
    @staticmethod
    @abstractmethod
    def get_generic_constraint_attribute(data, constraint_id, attribute):
        """High-level generic constraint information. E.g. constraint type, violation price, etc."""
        pass

    @staticmethod
    @abstractmethod
    def get_generic_constraint_solution_attribute(data, constraint_id, attribute, intervention=0):
        """Get generic constraint solution information. E.g. marginal value."""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_attribute(data, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_initial_condition_attribute(data, trader_id, attribute):
        """Extract desired initial condition attribute value given generators initial conditions"""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_period_attribute(data, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_price_band_attribute(data, trader_id, trade_type, attribute):
        """Get price band information"""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_quantity_band_attribute(data, trader_id, trade_type, attribute):
        """Get trader quantity band information"""
        pass

    @staticmethod
    @abstractmethod
    def get_trader_solution_attribute(data, trader_id, attribute, intervention=0):
        """Get trader solution information (shows actual energy targets)"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_attribute(data, interconnector_id, attribute):
        """Get high-level attribute for given interconnector e.g. FromRegionLF, ToRegionLF, etc"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_initial_condition_attribute(data, interconnector_id, attribute):
        """Get interconnector initial condition information"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_loss_model_attribute(data, interconnector_id, attribute):
        """Get interconnector loss model attributes"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_period_attribute(data, interconnector_id, attribute):
        """High-level attribute giving access to interconnector limits and 'from' and 'to' regions"""
        pass

    @staticmethod
    @abstractmethod
    def get_interconnector_solution_attribute(data, interconnector_id, attribute, intervention=0):
        """Get interconnector solution information"""
        pass

    @staticmethod
    @abstractmethod
    def get_mnsp_price_band_attribute(data, interconnector_id, region_id, attribute):
        """MNSP price band attribute"""
        pass

    @staticmethod
    @abstractmethod
    def get_mnsp_quantity_band_attribute(data, interconnector_id, region_id, attribute):
        """Get quantity band information for given MNSP for a bids in a given region"""
        pass

    @staticmethod
    @abstractmethod
    def get_case_attribute(data, attribute):
        """Get case input attributes"""
        pass

    @staticmethod
    @abstractmethod
    def get_case_solution_attribute(data, attribute):
        """Get case solution information"""
        pass

    @staticmethod
    @abstractmethod
    def get_period_solution_attribute(data, attribute):
        """High-level period solution information"""
        pass

    @staticmethod
    @abstractmethod
    def get_region_period_attribute(data, region_id, attribute):
        """Get region period attributes e.g. demand forecast"""
        pass

    @staticmethod
    @abstractmethod
    def get_region_initial_condition_attribute(data, region_id, attribute):
        """Get region attributes"""
        pass

    @staticmethod
    @abstractmethod
    def get_region_solution_attribute(data, region_id, attribute, intervention=0):
        """Get region solution information"""
        pass


class CaseFileLookupJSON(CaseFileLookupAbstractClass):
    @staticmethod
    @str_to_float
    def get_generic_constraint_attribute(data, constraint_id, attribute):
        """High-level generic constraint information. E.g. constraint type, violation price, etc."""

        # All constraints
        constraints = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('GenericConstraintCollection')
                       .get('GenericConstraint'))

        for i in constraints:
            if i.get('ConstraintID') == constraint_id:
                return i[attribute]

        raise Exception(f'Attribute not found: {constraint_id, attribute}')

    @staticmethod
    @str_to_float
    def get_generic_constraint_solution_attribute(data, constraint_id, attribute, intervention=0):
        """Get generic constraint solution information. E.g. marginal value."""

        # All constraints
        constraints = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('ConstraintSolution')

        for i in constraints:
            if (i.get('ConstraintID') == constraint_id) and (i.get('Intervention') == f'{intervention}'):
                return i[attribute]

        raise Exception(f'Attribute not found: {constraint_id, attribute}')

    @staticmethod
    @str_to_float
    def get_trader_attribute(data, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""

        # All traders
        traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

        for i in traders:
            if i.get('TraderID') == trader_id:
                return i.get(attribute)

        raise Exception(f'Attribute not found: {trader_id, attribute}')

    @staticmethod
    @str_to_float
    def get_trader_initial_condition_attribute(data, trader_id, attribute):
        """Extract desired initial condition attribute value given generators initial conditions"""

        # All traders
        traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

        for i in traders:
            if i.get('TraderID') != trader_id:
                continue

            # Extract initial conditions
            initial_conditions = i.get('TraderInitialConditionCollection').get('TraderInitialCondition')

            # Identify initial condition attribute to extract
            for j in initial_conditions:
                if j.get('InitialConditionID') == attribute:
                    return j['Value']

        raise Exception(f'Attribute not found: {trader_id, attribute}')

    @staticmethod
    @str_to_float
    def get_trader_period_attribute(data, trader_id, attribute):
        """Get high-level trader period attributes e.g. RegionID"""

        # All traders
        traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('TraderPeriodCollection').get('TraderPeriod'))

        for i in traders:
            if i.get('TraderID') == trader_id:
                return i[attribute]

        raise Exception(f'Attribute not found: {trader_id, attribute}')

    @staticmethod
    @str_to_float
    def get_trader_price_band_attribute(data, trader_id, trade_type, attribute):
        """Get price band information"""

        # All traders
        traders = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('TraderCollection').get('Trader')

        for i in traders:
            if i.get('TraderID') == trader_id:
                trade_types = (i.get('TradePriceStructureCollection').get('TradePriceStructure')
                               .get('TradeTypePriceStructureCollection').get('TradeTypePriceStructure'))

                if isinstance(trade_types, list):
                    for j in trade_types:
                        if j.get('TradeType') == trade_type:
                            return j[attribute]

                elif isinstance(trade_types, dict):
                    if trade_types.get('TradeType') == trade_type:
                        return trade_types[attribute]

                else:
                    raise Exception(f'Unexpected type: {trader_id, attribute, trade_types}')

        raise Exception(f'Attribute not found: {trader_id, attribute}')

    @staticmethod
    @str_to_float
    def get_trader_quantity_band_attribute(data, trader_id, trade_type, attribute):
        """Get trader quantity band information"""

        # All traders
        traders = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('TraderPeriodCollection').get('TraderPeriod'))

        for i in traders:
            if i.get('TraderID') == trader_id:
                # Get all trade types
                trade_types = i.get('TradeCollection').get('Trade')

                # Handle cases where there are multiple trade types for a given trader ID
                if isinstance(trade_types, list):
                    for j in trade_types:
                        if j.get('TradeType') == trade_type:
                            return j[attribute]

                # Handle case where these is only one trade type for a give trader ID
                elif isinstance(trade_types, dict):
                    if trade_types.get('TradeType') == trade_type:
                        return trade_types[attribute]

                else:
                    raise Exception(f'Unexpected type: {trader_id, attribute, trade_types}')

        raise Exception(f'Attribute not found: {trader_id, attribute}')

    @staticmethod
    @str_to_float
    def get_trader_solution_attribute(data, trader_id, attribute, intervention=0):
        """Get trader solution information (shows actual energy targets)"""

        # All traders
        traders = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('TraderSolution')

        for i in traders:
            if (i.get('TraderID') == trader_id) and (i.get('Intervention') == f'{intervention}'):
                return i[attribute]

        raise Exception(f'Attribute not found: {trader_id, attribute, intervention}')

    @staticmethod
    @str_to_float
    def get_interconnector_attribute(data, interconnector_id, attribute):
        """Get high-level attribute for given interconnector e.g. FromRegionLF, ToRegionLF, etc"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        for i in interconnectors:
            if i.get('InterconnectorID') == interconnector_id:
                return i[attribute]

        raise Exception(f'Attribute not found: {interconnector_id, attribute}')

    @staticmethod
    @str_to_float
    def get_interconnector_initial_condition_attribute(data, interconnector_id, attribute):
        """Get interconnector initial condition information"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        for i in interconnectors:
            if i.get('InterconnectorID') == interconnector_id:

                # Get all initial conditions
                initial_conditions = (i.get('InterconnectorInitialConditionCollection')
                                      .get('InterconnectorInitialCondition'))

                # Identify initial condition attribute to extract
                for j in initial_conditions:
                    if j.get('InitialConditionID') == attribute:
                        return j['Value']

        raise Exception(f'Attribute not found: {interconnector_id, attribute}')

    @staticmethod
    @str_to_float
    def get_interconnector_loss_model_attribute(data, interconnector_id, attribute):
        """Get interconnector loss model attributes"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        for i in interconnectors:
            if i.get('InterconnectorID') == interconnector_id:
                return i.get('LossModelCollection').get('LossModel')[attribute]

        raise Exception(f'Attribute not found: {interconnector_id, attribute}')

    @staticmethod
    @str_to_float
    def get_interconnector_period_attribute(data, interconnector_id, attribute):
        """High-level attribute giving access to interconnector limits and 'from' and 'to' regions"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                           .get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        for i in interconnectors:
            if i.get('InterconnectorID') == interconnector_id:
                return i[attribute]

        raise Exception(f'Attribute not found: {interconnector_id, attribute}')

    @staticmethod
    @str_to_float
    def get_interconnector_solution_attribute(data, interconnector_id, attribute, intervention=0):
        """Get interconnector solution information"""

        # All interconnectors
        interconnectors = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('InterconnectorSolution')

        for i in interconnectors:
            if (i.get('InterconnectorID') == interconnector_id) and (i.get('Intervention') == f'{intervention}'):
                return i[attribute]

        raise Exception(f'Attribute not found: {interconnector_id, attribute}')

    @staticmethod
    @str_to_float
    def get_mnsp_price_band_attribute(data, interconnector_id, region_id, attribute):
        """MNSP price band attribute"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('InterconnectorCollection')
                           .get('Interconnector'))

        for i in interconnectors:
            if i.get('InterconnectorID') == interconnector_id:

                # Trade types for each region
                trade_types = (i.get('MNSPPriceStructureCollection').get('MNSPPriceStructure')
                               .get('MNSPRegionPriceStructureCollection').get('MNSPRegionPriceStructure'))

                for j in trade_types:
                    if j.get('RegionID') == region_id:
                        return j[attribute]

        raise Exception(f'Attribute not found: {interconnector_id, region_id, attribute}')

    @staticmethod
    @str_to_float
    def get_mnsp_quantity_band_attribute(data, interconnector_id, region_id, attribute):
        """Get quantity band information for given MNSP for a bids in a given region"""

        # All interconnectors
        interconnectors = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection')
                           .get('Period').get('InterconnectorPeriodCollection').get('InterconnectorPeriod'))

        for i in interconnectors:
            if i.get('InterconnectorID') == interconnector_id:

                # Trade types for each region
                trade_types = i.get('MNSPOfferCollection').get('MNSPOffer')

                for j in trade_types:
                    if j.get('RegionID') == region_id:
                        return j[attribute]

        raise Exception(f'Attribute not found: {interconnector_id, region_id, attribute}')

    @staticmethod
    @str_to_float
    def get_case_attribute(data, attribute):
        """Get case input attributes"""

        return data.get('NEMSPDCaseFile').get('NemSpdInputs').get('Case')[attribute]

    @staticmethod
    @str_to_float
    def get_case_solution_attribute(data, attribute):
        """Get case solution information"""

        return data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('CaseSolution')[attribute]

    @staticmethod
    @str_to_float
    def get_period_solution_attribute(data, attribute):
        """High-level period solution information"""

        return data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('PeriodSolution')[attribute]

    @staticmethod
    @str_to_float
    def get_region_period_attribute(data, region_id, attribute):
        """Get region period attributes e.g. demand forecast"""

        # All regions
        regions = (data.get('NEMSPDCaseFile').get('NemSpdInputs').get('PeriodCollection').get('Period')
                   .get('RegionPeriodCollection').get('RegionPeriod'))

        for i in regions:
            if i.get('RegionID') == region_id:
                return i[attribute]

        raise Exception(f'Attribute not found: {region_id, attribute}')

    @staticmethod
    @str_to_float
    def get_region_initial_condition_attribute(data, region_id, attribute):
        """Get region attributes"""

        # All regions
        regions = data.get('NEMSPDCaseFile').get('NemSpdInputs').get('RegionCollection').get('Region')

        for i in regions:
            if i.get('RegionID') == region_id:
                initial_conditions = i.get('RegionInitialConditionCollection').get('RegionInitialCondition')

                for j in initial_conditions:
                    if j.get('InitialConditionID') == attribute:
                        return j['Value']

        raise Exception(f'Attribute not found: {region_id, attribute}')

    @staticmethod
    @str_to_float
    def get_region_solution_attribute(data, region_id, attribute, intervention=0):
        """Get region solution information"""

        # All regions
        regions = data.get('NEMSPDCaseFile').get('NemSpdOutputs').get('RegionSolution')

        for i in regions:
            if (i.get('RegionID') == region_id) and (i.get('Intervention') == f'{intervention}'):
                return i[attribute]


class CaseFileLookupXML(CaseFileLookupAbstractClass):
    @staticmethod
    def get_generic_constraint_attribute(data, constraint_id, attribute):
        """High-level generic constraint information. E.g. constraint type, violation price, etc."""

        # Path to element containing generic constraint information for a given constraint ID
        path = f".//NemSpdInputs/GenericConstraintCollection/GenericConstraint[@ConstraintID='{constraint_id}']"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_generic_constraint_solution_attribute(data, constraint_id, attribute, intervention=0):
        """Get generic constraint solution information. E.g. marginal value."""

        # Path to element containing generic constraint information for a given constraint ID
        path = f".//NemSpdOutputs/ConstraintSolution[@ConstraintID='{constraint_id}'][@Intervention='{intervention}']"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_trader_attribute(data, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""

        # Path to elements containing price band information. Also contains trader type for each unit.
        path = f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']"

        # Trader elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_trader_initial_condition_attribute(data, trader_id, attribute):
        """Get trader initial condition information"""

        # Path to elements containing trader information
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TraderInitialConditionCollection/"
                f"TraderInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = data.findall(path)

        # Check only one element
        assert len(elements) == 1, 'Expected one element in list'

        # Return AGC status as an int if specified as the attribute
        if attribute == 'AGCStatus':
            return int(elements[0].get('Value'))
        else:
            return float(elements[0].get('Value'))

    @staticmethod
    def get_trader_period_attribute(data, trader_id, attribute):
        """Get high-level trader attributes e.g. fast start status, min loading etc."""

        # Path to elements containing price band information. Also contains trader type for each unit.
        path = f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"

        # Trader elements
        elements = [data.find(path)]

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_trader_price_band_attribute(data, trader_id, trade_type, attribute):
        """Get price band information"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/TraderCollection/Trader[@TraderID='{trader_id}']/TradePriceStructureCollection/"
                f"TradePriceStructure/TradeTypePriceStructureCollection/"
                f"TradeTypePriceStructure[@TradeType='{trade_type}']")

        # Matching elements
        elements = [data.find(path)]

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_trader_quantity_band_attribute(data, trader_id, trade_type, attribute):
        """Get trader quantity band information"""

        # Path to element containing price band information for given unit and offer type
        path = (f".//NemSpdInputs/PeriodCollection/Period/TraderPeriodCollection/TraderPeriod[@TraderID='{trader_id}']"
                f"/TradeCollection/Trade[@TradeType='{trade_type}']")

        # Matching elements
        elements = [data.find(path)]

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_trader_solution_attribute(data, trader_id, attribute, intervention=0):
        """Get trader solution information (shows actual energy targets)"""

        # Path to elements containing energy target information (only consider no intervention case for now)
        path = f".//NemSpdOutputs/TraderSolution[@TraderID='{trader_id}'][@Intervention='{intervention}']"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_interconnector_attribute(data, interconnector_id, attribute):
        """Get high-level attribute for given interconnector e.g. FromRegionLF, ToRegionLF, etc"""

        # Path to interconnector elements
        path = f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_interconnector_initial_condition_attribute(data, interconnector_id, attribute):
        """Get interconnector initial condition information"""

        # Path to interconnector elements
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"InterconnectorInitialConditionCollection/"
                f"InterconnectorInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, 'Value')

    @staticmethod
    def get_interconnector_loss_model_attribute(data, interconnector_id, attribute):
        """Get interconnector loss model attributes"""

        # Path to interconnector elements
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"LossModelCollection/LossModel")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_interconnector_period_attribute(data, interconnector_id, attribute):
        """High-level attribute giving access to interconnector limits and 'from' and 'to' regions"""

        # Path to MNSP elements
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector_id}']")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_interconnector_solution_attribute(data, interconnector_id, attribute, intervention=0):
        """Get interconnector solution information"""

        # Path to interconnector solution elements. Only consider no intervention case for now.
        path = (f".//NemSpdOutputs/"
                f"InterconnectorSolution[@InterconnectorID='{interconnector_id}'][@Intervention='{intervention}']")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_mnsp_price_band_attribute(data, interconnector_id, region_id, attribute):
        """MNSP price band attribute"""

        # Path to element containing price band information for given interconnector and region
        path = (f".//NemSpdInputs/InterconnectorCollection/Interconnector[@InterconnectorID='{interconnector_id}']/"
                f"MNSPPriceStructureCollection/MNSPPriceStructure/MNSPRegionPriceStructureCollection/"
                f"MNSPRegionPriceStructure[@RegionID='{region_id}']")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_mnsp_quantity_band_attribute(data, interconnector_id, region_id, attribute):
        """Get quantity band information for given MNSP for a bids in a given region"""

        # Path to element containing quantity band information for given interconnector and region
        path = (f".//NemSpdInputs/PeriodCollection/Period/InterconnectorPeriodCollection/"
                f"InterconnectorPeriod[@InterconnectorID='{interconnector_id}']/MNSPOfferCollection"
                f"/MNSPOffer[@RegionID='{region_id}']")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_case_attribute(data, attribute):
        """Get case input attributes"""

        # Path to element containing case information
        path = f".//NemSpdInputs/Case"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_case_solution_attribute(data, attribute):
        """Get case solution information"""

        # Path to element containing case solution information
        path = f".//NemSpdOutputs/CaseSolution"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_period_solution_attribute(data, attribute):
        """High-level period solution information"""

        # Path to element containing period solution information
        path = f".//NemSpdOutputs/PeriodSolution"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_region_period_attribute(data, region_id, attribute):
        """Get region period attributes e.g. demand forecast"""

        # Path to element containing region period information
        path = f".//NemSpdInputs/PeriodCollection/Period/RegionPeriodCollection/RegionPeriod[@RegionID='{region_id}']"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)

    @staticmethod
    def get_region_initial_condition_attribute(data, region_id, attribute):
        """Get region attributes"""

        # Path to element containing case information
        path = (f".//NemSpdInputs/RegionCollection/Region[@RegionID='{region_id}']/RegionInitialConditionCollection/"
                f"RegionInitialCondition[@InitialConditionID='{attribute}']")

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, 'Value')

    @staticmethod
    def get_region_solution_attribute(data, region_id, attribute, intervention=0):
        """Get region solution information"""

        # Path to element containing region solution information
        path = f".//NemSpdOutputs/RegionSolution[@RegionID='{region_id}'][@Intervention='{intervention}']"

        # Matching elements
        elements = data.findall(path)

        return parse_single_attribute(elements, attribute)


if __name__ == '__main__':
    # Data directory
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Load case data in json and xml formats
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)
    case_data_xml = load_dispatch_interval_xml(data_directory, 2019, 10, 10, 1)

    # Convert JSON to dictionary
    cdata = json.loads(case_data_json)

    # Object used to lookup casefile data
    lookup_json = CaseFileLookupJSON()
    lookup_xml = CaseFileLookupXML()

    import time
    t0 = time.time()
    m = lookup_json.get_trader_period_attribute(cdata, 'HDWF1', 'RegionID')
    print(time.time() - t0)

    t1 = time.time()
    g = lookup_xml.get_trader_period_attribute(case_data_xml, 'HDWF1', 'RegionID')
    print(time.time() - t1)
