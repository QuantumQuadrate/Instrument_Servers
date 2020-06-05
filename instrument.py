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

## built-in modules
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
import logging
import re

## local class imports
from instrumentfuncs import str_to_bool


class XMLLoader(ABC):
    """
    Class for all classes that load from an xml
    TODO : tag classes that can be wrapped into this
    """
    def __init__(self, node: ET.Element = None):
        """
        Args:
            node : optional node so that a second call to load_xml does not have to be made
        """
        self.logger = logging.getLogger(str(self.__class__.__name__))
        if node is not None:
            self.load_xml(node)

    @abstractmethod
    def load_xml(self, node: ET.Element):
        """
        Initialize the instrument class attributes from XML received from CsPy

         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """
        pass

    @staticmethod
    def str_to_bool(boolstr: str) -> bool:
        # TODO : Replace usages of instrumentfuncs versions with this one
        """
        return True or False case-insensitively for a string 'true' or 'false'

        If boolstr is not 'true' or 'false' this function will raise a KeyError

        Args:
            'boolstr': string to be converted; not case-sensitive
        Return:
            'boolean': True or False.
        """
        conv = {"true": True,
                "false": False}
        try:
            ret = conv[boolstr.lower()]
        except ValueError as e:
            m = f"boolstr = {boolstr} is non-boolean!"
            raise ValueError(m)
        return conv[boolstr.lower()]

    @staticmethod
    def str_to_int(num_str: str) -> int:
        # TODO : replace usages of instrumentfuncs version with this one
        """
        return a signed integer anchored to the beginning of num_str

        Args:
            num_str : a signed integer, if found

                Example input/output pairs:

                    Input     | Output
                    -----------------
                    '-4.50A'  | -4
                    '31415q' | 31415
                    'ph7cy'   | None, throws IndexError

        Returns:
            integer value encoded in num_str
        """
        try:
            ret = int(re.findall("^-?\d+", num_str)[0])
        except IndexError:
            m = f"num_str = {num_str} is non-numeric!"
            raise ValueError(m)
        return ret

    @staticmethod
    def str_to_float(num_str: str) -> float:
        """
        Return a float based on input string, handle errors gracefully
        Args:
            num_str : floating point number encoded in a string.
                Example i/o pairs:

                    Input   | Output
                    '6.345' | 6.345
                    '-924.3'| -924.3
                    'a775'  | None, throws ValueError
        Returns:
            float value encoded in num_str
        """
        try:
            ret = float(num_str)
        except ValueError:
            m = f"num_str = {num_str} is non-numeric!"
            raise ValueError(m)
        return ret

    def set_by_dict(self, attr: str, node_text: str, values: {str: str}):
        """
        Set the class a attribute attr based on the node_text

        Class attribute is set based on node_text, using a dictionary of
        values for the attribute. If node_text is not a key in the
        dictionary, a default value specified in the dictionary itself will
        be used.

        Args:
            'attr': the name of the attribute to be set, which is
                also the node tag.
            'node_text': the text of the node whose tag  is 'attr'
            'values': dictionary of values, where at least one key
                is "Default", whose value is the key for the default value
                in the dictionary
        """
        try:
            default = values["Default"]
        except KeyError as e:
            cl_str = str(self.__class__.__name__)
            m = f"{e}\nIn {cl_str}, value dictionary for {attr} must include" +\
                "the key \'Default\', where the value is the key of" +\
                "the default value in the dictionary."
            raise KeyError(m)

        try:
            setattr(self, attr, values[node_text])
        except KeyError as er:
            self.logger.warning(
                f"{er}\n {attr} value {node_text} should be in {values.keys()}"
                f"\nKeeping default {default} value {values[default]}"
            )
            setattr(self, attr, values[default])


class Instrument(XMLLoader):
    
    def __init__(self, pxi, expected_root, node: ET.Element = None):
        """
        Constructor for the Instrument abstract base class
        
        Args:
            'pxi': reference to the parent PXI instance
            'expectedRoot': the xml tag corresponding to your instrument. This 
                should be in the xml sent by CsPy to talk to setup this device.
            'node': xml node if available, if passed self.load_xml is called in __init__
        """
        super().__init__(node)
        self.pxi = pxi
        self.expectedRoot = expected_root
        self.enable = False
    
    @property
    def reset_connection(self) -> bool:
        return self.pxi.reset_connection

    @reset_connection.setter
    def reset_connection(self, value):
        self.pxi.reset_connection = value

    @property
    def stop_connections(self) -> bool:
        return self.pxi.stop_connections

    @stop_connections.setter
    def stop_connections(self, value):
        self.pxi.stop_connections = value
   
    @abstractmethod
    def load_xml(self, node: ET.Element):
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """

        if self.stop_connections or self.reset_connection:
            return

        as_ms = f"node to open camera is tagged {node.tag}. Must be tagged {self.expectedRoot}"
        assert node.tag == self.expectedRoot, as_ms

        '''
        Not sure any of this (except the self.enable setting) should be here -Juan

        if not (self.stop_connections or self.reset_connection):
        
            assert node.tag == self.expectedRoot, f"Expected xml tag {self.expectedRoot}"

            for child in node: 

                if type(child) == ET.Element:
                
                    if child.tag == "enable":
                        self.enable = self.str_to_bool(child.text)
                
                    # elif child.tag == "someOtherProperty":
                        # self.thatProperty = child.text
                    
                    else:
                        # TODO handle unexpected tag case
                        # self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
                        pass
        '''

    @abstractmethod
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return
                                
            
    
        
        