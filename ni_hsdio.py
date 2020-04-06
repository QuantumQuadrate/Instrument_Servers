from ctypes import *
import os
import struct
import platform # for checking the os bitness


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

    def init_generation_sess(self, resource_name: str, id_query: bool = True, reset_instr: bool = True,
                             check_error: bool = True) -> int:
        """
        Creates new generation session with device_name. This doesn't automatically tristate front panel terminals or
        channels that might have been left driving voltages from previous sessions (Refer to self.close() ).

        Pass in reset_instr = True to place device in a known state when creating a new session. This is equivalent to
        calling self.reset() and tristates front panel terminals and channels.


        Args:
            resource_name : address of device to be accessed as it shows up in NI MAX (e.g. "Dev1")
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

        error_code = self.hsdio.niHSDIO_InitGenerationSession(c_char_p(resource_name.encode('utf-8')),  # ViRsrc
                                                              c_bool(id_query),                         # ViBoolean
                                                              c_bool(reset_instr),                      # ViBoolean
                                                              c_char_p("".encode('utf-8')),             # ViConstString
                                                              byref(self.vi))                           # ViSession

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="init_generation_sess")

        return error_code

    def assign_dynamic_channels(self, channel_list: str, check_error: bool = True) -> int:
        """
        Configures channels for dynamic acquisition (if self.vi is an acquisition session) or dynamic generation
        (if self.vi is a generation session).

        wraps niHSDIO_AssignDynamicChannels

        Args:
            channel_list : Identifies which channels are reserved for dynamic operation.
                Valid Syntax:
                "0-19" or "0-15,16-19" or "0-18,19", "" (empty string) or None to specify all channels
                "none" to unassign all channels

                Channels cannot be configured for both static generation and dynamic generation.
            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_AssignDynamicChannels(self.vi,                                  # ViSession
                                                              c_char_p(channel_list.encode('utf-8')))   # ViConstString

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="assign_dynamic_channels")

        return error_code

    def configure_sample_clock(self, clock_rate: float, clock_source: str = "OnBoardClock", check_error: bool = True) \
            -> int:
        """
        Configures the Sample clock. This function allows you to specify the Sample clock source and rate.

        wraps niHSDIO_ConfigureSampleClock

        Args:
            clock_rate : Specifies the Sample clock rate, expressed in Hz. You must set this parameter even when you
                supply an external clock because NI-HSDIO uses this parameter for a number of reasons, including optimal
                error checking and certain pulse width selections.
            clock_source : Specifies the Sample clock source.
                Allowed Values:
                "OnBoardClock" — The device uses the On Board Clock as the Sample clock source.
                "STROBE" — The device uses the signal present on the STROBE channel as the Sample clock source. This
                choice is valid only for acquisition operations.
                "ClkIn" — The device uses the signal present on the front panel CLK IN connector as the Sample clock
                source.
                "PXI_STAR" — The device uses the signal present on the PXI_STAR line as the Sample clock source. This
                choice is valid for devices in slots that support PXI_STAR.
            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        # TODO : Is this the right way to perform this check?
        allowed_sources = ["OnBoardClock", "STROBE", "ClkIn", "PXI_STAR"]
        assert clock_source in allowed_sources

        error_code = self.hsdio.niHSDIO_ConfigureSampleClock(self.vi,
                                                             c_char_p(clock_source.encode('utf-8')),  # ViConstString
                                                             c_double(clock_rate))                    # ViReal64

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="configure_sample_clock")

        return error_code

    def configure_generation_mode(self, generation_mode: int = 14, check_error: bool = True) \
            -> int:
        """

        Configures whether to generate the waveform specified in NIHSDIO_ATTR_WAVEFORM_TO_GENERATE or the script
        specified in NIHSDIO_ATTR_SCRIPT_TO_GENERATE upon calling the niHSDIO_Initiate function.

        wraps niHSDIO_ConfigureGenerationMode

        Args:
            generation_mode : code specifying generation mode to configure
                14(WAVEFORM) - Calling self.initiate generates the named waveform represented by
                NIHSDIO_ATTR_WAVEFORM_TO_GENERATE
                15(SCRIPTED) - Calling niHSDIO_Initiate generates the script represented by
                NIHSDIO_ATTR_SCRIPT_TO_GENERATE

            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        # TODO : Is this the right way to perform this check?
        allowed_modes = [14, 15]
        assert generation_mode in allowed_modes

        error_code = self.hsdio.niHSDIO_ConfigureGenerationMode(self.vi,                   # ViSession
                                                                c_int32(generation_mode))  # ViInt32

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="configure_generation_mode")

        return error_code

    def configure_initial_state(self,channel_list: str, initial_state: str, check_error : bool = True) -> int:
        """
        Sets the initial state for a dynamic generation operation.

        The initial state of each channel is driven after the session is initiated using the self.initiate function.

        Note : NI 656x devices do not support the high-impedance (Z) Initial state

        Wraps niHSDIO_ConfigureInitialState()

        Args:
            channel_list : Specifies which channels have their initial value set using the initial_state  string. The
                order of channels in channel_list determines the order of the initial_state string.
            initial_state : Describes the Initial state of a dynamic generation operation. This expression is composed
                of characters:
                * 'X' or 'x': keeps previous value
                * '1': sets channel logic high
                * '0': sets channel logic low
                * 'Z' or 'z': disables channel or sets it to high-impedance.
                The first character in the expression corresponds to the first channel in channel_list. The number of
                characters in pattern must equal the number of channels specified in channel_list or an error is
                returned

                The default state of a channel is to keep the previous value.
            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_ConfigureInitialState(self.vi,                                  #ViSession
                                                              c_char_p(channel_list.encode('utf-8')),   #ViConstString
                                                              c_char_p(initial_state.encode('utf-8')))  #ViConstString
        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="configure_initial_state")

        return error_code

    def configure_idle_state(self,channel_list: str, idle_state: str, check_error : bool = True) -> int:
        """
        Sets the Idle state for a dynamic operation.

        The Idle state may be active in a variety of conditions:
        * The generation operation completes normally
        * The generation operation pauses from an active Pause trigger
        * The generation operation terminates due to an underflow error

        Wraps niHSDIO_ConfigureIdleState

        Args:
            channel_list :Specifies which channels have their idle value set using the idle_state string. The order of
                channels in channel_list determines the order of the idle_state string.
            idle_state : Describes the Idle state of a dynamic generation operation. This expression is composed
                of characters:
                * 'X' or 'x': keeps previous value
                * '1': sets channel logic high
                * '0': sets channel logic low
                * 'Z' or 'z': disables channel (sets it to high-impedance.)
            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_ConfigureIdleState(self.vi,                                 # ViSession
                                                           c_char_p(channel_list.encode('utf-8')),  # ViConstString
                                                           c_char_p(idle_state.encode('utf-8')))    # ViConstString
        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="configure_idle_state")

        return error_code

    def initiate(self,check_error: bool = True) -> int:
        """
        Commits any pending attributes to hardware and starts the dynamic operation

        (refer to the niHSDIO_CommitDynamic
        function for more information about committing).

        For a generation operation with a Start trigger configured, calling this function causes the channels to go to
        their Initial states.

        This function is valid only for dynamic operations (acquisition or generation). It is not valid for static
        operations.

        wraps niHSDIO_Initiate

        Args:
            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.hsdio.niHSDIO_Initiate(self.vi)  # ViSession

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="initiate")

        return error_code

    def configure_digital_edge_start_trigger(self, source: str, edge: int, check_error: bool = True) -> int:
        """

        Configures the Start trigger for edge triggering.

        Args:
            source : You may specify any valid source terminal for this trigger. Trigger voltages and positions are only
                relevant if the source of the trigger is from the front panel connectors. For more info on valid Source
                values
                http://zone.ni.com/reference/en-XX/help/370520P-01/hsdiocref/cvinihsdio_configuredigitaledgestarttrigger
                Note : Only NI 6555/6556 devices support PFI <24..31> and PXIe DStarB.
            edge : Specifies the edges to detect
                12 - rising edge trigger
                13 - falling edge trigger
            check_error : should the check() function be called once operation has completed
        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        allowed_edges = [12, 13]
        assert edge in allowed_edges

        c_source = c_char_p(source.encode('utf-8'))
        error_code = self.hsdio.niHSDIO_ConfigureDigitalEdgeStartTrigger(self.vi,        # ViSession
                                                                         c_source,       #ViConstString
                                                                         c_int32(edge))  # ViInt32

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="configure_digital_edge_start_trigger")

        return error_code

    def configure_digital_level_script_trigger(self,
                                               trigger_id: str,
                                               source: str,
                                               level: int,
                                               check_error: bool = True) -> int:
        """
        Configures the Script trigger for level triggering.

        This function is valid only for generation sessions that use scripting.

        Args:
            trigger_id : Identifies which Script trigger this function configures.
                Defined Values :
                "ScriptTrigger0"
                "ScriptTrigger1"
                "ScriptTrigger2"
                "ScriptTrigger3"

            source : You may specify any valid source terminal for this trigger. Trigger voltages and positions are only
                relevant if the source of the trigger is from the front panel connectors.

                For more info on valid Source values
                http://zone.ni.com/reference/en-XX/help/370520P-01/hsdiocref/cvinihsdio_configuredigitaledgestarttrigger

                Note  Only NI 6555/6556 devices support PFI <24..31> and PXIe DStarB.

            level : Specifies the active level for the desired trigger.
                Defined Values :
                NIHSDIO_VAL_HIGH (34) — Trigger is active while its source is high level.
                NIHSDIO_VAL_LOW (35) — Trigger is active while its source is low level.

            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        allowed_levels = [34, 35]
        assert level in allowed_levels
        allowed_ids = ["ScriptTrigger0",
                       "ScriptTrigger1",
                       "ScriptTrigger2",
                       "ScriptTrigger3"]
        assert trigger_id in allowed_ids

        c_source = c_char_p(source.encode('utf-8'))
        c_trigger_id = c_char_p(trigger_id.encode('utf-8'))
        error_code = self.hsdio.niHSDIO_ConfigureDigitalLevelScriptTrigger(self.vi,              # ViSession
                                                                           c_trigger_id,         # ViConstString
                                                                           c_source,             # ViConstString
                                                                           c_int32(trigger_id))  # ViInt32

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="configure_digital_level_script_trigger")

        return error_code

    def write_waveform_wdt(self,waveform_name: str, samp_per_chan: int, data_layout: int, data: ):

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