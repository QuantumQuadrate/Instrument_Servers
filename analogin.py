"""
AnalogInput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

# TODO: handle errors where nidaqmx functions are called?

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal, TerminalConfiguration
import numpy as np
import xml.etree.ElementTree as ET
import csv
import re
from io import StringIO
import logging
from recordclass import recordclass as rc

## local imports
from instrument import Instrument
from trigger import StartTrigger
from instrumentfuncs import *


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
        
        assert node.tag == self.expectedRoot

        for child in node: 

            # not sure if this is necessary... could probably remove
            if type(child) == ET.Element:
            
                if child.tag == "enable":
                    self.enable = str_to_bool(child.text)
            
                elif child.tag == "sample_rate":
                    self.sampleRate = float(child.text) # [Hz]
                
                elif child.tag == "samples_per_measurement":
                    self.samplesPerMeasurement = int_from_str(child.text)
                    
                elif child.tag == "source":
                    self.source = child.text
                    
                elif child.tag == "waitForStartTrigger":
                    self.startTrigger.waitForStartTrigger = str_to_bool(child.text)
                    
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
                        self.logger.error(f"Not a valid {child.tag} value {child.text} \n {e}")
                        raise
                
                else:
                    self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")

        
    def init(self):
    
        if not (self.stop_connections or self.reset_connection):
    
            if self.enable: 
            
                # Clear old task
                if self.task != None:
                    self.task.close()
                
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
                if self.startTrigger.waitForStartTrigger:
                    self.start_trigger.cfg_dig_edge_start_trig(
                        trigger_source = self.startTrigger.source,
                        trigger_edge=self.startTrigger.edge)
                        
                        
    def is_done(self) -> bool:
        """
        Check if the tasks being run are completed
        
        Return:
            'done': True if tasks completed, connection was stopped or reset, or
                self.enable is False. False otherwise.
        """
        
        done = True
        if not (self.stop_connections or self.reset_connection) and self.enable:
        
            # check if NI task is dones
            done = self.task.is_task_done()
            
        return done
        

     # TODO: call in PXI.start_tasks  
    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.reset_connection) and self.enable:
            self.task.start()
            
            
    def stop(self):
        """
        Stop the task
        """
        
        if self.enable:
            self.task.stop()
            
            
    def get_data(self):
        """
        Call nidaqmx.Task.read function to fill self.data. 
        
        self.data will be of a 2D array of floats, with dimensions based on the
        sample/channel arguments passed to Task.ai_channels.add_ai_voltage_chan
        """
        
        if not (self.stop_connections or self.reset_connection) and self.enable:
        
            # dadmx read 2D DBL N channel N sample. use defaults args. 
            # measurement type inferred from the task virtual channel
            self.data = self.task.read()