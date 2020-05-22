"""
TTL Input class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For parsing XML strings which setup NI DAQ hardware for reading digital input.
"""

#### built-in modules
import xml.etree.ElementTree as ET

#### third-party modules
import numpy as np # for arrays
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, Signal, TerminalConfiguration
import nidaqmx
import logging

#### local class imports
from instrumentfuncs import str_to_bool


class TTLInput(Instrument):
    
    def __init__(self, pxi):
        super().__init__(pxi, "TTL")
        self.logger = logging.getLogger(str(self.__class__))
        self.task = None
        self.lines = ""
        
        
    def load_xml(self, node):
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """
        
        if not (self.stop_connections or self.reset_connection):
        
            assert node.tag == self.expectedRoot

            for child in node: 

                if type(child) == ET.Element:
                
                    if child.tag == "enable":
                        self.enable = str_to_bool(child.text)
                
                    elif child.tag == "lines":
                        self.lines = child.text
                    
                    else:
                        self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
                    
    
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if not (self.stop_connections or self.reset_connection):
            
            if self.enable:
            
                # Clear old task
                if self.task != None:
                    self.task.close()
                    
                self.task = nidaqmx.Task() # might be task.Task()
                
                # Create a digital input channel
                self.task.di_channels.add_di_chan(
                    lines=self.lines
                    name_to_assign_to_lines=u'', 
                    line_grouping=<LineGrouping.CHAN_FOR_ALL_LINES: 1>)                
            
    