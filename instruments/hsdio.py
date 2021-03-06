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
import platform  # for checking the os bit
from math import floor
from typing import List

## local class imports
from instruments.ni_hsdio import HSDIOSession
from trigger import Trigger, StartTrigger
from waveform import HSDIOWaveform
from instruments.instrument import Instrument
from pxierrors import XMLError, HSDIOError, HardwareError


class HSDIO(Instrument):

    if platform.machine().endswith("64"):
        programsDir32 = "Program Files (x86)"
    else:
        programsDir32 = "Program Files"

    dllpath32 = os.path.join(f"C:\{programsDir32}\IVI Foundation\IVI\Bin", "niHSDIO.dll")
    dllpath64 = os.path.join("C:\Program Files\IVI Foundation\IVI\Bin", "niHSDIO_64.dll")

    HSDIO_ERR_BSESSION = -1074130544  # Invalid session code

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

        self.de_initialize()

        super().load_xml(node)

        if not (self.exit_measurement or self.stop_connections):

            for child in node:

                if self.exit_measurement or self.stop_connections:
                    break
        
                try:

                    # self.logger.debug(child)
                    # handle each tag by name:
                    if child.tag == "enable":
                        self.enable = Instrument.str_to_bool(child.text)

                    elif child.tag == "description":
                        self.description = child.text

                    elif child.tag == "resourceName":
                        resources = np.array(child.text.split(","))
                        self.resourceNames = resources

                    elif child.tag == "clockRate":
                        self.logger.debug(f"XML clockRate = {child.text}")
                        self.clockRate = float(child.text)

                    elif child.tag == "hardwareAlignmentQuantum":
                        try:
                            self.hardwareAlignmentQuantum = floor(float(child.text))
                        except ValueError as e:
                            raise e

                    elif child.tag == "triggers":

                        trigger_node = child
                        for t_child in trigger_node:
                            self.scriptTriggers.append(Trigger(t_child))

                    elif child.tag == "waveforms":
                        # self.logger.debug("found a waveform")
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

        if self.stop_connections or self.exit_measurement:
            return

        if not self.enable:
            return

        self.de_initialize()

        iterables = zip(self.idleStates, self.initialStates,
                        self.activeChannels, self.resourceNames)
        for idle_state, init_state, chan_list, resource in iterables:
            self.sessions.append(HSDIOSession(resource))
            session = self.sessions[-1]

            try:
                self.logger.debug(f"resource: {resource} \n chan_list: {chan_list} \n idle_state: {idle_state} \n init_state: {init_state}")
                session.init_generation_sess()
                # TODO : deal with error case where session is not initiated
                session.assign_dynamic_channels(chan_list)
                self.logger.debug(f"ClockRate = {self.clockRate}")
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
                self.stop()
                self.close()

                if isinstance(e, HSDIOError):
                    raise HardwareError(self, session, message=e.message)
                else:
                    raise e
                    
        self.logger.info(f"{len(self.sessions)} HSDIO card(s) initiated")
        self.is_initialized = True

    def update(self):
        """
        write waveforms to the HSDIO on-board storage
        """

        self.wvf_written = False

        if self.stop_connections or self.exit_measurement:
            return

        if not self.enable:
            return
            
        self.logger.info("Updating HSDIO...")

        self.write_waveforms()

        self.logger.info(f"Waveforms written")

        # write the script
        for session in self.sessions:
            session.write_script(self.pulseGenScript)

    def is_done(self) -> bool:
        """
        Check if the tasks being run are completed

        Return:
            'done': True if tasks completed, connection was stopped or reset, or
                self.enable is False. False otherwise.
        """

        done = True
        if not (self.stop_connections or self.exit_measurement) and self.enable:

            for session in self.sessions:
                try:
                    error_code, _is_done = session.is_done()
                    if not _is_done:
                        done = False
                        break
                except HSDIOError as e:
                    raise HardwareError(self, session, message=e.message)

        return done

    def de_initialize(self):

        if self.is_initialized:
            self.logger.info("stopping initialized sessions")
            self.stop()
            self.remove_waveforms()
            self.close()

            self.sessions = []  # reset
        self.is_initialized = False

    def start(self):
        """
        Start the tasks
        """

        if not (self.stop_connections or self.exit_measurement) and self.enable:
            if self.enable:
                for session in self.sessions:
                    try:
                        session.initiate()
                    except HSDIOError as e:
                        self.logger.debug(f"Unable to initiate session {session}.")
                        # self.stop()
                        self.is_initialized = False
                        raise HardwareError(self, session, message=e.message)

    def stop(self):
        """
        Abort the session
        """
        for session in self.sessions:
            try:
                session.abort()
                self.logger.debug("Aborted an HSDIO session")
            except HSDIOError as e:
                if e.error_code == HSDIO.HSDIO_ERR_BSESSION:
                    self.logger.warning(
                        f"Tried to abort {session}, but it does not exist"
                    )
                else:
                    raise HardwareError(self, session, message=e.message)

    def close(self):
        """
        Close the session
        """
        self.is_initialized = False
        for session in self.sessions:
            try:
                session.close(check_error=True)
                self.logger.debug("Closed an HSDIO session")
            except HSDIOError as e:
                if e.error_code == HSDIO.HSDIO_ERR_BSESSION:
                    self.logger.warning(
                        f"Tried to close {session}, but it does not exist"
                    )
                else:
                    raise HardwareError(self, session, message=e.message)
                    
    def log_settings(self, wf_arr, wf_names):  # TODO : @Juan Implement
        pass
        # the labview code has HSDIO.settings specifically for reading out the
        # settings on the front panel. for debugging, we could just have this
        # log certain HSDIO attributes

        # log stuff, call settings in the server code for debugging?

    def print_txt(self, node):  # for debugging
        self.logger.info(f"{node.tag} = {node.text}")

    def write_waveforms(self):
        """
        Writes our defined waveforms to hardware.
        """
        for wf in self.waveformArr:

            # self.logger.debug(f"wf pre-split : {wf}")
            wv_arr = wf.wave_split(flip=False)
            # for each HSDIO card (e.g., Rb experiment has two cards)
            for session, wave in zip(self.sessions, wv_arr):

                # self.logger.debug(f"post-split : {wave}")
                wave_format, data = wave.decompress()

                # self.logger.debug(f"format of waveform is {wave_format}")
                try:

                    if wave_format == "WDT":
                        # grouping = HSDIOSession.NIHSDIO_VAL_GROUP_BY_CHANNEL
                        grouping = HSDIOSession.NIHSDIO_VAL_GROUP_BY_SAMPLE

                        # self.logger.debug(f"{wave}")

                        session.write_waveform_wdt(
                            wave.name,
                            len(wave),
                            grouping,
                            data
                        )
                    elif wave_format == "uInt32":
                        session.write_waveform_uint32(
                            wave.name,
                            len(wave),
                            data
                        )
                except HSDIOError as e:
                    m = f"{e}\nError writing waveform. Waveform has not been updated",
                    self.is_initialized = False
                    raise HardwareError(self, session, message=e.message)

        self.wvf_written = True

    def remove_waveforms(self):
        """
        Removes our written waveforms from the hsdio devices
        """
        for wave_name in [wf.name for wf in self.waveformArr]:
            for session in self.sessions:
                session.delete_named_waveform(wave_name)

        self.waveformArr = []