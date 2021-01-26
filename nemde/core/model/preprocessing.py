"""Apply pre-processing logic to case data"""

import nemde.core.model.utils.fcas


def reorder_tuple(input_tuple) -> tuple:
    """Sort tuples alphabetically"""

    if input_tuple[0][0] > input_tuple[1][0]:
        return tuple((input_tuple[1], input_tuple[0]))
    else:
        return tuple((input_tuple[0], input_tuple[1]))


def get_trader_price_tied_bands(data):
    """Get price-tied generators"""

    # Price and quantity bands
    price_bands = data['P_TRADER_PRICE_BAND']
    quantity_bands = data['P_TRADER_QUANTITY_BAND']

    # Generator energy offer price bands
    filtered_price_bands = {k: v for k, v in price_bands.items() if k[1] == 'ENOF'}

    # Trader region
    trader_region = data['P_TRADER_REGION']

    # Container for price tied bands
    price_tied = []

    # For each price band
    for i, j in filtered_price_bands.items():
        # Compare it to every other price band
        for m, n in filtered_price_bands.items():
            # Price bands must be in same region (also ignore the input trader - will of course match)
            if (m == i) or (trader_region[i[0]] != trader_region[m[0]]):
                continue

            # Check if price difference less than threshold - append to container if so
            if abs(j - n) < 1e-6:
                if (quantity_bands[m[0], m[1], m[2]] != 0) and (quantity_bands[i[0], i[1], i[2]] != 0):
                    price_tied.append((i, m))

    # Re-order tuples, get unique price-tied combinations, and sort alphabetically
    price_tied_reordered = [reorder_tuple(i) for i in price_tied]
    price_tied_unique = list(set(price_tied_reordered))
    price_tied_unique.sort()

    # Flatten to produce one tuple for a given pair of price-tied generators
    price_tied_flattened = [(i[0][0], i[0][1], i[0][2], i[1][0], i[1][1], i[1][2]) for i in price_tied_unique]

    return price_tied_flattened


def get_mnsp_region_loss_indicator(data) -> dict:
    """Get region loss indicator. =1 if from region and InitialMW >= 0, or if ToRegion and InitialMW < 0, else =0"""

    # MNSP and region index
    mnsp_index = data['S_MNSPS']
    region_index = data['S_REGIONS']

    # MNSP attributes # TODO: this needs to change if intervention pricing case is considered
    initial_mw = data['P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW']
    to_region = data['P_INTERCONNECTOR_TO_REGION']
    from_region = data['P_INTERCONNECTOR_FROM_REGION']

    # Container for output
    out = {}
    for i in mnsp_index:

        for j in region_index:
            # Loss applied to FromRegion
            if (j == from_region[i]) and (initial_mw[i] >= 0):
                out[(i, j)] = 1

            # Loss applied to ToRegion
            elif (j == to_region[i]) and (initial_mw[i] < 0):
                out[(i, j)] = 1

            else:
                out[(i, j)] = 0

    return out


def get_trader_fcas_info(data) -> dict:
    """Extract parameter used in FCAS availability calculations - convert to standard format"""

    # FCAS trade types
    fcas_trade_types = ['R6SE', 'R60S', 'R5MI', 'R5RE', 'L6SE', 'L60S', 'L5MI', 'L5RE']

    # Container for output
    out = {}
    for trader_id, trade_type in data['S_TRADER_OFFERS']:
        if trade_type in fcas_trade_types:
            # Extract trader quantity bands for given service
            quantity_bands = {k: v for k, v in data['P_TRADER_QUANTITY_BAND'].items()
                              if k[0] == trader_id and k[1] == trade_type}

            # Energy offer trade type depends on whether trader is a generator or a load
            if data['P_TRADER_TYPE'][trader_id] == 'GENERATOR':
                energy_offer_type = 'ENOF'
            elif data['P_TRADER_TYPE'][trader_id] in ['LOAD', 'NORMALLY_ON_LOAD']:
                energy_offer_type = 'LDOF'
            else:
                raise Exception('Unexpected trader type:', trader_id, data['P_TRADER_TYPE'][trader_id])

            # Compile output into single dictionary
            out[(trader_id, trade_type)] = {
                'trader_id': trader_id,
                'trade_type': trade_type,
                'quantity_bands': quantity_bands,
                'energy_max_avail': data['P_TRADER_MAX_AVAIL'].get((trader_id, energy_offer_type)),
                'enablement_min': data['P_TRADER_ENABLEMENT_MIN'][(trader_id, trade_type)],
                'low_breakpoint': data['P_TRADER_LOW_BREAKPOINT'][(trader_id, trade_type)],
                'high_breakpoint': data['P_TRADER_HIGH_BREAKPOINT'][(trader_id, trade_type)],
                'enablement_max': data['P_TRADER_ENABLEMENT_MAX'][(trader_id, trade_type)],
                'max_avail': data['P_TRADER_MAX_AVAIL'][(trader_id, trade_type)],
                'initial_mw': data['P_TRADER_EFFECTIVE_INITIAL_MW'].get(trader_id),  # TODO: may need to be updated (intervention)
                'uigf': data['P_TRADER_UIGF'].get(trader_id),
                'hmw': data['P_TRADER_HMW'].get(trader_id),
                'lmw': data['P_TRADER_LMW'].get(trader_id),
                'agc_status': data['P_TRADER_AGC_STATUS'].get(trader_id),
                'agc_ramp_up': data['P_TRADER_SCADA_RAMP_UP_RATE'].get(trader_id),
                'agc_ramp_dn': data['P_TRADER_SCADA_RAMP_DN_RATE'].get(trader_id),
                'trader_type': data['P_TRADER_TYPE'].get(trader_id),
                'semi_dispatch': data['P_TRADER_SEMI_DISPATCH_STATUS'].get(trader_id),
            }

    return out


