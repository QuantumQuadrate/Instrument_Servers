"""
TTL Input class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For parsing XML strings which setup NI-DAQ hardware for reading digital input.
"""

## built-in modules
import xml.etree.ElementTree as ET

## third-party modules
import numpy as np # for arrays
import nidaqmx
from nidaqmx.constants import (Edge, AcquisitionType, Signal, 
    TerminalConfiguration, LineGrouping)
from nidaqmx.errors import DaqError, DaqWarning
from nidaqmx.error_codes import DAQmxErrors, DAQmxWarnings
import logging
import struct

## local class imports
from pxierrors import XMLError, HardwareError
from instrument import Instrument
from tcp import TCP


class TTLInput(Instrument):
    
    def __init__(self, pxi):
        super().__init__(pxi, "TTL")
        self.data_string = ""
        self.task = None
        self.lines = ""

    def load_xml(self, node: ET.Element):
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            node (ET.Element): tag should match self.expectedRoot, that is
            node.tag == self.expectedRoot
        """
        
        self.is_initialized = False
        
        assert (node.tag == self.expectedRoot,
                f"Expected tag <{self.expectedRoot}>, but received <{node.tag}>")
        
        if not (self.exit_measurement or self.stop_connections):

            for child in node:

                if self.exit_measurement or self.stop_connections:
                    break
            
                try:
                    
                    if child.tag == "enable":
                        self.enable = Instrument.str_to_bool(child.text)
                
                    elif child.tag == "lines":
                        self.lines = child.text
                    
                    else:
                        self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
                            
                except ValueError:
                    raise XMLError(self, child)
    
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if not (self.stop_connections or self.exit_measurement) and self.enable:

            # Clear old task
            if self.task is not None:
                try:
                    self.close()
                except DaqError as e:
                    if e.error_code == DAQmxErrors.INVALID_TASK.value:
                        self.logger.warning("Tried to close TTLInput task that probably didn't exist")
                    else:
                        self.logger.exception(e)
               
            try:
                self.task = nidaqmx.Task()
            
                # Create a digital input channel.
                # Number of samples_per channel unspecified, so returns only one 
                #   sample at a time
                # Line grouping is 1 Channel for All Lines, so samples returned by 
                #   task.read will be of type int... should be bool??
                self.task.di_channels.add_di_chan(
                    lines=self.lines,
                    # name_to_assign_to_lines=u'', # this looks like a typo but came from nidaqmx docs...
                    line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                    
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n TTLInput hardware initialization failed'
                raise HardwareError(self, task=self.task, message=msg)

            self.is_initialized = True
    
    def reset_data(self):
        """
        Reset the aqcuired data array to an empty array
        """
        
        # labview initializes an empty binary 2D array. 
        # the array properties in labview give a width,height of something like 38,64 but
        # don't think it's initializing an array of that size-- just stating the default capacity
        # of that data type, because all of the elements are greyed out
        self.data = np.array([]) 

    # TODO: see what kind of data we actually get when this runs
    def check(self,timeout=1):
        """
        Check for data. Waits up to 1 second for data to become available.
        
        Args:
            timeout: seconds to wait for data. 1 by default.
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:
            
            self.start()
            
            try:                
                # number_of_samples_per_channel unset means 1 sample per channel
                # 1 second timeout
                data = self.task.read(timeout=timeout)
                self.logger.debug(f'TTL Data out: {data}')# \n shape: {data.shape}')
                
                # get data out and append it to the extant data array
                # i think this ends up being an array of dimensions (1, samples)
                # so it is technically 2D as each newly acquired datum is a column
                self.data = np.append(self.data, data)
                
                # Stop the task and reset it to the state it was initially
                self.stop()
                           
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n TTLInput data check failed'
                self.is_initialized = False
                raise HardwareError(self, task=self.task, message=msg)
            
    def data_out(self) -> str:
        """
        Convert the received data into a specially-formatted string for CsPy
        
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

                self.data_string = TCP.format_data('TTL/dimensions', shape_str) + \
                    TCP.format_data('TTL/data', data_bytes)
            except Exception as e:
                self.logger.exception(f"Error formatting data from {self.__class__.__name__}")
                raise e

            return self.data_string
            
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
            
    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.exit_measurement) and self.enable:
            self.logger.debug("started TTL task")
            try:
                self.task.start()
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n TTLInput failed to start task'
                raise HardwareError(self, task=self.task, message=msg)
            
    def stop(self):
        """
        Stop the task
        """
        
        if self.task is not None:
            try:          
                self.task.stop()
                self.logger.debug(f"stopped {self.__class__.__name__} task")
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
            try:
                self.task.close()
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                    msg = f'\n Failed to close {self.__class__.__name__} task'
                    self.logger.warning(msg)
                    self.logger.exception(e)