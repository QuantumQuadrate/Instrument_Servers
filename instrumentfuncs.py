"""
Functions for use in the PXI Server Instruments
SaffmanLab, University of Wisconsin - Madison

Functions here are used in many/all of the instrument classes for the PXI 
Server, and are stated here to avoid hardcoding them in each class. 
If there are enough of them here, that could be an argument for building an
instrument class. 
"""

## modules
import re


def str_to_bool(boolstr):
    """
    return True or False case-insensitively for a string 'true' or 'false'

    Args:
        'boolstr': string to be converted; not case-sensitive

    Returns:
        boolean valued True or False.

    Raises:
        ValueError if the provided string isn't recognized as true or false.
    """
    boolstr = boolstr.lower()
    if boolstr == "true":
        return True
    elif boolstr == "false":
        return False
    else:
        raise ValueError(f"Expected a string 'true' or 'false' but received {boolstr}")


def int_from_str(numstr): 
    """ 
    Returns a signed integer anchored to beginning of a string
    behaves like LabVIEW Number from String VI (with the VI defaults)

    Example input/output pairs:

    Input     | Output
    -----------------
    '-4.50A'  | -4
    '31415q' | 31415
    'ph7cy'   | None, throws ValueError


    Args:
        'numstr': a string which may contain a signed number at the beginning
    
    Returns:
        'num': (int) a signed integer, if found

    Raises:
        ValueError if there is no leading integer in the string

    """
    try:
        return int(re.findall("^-?\d+", numstr)[0])
    except IndexError:
        raise ValueError(f'String {numstr} is non-numeric.')
