"""
AnalogOutput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

"""

import nidaqmx
import numpy as np
import xml.etree.ElementTree as ET


class AnalogOutput:
    
    def __init__(self):

        self.enable = False
        self.physical_channels = ""

    def load_xml(self, node):
        """
        Initialize AnalogOutput instance attributes with xml from CsPy

        Expects node.tag == "AnalogOutput"

        Args:
            'node': type is ET.Element. tag should be "HSDIO"
        """
        
        assert node.tag == "AnalogOutput"

        for child in node: 

            if child.tag == "enable":
                enable = False
                if child.text.lower() == "true":
                    enable = True
                self.enable = enable

            elif child.tag == "physicalChannels":
                self.physical_channels = child.text

            elif child.tag == ""

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 

            #elif child.tag == 
                
            #else:
            #    # TODO: replace with logger
            #    print(f"Unrecognized XML tag {child.tag} in <AnalogOutput>)



    def init(self):
        pass


    def update(self):
        pass
 