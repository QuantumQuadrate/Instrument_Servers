"""
AnalogInput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

# TODO: need to handle what happens if server is stopped or reset;
# maybe call a function in pxi when the connection is stopped or reset, which
# then in turn sets stop/reset attributes in each of the device classes

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal, TerminalConfiguration
import numpy as np
import xml.etree.ElementTree as ET
import csv
import re
from io import StringIO
from recordclass import recordclass as rc

## local imports
from trigger import StartTrigger
from instumentfuncs import *


class AnalogInput:

    def __init__(self):
        """
        Constructor for the AnalogInput class. Not intended for initialization.
        
        Instance attributes are set to default values here which are not 
        necessarily suitable for running measurements with this class. Proper
        initialization should be done through the load_xml method with xml
        from CsPy. 
        """
    
        self.expectedRoot = "AnalogInput"
        self.enable = False
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

        Expects node.tag == "AnalogInput"

        Args:
            'node': type is ET.Element. tag should be "AnalogInput"
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
                        # TODO: replace with logger
                        print(f"Not a valid {child.tag} value {child.text} \n {e}")
                        raise
                
                else:
                        # TODO: replace with logger
                        print(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
            
        
    def init(self):
    
        # TODO: check if start or stop 
    
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
                # TODO replace with logger
                print(f"Invalid output terminal setting \'{self.source}\' \n"+
                         "Using default, 'NRSE' , instead")
                inputTerminalConfig = TerminalConfiguration['NRSE']
                
            self.task = nidaqmx.Task() # can't tell if task.Task() or just Task()
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