"""
Algorithms used when preprocessing attributes from casefile information
"""


from nemde.core.casefile.lookup import get_interconnector_loss_model_attribute
from nemde.core.casefile.lookup import get_interconnector_loss_model_segments


def get_parsed_interconnector_loss_model_segments(data, interconnector_id) -> list:
    """
    Use breakpoints and segment factors to construct a new start-end-factor
    representation for a given interconnector's MLF curve segments

    Parameters
    ----------
    data : dict
        NEMDE casefile

    interconnector_id : str
        Interconnector ID

    Returns
    -------
    new_segments : list
        Loss model segments in a start-end-factor representation
        E.g. [{'start': float, 'end': float, 'factor': float}, ...]
    """

    # Lower bound for loss model
    loss_lower_limit = get_interconnector_loss_model_attribute(
        data=data, interconnector_id=interconnector_id,
        attribute='@LossLowerLimit', func=float)

    # Get segments from casefile
    segments = get_interconnector_loss_model_segments(
        data=data, interconnector_id=interconnector_id)

    # First segment set equal to loss lower limit
    start = -loss_lower_limit

    # Format segments with start, end, and factor
    new_segments = []
    for s in segments:
        segment = {'start': start, 'end': s['@Limit'], 'factor': s['@Factor']}
        start = s['@Limit']
        new_segments.append(segment)

    return new_segments


def get_interconnector_loss_estimate(data, interconnector_id, flow) -> float:
    """
    Estimate interconnector loss by numerically integrating loss model segments

    Parameters
    ----------
    data : dict
        NEMDE casefile

    interconnector_id : str
        Interconnector ID

    flow : float
        Flow over interconnector (MW)

    Returns
    -------
    total_area : float
        Total area under MLF curve corresponds to total loss (MW)
    """

    # Construct segments based on loss model
    segments = get_parsed_interconnector_loss_model_segments(
        data=data, interconnector_id=interconnector_id)

    # Initialise total area
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
