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

    def open_interface(
            self,
            dev_addr: str,
            check_error: bool = True) -> c_int32:
        """
        Opens an ni-imaq interface by name as specified in Measurement & Automation Explorer (MAX).
        If it is successful, this function self.interface_id to a valid INTERFACE_ID

        Args:
            dev_addr : name of the interface to open as it shows up in NI MAX, such as img0, img1,
                and so on.
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        c_addr = c_char_p(dev_addr.encode('utf-8'))
        error_code = self.imaq.imgInterfaceOpen(
            c_addr,                   # char*
            byref(self.interface_id)  # INTERFACE_ID*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="open_interface")

        return error_code

    def open_session(
            self,
            check_error: bool = True) -> c_int32:
        """
        Opens a session and sets a session ID.

        This function inherits all data associated with the given interface.

        if successful sets self.session_id to a valid SESSION_ID

        wraps imgSessionOpen()

        Args:
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgSessionOpen(
            self.interface_id,      # INTERFACE_ID
            byref(self.session_id)  # SESSION_ID*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="open_interface")

        return error_code

    def close(
            self,
            free_resources: bool = True,
            check_error: bool = True) -> c_int32:
        """
        Closes both session and interface, releases all associated resources if free_resources is
        set to true

        wraps imgClose()

        Args:
            free_resources : should all resources associated with this interface and session be
                freed?
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        # close session
        error_code = self.imaq.imgClose(
            self.session_id,
            free_resources)
        self.session_id = c_uint32(0)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close session")

        # close interface
        error_code = self.imaq.imgClose(
            self.interface_id,
            free_resources)
        self.session_id = c_uint32(0)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close interface")

    def session_get_roi(
            self):