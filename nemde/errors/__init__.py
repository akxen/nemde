"""
Public exceptions and warnings
"""


class CasefileNotFoundError(FileNotFoundError):
    """
    Raised when casefile cannot be found.
    """


class CasefileQueryError(ValueError):
    """
    Raised if more than one casefile returned when querying database. Case ID
    is unique, so should only return one file.
    """


class CasefileValueError(ValueError):
    """
    Raised if casefile is not a string
    """