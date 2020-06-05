"""
Error classes for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Error types intended to organize the different common runtime errors into 
useful categories where specific handling action pertains to each type. 
"""

from abc import ABC, abstractmethod 

class PXIError(ABC, Error):
    """
    Abstract base class for PXI Error types
    """
    
    def __init__(self, error):
        """
        Constructor for TimeoutError. 
        
        Args:
            error: an Error object or object that inherits from Error, having 
                a message attribute, and optionally an error code
        """
        super().__init__() #TODO: see if this requires pos. args
        
    @abstractmethod
    def send_err_msg(self):
        """
        Return an error message to CsPy over the TCP connection
        """
        pass
        
    @abstractmethod
    def handle_err(self):
        """
        Do cleanup or state change for specific for this type of error
        """
        pass
        
        
class TimeoutError(PXIError):
    pass
    
class XMLError(PXIError):
    pass
    
class HardwareError(PXIError):
    pass