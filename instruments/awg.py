"""
AWG class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Represents the Signadyne Arbitrary Waveform Generator card. As much as possible, 
I've used the same variable names, down to the single camel font, as used in the
AWG card manual. See also examples here to better understant the intended work
flow: https://github.com/QuantumQuadrate/AWG
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

class AWGchannel:
    
    modulationFunctionList = ['amplitude','angle']
    modulationTypeDescriptions = {'amplitude': ['Modulation off','Amplitude','Offset'],
                          'angle': ['Modulation off','Frequency','Phase']}
    modulationTypeDict = {'amplitude': ['AOU_MOD_OFF','AOU_MOD_AM','AOU_MOD_OFFSET'],
                          'angle': ['AOU_MOD_OFF','AOU_MOD_FM','AOU_MOD_PM']}
    
    def __init__(self, number: int):
        self.number = number
        self.amplitude = 0
        self.frequency = 0
        self.waveformQueue = []
        self.waveshape = ''
        self.modulationFunction = 0
        self.modulationType = 0
        self.deviationGain = 0
        self.trigger = ExternalTrigger()
        
        
class ExternalTrigger:

    def __init__(self, triggerBehavior=0, externalSource=0):
        self.triggerBehavior = triggerBehavior
        self.externalSource = externalSource


class AWG(Instrument):

    Waveform = rc('Waveform',['mod_type','tau','pts','sigma','arr','prescl','delay','trig_type','SDwave'])
    # maybe also have external trigger
    
    def __init__(self, pxi):
        super().__init__(pxi, "AWG")
        
        self.channels = [AWGchannel(i) for i in range(4)]

    def load_xml(self, node: ET.Element):
        """
        Initialize AnalogOutput instance attributes with xml from CsPy

        Args:
            'node': type is ET.Element. tag should be "AWG"
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

                    if child.tag == 'slot':
                        self.slot = int(child.text)
                        
                    if child.tag == 'clockFrequency':
                        self.clockFrequency = float(child.text)
                        
                    if child.tag == 'channels':
                        for chan in child:
                            
                            # todo some error handling here
                            cnum = int(chan.tag[-1]) # get the channel number
                            for attr in chan:
                                
                                if attr.tag == 'waveformQueue':
                                    self.channels[cnum].waveformQueue = child.text
                                
                                if attr.tag == 'waveshape':
                                    self.channels[cnum].waveshape = child.text
                                
                                if attr.tag == 'modulationFunction':
                                    self.channels[cnum].modulationFunction = chan.text
                                    
                                if attr.tag == 'modulationType':
                                    self.channels[cnum].modulationType = int(chan)
                                    
                                if attr.tag == 'deviationGain':
                                    self.channels[cnum].modulationType = int(chan)

                                if attr.tag == 'trigger':
                                    for item in attr:
                                        if item.tag = 'triggerBehavior':
                                            self.channels[cnum].trigger.triggerBehavior = int(item.text)
                                        if item.tag = 'externalSource':
                                            self.channels[cnum].trigger.externalSource = int(item.text)

                                if attr.tag == 'waveformList':
                                    #todo: proper error handling; import numpy functions or build a way
                                    # to add 'np.' to the beginning of functions. sounds tough. 
                                    self.waveformList = eval(attr.tag)                                

                    else:
                        self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <AWG>")

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