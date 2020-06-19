"""
HSDIO class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For parsing XML strings which specify triggers and waveforms to be loaded to National
Instruments HSDIO hardware. 
"""

from ctypes import *
import numpy as np
import xml.etree.ElementTree as ET
import os
import struct
import platform  # for checking the os bit
import logging
from ni_hsdio import HSDIOSession
from typing import List

## local class imports
from trigger import Trigger, StartTrigger
from waveform import HSDIOWaveform
from instrument import Instrument
from pxierrors import XMLError, HSDIOError, HardwareError


class HSDIO(Instrument):

    if platform.machine().endswith("64"):
        programsDir32 = "Program Files (x86)"
    else:
        programsDir32 = "Program Files"

    dllpath32 = os.path.join(f"C:\{programsDir32}\IVI Foundation\IVI\Bin", "niHSDIO.dll")
    dllpath64 = os.path.join("C:\Program Files\IVI Foundation\IVI\Bin", "niHSDIO_64.dll")

    def __init__(self, pxi, node: ET.Element = None):
        # device settings
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

        self.sessions: List[HSDIOSession] = []
        self.waveformArr: List[HSDIOWaveform] = []

        # check this to see if waveform has been written and updated without error
        self.wvf_written = False

        super().__init__(pxi, "HSDIO", node)

    def load_xml(self, node):
        """
        iterate through node's children and parse xml by tag to update HSDIO
        device settings
        'node': type is ET.Element. tag should be "HSDIO"
        """
        
        self.is_initialized = False

        super().load_xml(node)

        if not (self.exit_measurement or self.stop_connections):

            for child in node:

                if self.exit_measurement or self.stop_connections:
                    break
        
                try:

                    self.logger.debug(child)
                    # handle each tag by name:
                    if child.tag == "enable":
                        self.enable = Instrument.str_to_bool(child.text)

                    elif child.tag == "description":
                        self.description = child.text

                    elif child.tag == "resourceName":
                        resources = np.array(child.text.split(","))
                        self.resourceNames = resources

                    elif child.tag == "clockRate":
                        self.clockRate = float(child.text)

                    elif child.tag == "hardwareAlignmentQuantum":
                        self.hardwareAlignmentQuantum = child.text

                    elif child.tag == "triggers":

                        if type(child) == ET.Element:
                            trigger_node = child
                            for t_child in trigger_node:
                                self.scriptTriggers.append(Trigger(t_child))

                    elif child.tag == "waveforms":
                        self.logger.debug("found a waveform")
                        wvforms_node = child
                        for wvf_child in wvforms_node:
                            if wvf_child.tag == "waveform":
                                self.waveformArr.append(HSDIOWaveform(node=wvf_child))

                    elif child.tag == "script":
                        self.pulseGenScript = child.text

                    elif child.tag == "startTrigger":
                        self.startTrigger = StartTrigger(child)

                    elif child.tag == "InitialState":
                        self.initialStates = np.array(child.text.split(","))

                    elif child.tag == "IdleState":
                        self.idleStates = np.array(child.text.split(","))

                    elif child.tag == "ActiveChannels":
                        self.activeChannels = np.array(child.text.split("\n"))

                    else:
                        self.logger.warning(f"Unrecognized XML tag '{child.tag}' in <{self.expectedRoot}>")

                except ValueError: # maybe catch other errors too.
                    raise XMLError(self, child)

    def init(self):
        """
        set up the triggering, initial states, script triggers, etc
        """

        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return

        if not self.is_initialized: 

            # TODO : Figure out error handling when these fail 
            # ^ @Juan: handle errors inside abort and close. see stop,close in 
            # other device classes for inspiration. - Preston
            for session in self.sessions:
                session.abort()
                session.close()

            self.sessions = []  # reset

        iterables = zip(self.idleStates, self.initialStates,
                        self.activeChannels, self.resourceNames)
        for idle_state, init_state, chan_list, resource in iterables:
            self.sessions.append(HSDIOSession(resource))
            session = self.sessions[-1]

            try:
                session.init_generation_sess()
                # TODO : deal with error case where session is not initiated
                session.assign_dynamic_channels(chan_list)
                session.configure_sample_clock(self.clockRate)
                session.configure_generation_mode(
                    generation_mode=HSDIOSession.NIHSDIO_VAL_SCRIPTED
                )
                session.configure_initial_state(chan_list, init_state)
                session.configure_idle_state(chan_list, idle_state)

                for trig in self.scriptTriggers:
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

                if self.startTrigger.wait_for_start_trigger:
                    session.configure_digital_edge_start_trigger(
                        self.startTrigger.source,
                        self.startTrigger.edge
                    )
            except (AssertionError, HSDIOError) as e:
                session.abort()
                session.close()

                if isinstance(e, HSDIOError):
                    raise HardwareError(self, session, message=e.message)
                else:
                    raise e

        self.is_initialized = True

    def update(self):
        """
        write waveforms to the HSDIO on-board storage
        """

        self.wvf_written = False

        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return

        for wf in self.waveformArr:

            wv_arr = wf.wave_split()
            # for each HSDIO card (e.g., Rb experiment has two cards)
            for session, wave in zip(self.sessions, wv_arr):

                fmt, data = wave.decompress()
                try:
                    if format == "WDT":
                        # grouping = HSDIOSession.NIHSDIO_VAL_GROUP_BY_CHANNEL
                        grouping = HSDIOSession.NIHSDIO_VAL_GROUP_BY_SAMPLE
                        session.write_waveform_wdt(
                            wave.name,
                            max(wave.transitions),
                            grouping,
                            data
                        )
                    elif format == "uInt32":
                        session.write_waveform_uint32(
                            wave.name,
                            max(wave.transitions),
                            data
                        )
                except HSDIOError as e:
                    m = f"{e}\nError writing waveform. Waveform has not been updated",
                    self.is_initialized = False
                    raise HardwareError(self, session, message=e.message)

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
                try:
                    error_code, _is_done = session.is_done()
                    if not _is_done:
                        done = False
                        break
                except HSDIOError as e:
                    raise HardwareError(self, session, message=e.message)

        return done

    def start(self):
        """
        Start the tasks
        """
        if not (self.stop_connections or self.reset_connection) and self.enable:
            for session in self.sessions:
                try:
                    session.initiate()
                except HSDIOError as e:
                    session.abort()
                    session.close()
                    self.is_initialized = False
                    raise HardwareError(self, session, message=e.message)

    def stop(self):
        """
        Abort the session
        """
        if self.enable:
            for session in self.sessions:
                try:
                    session.abort()
                except HSDIOError as e:
                    raise HardwareError(self, session, e.message)

    def log_settings(self, wf_arr, wf_names):  # TODO : @Juan Implement
        pass
        # the labview code has HSDIO.settings specifically for reading out the
        # settings on the front panel. for debugging, we could just have this
        # log certain HSDIO attributes

        # log stuff, call settings in the server code for debugging?

    def print_txt(self, node):  # for debugging
        self.logger.info(f"{node.tag} = {node.text}")
