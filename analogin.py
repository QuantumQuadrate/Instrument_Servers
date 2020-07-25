"""
AnalogInput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal, TerminalConfiguration
from nidaqmx.errors import DaqError, DaqWarning
from nidaqmx.error_codes import DAQmxErrors, DAQmxWarnings
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
        self.groundMode = ''
        self.sampleRate = 0
        self.samplesPerMeasurement = 0
        self.source = ''
        self.minValue = -10.0
        self.maxValue = 10.0
        self.startTrigger = StartTrigger()
        self.task = None

    def load_xml(self, node: ET.Element):
        """
        Initialize AnalogInput instance attributes with xml from CsPy

        Args:
            'node': type is ET.Element. tag should be "AnalogInput" Expects
            node.tag == "AnalogInput"
        """
        
        self.is_initialized = False
        
        assert node.tag == self.expectedRoot, "expected node" + \
            f" <{self.expectedRoot}> but received <{node.tag}>"

        if not (self.exit_measurement or self.stop_connections):

            for child in node:

                if self.exit_measurement or self.stop_connections:
                    break

                try:
                    if child.tag == "enable":
                        self.enable = Instrument.str_to_bool(child.text)

                    elif child.tag == "sample_rate":
                        self.sampleRate = float(child.text)  # [Hz]

                    elif child.tag == "samples_per_measurement":
                        self.samplesPerMeasurement = Instrument.str_to_int(child.text)
                        self.logger.debug(self.samplesPerMeasurement)

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
                            self.startTrigger.edge = StartTrigger.nidaqmx_edges[child.text.lower()]
                        except KeyError as e:
                            raise KeyError(f"Not a valid {child.tag} value {child.text} \n {e}")

                    else:
                        self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")

                except (KeyError, ValueError):
                    raise XMLError(self, child)
                
    def init(self):
    
        if not (self.stop_connections or self.reset_connection) and self.enable:
                
            # Clear old task
            if self.task is not None:
                try:
                    self.close()
                except DaqError as e:
                    if e.error_code == DAQmxErrors.INVALID_TASK.value:
                        self.logger.warning("Tried to close AI task that probably didn't exist")
                    else:
                        self.logger.exception(e)
            
            # configure the output terminal from an NI Enum
            
            # in the LabVIEW code, no error handling is done when an invalid
            # terminal_config is supplied; the default is used. The xml coming 
            # from Rb's CsPy supplies the channel name for self.source, rather 
            # than a valid key for TerminalConfiguration, hence the default is 
            # value is what gets used. This seems like a bug on the CsPy side,
            # even if the default here is desired.
            try: 
                # this is what is done in LabVIEW but I believe it is an error. 
                # self.source will always refer to physical channel(s), which will
                # never be a key in TerminalConfiguration. 
                inputTerminalConfig = TerminalConfiguration[self.source]
            except KeyError as e:
                self.logger.warning(f"Invalid output terminal setting \'{self.source}\' \n"+
                         "Using default, 'NRSE' , instead")
                inputTerminalConfig = TerminalConfiguration['NRSE']
                
            try:
                self.task = nidaqmx.Task()
                self.task.ai_channels.add_ai_voltage_chan(
                    physical_channel=self.source,
                    min_val=self.minValue,
                    max_val=self.maxValue,
                    terminal_config=inputTerminalConfig)
                
                # Setup timing. Use the onboard clock
                self.task.timing.cfg_samp_clk_timing(
                    rate=self.sampleRate, 
                    active_edge=Edge.RISING, # default
                    sample_mode=AcquisitionType.FINITE, # default
                    samps_per_chan=self.samplesPerMeasurement)
                
                self.logger.debug(f"sampRate = {self.sampleRate} \n"+
                    f"sampsPerMeasurement = {self.samplesPerMeasurement} \n")
                
                # Setup start trigger if configured to wait for one
                if self.startTrigger.wait_for_start_trigger:
                    self.logger.debug("Will wait for digital edge trigger")
                    self.task.triggers.start_trigger.cfg_dig_edge_start_trig(
                        trigger_source=self.startTrigger.source,
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
                
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
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
                # daqmx read 2D DBL N channel N sample. use defaults kwargs. 
                # measurement type inferred from the task virtual channel
                self.data = self.task.read(
                    number_of_samples_per_channel=self.samplesPerMeasurement,
                    timeout=1 # [s]
                )
                
                try:
                    self.logger.debug("aqcuired data:\n"+
                        f"len(data) = {len(self.data)}\n"
                        f"data = {self.data}"
                    )
                except Exception as e:
                    self.logger.info("trouble logging ai data")
                    self.logger.exception(e)
                
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n AnalogInput failed to read data from hardware'
                raise HardwareError(self, task=self.task, message=msg)
            
    # TODO: compare output to what the LabVIEW method returns
    def data_out(self) -> str:
        """
        Convert the received data into a string parsable by CsPy
        
        Returns:
            the instance's data string, formatted for reception by CsPy
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:

            try:
                # flatten the data and convert to a str
                data_shape = np.array(self.data).shape
                flat_data = np.reshape(self.data, np.prod(data_shape)) # nD data --> 1D data

                shape_str = ",".join([str(x) for x in data_shape])

                data_bytes = struct.pack(f'!{len(flat_data)}d', *flat_data)

                self.data_string = (TCP.format_data('AI/dimensions', shape_str) + 
                                    TCP.format_data('AI/data', data_bytes))

            except Exception as e:
                self.logger.exception(f"Error formatting data from {self.__class__.__name__}")
                raise e
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
            msg = ""
            try:
                # be nice and attempt to wait for the measurement to end
                try:
                    while not self.is_done():
                        pass
                except DaqWarning as e:
                    if e.error_code == DAQmxWarnings.STOPPED_BEFORE_DONE.value:
                        pass
                                            
                self.task.stop()
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                    msg = f'\n {self.__class__.__name__} failed to stop current task'
                    self.logger.warning(msg)
                    self.logger.exception(e)

    def close(self):
        """
        Close the task
        """
        
        if self.task is not None:
            self.is_initialized = False
            try:
                self.task.close()
            except DaqError as e:
                msg = '\n AnalogInput failed to close current task'
                self.logger.warning(msg)
                self.logger.exception(e)