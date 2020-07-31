"""Parse data allowing model components to be set directly"""

import os
import json
from abc import ABC, abstractmethod

try:
    from .utils.loader import load_dispatch_interval_json
except (ImportError, ModuleNotFoundError):
    import parser
    from utils.loader import load_dispatch_interval_json


class AbstractInputConstructor(ABC):
    @staticmethod
    @abstractmethod
    def get_trader_index(data):
        """Get trader index"""
        pass


class ParsedInputConstructor:
    @staticmethod
    def get_trader_index(data):
        """Get trader index"""
        return list(data['trader_period_collection'])

    @staticmethod
    def get_mnsp_index(data):
        """Get MNSP index"""
        return [k for k, v in data.get('interconnector_period_collection').items() if v.get('MNSP') == 1]

    @staticmethod
    def get_interconnector_index(data):
        """Get interconnector index"""
        return list(data.get('interconnector_period_collection').keys())

    @staticmethod
    def get_trader_offer_index(data):
        """Get trader offer index"""
        return [(trader, trade_type) for trader in data.get('trader_period_collection').keys()
                for trade_type in data.get('trader_period_collection').get(trader).get('trader_period').keys()]

    @staticmethod
    def get_mnsp_offer_index(data):
        """Get MNSP offer index"""
        return [(trader, trade_type) for trader, v in data.get('interconnector_period_collection').items()
                if v.get('offer_collection') for trade_type in v.get('offer_collection').keys()]

    @staticmethod
    def get_generic_constraint_index(data, intervention=0):
        """Get generic constraint index"""

        # All constraints
        constraints = [i for i in data.get('generic_constraint_period_collection')
                       if i.get('Intervention') == f'{intervention}']

        # Unique constraint IDs
        constraint_ids = list(set([i.get('ConstraintID') for i in constraints]))

        # Check no duplicates
        assert len(constraint_ids) == len(constraints)

        return constraint_ids

    @staticmethod
    def get_region_index(data):
        """Get region index"""
        return data.get('region_collection').keys()

    @staticmethod
    def get_generic_constraint_trader_variable_index(data):
        """Get generic constraint trader variable index"""

        # All constraints
        constraints = data.get('generic_constraint_collection').get('constraints')

        # Container for variables
        variables = []

        for i in constraints:
            if (i.get('LHSFactorCollection') is None) or (i.get('LHSFactorCollection').get('TraderFactor') is None):
                continue

            # Extract trader factor
            trader_factor = i.get('LHSFactorCollection').get('TraderFactor')

            if isinstance(trader_factor, dict):
                variables.append((trader_factor.get('TraderID'), trader_factor.get('TradeType')))
            elif isinstance(trader_factor, list):
                for j in trader_factor:
                    variables.append((j.get('TraderID'), j.get('TradeType')))
            else:
                raise Exception(f'Unexpected type: {trader_factor}')

        return list(set(variables))

    @staticmethod
    def get_generic_constraint_interconnector_variable_index(data):
        """Get generic constraint interconnector variable index"""

        # All constraints
        constraints = data.get('generic_constraint_collection').get('constraints')

        # Container for variables
        variables = []

        for i in constraints:
            # LHS factor collection
            lhs_factors = i.get('LHSFactorCollection')

            if (lhs_factors is None) or (lhs_factors.get('InterconnectorFactor') is None):
                continue

            # Extract interconnector components
            interconnector = lhs_factors.get('InterconnectorFactor')

            if isinstance(interconnector, dict):
                variables.append(interconnector.get('InterconnectorID'))
            elif isinstance(interconnector, list):
                for j in interconnector:
                    variables.append(j.get('InterconnectorID'))
            else:
                raise Exception(f'Unexpected type: {interconnector}')

        return list(set(variables))

    @staticmethod
    def get_generic_constraint_region_variable_index(data):
        """Get generic constraint region variable index"""

        # All constraints
        constraints = data.get('generic_constraint_collection').get('constraints')

        # Container for variables
        variables = []

        for i in constraints:
            # LHS factor collection
            lhs_factors = i.get('LHSFactorCollection')

            if (lhs_factors is None) or (lhs_factors.get('RegionFactor') is None):
                continue

            # Extract region components
            region = lhs_factors.get('RegionFactor')

            if isinstance(region, dict):
                variables.append((region.get('RegionID'), region.get('TradeType')))
            elif isinstance(region, list):
                for j in region:
                    variables.append((j.get('RegionID'), j.get('TradeType')))
            else:
                raise Exception(f'Unexpected type: {region}')

        return list(set(variables))

    @staticmethod
    def get_trader_price_bands(data):
        """Get trader price bands"""

        price_bands = {}
        for trader, trader_data in data.get('trader_collection').items():
            for trade_type, trade_data in trader_data.get('price_structure').items():
                for band in range(1, 11):
                    price_bands[(trader, trade_type, band)] = trade_data.get(f'PriceBand{band}')

        return price_bands

    @staticmethod
    def get_trader_quantity_bands(data):
        """Get trader quantity bands"""

        quantity_bands = {}
        for trader, trader_data in data.get('trader_period_collection').items():
            for trade_type, trade_data in trader_data.get('trader_period').items():
                for band in range(1, 11):
                    quantity_bands[(trader, trade_type, band)] = trade_data.get(f'BandAvail{band}')

        return quantity_bands

    @staticmethod
    def get_trader_max_available(data):
        """Get trader max available"""

        max_available = {}
        for trader_id, trader_data in data.get('trader_period_collection').items():
            # Try and get UIGF value - only for semi-dispatchable plant, otherwise None
            uigf = trader_data.get('UIGF')

            for trade_type, trade_data in trader_data.get('trader_period').items():
                if (uigf is not None) and (trade_type == 'ENOF'):
                    max_available[(trader_id, trade_type)] = float(uigf)
                else:
                    max_available[(trader_id, trade_type)] = float(trade_data.get('MaxAvail'))

        return max_available

    @staticmethod
    def get_trader_initial_mw(data):
        """Get trader initial MW"""

        return {k: v.get('initial_conditions').get('InitialMW') for k, v in data.get('trader_collection').items()}

    @staticmethod
    def get_mnsp_price_bands(data):
        """Get MNSP price bands"""

        price_bands = {}
        for interconnector_id, interconnector_data in data.get('interconnector_collection').items():
            # Get price data
            price_data = interconnector_data.get('price_structure')

            # Only MNSPs will have price structure - continue if no price information
            if price_data is None:
                continue

            # Extract price band information
            for region_id, trade_data in price_data.items():
                for band in range(1, 11):
                    price_bands[(interconnector_id, region_id, band)] = trade_data.get(f'PriceBand{band}')

        return price_bands

    @staticmethod
    def get_mnsp_quantity_bands(data):
        """Get MNSP quantity bands"""

        quantity_bands = {}
        for interconnector_id, interconnector_data in data.get('interconnector_period_collection').items():
            # Get quantity data
            quantity_data = interconnector_data.get('offer_collection')

            # Only MNSPs will have price structure - continue if no price information
            if quantity_data is None:
                continue

            # Extract price band information
            for region_id, trade_data in quantity_data.items():
                for band in range(1, 11):
                    quantity_bands[(interconnector_id, region_id, band)] = trade_data.get(f'BandAvail{band}')

        return quantity_bands

    @staticmethod
    def get_mnsp_max_available(data):
        """Get MNSP max available"""

        max_available = {}
        for interconnector_id, interconnector_data in data.get('interconnector_period_collection').items():
            # Get quantity data
            offer_data = interconnector_data.get('offer_collection')

            # Only MNSPs will have price structure - continue if no price information
            if offer_data is None:
                continue

            # Extract price band information
            for region_id, trade_data in offer_data.items():
                max_available[(interconnector_id, region_id)] = trade_data.get('MaxAvail')

        return max_available

    @staticmethod
    def get_generic_constraint_rhs(data, intervention=0):
        """Get generic constraint RHS terms"""

        return {i.get('ConstraintID'): i.get('RHS') for i in data.get('constraint_solution')
                if i.get('Intervention') == f'{intervention}'}

    @staticmethod
    def get_generic_constraint_violation_factors(data):
        """Get generic constraint violation factors"""

        return {i.get('ConstraintID'): float(i.get('ViolationPrice'))
                for i in data.get('generic_constraint_collection').get('constraints')
                if i.get('LHSFactorCollection') is not None}

    @staticmethod
    def get_case_attribute(data, attribute):
        """Extract case attribute"""
        return data.get('case_attributes')[attribute]

    @staticmethod
    def get_region_trader_map(data):
        """Mapping between regions and traders"""

        # Container used to map traders to regions
        trader_region_map = {}

        for trader_id, trader_data in data.get('trader_period_collection').items():
            # Extract region ID
            region_id = trader_data.get('RegionID')

            # If region ID not already in dict
            if region_id not in trader_region_map.keys():
                trader_region_map[region_id] = [trader_id]

            # Append trader to list if not in the list
            elif trader_id not in trader_region_map[region_id]:
                trader_region_map[region_id].append(trader_id)

            else:
                continue

        return trader_region_map

    @staticmethod
    def get_interconnector_from_regions(data):
        """Get interconnector from regions"""

        return {k: v.get('FromRegion') for k, v in data.get('interconnector_period_collection').items()}

    @staticmethod
    def get_interconnector_to_regions(data):
        """Get interconnector to regions"""

        return {k: v.get('ToRegion') for k, v in data.get('interconnector_period_collection').items()}

    @staticmethod
    def get_interconnector_mnsp_status(data):
        """Get interconnector MNSP status"""

        return {k: bool(v.get('MNSP')) for k, v in data.get('interconnector_period_collection').items()}

    @staticmethod
    def get_mnsp_from_region_loss_factor(data):
        """Get from region loss factor"""

        loss_factors = {}
        for interconnector_id, interconnector_data in data.get('interconnector_collection').items():
            factor = interconnector_data.get('FromRegionLF')
            if factor is not None:
                loss_factors[interconnector_id] = factor

        return loss_factors

    @staticmethod
    def get_mnsp_to_region_loss_factor(data):
        """Get to region loss factor"""

        loss_factors = {}
        for interconnector_id, interconnector_data in data.get('interconnector_collection').items():
            factor = interconnector_data.get('ToRegionLF')
            if factor is not None:
                loss_factors[interconnector_id] = factor

        return loss_factors

    @staticmethod
    def get_trader_regions(data):
        """Get region for each trader"""

        return {k: v.get('RegionID') for k, v in data.get('trader_period_collection').items()}

    @staticmethod
    def get_trader_semi_dispatch_status(data):
        """Get trader semi-dispatch status"""

        return {k: bool(v.get('SemiDispatch')) for k, v in data.get('trader_collection').items()}

    @staticmethod
    def get_region_initial_demand(data):
        """Get region initial demand"""

        return {k: v.get('initial_conditions').get('InitialDemand') for k, v in data.get('region_collection').items()}

    @staticmethod
    def get_region_ade(data):
        """Get region aggregate dispatch error"""

        return {k: v.get('initial_conditions').get('ADE') for k, v in data.get('region_collection').items()}

    @staticmethod
    def get_region_df(data):
        """Get region demand forecast"""

        return {k: v.get('DF') for k, v in data.get('region_period_collection').items()}

    # TODO: need to fix loss model construction
    @staticmethod
    def get_loss_model_breakpoint_index(data):
        """Get loss model breakpoints index"""

        return {k: range(0, len(v.get('loss_model').get('segment_collection').keys()) + 1)
                for k, v in data.get('interconnector_collection').items()}

    @staticmethod
    def get_loss_model_breakpoints_x(data):
        """Get loss model breakpoint x-coordinate"""

        # Container for loss model breakpoint x-coordinates
        breakpoints_x = {}

        for interconnector_id, interconnector_data in data.get('interconnector_collection').items():
            # Get all loss model segments segments
            segments = interconnector_data.get('loss_model').get('segment_collection')

            for i in range(0, len(segments.keys()) + 1):
                # First element is loss lower limit
                if i == 0:
                    breakpoints_x[(interconnector_id, i)] = -interconnector_data.get('loss_model').get('LossLowerLimit')
                # Remaining elements are from loss model segments
                else:
                    breakpoints_x[(interconnector_id, i)] = segments[i - 1].get('Limit')

        return breakpoints_x

    @staticmethod
    def get_interconnector_loss_estimate(data, interconnector_id, flow):
        """Estimate interconnector loss - numerically integrating loss model segments"""

        # Construct segments based on loss model
        # segments = self.get_segments(interconnector_id)
        segments = (data.get('interconnector_collection').get(interconnector_id).get('loss_model')
                    .get('segment_collection'))

        # First segment
        # start = -self.get_interconnector_loss_model_attribute(interconnector_id, 'LossLowerLimit')
        start = -data.get('interconnector_collection').get(interconnector_id).get('loss_model').get('LossLowerLimit')

        # Format segments with start, end, and factor
        new_segments = []
        for _, s in segments.items():
            segment = {'start': start, 'end': s['Limit'], 'factor': s['Factor']}
            start = s['Limit']
            new_segments.append(segment)

        # Initialise total in
        total_area = 0
        for s in new_segments:
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

    # TODO: need to fix this
    def get_loss_model_breakpoints_y(self, data):
        """Compute absolute loss at each breakpoint"""

        # Container for all losses
        losses = {}

        for i, i_data in data.get('interconnector_collection').items():
            for segment_id, segment_data in i_data.get('loss_model').get('segment_collection').items():
                losses[(i, segment_id + 1)] = self.get_interconnector_loss_estimate(data, i, segment_data.get('Limit'))

            # Loss lower limit as first element
            losses[(i, 0)] = self.get_interconnector_loss_estimate(data, i,
                                                                   -i_data.get('loss_model').get('LossLowerLimit'))

        return losses

    @staticmethod
    def get_generic_constraint_type(data):
        """Get generic constraint types"""

        # All constraints
        constraints = data.get('generic_constraint_collection').get('constraints')

        return {i.get('ConstraintID'): i.get('Type') for i in constraints if i.get('LHSFactorCollection') is not None}

    @staticmethod
    def get_trader_ramp_up_rate(data):
        """Get trader ramp-up rate"""

        # All traders
        traders = data.get('trader_period_collection')

        # Container for parsed data
        parsed = {}

        for trader_id, trader_data in traders.items():
            if 'ENOF' in trader_data.get('trader_period').keys():
                ramp_rate = trader_data.get('trader_period').get('ENOF').get('RampUpRate')
            elif 'LDOF' in trader_data.get('trader_period').keys():
                ramp_rate = trader_data.get('trader_period').get('LDOF').get('RampUpRate')
            else:
                ramp_rate = None

            # Append to container
            parsed[trader_id] = ramp_rate

        return parsed

    @staticmethod
    def get_trader_ramp_down_rate(data):
        """Get trader ramp-down rate"""

        # All traders
        traders = data.get('trader_period_collection')

        # Container for parsed data
        parsed = {}

        for trader_id, trader_data in traders.items():
            if 'ENOF' in trader_data.get('trader_period').keys():
                ramp_rate = trader_data.get('trader_period').get('ENOF').get('RampDnRate')
            elif 'LDOF' in trader_data.get('trader_period').keys():
                ramp_rate = trader_data.get('trader_period').get('LDOF').get('RampDnRate')
            else:
                ramp_rate = None

            # Append to container
            parsed[trader_id] = ramp_rate

        return parsed

    @staticmethod
    def get_interconnector_upper_limits(data):
        """Get interconnector upper limits"""

        return {k: v.get('UpperLimit') for k, v in data.get('interconnector_period_collection').items()}

    @staticmethod
    def get_interconnector_lower_limits(data):
        """Get interconnector lower limits"""

        return {k: v.get('LowerLimit') for k, v in data.get('interconnector_period_collection').items()}

    @staticmethod
    def get_interconnector_loss_share(data):
        """Get interconnector loss share"""

        return {k: v.get('loss_model').get('LossShare') for k, v in data.get('interconnector_collection').items()}


class JSONInputConstructor:
    @staticmethod
    def get_trader_index(data):
        """Get trader index"""
        pass


class XMLInputConstructor:
    @staticmethod
    def get_trader_index(data):
        """Get trader index"""
        pass


if __name__ == '__main__':
    # Data directory
    data_directory = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, os.path.pardir,
                                  os.path.pardir, os.path.pardir, os.path.pardir, 'nemweb', 'Reports', 'Data_Archive',
                                  'NEMDE', 'zipped')

    # Object used to get case data
    case_data_json = load_dispatch_interval_json(data_directory, 2019, 10, 10, 1)

    # Convert to dictionary
    cdata_r = json.loads(case_data_json)
    cdata = parser.parse_data(cdata_r)

    ParsedInputConstructor().get_interconnector_loss_estimate(cdata, 'V-SA', 100)
