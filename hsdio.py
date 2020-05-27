"""
HSDIO class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For parsing XML strings which specify triggers and waveforms to be loaded to National
Instruments HSDIO hardware. 
"""

from ctypes import * # open to suggestions on making this better with minimal obstruction to workflow
import numpy as np
import xml.etree.ElementTree as ET
import os
import struct
import platform  # for checking the os bit
import logging
from ni_hsdio import HSDIOSession, HSDIOError
from typing import List

## local class imports
from instrumentfuncs import str_to_bool
from trigger import Trigger, StartTrigger
from waveform import HSDIOWaveform
from instrument import Instrument


class HSDIO(Instrument): # could inherit from an Instrument class if helpful

    if platform.machine().endswith("64"):
        programsDir32 = "Program Files (x86)"
    else:
        programsDir32 = "Program Files"

    dllpath32 = os.path.join(f"C:\{programsDir32}\IVI Foundation\IVI\Bin", "niHSDIO.dll")
    dllpath64 = os.path.join("C:\Program Files\IVI Foundation\IVI\Bin", "niHSDIO_64.dll")

    def __init__(self, pxi):
        super().__init__(pxi, "HSDIO")

        # device settings
        self.logger = logging.getLogger(str(self.__class__))
        self.pxi = pxi
        self.resourceNames = np.array([], dtype=str)
        self.clockRate = 2*10**7  # 20 MHz
        self.hardwareAlignmentQuantum = 1 # (in samples)
        self.activeChannels = np.array([], dtype=c_int32)
        self.initialStates = np.array([], dtype=str)
        self.idleStates = np.array([], dtype=str)
        self.pulseGenScript = """script script 1
                                      wait 1
                                   end script"""
        self.scriptTriggers: List[Trigger] = []
        self.startTrigger: StartTrigger = StartTrigger()
        self.description = ""

        # These two have are related to one another, each session is attached to a handle, each handle can support man
        # sessions. Sessions now have an attribute HsdioSession.handle (a python string)
        self.instrumentHandles: List[str] = []  # List to hold instrument handles; CAN PROBABLY DELETE; sessions takes care of this
        self.sessions: List[HSDIOSession] = []  # List to hold HsdioSession objects
        self.waveformArr: List[HSDIOWaveform] = []

        # whether or not we've actually populated the attributes above
        self.isInitialized = False
        # check this to see if waveform has been written and updated without error
        self.wvf_written = False

    def load_xml(self, node):
        """
        iterate through node's children and parse xml by tag to update HSDIO
        device settings
        'node': type is ET.Element. tag should be "HSDIO"
        """

        assert node.tag == self.expectedRoot, "This XML is not tagged for the HSDIO"

        for child in node:
            # the LabView code ignores non-element nodes. not sure if this
            # equivalent
            if type(child) == ET.Element:
                self.logger.debug(child)
                # handle each tag by name:
                if child.tag == "enable":
                    self.enable = self.str_to_bool(child.text)

                elif child.tag == "description":
                    self.description = child.text

                elif child.tag == "resourceName":
                    resources = np.array(child.text.split(","))
                    self.resourceNames = resources

                elif child.tag == "clockRate":
                    clock_rate = self.str_to_float(child.text)
                    self.clockRate = clock_rate

                elif child.tag == "hardwareAlignmentQuantum":
                    self.hardwareAlignmentQuantum = child.text

                elif child.tag == "triggers":

                    if type(child) == ET.Element:
                        trigger_node = child
                        for t_child in trigger_node:
                            if type(t_child) == ET.Element:  # TODO : Should we deal with the else?
                                self.scriptTriggers.append(Trigger(t_child))

                elif child.tag == "waveforms":
                    self.logger.debug("found a waveform")
                    wvforms_node = child
                    for wvf_child in wvforms_node:
                        if type(wvf_child) == ET.Element:  # TODO : Should we deal with the else?
                            if wvf_child.tag == "waveform":
                                self.waveformArr.append(HSDIOWaveform(wvf_child))

                elif child.tag == "script":
                    self.pulseGenScript = "Loren Ipsum"  # TODO : @Preston What goes here?

                elif child.tag == "startTrigger":
                    self.startTrigger = StartTrigger(child)

                elif child.tag == "InitialState":
                    self.initialStates = np.array(child.text.split(","))

                elif child.tag == "IdleState":
                    self.idleStates = np.array(child.text.split(","))

                elif child.tag == "ActiveChannels":
                    self.activeChannels = np.array(child.text.split("\n"))

                else:
                    self.logger.warning("Not a valid XML tag for HSDIO initialization")

    def init(self):
        """
        set up the triggering, initial states, script triggers, etc
        """

        if not (self.stop_connections or self.reset_connection):

            if self.isInitialized:

                # TODO : Figure out error handling for this case
                for session in self.sessions:
                    session.abort()
                    session.close()
                    pass

                self.sessions = []  # reset

            if self.enable:

                iterables = zip(self.idleStates, self.initialStates,
                                self.activeChannels, self.resourceNames)
                for idle_state, init_state, chan_list, resource in iterables:
                    self.sessions.append(HSDIOSession(resource))
                    session = self.sessions[-1]

                    try:
                        session.init_generation_sess()
                    except HSDIOError as e:
                        self.logger.error(f"{e}\nError Initiating session.", exc_info=True)
                        raise

                    try:
                        session.assign_dynamic_channels(chan_list)
                        session.configure_sample_clock(self.clockRate)
                        # TODO : use defined constant
                        session.configure_generation_mode(generation_mode=15)
                        session.configure_initial_state(chan_list, init_state)
                        session.configure_idle_state(chan_list,idle_state)
                    except HSDIOError as e:
                        self.logger.error(
                            f"{e}\nError setting generation parameters.",
                            exc_info=True
                        )
                        raise

                    try:
                        for trig in self.scriptTriggers:

                            # implement this in a better way so not hard-coding the numeric code
                            if trig.trig_type == trig.TYPES["Level"]:  # Level type

                                session.configure_digital_level_script_trigger(
                                    trig.trig_ID,  # str
                                    trig.source,  # str
                                    trig.level    # int
                                )

                            else:  # Edge type is default when initialized

                                session.configure_digital_edge_script_trigger(
                                    trig.trig_ID,
                                    trig.source,
                                    trig.edge
                                )
                    except HSDIOError as e:
                        self.logger.error(f"{e}\nError Configuring script triggers", exc_info=True)
                        raise

                    try:
                        if self.startTrigger.wait_for_start_trigger:
                            session.configure_digital_edge_start_trigger(
                                self.startTrigger.source,
                                self.startTrigger.edge
                            )
                    except HSDIOError as e:
                        self.logger.error(f"{e}\nError Configuring start trigger", exc_info=True)
                        raise

            self.isInitialized = True

    def update(self):
        """
        write waveforms to the HSDIO on-board storage
        """

        self.wvf_written = False

        if self.stop_connections or self.reset_connection:
            return

        if self.enable:

            for wf in self.waveformArr:

                wv_arr = wf.wave_split()
                # for each HSDIO card (e.g., Rb experiment has two cards)
                for i, session in enumerate(self.sessions):

                    wave = wv_arr[i]
                    fmt, data = wave.decompress()
                    try:
                        if format == "WDT":
                            session.write_waveform_wdt(
                                wave.name,
                                max(wave.transitions),
                                71,  # Group by sample for group by channel use 72
                                data
                            )
                        elif format == "uInt32":
                            session.write_waveform_uint32(
                                wave.name,
                                max(wave.transitions),
                                data
                            )
                    except HSDIOError as e:
                        self.logger.error(
                            f"{e}\nError writing waveform. Waveform has not been updated",
                            exc_info=True
                        )
        self.wvf_written = True

    def is_done(self) -> bool:
        """
        Check if the tasks being run are completed

        Return:
            'done': True if tasks completed, connection was stopped or reset, or
                self.enable is False. False otherwise.
        """

        done = True
        if not (self.stop_connections or self.reset_connection) and self.enable:

            for session in self.sessions:
                error_code, _is_done = session.is_done()
                # TODO : handle errors logically here or upstream
                if not _is_done:
                    done = False
                    break

        return done

    def start(self):
        """
        Start the tasks
        """
        if not (self.stop_connections or self.reset_connection) and self.enable:
            for session in self.sessions:
                error_code = self.session.initiate()

    def stop(self):
        """
        Abort the session
        """
        if self.enable:
            for session in self.sessions:
                error_code = session.abort()

    def settings(self, wf_arr, wf_names):  # TODO : @Juan Implement
        pass
        # the labview code has HSDIO.settings specifically for reading out the
        # settings on the front panel. for debugging, we could just have this
        # log certain HSDIO attributes

        # log stuff, call settings in the server code for debugging?

    def print_txt(self, node): # for debugging
        self.logger.info(f"{node.tag} = {node.text}")