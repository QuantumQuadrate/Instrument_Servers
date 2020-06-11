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
    EDGES = {"Rising Edge": 12,
             "Falling Edge": 13,
             "Default": "Rising Edge"}

    TYPES = {"Edge": 0,
             "Level": 1,
             "Default": "Edge"}

    LEVELS = {"High Level": 34,
              "Low Level": 35,
              "Default": "High Level"}
    
    def __init__(self, node: ET.Element = None):
        self.source = ""
        self.trig_ID = ""
        self.trig_type = self.TYPES[self.TYPES["Default"]]
        self.edge = self.EDGES[self.EDGES["Default"]]
        self.level = self.LEVELS[self.LEVELS["Default"]]

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
    TODO : @Preston write docstring for this class
    """
    EDGES = {"Rising Edge": 12,
             "Falling Edge": 13,
             "Default": "Rising Edge"}

    nidaqmx_edges = {"Rising": Edge.RISING,
                     "Falling": Edge.FALLING,
                     "Default": "Rising"}

    def __init__(self, node: ET.Element = None):
        self.source = ""
        self.wait_for_start_trigger = False
        self.description = ""
        self.edge = self.EDGES[self.EDGES["Default"]]

        super().__init__(node)

    def load_xml(self, node: ET.Element):
        """
        re-initialize attributes for existing StartTrigger from children of node. 
        'node' is of type xml.etree.ElementTree.Element, with tag="startTrigger"
        """
        for child in node:

            try:
            
                if child.tag == "waitForStartTrigger":
                    self.wait_for_start_trigger = Instrument.str_to_bool(child.tag)

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

    def __repr__(self):  # mostly for debugging
        return (f"StartTrigger(waitForStartTrigger={self.wait_for_start_trigger}, "
                f"source={self.source}, description={self.description}, "
                f"edge={self.edge})")