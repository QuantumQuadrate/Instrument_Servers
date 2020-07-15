"""
Trigger class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

from ctypes import c_uint32
import xml.etree.ElementTree as ET
from nidaqmx.constants import Edge
from instrument import XMLLoader, Instrument
from pxierrors import XMLError


class Trigger(XMLLoader):
    """ Trigger data type for PXI server """
    EDGES = {"rising edge": 12,
             "falling edge": 13,
             "default": "rising edge"}

    TYPES = {"edge": 0,
             "level": 1,
             "default": "edge"}

    LEVELS = {"high level": 34,
              "low level": 35,
              "default": "high level"}
    
    def __init__(self, node: ET.Element = None):
        self.source = ""
        self.trig_ID = ""
        self.trig_type = self.TYPES[self.TYPES["default"]]
        self.edge = self.EDGES[self.EDGES["default"]]
        self.level = self.LEVELS[self.LEVELS["default"]]

        super().__init__(node)

    def load_xml(self, node: ET.Element):
        """
        re-initialize attributes for existing Trigger from children of node. 
        'node' is of type xml.etree.ElementTree.Element, with tag="trigger"
        """
        for child in node:
        
            try:

                if child.tag == "id":
                    self.trig_ID = child.text  # script trigger 0

                elif child.tag == "source":
                    self.source = child.text  # PFI 0

                elif child.tag == "type":
                    self.set_by_dict("trig_type", child.text, self.TYPES)

                elif child.tag == "edge":
                    self.set_by_dict("edge", child.text, self.EDGES)

                elif child.tag == "level":
                    self.set_by_dict("level", child.text, self.LEVELS)

                else:
                    self.logger.warning(f"{child.tag} is not a valid trigger attribute")
                    
            except KeyError:
                raise XMLError(self, child)

    def __repr__(self):  # mostly for debugging
        return (f"Trigger(id={self.trig_ID}, source={self.source}, "
                f"type={self.trig_type}, edge={self.edge}, level={self.level})")
                

class StartTrigger(XMLLoader):
    """
    StartTrigger class for initializing and setting triggers for NI devices
    
    For example usage, see hsdio.py,analogout.py,analogin.py,digitalout.py,
    and digitalin.py in the PXI Server project.
    
    Allowed trigger edges, which are set in load_xml, are the values in the
    dictionaries below. The second dictionary applies to devices which uses
    the NI-DAQmx python module. 
    
    EDGES = {"rising edge": 12,
             "falling edge": 13,
             "default": "rising edge"}
             
    nidaqmx_edges = {"rising": Edge.RISING,
                     "falling": Edge.FALLING,
                     "default": "rising"}
    
    Attributes:
        source: the physical source name
        wait_for_start_trigger: boolean. self-documenting.
        description: again, self-documenting.
        edge: an allowed trigger edge, as defined by internal dictionaries (see
            above).
    """
    EDGES = {"rising edge": 12,
             "falling edge": 13,
             "default": "rising edge"}

    nidaqmx_edges = {"rising": Edge.RISING,
                     "falling": Edge.FALLING,
                     "default": "rising"}

    def __init__(self, node: ET.Element = None):
        self.source = ""
        self.wait_for_start_trigger = False
        self.description = ""
        self.edge = self.EDGES[self.EDGES["default"]]

        super().__init__(node)

    def load_xml(self, node: ET.Element):
        """
        re-initialize attributes for existing StartTrigger from children of node. 
        
        Args:
            'node' is of type xml.etree.ElementTree.Element, with 
            tag="startTrigger"
        """
        for child in node:

            try:
            
                if child.tag == "waitForStartTrigger":
                    self.wait_for_start_trigger = Instrument.str_to_bool(child.text)

                elif child.tag == "source":
                    self.source = child.text  # PFI 0

                elif child.tag == "description":
                    self.description = child.text

                elif child.tag == "edge":
                    self.set_by_dict("edge", child.text, self.EDGES)

                else:
                    self.logger.warning("Unrecognized XML tag for StartTrigger")
            
            except KeyError:
                raise XMLError(self, child)

    def __repr__(self):
        return (f"StartTrigger(waitForStartTrigger={self.wait_for_start_trigger}, "
                f"source={self.source}, description={self.description}, "
                f"edge={self.edge})")