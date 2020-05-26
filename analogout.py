"""
AnalogOutput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal
import numpy as np
import xml.etree.ElementTree as ET
import csv
from io import StringIO
import logging
from recordclass import recordclass as rc

## local imports
from instrument import Instrument
from trigger import StartTrigger
from instrumentfuncs import *

class AnalogOutput(Instrument):

    ExportTrigger = rc('ExportTrigger', ('exportStartTrigger', 'outputTerminal'))
    ExternalClock = rc('ExternalClock', ('useExternalClock', 'source', 'maxClockRate'))
    
    def __init__(self, pxi):
        super().__init__(pxi=pxi, expectedRoot="AnalogOutput")
        self.logger = logging.getLogger(str(self.__class__))
        self.physicalChannels = ""
        self.minValue = -10
        self.maxValue = 10
        self.sampleRate = 0
        self.waveforms = None
        self.exportTrigger = self.ExportTrigger(False, None)
        self.externalClock = self.ExternalClock(False, '', 0)
        self.startTrigger = StartTrigger()
        self.task = None
        self.isInitialized = False


    def wave_from_str(self, wave_str, delim=' '):
        """
        Efficiently build return waveform as a numpy ndarray from a string

        Args:
            'wave_str': (str) a (possibly multi-line) string of space-delimited
                float-convertable values. 
            'delim': (str, optional) the value delimiter. ' ' by default
        Returns:
            'wave_arr': (np.ndarray, float) the waveform with one row per line 
                in wave_str, and one column per value in a line. The shape for 
                of the output is (samples, channels per sample)
        """

        with StringIO(wave_str) as f:
            reader = csv.reader(f, delimiter=delim)
            cols = len(next(reader))
            try:
                rows = sum([1 for row in reader]) + 1
            except StopIteration:
                rows = 1
            wave_arr = np.empty((rows, cols), float)
    
        with StringIO(wave_str) as f:
            reader = csv.reader(f, delimiter=delim)
            for i,row in enumerate(reader):
                wave_arr[i,:] = row

        return wave_arr

    def load_xml(self, node: ET.Element):
        """
        Initialize AnalogOutput instance attributes with xml from CsPy

        Args:
            'node': Node of xml ElementTree containing information about AnalogOutput parameters

        Raises:
            AssertionError:
                If the provided node does not have the expected tag of "AnalogOutput"
            KeyError:
                If an invalid trigger-edge value is provided
        """
        
        assert node.tag == self.expectedRoot, f"Expected xml tag {self.expectedRoot}"

        for child in node:
            if child.tag == "enable":
                self.enable = str_to_bool(child.text)

            elif child.tag == "physicalChannels":
                self.physicalChannels = child.text

            elif child.tag == "minimum":
                self.minValue = float(child.text)

            elif child.tag == "maximum":
                self.maxValue = float(child.text)

            elif child.tag == "clockRate":
                self.sampleRate = float(child.text) # samples per second in LabVIEW

            elif child.tag == "waveform":
                self.waveforms = self.wave_from_str(child.text)

            elif child.tag == "waitForStartTrigger":
                self.startTrigger.waitForStartTrigger = str_to_bool(child.text)

            elif child.tag == "exportStartTrigger":
                self.exportTrigger.exportStartTrigger = str_to_bool(child.text)

            elif child.tag == "triggerSource":
                self.startTrigger.source = child.text

            elif child.tag == "exportStartTriggerDestination":
                self.exportTrigger.outputTerminal = child.text

            elif child.tag == "triggerEdge":
                try:
                    self.startTrigger.edge = StartTrigger.nidaqmx_edges[child.text]
                except KeyError:
                    raise KeyError(f"Not a valid trigger edge value: {child.text}")

            elif child.tag == "useExternalClock":
                self.externalClock.useExternalClock = str_to_bool(child.text)

            elif child.tag == "externalClockSource":
                self.externalClock.source = child.text

            elif child.tag == "maxExternalClockRate":
                self.externalClock.maxClockRate = float(child.text)

            else:
                self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <AnalogOutput>")



    # TODO: test with hardware
    def init(self):
        """
        Create and initialize an nidaqmx Task object
        """
        
        if not (self.stop_connections or self.reset_connection):
        
            if self.enable:

                # Clear old task
                if self.task != None:
                    self.task.close()

                self.task = nidaqmx.Task() # might be task.Task()
                self.task.ao_channels.add_ao_voltage_chan(
                    self.physicalChannels,
                    min_val = self.minValue,
                    max_val = self.maxValue)
                
                if self.externalClock.useExternalClock:
                    self.task.timing.cfg_samp_clk_timing(
                        rate=self.externalClock.maxClockRate, 
                        source=self.externalClock.source, 
                        active_edge=Edge.RISING, # default
                        sample_mode=AcquisitionType.FINITE, # default
                        samps_per_chan=1000) # default
                    
                if self.startTrigger.waitForStartTrigger:
                    self.task.start_trigger.cfg_dig_edge_start_trig(
                        trigger_source=self.startTrigger.source,
                        trigger_edge=self.startTrigger.edge) # default
                                    
                if self.exportStartTrigger:
                    self.task.export_signals.export_signal(
                        Signal.START_TRIGGER,
                        self.exportTrigger.outputTerminal)
                    
                self.isInitialized = True


    # TODO: test with hardware
    def update(self):
        """
        Update the Analog Output hardware
        """
        
        # TODO: check if stop or reset
        if not (self.stop_connections or self.reset_connection):
        
            if self.enable:
                pass
                
                channels, samples = self.waveforms.shape
                sample_mode = AcquisitionType.FINITE 
                self.task.timing.cfg_samp_clk_timing(
                        rate=self.sampleRate, 
                        active_edge=Edge.RISING, # default
                        sample_mode=AcquisitionType.FINITE, # default
                        samps_per_chan=samples)
            
                # Auto-start is false by default when the data passed in contains
                # more than one sample per channel
                self.task.write(self.waveforms)
            
            