"""
AnalogInput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

# TODO: handle errors where nidaqmx functions are called?

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal, TerminalConfiguration
from nidaqmx.errors import DaqError
import numpy as np
import xml.etree.ElementTree as ET
import struct
import logging

## local imports
from tcp import TCP
from instrument import Instrument
from trigger import StartTrigger
from pxierrors import XMLError, HardwareError


class AnalogInput(Instrument):

    def __init__(self, pxi):
        """
        Constructor for the AnalogInput class. Not intended for initialization.
        
        Instance attributes are set to default values here which are not 
        necessarily suitable for running measurements with this class. Proper
        initialization should be done through the load_xml method with xml
        from CsPy. 
        """
        super().__init__(pxi, "AnalogInput")
        self.logger = logging.getLogger(str(self.__class__))
        self.groundMode = ''
        self.sampleRate = 0
        self.samplesPerMeasurement = 0
        self.source = ''
        self.minValue = -10.0
        self.maxValue = 10.0
        self.startTrigger = StartTrigger()
        self.task = None
        
    
    def load_xml(self, node):
        """
        Initialize AnalogInput instance attributes with xml from CsPy

        Args:
            'node': type is ET.Element. tag should be "AnalogInput" Expects
            node.tag == "AnalogInput"
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

                    elif child.tag == "sample_rate":
                        self.sampleRate = float(child.text) # [Hz]

                    elif child.tag == "samples_per_measurement":
                        self.samplesPerMeasurement = Instrument.int_from_str(child.text)

                    elif child.tag == "source":
                        self.source = child.text

                    elif child.tag == "waitForStartTrigger":
                        self.startTrigger.wait_for_start_trigger = Instrument.str_to_bool(child.text)

                    elif child.tag == "triggerSource":
                        self.startTrigger.source = child.text

                    elif child.tag == "ground_mode":
                        self.groundMode = child.text

                    elif child.tag == "triggerEdge":
                        try:
                            # CODO: could make dictionary keys in StartTrigger
                            # lowercase and then just .lower() the capitalized keys
                            # passed in elsewhere
                            text = child.text[0].upper() + child.text[1:]
                            self.startTrigger.edge = StartTrigger.nidaqmx_edges[text]
                        except KeyError as e:
                            raise KeyError(f"Not a valid {child.tag} value {child.text} \n {e}")

                    else:
                        self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")

                except (KeyError, ValueError):
                    raise XMLError(self, child)
                
        
    def init(self):
    
        if not (self.stop_connections or self.reset_connection) and self.enable:
                
            # Clear old task
            self.close()
            
            # configure the output terminal from an NI Enum
            
            # in the LabVIEW code, no error handling is done when an invalid
            # terminal_config is supplied; the default is used. The xml coming 
            # from Rb's CsPy supplies the channel name for self.source, rather 
            # than a valid key for TerminalConfiguration, hence the default is 
            # value is what gets used. This seems like a bug on the CsPy side,
            # even if the default here is desired.
            try: 
                inputTerminalConfig = TerminalConfiguration[self.source]
            except KeyError as e:
                self.logger.error(f"Invalid output terminal setting \'{self.source}\' \n"+
                         "Using default, 'NRSE' , instead")
                inputTerminalConfig = TerminalConfiguration['NRSE']
                
            try:
                self.task = nidaqmx.Task() # might be task.Task()
                self.task.ai_channels.add_ai_voltage_chan(
                    self.physicalChannels,
                    min_val = self.minValue,
                    max_val = self.maxValue,
                    terminal_config=inputTerminalConfig)
                
                # Setup timing. Use the onboard clock
                self.task.timing.cfg_samp_clk_timing(
                    rate=self.sampleRate, 
                    active_edge=Edge.RISING, # default
                    sample_mode=AcquisitionType.FINITE, # default
                    samps_per_chan=samplesPerMeasurement) 
                
                # Setup start trigger if configured to wait for one
                if self.startTrigger.wait_for_start_trigger:
                    self.start_trigger.cfg_dig_edge_start_trig(
                        trigger_source = self.startTrigger.source,
                        trigger_edge=self.startTrigger.edge)
            
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogInput task initialization failed'
                raise HardwareError(self, task=self.task, message=msg)

            self.is_initialized = True
                        
                        
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
                # check if NI task is done
                done = self.task.is_task_done()
                
            except DaqError:               
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogInput check for task completion failed'
                raise HardwareError(self, task=self.task, message=msg)

        return done
            
            
    def get_data(self):
        """
        Call nidaqmx.Task.read function to fill self.data. 
        
        self.data will be of a 2D array of floats, with dimensions based on the
        sample/channel arguments passed to Task.ai_channels.add_ai_voltage_chan
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:
        
            try: 
                # dadmx read 2D DBL N channel N sample. use defaults args. 
                # measurement type inferred from the task virtual channel
                self.data = self.task.read()
                
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogInput failed to read data from hardware'
                raise HardwareError(self, task=self.task, message=msg)
            
            
    # TODO: compare output to what the LabVIEW method returns
    def data_out(self) -> str:
        """
        Convert the received data into a specially-formatted string for CsPy
        
        Returns:
            the instance's data string, formatted for reception by CsPy
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:
        
            # flatten the data and convert to a str 
            data_shape = self.data.shape
            flat_data = np.reshape(self.data, np.prod(data_shape))
            
            shape_str = ",".join([str(x) for x in data_shape])
            
            # flatten data to string of bytes. supposed to mimic LabVIEW's Flatten to String VI, 
            # which is inappropriately named. according to the inconsistent docs it either outputs
            # UTF-8 JSON or binary. this returns bytes and may therefore be wrong. 
            data_bytes = struct.pack('!L', "".join([str(x) for x in flat_data]))
                        
            self.data_string = TCP.format_data('AI/dimensions', shape_str) + \
                TCP.format_data('AI/data', data_bytes)
                
            return self.data_string
            
            
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
                msg = '\n AnalogInput failed to start task'
                raise HardwareError(self, task=self.task, message=msg)


    def stop(self):
        """
        Stop the task
        """
        
        if self.task is not None:
            try:
                self.task.stop()
                
            except DaqError:
                self.close()
                msg = '\n AnalogInput failed to stop current task'
                raise HardwareError(self, task=self.task, message=msg)

                
    def close(self):
        """
        Close the task
        """
        
        if self.task is not None:
            try:
                self.task.close()
                
            except DaqError:
                msg = '\n AnalogInput failed to close current task'
                raise HardwareError(self, task=self.task, message=msg)