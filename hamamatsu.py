"""
Hamamatsu class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

For parsing XML strings which specify the settings for the Hamamatsu C9100-13
camera and initialization of the hardware of said camera. 
"""

from ctypes import * # open to suggestions on making this better with minimal obstruction to workflow
import numpy as np
import xml.etree.ElementTree as ET

class Hamamatsu: '''could inherit from a Camera class if we choose to move 
                    control of other cameras (e.g. Andor) over to this server
                 '''
                   
    def __init__(self):
    
        pass
        
        
    def load_xml(self):
    
        pass
        
    
    def init(self):
    
        pass
    