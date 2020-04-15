"""
NI_IMAQ c dll wrapping class and session handler for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

Wraps the native NI_IMAQ functions defined in the niimaq.dll file and track the session and
interface data.
"""

from ctypes import *
import os
import struct
import platform

class NiImaqSession:
    def __init__(self):
        self.imaq = CDLL(os.path.join("C:\Windows\System32", "imaq.dll"))
        self.interface_id = c_ulong(0)
        self.session_id = c_ulong(0)

    def check(
            self,
            error_code: int,
            traceback_msg: str = None):
        """

        Args:
            error_code : error code which encodes status of operation.

            traceback_msg ():

        TODO : Proper logging
        TODO : Proper traceback
        TODO : Raise Errors and Warnings where appropriate

        Returns:

        """
