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
    
        if not (self.stop_connections or self.reset_connection) and self.enable:
                        
            # Clear old task
            if self.task != None:
                self.task.close()
                
            self.task = nidaqmx.Task() # might be task.Task()
            
            # Create a digital input channel
            self.task.di_channels.add_di_chan(
                lines=self.lines
                name_to_assign_to_lines=u'', 
                line_grouping=<LineGrouping.CHAN_FOR_ALL_LINES: 1>)                
            
    
    def reset_data(self):
        """
        Reset the aqcuired data array
        
        TODO: properly initialize the data. It is not straightforward to see what the format of 
            returned data from task.read is. Based on labview code for both the ttl reset method
            and the ttl system check method, I would guess it goes something like this:
                self.data = np.zeros((39,68)) # init in ttl reset data
                                
                labview says: data input is 2D and height=39,width=68 (when i change the constant to a control)
                
                and the read function is set to read only 1 channel, 1 sample, so presumably it outputs
                a single value. the array out seems to still be 2D. or maybe it's actually 3D and looks like
                
                data = [[0], [0], [0]] where the first two columns are the initialization, and the height/width 
                    were only because I made the data a control, and that was the control default
                
                TODO: try other checks to get an idea of how this is formatted
        """
        
        # TODO: reset data. need to actually create data first
        # something like
        # self.data = np.array([0], [0]) # labview does something like this, with False instead of 0. 
        pass
        

    def check(self):
        """
        I believe this just takes a 1 second data sample. Not clear than 
        anything else happens. 
        
        TODO: need to implement error checking here
        """
        
        if not (self.stop_connections or self.reset_connection) and self.enable:
            
            # TODO: daqmx start task
            self.task.start()
            
            # number_of_samples_per_channel unset means 1 sample per channel
            # 1 second timeout
            self.task.read(timeout=1)
            
            # TODO: get data out and append it to the extant data array
            # labview comment: low is good, bad is high
            # careful with the dimensions here. see comment is reset_data docstring above
            # something like this self.data = np.append(self.data, data)
            
            # Stop the task and reset it to the state it was initiially
            self.task.stop()