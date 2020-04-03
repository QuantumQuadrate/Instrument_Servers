from ctypes import *
import os
import struct
import platform # for checking the os bit

class niHSDIO():
    """"
    Class to serve as a wrapper for niHSDIO.dll functions in a more python-like manner
    """

    if platform.machine().endswith("64"):
        programsDir32 = "Program Files (x86)"
    else:
        programsDir32 = "Program Files"

    dllpath32 = os.path.join(f"C:\{programsDir32}\IVI Foundation\IVI\Bin", "niHSDIO.dll")
    dllpath64 = os.path.join("C:\Program Files\IVI Foundation\IVI\Bin", "niHSDIO_64.dll")

    def __init__(self):

        # Quick test for bitness
        self.bitness = struct.calcsize("P") * 8
        if self.bitness == 32:
            # Default location of the 32 bit dll
            self.hsdio = CDLL(self.dllpath32)
        else:
            # Default location of the 64 bit dll
            self.hsdio = CDLL(self.dllpath64)

        self.vi = c_int(0)  # session id

    def check(self, error_code: int, traceback_msg: str = None):
        """
        Checks error_code against NI HSDIO built in error codes, prints (should become logs) error if operation was
        unsuccessful.

        TODO : Make this do proper traceback
        TODO : Setup logging
        TODO : Raise Errors and Warnings where appropriate


        Args:
            error_code: error code which reports status of operation.

                0 = Success, positive values = Warnings , negative values = Errors
            traceback_msg: message useful for traceback
        """

        if error_code == 0:
            return

        err_msg = c_char_p("".encode("utf-8"))  # unsure this will work, c function requires buffer array of length 256
        self.hsdio.niHSDIO_error_message(self.vi,                       # ViSession
                                         c_int32(error_code),           # ViStatus
                                         err_msg)                       # ViChar[256]

        if error_code < 0:
            message = "Error Code"
        elif error_code > 0:
            message = "Warning Code"
        else:
            message = ""
        message += " {} : {}"
        if traceback_msg is not None:
            message += "\n{}"

        message = message.format(error_code, err_msg, traceback_msg)

        print(message)
        return

    def init_generation_sess(self, device_name: str, id_query: bool = True, reset_instr: bool = True,
                             check_error: bool = True) -> int:
        """
        Creates new generation session with device_name. This doesn't automatically tristate front panel terminals or
        channels that might have been left driving voltages from previous sessions (Refer to self.close() ).

        Pass in reset_instr = True to place device in a known state when creating a new session. This is equivalent to
        calling self.reset() and tristates front panel terminals and channels.


        Args:
            device_name : address of device to be accessed as it shows up in NI MAX (e.g. "Dev1")
            id_query : should the driver perform and ID query on the device. When true, compatibility
                between device and driver is ensured
            reset_instr : should the instrument be reset when session is generated. This is equivalent to
                calling self.reset() and tristates front panel terminals and channels.

                Warning: This will reset the entire device. Acquisition or generation operations in progress are aborted
                and cleared.
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_InitGenerationSession(c_char_p(device_name.encode('utf-8')),  # ViRsrc
                                                              c_bool(id_query),                       # ViBoolean
                                                              c_bool(reset_instr),                    # ViBoolean
                                                              c_char_p("".encode('utf-8')),           # ViConstString
                                                              byref(self.vi))                         # ViSession

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="init_generation_sess")

        return error_code

    def assign_dynamic_channels(self, channel_list: str) -> int:
        """
        Configures channels for dynamic acquisition (if self.vi is an acquisition session) or dynamic generation
        (if self.vi is a generation session).


        Args:
            channel_list : Identifies which channels are reserved for dynamic operation.
                Valid Syntax:
                "0-19" or "0-15,16-19" or "0-18,19", "" (empty string) or None to specify all channels
                "none" to unassign all channels

                Channels cannot be configured for both static generation and dynamic generation.

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        # c function take vi const string : mapped to const ViChar * mapped to char *.

    def close(self, reset: bool = True, check_error: bool = True) -> int:
        """
        Closes the session and frees resources that were reserved. If the session is running, it is first aborted.

        To prevent generating unwanted signal glitches between sessions, no front panel terminals or channels are
        tristated by calling this function; they all continue to drive whatever voltage they would drive had you simply
        called the self.abort() function. Pass in reset = True if you want to tristate your terminals and channels
        before closing your session.


        Args:
            reset : error code which reports status of operation. 0 = Success,
                positive values = Warnings , negative values = Errors
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        if reset:
            self.reset()
        error_code = self.hsdio.niHSDIO_close(self.vi)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close")

        return error_code

    def abort(self, check_error: bool = True) -> int:
        """
        Stops a running dynamic session. This function is generally not required on finite data operations, as these
        operations complete after the last data point is generated or acquired. This function is generally required for
        continuous operations or if you wish to interrupt a finite operation before it is completed.

        This function is valid only for dynamic operations (acquisition or generation). It is not valid for static
        operations.

        @return: error_code : Int, error code which reports status of operation. 0 = Success,
            positive values = Warnings , negative values = Errors


        Args:
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_Abort(self.vi)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="abort")

        return error_code

    def reset(self, check_error: bool = True) -> int:
        """
        Call this function to reset the session to its Initial state. All channels and front panel terminals are put
        into a high-impedance state. All software attributes are reset to their initial values.

        During a reset, signal routes between this and other devices are released, regardless of which device created
        the route. For instance, a trigger signal being exported to a PXI trigger line and used by another device no
        longer exported.

        The reset is applied to the entire device. If you have both a generation and an acquisition session active, this
        function resets the current session, including attributes, and invalidates the other session if it is committed
        or running. The other session must be closed.

        Note: The above is straight from the NI HSDIO c function reference (version 19.5). This class assumes a single
        session is active at a time (as of 2020.04.03).


        Args:
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_reset(self.vi)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="reset")

        return error_code