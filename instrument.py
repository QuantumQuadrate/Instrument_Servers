"""
Instrument abstract base class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Base class from which all instrument classes for the PXI server should inherit.
If you are implementing a new instrument class for your experiment, this code
shows the minimum required methods to be implemented. Where possible, 
generally applicable methods or attributes are implemented here. Specifically,
all methods decorated with "abstractmethod" must be overriden in the class
that inherits from Instrument.

For example usage, go look at implementation in hsdio.py, analogin.py, etc. 
"""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from instrumentfuncs import str_to_bool

class Instrument(ABC):
    
    def __init__(self, pxi, expectedRoot):
        """
        Constructor for the Instrument abstract base class
        
        Args:
            'pxi': reference to the parent PXI instance
            'expectedRoot': the xml tag corresponding to your instrument. This 
            should be in the xml sent by CsPy to talk to setup this device.
        """
        
        self.pxi = pxi
        self.expectedRoot = expectedRoot 
        self.enable = False
    
    @property
    def reset_connection(self) -> bool:
        return self.pxi.reset_connection

    @reset_connection.setter
    def reset_connection(self, value):
        self.pxi.reset_connection = value

    @property
    def stop_connections(self) ->bool:
        return self.pxi.stop_connections

    @stop_connections.setter
    def stop_connections(self, value):
        self.pxi.stop_connections = value
   
    
    @abstractmethod
    def load_xml(self, node)
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """
        
        assert node.tag == self.expectedRoot

        for child in node: 

            if type(child) == ET.Element:
            
                if child.tag == "enable":
                    self.enable = str_to_bool(child.text)
            
                # elif child.tag == "someOtherProperty":
                    # self.thatProperty = child.text
                
                else:
                    self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
                    
    @abstractmethod
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if not (self.stop_connections or self.reset_connection):
            pass
                    
            
    
        
        