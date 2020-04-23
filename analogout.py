"""
AnalogOutput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

# TODO: need to handle what happens if server is stopped or reset;
# maybe call a function in pxi when the connection is stopped or reset, which
# then in turn sets stop/reset attributes in each of the device classes


import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal
import numpy as np
import xml.etree.ElementTree as ET
import csv
from io import StringIO


class AnalogOutput:
    
    def __init__(self):

        self.enable = False
        
        # probably don't need to initialize unused variables here
        #self.physicalChannels = ""
        #self.minValue = 
        #self.maxValue

        self.startTrigger = StartTrigger()
        self.isInitialized = False


    # TODO: good candidate for a unit test
    def wave_from_str(self, wave_str, delim=' '):
        """
        Efficiently build waveform from a string

        Args:
            'wave_str': (str) a (possibly multi-line) string of space-delimited
                float-convertable values. 
            'delim': (str, optional) the value delimiter. ' ' by default
        Returns:
            'wave_arr': (np.ndarray, float) the waveform with one row per line 
                in wave_str, and one column per value in a line
        """

        with StringIO(wstr) as f:
            reader = csv.reader(f, delimiter=delim)
            cols = len(next(reader))
            #print(f"cols={cols}") # DEBUG
            try:
                rows = sum([1 for row in reader]) + 1
            except StopIteration:
                rows = 1
                #print(f"rows={rows}") # DEBUG
            wave_arr = np.empty((rows, cols), float)
    
        with StringIO(wstr) as f:
            reader = csv.reader(f, delimiter=delim)
            for i,row in enumerate(reader):
                #print(row, len(row),'\n') # DEBUG
                wave_arr[i,:] = row
        #print(wave) # DEBUG

        return wave_arr


    def str_to_bool(boolstr):
        """ 
        return True or False case-insensitively for a string 'true' or 'false'

        Args: 
            'boolstr': string to be converted; not case-sensitive
        Return:
            'boolean': True or False. 
        """

        boolstr = boolstr.lower()
        if boolstr == "true":
            return True
        elif boolstr == "false":
            return False
        else:
            print("Expected a string 'true' or 'false' but received {boolstr}")
            raise


    def load_xml(self, node):
        """
        Initialize AnalogOutput instance attributes with xml from CsPy

        Expects node.tag == "AnalogOutput"

        Args:
            'node': type is ET.Element. tag should be "HSDIO"
        """
        
        assert node.tag == "AnalogOutput"

        for child in node: 

            # not sure if this is necessary... could probably remove
            if type(child) == ET.Element:

                if child.tag == "enable":
                    self.enable = str_to_bool(child.text)

                elif child.tag == "physicalChannels":
                    self.physicalChannels = child.text

                elif child.tag == "minimum":
                    self.minValue = float(child.text)

                elif child.tag == "maximum":
                    self.maxValue = float(child.text)

                elif child.tag == "clockRate":
                    self.sampRate = float(child.text) # samples per second in LabVIEW

                elif child.tag == "waveform":
                    self.waveforms = wave_from_str(child.text)

                elif child.tag == "waitForStartTrigger":
                    self.waitForStartTrigger = str_to_bool(child.text)

                elif child.tag == "exportStartTrigger":
                    self.exportStartTrigger = str_to_bool(child.text)

                elif child.tag == "triggerSource":
                    self.startTrigger.source = child.text

                elif child.tag == "exportStartTriggerDestination":
                    self.exportTrigger.outputTerminal = child.text # TODO implement the exportTrigger

                elif child.tag == "triggerEdge": # TODO: make ao_edges the correct form
                    try:
                        self.startTrigger.edge = StartTrigger.nidaqmx_edges[child.text]
                    except KeyError as e:
                        # TODO: replace with logger
                        print(f"Not a valid {child.tag} value {child.text} \n {e}")
                        raise

                # TODO: external clock could be a class as in LabVIEW. TBD.
                elif child.tag == "useExternalClock":
                    self.useExternalClock = str_to_bool(child.text)

                elif child.tag == "externalClockSource":
                    self.externalClockSource = child.text

                elif child.tag == "maxExternalClockRate":
                    self.externalClockRateMax = float(child.text)

                else:
                    # TODO: replace with logger
                    print(f"Unrecognized XML tag {child.tag} in <AnalogOutput>")


    def init(self):
        """
        Create and initialize an nidaqmx Task object
        """
        
        if self.enable:

            # Clear old task
            if self.task != None:
                self.task.close()

            self.task = nidaqmx.Task()
            self.task.ao_channels.add_ao_voltage_chan(
                self.physicalChannels,
                min_val = self.minValue,
                max_val = self.maxValue)
            
            if self.useExternalClock:
                self.task.timing.cfg_samp_clk_timing(
                    rate=self.externalClockRateMax, 
                    source=self.externalClockSource, 
                    active_edge=Edge.RISING, # default
                    sample_mode=AcquisitionType.FINITE, # default
                    samps_per_chan=1000) # default
                
            if self.waitForStartTrigger:
                self.task.start_trigger.cfg_dig_edge_start_trig(
                    trigger_source=self.startTrigger.source,
                    trigger_edge=self.startTrigger.edge) # default
                                
            if self.exportStartTrigger:
                self.task.export_signals.export_signal(
                    Signal.START_TRIGGER,
                    self.exportTrigger.outputTerminal)
                
            self.isInitialized = True


    def update(self):
        """
        Update the Analog Output hardware
        """
        
        if self.enable:
            pass
            
            # TODO: Timing (Sample clock) VI
            channels, samples = self.waveforms.shape
            sample_mode = AcquisitionType.FINITE 
            # args: samples per channel, channels, rate, source, active edge: 12522
            #
        
            # TODO: DAQ Write
 