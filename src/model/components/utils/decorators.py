"""Decorators used to parse attributes within NEMDE case files"""

import functools


def str_to_float(func):
    """Attempt to convert string to float, return input if conversion fails"""

    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        value = func(*args, **kwargs)

        if type(value) == str:
            try:
                return float(value)
            except ValueError:
                return value
        return value

    return wrapper_decorator


