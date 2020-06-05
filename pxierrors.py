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


class PXIError(Exception, ABC):
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
        super().__init__(message)
        self._device = device
        
    @property
    def device(self):
        """
        Reference to an instance of the device class where the error occured
        """
        return self._device
        
    @abstractmethod
    def more_info(self) -> str:
        """
        Return additional info about the error that occured
        """
        pass
    
class XMLError(PXIError):
    """
    Exception pertaining to errors in parsing xml for setting device parameters
    """
    
    def __init__(self, message: str, node: ET.Element, device: XMLLoader):
        """
        Constructor for XMLError. 
        
        Args:
            message: error message
            node: xml node being read or set when the error occurred
            device: a instance of an object which inherits from XMLLoader
        """
        self._node = node
        super().__init__(message, device)
        
    @property
    def node(self):
        """
        XML node associated with the error
        """
        return self._node
        
    def more_info(self):
        """
        Return additional info about the error that occured
        """
        info = f"{self.device} encountered error at XML node {self.node.tag}"+\
             f"\n with text {self.node.text}"
        return info
    
class HardwareError(PXIError):
    """
    Exception pertaining to failure in reading from or writing to hardware
    """
    
    def __init__(self, message: str, device: XMLLoader, task):
        """
        Constructor for HardwareError. 
        
        Args:
            message: error message
            node: xml node being read or set when the error occurred
            task: reference to an instance of an object that controls a hardware process, 
                e.g. an NI-DAQmx task or an HSDIOSession
                # TODO: maybe other info is useful too/instead?
            
        """
        super().__init__(message, device)
        self._task = task
        self.message += self.more_info()
        
    @property
    def task(self):
        """
        Reference to an instance of the task class where the error occured
        """
        return self._task
        
    def more_info(self):
        """
        Return additional info about the error that occured
        """
        info = f"{self.device} encountered error in task/sesssion {self.task}"+\
             f"\n with text {self.node.text}"
        return info
    
class TimeoutError(PXIError):
    pass
    
    
## stuff for testing :

if __name__ == '__main__':
    
    do = DAQmxDO(None) # some device instance 
    try: 
        node = ET.Element('wumbo', text="it's first grade, SpongeBob")
        do.load_xml(node)
    except Exception as e:
        xml_err = XMLError(e, node, do)
        print(xml_err.more_info())
        raise xml_err