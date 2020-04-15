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
        self.interface_id = c_uint32(0)
        self.session_id = c_uint32(0)

    def check(
            self,
            error_code: int,
            traceback_msg: str = None):
        """
        Checks error_code with self.imaq to get out a descriptive error message and prints(logs)
        error/warning  if operation was unsuccessful
        TODO : Proper logging
        TODO : Proper traceback
        TODO : Raise Errors and Warnings where appropriate

        Args:
            error_code : error code which encodes status of operation.
                0 = Success, positive values = Warnings , negative values = Errors
            traceback_msg: message useful for traceback
        """
        if error_code == 0:
            return

        err_msg = c_char_p("".encode('utf-8'))

        self.imaq.imgShowError(
            error_code,  # IMG_ERR
            err_msg)     # char*

        if error_code < 0:
            code_type = "Error Code"
        elif error_code > 0:
            code_type = "Warning Code"
        else:
            code_type = ""
        if traceback_msg is None:
            message = f"{code_type} {error_code} :\n {err_msg}"
        else:
            message = f"{code_type} {error_code} in {traceback_msg}:\n {err_msg}"

        print(message)
        return

    def open_interface(self,dev_addr):