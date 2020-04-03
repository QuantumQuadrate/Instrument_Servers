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

    def check(self, error_code, traceback_msg=None):
        """
        Checks error_code against NI HSDIO built in error codes, prints (should become logs) error if operation was
        unsuccessful.
        @param error_code : Int, error code which reports status of operation. 0 = Success,
            positive values = Warnings , negative values = Errors
        @param traceback_msg : String, message useful for traceback
        """

        if error_code == 0:
            return

        err_msg = c_char_p("".encode("utf-8"))  # unsure this will work, c function requires buffer array of length 256
        self.hsdio.niHSDIO_error_message(self.vi, c_int32(error_code), err_msg)

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

    def init_generation_sess(self, device_name, id_query=True, reset_instr=True, check_error=True):
        """
        Creates new generation session with device_name. This doesn't automatically tristate front panel terminals or
        channels that might have been left driving voltages from previous sessions (Refer to self.close() ).

        Pass in reset_instr = True to place device in a known state when creating a new session. This is equivalent to
        calling self.reset() and tristates front panel terminals and channels.

        @return: error_code : Int, error code which reports status of operation. 0 = Success,
            positive values = Warnings , negative values = Errors
        @param device_name : String, name/address of device to be accessed as it shows up in NI MAX (e.g. "Dev1")
        @param id_query : Boolean, should the driver perform and ID query on the device. When true, compatibility
            between device and driver is ensured
        @param reset_instr : Boolean, should the instrument be reset when session is generated. This is equivalent to
            calling self.reset() and tristates front panel terminals and channels.
        @param check_error : Boolean, should the check() function be called once operation has completed
        """

        error_code = self.hsdio.niHSDIO_InitGenerationSession(c_char_p(device_name.encode('utf-8')),
                                                         c_bool(id_query),
                                                         c_bool(reset_instr),
                                                         c_char_p("".encode('utf-8')),
                                                         byref(self.vi))

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="init_generation_sess")

        return error_code

    def close(self, reset=True, check_error=True):
        """
        Closes the session and frees resources that were reserved. If the session is running, it is first aborted.

        To prevent generating unwanted signal glitches between sessions, no front panel terminals or channels are
        tristated by calling this function; they all continue to drive whatever voltage they would drive had you simply
        called the self.abort() function. Pass in reset = True if you want to tristate your terminals and channels
        before closing your session.

        @return: error_code : Int, error code which reports status of operation. 0 = Success,
            positive values = Warnings , negative values = Errors
        @param reset : Boolean, calls self.reset() prior to closing the session, tristates terminals and channels
        @param check_error : Boolean, should the check() function be called once operation has completed
        """

        if reset:
            self.reset()
        error_code = self.hsdio.niHSDIO_close(self.vi)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close")

        return error_code

    def abort(self, check_error=True):
        """
        Stops a running dynamic session. This function is generally not required on finite data operations, as these
        operations complete after the last data point is generated or acquired. This function is generally required for
        continuous operations or if you wish to interrupt a finite operation before it is completed.

        This function is valid only for dynamic operations (acquisition or generation). It is not valid for static
        operations.

        @return: error_code : Int, error code which reports status of operation. 0 = Success,
            positive values = Warnings , negative values = Errors
        @param check_error : Boolean, should the check() function be called once operation has completed
        """

        error_code = self.hsdio.niHSDIO_Abort(self.vi)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="abort")

        return error_code

    def reset(self, check_error=True):
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


        @return: error_code : Int, error code which reports status of operation. 0 = Success,
            positive values = Warnings , negative values = Errors
        @param check_error : Boolean, should the check() function be called once operation has completed
        """

        error_code = self.hsdio.niHSDIO_reset(self.vi)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="reset")

        return  error_code