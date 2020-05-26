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


def str_to_bool(boolstr: str) -> bool:
    """
    return True or False case-insensitively for a string 'true' or 'false'

    If boolstr is not 'true' or 'false' this function will raise a KeyError

    Args:
        'boolstr': string to be converted; not case-sensitive
    Return:
        'boolean': True or False.
    """
    conv = {"true": True,
            "false": False}
    return conv[boolstr.lower()]


def int_from_str(numstr): 
    """ 
    Returns a signed integer ancored to beginning of a string
    
    behaves like LabVIEW Number from String VI (with the VI defaults
    
    Args:
        'numstr': a string which may contain a signed number at the beginning
    
    Returns:
        'num': (int) a signed integer, if found
    
        Example input/output pairs:
        
            Input     | Output
            -----------------
            '-4.50A'  | -4.5
            '31415q' | 31415
            'ph7cy'   | None, throws ValueError
    """
    try:
        return int(re.findall("^-?\d+", numstr)[0])
    except ValueError as e:
        # TODO: replace with logger
        print(f'String {numstr} is non-numeric. \n {e}')
        raise