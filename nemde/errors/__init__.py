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


class CasefileLookupError(LookupError):
    """
    Raised if casefile attribute is not found
    """


class CasefileRunModeError(ValueError):
    """
    Raised if intervention run mode is not 'physical' or 'pricing'
    """


class CasefileUpdaterLookupError(ValueError):
    """
    Raised when lookup performed in casefile updater does not return a single
    element.
    """


class CasefileOptionsError(ValueError):
    """
    Raised when user defined options are set incorrectly
    """
