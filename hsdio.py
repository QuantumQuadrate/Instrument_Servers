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
import platform # for checking the os bit
import logging
from ni_hsdio import HsdioSession

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

        ## device settings
        self.logger = logging.getLogger(str(self.__class__))
        self.pxi = pxi
        self.resourceNames = np.array([], dtype=str)
        self.clockRate = 2*10**7 # 20 MHz
        self.hardwareAlignmentQuantum = 1 # (in samples)
        self.activeChannels = np.array([], dtype=c_int32)
        self.initialStates = np.array([], dtype=str)
        self.idleStates = np.array([], dtype=str)
        self.pulseGenScript = """script script 1
                                      wait 1
                                   end script"""
        self.scriptTriggers = []
        self.startTrigger = StartTrigger()


        # These two have are related to one another, each session is attached to a handle, each handle can support man
        # sessions. Sessions now have an attribute HsdioSession.handle (a python string)
        self.instrumentHandles = []  # array to hold instrument handles; CAN PROBABLY DELETE; sessions takes care of this
        self.sessions = []  # array to hold HsdioSession objects
        self.waveformArr = []

        # whether or not we've actually populated the attributes above
        self.isInitialized = False
        
        
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

                # handle each tag by name:
                if child.tag == "enable":
                    self.enable = str_to_bool(child.text)

                elif child.tag == "description":
                    self.print_txt(child) # DEBUGGING
                    self.description = child.text

                elif child.tag == "resourceName":
                    self.print_txt(child) # DEBUGGING
                    resources = np.array(child.text.split(","))
                    self.resourceNames = resources

                elif child.tag == "clockRate":
                    clockRate = float(child.text)
                    self.print_txt(child) # DEBUGGING
                    self.clockRate = clockRate

                elif child.tag == "hardwareAlignmentQuantum":
                    self.print_txt(child) # DEBUGGING
                    self.hardwareAlignmentQuantum = child.text

                elif child.tag == "triggers":
                    self.print_txt(child) # DEBUGGING

                    if type(child) == ET.Element:

                        trigger_node = child

                        # for each line of script triggers
                        for child in trigger_node:

                            if type(child) == ET.Element:

                                trig = Trigger()
                                trig.init_from_xml(child)
                                self.scriptTriggers.append(trig)

                elif child.tag == "waveforms":

                    self.logger.info("found a waveform")
                    
                    wvforms_node = child

                    # for each waveform
                    for wvf_child in wvforms_node:

                        if type(wvf_child) == ET.Element:

                            if wvf_child.tag == "waveform":

                                wvform = HSDIOWaveform()
                                wvform.init_from_xml(wvf_child)
                                self.waveformArr.append(wvform)

                elif child.tag == "script":
                    self.pulseGenScript

                elif child.tag == "startTrigger":
                    self.startTrigger = StartTrigger()
                    self.startTrigger.init_from_xml(child)

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

                for session in self.sessions: #
                    session.abort()
                    session.close()
                    pass

                    # i think this should clear the list of instrumentHandles too.
                    # in LabView the handle gets passed in/out of the above VIs.
                    # maybe just reset the array after the loop:
                    # Its worth considering how these handles are being populated - Juan

                self.sessions = []  # reset

            if self.enable:

                iterables = zip(self.idleStates, self.initialStates,
                                self.activeChannels, self.resourceNames)
                for idle_state,init_state,chan_list,resource in iterables:
                    self.sessions.append(HsdioSession(resource))
                    session = self.sessions[-1]

                    session.init_generation_sess()

                    session.assign_dynamic_channels(chan_list)

                    session.configure_sample_clock(self.clockRate)

                    session.configure_generation_mode(generation_mode=15)

                    session.configure_initial_state(chan_list, init_state)

                    session.configure_idle_state(chan_list,idle_state)

                    for trig in self.scriptTriggers:

                        # implement this in a better way so not hardcoding the numeric code
                        if trig.type == trig.types["Level"]:  # Level type

                            session.configure_digital_level_script_trigger(
                                trig.trigID,  # str
                                trig.source,  # str
                                trig.level    # int
                            )

                        else:  # Edge type is default when initialized

                            session.configure_digital_edge_script_trigger(
                                trig.trigID,
                                trig.source,
                                trig.edge
                            )

                    if self.startTrigger.waitForStartTrigger:
                        session.configure_digital_edge_start_trigger(
                            self.startTrigger.source,
                            self.startTrigger.edge
                        )

            self.isInitialized = True


    def update(self):
        """
        write waveforms to the PC memory
        """
        
        if not (self.stop_connections or self.reset_connection):

            if self.enable:

                for wf in self.waveformArr:

                    wv_arr = wf.wave_split()
                    # for each HSDIO card (e.g., Rb experiment has two cards)
                    for i, session in enumerate(self.sessions):

                        wave = wv_arr[i]
                        fmt, data = wave.decompress()

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
                            
    
    
    def is_done(self)
        """
        Check if the tasks being run are completed
        
        Return:
            'done': True if tasks completed, connection was stopped or reset, or
                self.enable is False. False otherwise.
        """
        
        done = True
        if not (self.stop_connections or self.reset_connection) and self.enable:
            
            for session is self.sessions:
                pass
                # TODO: @Juan implement niHSDIO Is Done VI
                #
                # if not session.is_done():
                    # done = False
                    # break
        
        return done
            
            


    def settings(self, wf_arr, wf_names):
        pass
        # the labview code has HSDIO.settings specifically for reading out the
        # settings on the front panel. for debugging, we could just have this
        # log certain HSDIO attributes

        # log stuff, call settings in the server code for debugging?

    def print_txt(self, node): # for debugging
        self.logger.info(f"{node.tag} = {node.text}")