"""Functions used to parse and convert attributes within NEMDE case files"""


def parse_single_attribute(data, attribute):
    """Check that only one element exists. Extract attribute value and attempt float conversion."""

    # Check there is only one value returned
    assert len(data) == 1, f'Length of list != 1. List has {len(data)} elements'

    # Attribute value
    value = data[0].get(attribute)

    # Try and convert to float if possible
    try:
        return float(value)
    except ValueError:
        return value
