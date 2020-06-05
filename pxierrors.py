"""
Error classes for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Error types intended to organize the different common runtime errors into 
useful categories where specific handling action pertains to each type. 
"""

## built-in modules
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET

## local class imports
from instrument import XMLLoader
from digitalout import *


class PXIError(Exception):
    """
    Base class for categorizing device class-level exceptions
    """

    def __init__(self, message: str, device: XMLLoader):
        """
        Constructor for XMLError. 
        
        Args:
            message: error message
            device: a instance of an object which inherits from XMLLoader
        """
        self._message = message
        super().__init__(self.message)
        self._device = device
        
    @property
    def device(self) -> XMLLoader:
        """
        Reference to an instance of the device class where the error occured
        """
        return self._device
        
    @property
    def message(self) -> str:
        """
        Return additional info about the error that occured
        """
        return self._message
   
   
class XMLError(PXIError):
    """
    Exception pertaining to errors in parsing xml for setting device parameters
    """
    
    def __init__(self, device: XMLLoader, node: ET.Element, message: str=None,):
        """
        Constructor for XMLError. 
        
        Args:
            node: xml node being read or set when the error occurred
            device: a instance of an object which inherits from XMLLoader
            message: error message. if None (default), initialized internally
        """
        self._node = node
        if message is None:
            message = f"{device} encountered error at XML node {self.node.tag}"+\
                f"\n with text {self.node.text}"

        super().__init__(message, device)
        
    @property
    def node(self) -> ET.Element:
        """
        XML node associated with the error
        """
        return self._node
    
    
class HardwareError(PXIError):
    """
    Exception pertaining to failure in reading from or writing to hardware
    """
    
    def __init__(self, device: XMLLoader, task, message: str=None):
        """
        Constructor for HardwareError. 
        
        Args:
            node: xml node being read or set when the error occurred
            task: reference to an instance of an object that controls a hardware process, 
                e.g. an NI-DAQmx task or an HSDIOSession
                # TODO: maybe other info is useful too/instead?
            message: error message. if None (default), initialized internally
            
        """
        self._task = task
        if message is None:
            message = f"{device} encountered error in {self.task}"
                
        super().__init__(message, device)
        
    @property
    def task(self):
        """
        Reference to an instance of the task class where the error occured
        """
        return self._task

    
class TimeoutError(PXIError):
    pass
    
    
## stuff for testing :

if __name__ == '__main__':
    
    do = DAQmxDO(None) # some device instance 
    try: 
        node = ET.Element('wumbo')
        do.load_xml(node)
    except Exception as e:
        xml_err = XMLError(do, node)
        print(xml_err.message)
        raise xml_err