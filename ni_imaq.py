"""
NI_IMAQ c dll wrapping class and session handler for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

Wraps the native NI_IMAQ functions defined in the niimaq.dll file and track the session and
interface data.
"""

from ctypes import *
import os
from typing import Tuple

class HamamatsuSerialError(Exception):
    """
    Error to deal with Hamamatsu serial writing issues

    TODO : Is this the right way to define this???
    """
    def __init__(self, msg: str):
        """
        Args:
            msg: message tied to this serial error
        """
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

class NiImaqSession:

    # timeout values
    IMG_TIMEOUT_INFINITE = int(0xFFFFFFFF, 16)  # found in niimaq.h

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
            check_error: bool = True) -> int:
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
            check_error: bool = True) -> int:
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
            check_error: bool = True) -> int:
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
            return error_code

        # close interface
        error_code = self.imaq.imgClose(
            self.interface_id,
            free_resources)
        self.session_id = c_uint32(0)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close interface")
            return error_code

        return error_code

    def hamamatsu_serial(
            self,
            command: str,
            expected_response: str = "Nothing",
            timeout: int = 10000,
            check_error: bool = True
    ) -> Tuple[int, str]:
        """
        Writes data to the serial port.

        Serial communication parameters, such as baud rate, are set in the camera file associated
        with the session. You can adjust these communication parameters directly in the camera file.

        Args:
            command : command being written to the Hamamatsu via imaq
            expected_response : expected response from the ni imaq. If camera's response doesn't
                expected_response a warning is printed out.
                TODO : Make this either throw an error or a warning
                If set to "Nothing" no check is performed on the camera's response. Otherwise
            timeout : time, in miliseconds, for imaq to wait or the data to be written.
                Use IMG_TIMEOUT_INFINITE to wait indefinitely
            check_error :

            check_error : should the check() function be called once operation has completed

        Returns:
            [error_code, camera_response]
                error_code : error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
                camera_response : camera's response to command. encoded in utf-8
        """

        # add carriage return, ends all camera serial i/o
        c_cmd = c_char_p(f"{command}\r".encode('utf-8'))
        enc_exp_rsp = f"{expected_response}\r".encode('utf-8')

        bf_size = c_uint32(sizeof(c_cmd))
        
        error_code = self.imaq.imgSessionSerialWrite(
            self.session_id,   # SESSION_ID
            c_cmd,             # void*
            byref(bf_size),    # uInt32*
            c_int32(timeout),  # uInt32
        )

        if error_code != 0 and check_error:
            self.check(error_code, f"imaq serial write command {command}")
            return error_code

        str_bf = create_string_buffer(b"", bf_size.value)
        error_code = self.imaq.imgSessionSerialRead(
            self.session_id,  # SESSION_ID
            str_bf,           # void*
            byref(bf_size),   # uInt32*
            c_int32(timeout)  # Int32
        )

        '''
        Not 100% on why this is here but it's done in the labview. In labview it's added to the 
        error tracker wire. Here I'm just printing(logging) a warning, maybe this should raise an 
        error instead. It should be treated consistently with check() at least
        '''
        enc_rsp = str_bf.value
        if expected_response == "Nothing" and enc_exp_rsp == enc_rsp:
            return error_code, enc_rsp
        er_msg = f"Serial write {command}. Expected Response {enc_exp_rsp}\n Got {enc_rsp}\n"
        print(er_msg)  # TODO : use logging
        return error_code, enc_rsp




