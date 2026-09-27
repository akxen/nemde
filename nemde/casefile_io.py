"""Normalize casefile input into the xmltodict-shaped dict run_model() expects."""

import xmltodict

CasefileInput = str | bytes | dict

# Elements that must always parse to a list, even when only one is present.
FORCE_LIST = ("Trade", "TradeTypePriceStructure")


def normalize_casefile(data: CasefileInput) -> dict:
    """Accept a raw XML casefile (str/bytes) or an already-xmltodict-parsed dict
    and return the xmltodict-shaped dict that run_model() expects."""

    if isinstance(data, dict):
        return data
    if isinstance(data, (str, bytes)):
        return xmltodict.parse(data, force_list=FORCE_LIST)
    raise TypeError(f"Unsupported casefile input type: {type(data)!r}")
