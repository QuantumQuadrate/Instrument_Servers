"""
DAQmxDO class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

## modules
import nidaqmx
from nidaqmx.constants import Edge

## local imports
from trigger import StartTrigger
from waveform import Waveform

class DAQmxDO(Instrument):

    def __init__(self, pxi):
        super().__init__(pxi, "DAQmxDO")
        self.logger = logging.getLogger(str(self.__class__))        
        self.physicalChannels = None
        self.startTrigger = StartTrigger()
        
    
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
            
                elif child.tag == "resourceName":
                    self.physicalChannels = child.text
                
                elif child.tag == "clockRate":
                    self.clockRate = float(child.text) 
                    
                elif child.tag == "startTrigger":
                    node = child
                    for child in node:
                    
                        if node.text = "waitForStartTrigger":
                            self.startTrigger.waitForStartTrigger = str_to_bool(child.text)
                        elif child.text = "source":
                            self.startTrigger.source = child.text
                        elif child.text == "edge":
                            try:
                                # CODO: could make dictionary keys in StartTrigger 
                                # lowercase and then just .lower() the capitalized keys
                                # passed in elsewhere 
                                text = child.text[0].upper() + child.text[1:]
                                self.startTrigger.edge = StartTrigger.nidaqmx_edges[text]
                            except KeyError as e: 
                                self.logger.error(f"Not a valid {child.tag} value {child.text} \n {e}")
                                raise
                        else:
                            self.logger.warning(f"Unrecognized XML tag \'{node.tag}\' in <{child.tag}>")
                            
                
                elif child.tag == "waveform":
                    self.waveform = Waveform()
                    self.waveform.init_from_xml(child)
                    
                else:
                    self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
                    
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if not (self.stop_connections or self.reset_connection):
            pass
            
        
    def load_waveform(wave_node):
        """
        Build waveform from an xml string
        
        Args: 
            'wave_node': the xml node containing the waveform
        """
        
        