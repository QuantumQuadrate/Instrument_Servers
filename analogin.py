"""
AnalogInput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

## modules 
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal
import numpy as np
import xml.etree.ElementTree as ET
import csv
from io import StringIO
from recordclass import recordclass as rc

## local imports
from trigger import StartTrigger


# TODO: there are a number of functions such as this which exist solely to 
# immitate LabVIEW VIs. Could put all of these in a dedicated module. 
def int_from_str(numstr): 
    """ 
    Returns a signed integer ancored to beginning of a string
    
    behaves like LabVIEW Number from String VI (with the VI defaults
    
    Args:
        'numstr': a string which may contain a signed number at the beginning
    
    Returns:
        'num': (int) a signed integer, if found
    
        Example input/output pairs:
        
            Input     | Output
            -----------------
            '-4.50A'  | -4.5
            '31415q' | 31415
            'ph7cy'   | None, throws ValueError
    """
    try:
        return int(re.findall("^-?\d+", numstr)[0])
    except ValueError as e:
        # TODO: replace with logger
        print(f'String {numstr} is non-numeric. \n {e}')
        raise
        


class AnalogInput:

    def __init__(self):
    
        self.expectedRoot = "AnalogOutput"
        self.enable = False
        self.minValue = -10.0
        self.maxValue = 10.0
        self.startTrigger = StartTrigger()
       
    def str_to_bool(self, boolstr):
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

        Expects node.tag == "AnalogInput"

        Args:
            'node': type is ET.Element. tag should be "HSDIO"
        """
        
        assert node.tag == self.expectedRoot

        for child in node: 

            # not sure if this is necessary... could probably remove
            if type(child) == ET.Element:
            
                if child.tag == "enable":
                    self.enable = self.str_to_bool(child.text)
            
                elif child.tag == "sample_rate":
                    self.sampleRate = float(child.text)
                
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
                
                elif child.tag == "triggerEdge": # TODO: make ao_edges the correct form
                    try:
                        # TODO: could make dictionary keys in StartTrigger 
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
    
        if self.enable: 
        
            # Clear old task
            if self.task != None:
                self.task.close()
                
            self.task = nidaqmx.Task() # can't tell if task.Task() or just Task()
            self.task.ai_channels.add_ai_voltage_chan(
                self.physicalChannels,
                min_val = self.minValue,
                max_val = self.maxValue
                ) # TODO: add output terminal config = ( self.source to NI Enum)
            
            
            
    
    
        