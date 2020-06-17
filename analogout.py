"""
AnalogOutput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

# TODO: could use nidaqmx task register_done_event, which can pass out and allow
# error handling if a task ends unexpectedly due to an error

# TODO: there exist DaqResourceWarning warnings that i neither handle nor log, 
# as it seems that the class merely points to a built-in Python ResourceWarning, 
# which is itself abstract. - Preston

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal
from nidaqmx.errors import DaqError
import numpy as np
import xml.etree.ElementTree as ET
import csv
from io import StringIO
import logging
from recordclass import recordclass as rc

## local imports
from instrument import Instrument
from trigger import StartTrigger
from pxierrors import XMLError, HardwareError


class AnalogOutput(Instrument):

    ExportTrigger = rc('ExportTrigger', ('exportStartTrigger', 'outputTerminal'))
    ExternalClock = rc('ExternalClock', ('useExternalClock', 'source', 'maxClockRate'))
    
    def __init__(self, pxi):
        super().__init__(pxi, "AnalogOutput")
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


    def load_xml(self, node):
        """
        Initialize AnalogOutput instance attributes with xml from CsPy

        Args:
            'node': type is ET.Element. tag should be "HSDIO". Expects 
            node.tag == "AnalogOutput"
        """
        
        self.is_initialized = False
        
        assert node.tag == self.expectedRoot, "expected node"+\
            f" <{self.expectedRoot}> but received <{node.tag}>"

        if not (self.exit_measurement or self.stop_connections):

            for child in node:

                if self.exit_measurement or self.stop_connections:
                    break

                try:

                    if child.tag == "enable":
                        self.enable = Instrument.str_to_bool(child.text)

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
                        self.startTrigger.wait_for_start_trigger = Instrument.str_to_bool(child.text)

                    elif child.tag == "exportStartTrigger":
                        self.exportTrigger.exportStartTrigger = Instrument.str_to_bool(child.text)

                    elif child.tag == "triggerSource":
                        self.startTrigger.source = child.text

                    elif child.tag == "exportStartTriggerDestination":
                        self.exportTrigger.outputTerminal = child.text

                    elif child.tag == "triggerEdge":
                        try:
                            self.startTrigger.edge = StartTrigger.nidaqmx_edges[child.text]
                        except KeyError as e:
                            raise KeyError(f"Not a valid {child.tag} value {child.text} \n {e}")

                    elif child.tag == "useExternalClock":
                        self.externalClock.useExternalClock = Instrument.str_to_bool(child.text)

                    elif child.tag == "externalClockSource":
                        self.externalClock.source = child.text

                    elif child.tag == "maxExternalClockRate":
                        self.externalClock.maxClockRate = float(child.text)

                    else:
                        self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <AnalogOutput>")

                except (KeyError, ValueError):
                    raise XMLError(self, child)


    # TODO: test with hardware
    def init(self):
        """
        Create and initialize an nidaqmx Task object
        """
        
        if not (self.stop_connections or self.reset_connection):
        
            if self.enable:

                # Clear old task
                try:
                    if self.task is not None:
                        try:
                            self.task.close()
                            
                        except DaqError:
                            # end the task nicely
                            self.stop()
                            self.close()
                            msg = '\n AnalogOutput failed to close current task'
                            raise HardwareError(self, task=self.task, message=msg)
                        
                try:
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
                        
                    if self.startTrigger.wait_for_start_trigger:
                        self.task.start_trigger.cfg_dig_edge_start_trig(
                            trigger_source=self.startTrigger.source,
                            trigger_edge=self.startTrigger.edge) # default
                                        
                    if self.exportStartTrigger:
                        self.task.export_signals.export_signal(
                            Signal.START_TRIGGER,
                            self.exportTrigger.outputTerminal)
                
                except DaqError:
                    # end the task nicely
                    self.stop()
                    self.close()
                    msg = '\n AnalogOutput hardware initialization failed'
                    raise HardwareError(self, task=self.task, message=msg)

                self.is_initialized = True

    # TODO: test with hardware
    def update(self):
        """
        Update the Analog Output hardware
        """
        
        # TODO: check if stop or reset
        if not (self.stop_connections or self.exit_measurement) and self.enable:
                        
            channels, samples = self.waveforms.shape
            
            try:
                self.task.timing.cfg_samp_clk_timing(
                    rate=self.sampleRate, 
                    active_edge=Edge.RISING, # default
                    sample_mode=AcquisitionType.FINITE, # default
                    samps_per_chan=samples)
            
                # Auto-start is false by default when the data passed in contains
                # more than one sample per channel
                self.task.write(self.waveforms)
                
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogOutput hardware update failed'
                raise HardwareError(self, task=self.task, message=msg)

                
    def is_done(self) -> bool:
        """
        Check if the tasks being run are completed
        
        Return:
            'done': True if tasks completed, connection was stopped or reset, or
                self.enable is False. False otherwise.
        """
        
        done = True
        if not (self.stop_connections or self.exit_measurement) and self.enable:
        
            try:
            # check if NI task is dones
                done = self.task.is_task_done()
                
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogOutput check for task completion failed'
                raise HardwareError(self, task=self.task, message=msg)

            
        return done
        

    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:
        
            try:
                self.task.start()
                
            except DaqError
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogOutput failed to start task'
                raise HardwareError(self, task=self.task, message=msg)


    def stop(self):
        """
        Stop the task
        """
        
        if self.enable:
            try:
                self.task.stop()
                        
            except DaqError:
                self.close()
                msg = '\n AnalogOutput failed to stop current task'
                raise HardwareError(self, task=self.task, message=msg)

                
    def close(self):
        """
        Close the task
        """
        
        if self.task is not None:
            try:
                self.task.close()
                
            except DaqError:
                msg = '\n AnalogOutput failed to close current task'
                raise HardwareError(self, task=self.task, message=msg)