def get_trader_fcas_availability_status(data) -> dict:
    """Get FCAS availability"""

    # Extract trade FCAS parameters into single dictionary to assist with availability calculations
    fcas_info = get_trader_fcas_info(data)

    # Container for FCAS availability
    fcas_status = {}
    for (trader_id, trade_type), params in fcas_info.items():
        # Get FCAS availability status
        fcas_status[(trader_id, trade_type)] = nemde.core.model.utils.fcas.get_trader_fcas_availability_status(params)

    return fcas_status


def get_interconnector_loss_model_breakpoints_x(data) -> dict:
    """Get interconnector loss model breakpoints - x-coordinate (power output)"""

    # Get loss model segments and lower limits for each interconnector
    limit = data['P_INTERCONNECTOR_LOSS_SEGMENT_LIMIT']
    lower_limit = data['P_INTERCONNECTOR_LOSS_LOWER_LIMIT']

    # Container for break point values - offset segment ID - first segment should be loss lower limit
    values = {(interconnector_id, segment_id + 1): v for (interconnector_id, segment_id), v in limit.items()}

    # Add loss lower limit with zero index (corresponds to first segment)
    for i in data['S_INTERCONNECTORS']:
        values[(i, 0)] = -lower_limit[i]

    return values


def get_interconnector_loss_estimate(segments, flow) -> float:
    """Estimate interconnector loss - numerically integrating loss model segments"""

    # Initialise total
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


def get_interconnector_loss_model_breakpoints_y(data) -> dict:
    """Get interconnector loss model breakpoints - y-coordinate (estimated loss)"""

    # Get loss model segments
    interconnectors = data['S_INTERCONNECTORS']
    limit = data['P_INTERCONNECTOR_LOSS_SEGMENT_LIMIT']
    lower_limit = data['P_INTERCONNECTOR_LOSS_LOWER_LIMIT']
    segments = data['intermediate']['loss_model_segments']

    # Container for break point values - offset segment ID - first segment should be loss lower limit
    values = {(interconnector_id, segment_id + 1): get_interconnector_loss_estimate(segments[interconnector_id], v)
              for (interconnector_id, segment_id), v in limit.items()}

    # Add loss lower limit with zero index (corresponds to first segment)
    for i in interconnectors:
        values[(i, 0)] = get_interconnector_loss_estimate(segments[i], -lower_limit[i])

    return values


def get_interconnector_initial_loss_estimate(data) -> dict:
    """Get initial loss estimate for each interconnector"""

    # Initial MW for all interconnectors
    interconnectors = data['S_INTERCONNECTORS']
    initial_mw = data['P_INTERCONNECTOR_EFFECTIVE_INITIAL_MW']  # TODO: will need to change if considering intervention pricing
    segments = data['intermediate']['loss_model_segments']

    # Loss estimate
    loss_estimate = {}
    for i in interconnectors:
        # Compute loss estimate for each interconnector
        loss_estimate[i] = get_interconnector_loss_estimate(segments[i], initial_mw[i])

    return loss_estimate


def preprocess_case_file(data) -> dict:
    """Apply pre-processing logic to formatted case file"""

    # Container for output
    out = {
        'S_TRADER_PRICE_TIED': get_trader_price_tied_bands(data),
        'P_TRADER_FCAS_AVAILABILITY_STATUS': get_trader_fcas_availability_status(data),
        'P_MNSP_REGION_LOSS_INDICATOR': get_mnsp_region_loss_indicator(data),
        'P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_X': get_interconnector_loss_model_breakpoints_x(data),
        'P_INTERCONNECTOR_LOSS_MODEL_BREAKPOINT_Y': get_interconnector_loss_model_breakpoints_y(data),
        'P_INTERCONNECTOR_INITIAL_LOSS_ESTIMATE': get_interconnector_initial_loss_estimate(data),
    }

    return out


def preprocess_serialized_casefile(data) -> dict:
    """Apply preprocessing and append to input dictionary"""

    # Preprocessed inputs
    preprocessed = {'preprocessed': preprocess_case_file(data)}

    # Output
    out = {**data, **preprocessed}

    return out
