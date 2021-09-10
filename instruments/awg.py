"""
AWG class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Represents the Signadyne Arbitrary Waveform Generator card
"""

# TODO: could use nidaqmx task register_done_event, which can pass out and allow
# error handling if a task ends unexpectedly due to an error

## modules 
import numpy as np
import xml.etree.ElementTree as ET
import csv
import logging
from recordclass import recordclass as rc
import sys, os

## local imports
from instruments.instrument import Instrument
from pxierrors import XMLError, HardwareError

# so we can find the Signadyne module, which is not pip installable
sys.path.insert(0,'C:/Program Files/Signadyne/Libraries/Python')
import signadyne as sd


class AWG(Instrument):

    Waveform = rc('Waveform',['mod_type','tau','pts','sigma','arr','prescl','delay','trig_type','SDwave'])
    # maybe also have external trigger
    
    def __init__(self, pxi):
        super().__init__(pxi, "AWG")
        

    def load_xml(self, node: ET.Element):
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
                            self.startTrigger.edge = StartTrigger.nidaqmx_edges[child.text.lower()]
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

    def init(self):
        """
        Create and initialize an nidaqmx Task object
        """
        
        if not (self.stop_connections or self.reset_connection):
        
            if self.enable:

                # Clear old task
                # if self.task is not None:
                    # try:
                        # self.close()
                    # except DaqError as e:
                        # if e.error_code == DAQmxErrors.INVALID_TASK.value:
                            # self.logger.warning("Tried to close AO task that probably didn't exist")
                        # else:
                            # self.logger.exception(e)
                        
                # try:
                    # self.task = nidaqmx.Task()
                    # self.task.ao_channels.add_ao_voltage_chan(
                        # self.physicalChannels,
                        # min_val=self.minValue,
                        # max_val=self.maxValue)
                    
                    # if self.externalClock.useExternalClock:
                        # self.task.timing.cfg_samp_clk_timing(
                            # rate=self.externalClock.maxClockRate, 
                            # source=self.externalClock.source, 
                            # active_edge=Edge.RISING, # default
                            # sample_mode=AcquisitionType.FINITE, # default
                            # samps_per_chan=1000) # default
                        
                    # if self.startTrigger.wait_for_start_trigger:
                        # self.task.triggers.start_trigger.cfg_dig_edge_start_trig(
                            # trigger_source=self.startTrigger.source,
                            # trigger_edge=self.startTrigger.edge) # default
                                        
                    # if self.exportTrigger.exportStartTrigger:
                        # self.task.export_signals.export_signal(
                            # Signal.START_TRIGGER,
                            # self.exportTrigger.outputTerminal)
                
                self.logger.info("AWG card-level setup completed")
                    
                # except HardwareError:
                    # end the task nicely
                    # self.stop()
                    # self.close()
                    # msg = '\n AnalogOutput hardware initialization failed'
                    # raise HardwareError(self, task=self.task, message=msg)

                self.is_initialized = True

    def update(self):
        """
        Update the Analog Output hardware
        """
        
        # if not (self.stop_connections or self.exit_measurement) and self.enable:
                        
            # channels, samples = self.waveforms.shape
            
            # try:
                # self.task.timing.cfg_samp_clk_timing(
                    # rate=self.sampleRate, 
                    # active_edge=Edge.RISING, # default
                    # sample_mode=AcquisitionType.FINITE, # default
                    # samps_per_chan=samples)
            
                # Auto-start is false by default when the data passed in contains
                # more than one sample per channel
                # self.task.write(self.waveforms)
                
                # self.logger.info("AO Waveform written")
                
            # except DaqError:
                # end the task nicely
                # self.stop()
                # self.close()
                # msg = '\n AnalogOutput hardware update failed'
                # raise HardwareError(self, task=self.task, message=msg)
                
        pass

    
    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:
        
            try:
                self.task.start()

            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogOutput failed to start task'
                raise HardwareError(self, task=self.task, message=msg)

    def stop(self):
        """
        Stop the task
        """
        if self.task is not None:
            try:
                self.task.stop()
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                    msg = f'\n {self.__class__.__name__} failed to stop current task'
                    self.logger.warning(msg)
                    self.logger.exception(e)
            except DaqWarning as e:
                if e.error_code == DAQmxWarnings.STOPPED_BEFORE_DONE.value:
                    pass

    def close(self):
        """
        Close the task
        """
        if self.task is not None:
            self.is_initialized = False
            try:
                self.task.close()
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                    msg = '\n AnalogOutput failed to close current task'
                    self.logger.warning(msg)
                    self.logger.exception(e)