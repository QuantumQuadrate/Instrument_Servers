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
    Exception type pertaining to errors in parsing xml
    
    When handling an error in an class which inherits from XMLLoader, 
    use this type to raise an XMLError in except statements dealing
    with XML related exceptions. 
    
    Examples of XML exceptions:
        failure in any of the following (but not limited to):
        - a waveform specified in xml was not formatted as expected
        - an invalid value was supplied for setting a device attribute (e.g. 
        allowed values were 'true' or 'false', but recieved 7 from xml)
    """
    
    def __init__(self, device: XMLLoader, node: ET.Element, message: str=None):
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
                f"\n with text \'{self.node.text}\'"

        super().__init__(message, device)
        
    @property
    def node(self) -> ET.Element:
        """
        XML node associated with the error
        """
        return self._node
    
    
class HardwareError(PXIError):
    """
    Exception type pertaining to failure in reading from or writing to hardware
    
    When handling an error at the device level, e.g. in the HSDIO class, 
    use this type to raise a HardwareError in except statements dealing
    with hardware related exceptions. 
    
    Examples of hardware exceptions:
        failure in any of the following (but not limited to):
        - reading/writing to NI-DAQmx Task
        - anything to do with an HSDIOSession
        - setting up triggers for hardware
    """
    
    def __init__(self, device: XMLLoader, task=None, message: str=None):
        """
        Constructor for HardwareError. 
        
        Args:
            device: class or instance of a type that inherits from 
                XMLLoader
            task: class or instance of an object that controls a hardware process, 
                e.g. an NI-DAQmx task, HSDIOSession, or NIIMAQSession. None by
                default. 
            message: additional error information to be appended to a message
                describing the origin of the error. if None (default), the error
                message is simply f"{device} encountered error in {self.task}".             
        """
        self._task = task
        msg = f"{device} encountered error in {self.task}"
        if message is not None:
            msg += message
                
        super().__init__(msg, device)
        
    @property
    def task(self):
        """
        Reference to an instance of the task class where the error occured
        """
        return self._task

    
class TimeoutError(PXIError):
    """
    """
    
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