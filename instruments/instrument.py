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
        self.logger = logging.getLogger(repr(self))
        self.logger.setLevel(logging.DEBUG)  # Adjust instrument level logging here
        # TODO : Set logging level globally. Maybe config file
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
        """
       Converts a string encoding "True" or "False" to boolean form case-insensitively.

        Args:
            'boolstr': string to be converted; not case-sensitive
        Returns:
             True or False depending on contents of string
        Throws:
            ValueError if the string cannot be converted due to a typo or other error
        """
        conv = {"true": True,
                "false": False}
        try:
            return conv[boolstr.lower()]
        except KeyError:
            raise ValueError(f"Expected a string 'true' or 'false' but received {boolstr}")

    @staticmethod
    def str_to_int(num_str: str) -> int:
        """
        Extracts a leading signed integer from a string.

        Example input/output pairs:

            Input     | Output
            -----------------
            '-4.50A'  | -4
            '31415q' | 31415
            'ph7cy'   | None, throws ValueError

        Args:
            num_str : string containing a leading integer
        Returns:
            integer value encoded in num_str
        Throws:
            ValueError: If no leading integer was found
        """
        try:
            return int(re.findall("^-?\d+", num_str)[0])
        except IndexError:
            raise ValueError(f"num_str = {num_str} is non-numeric!")

    def set_by_dict(self, attr: str, node_text: str, values: {str: str}):
        """
        Set the class a attribute attr based on the node_text

        Class attribute is set based on node_text, using a dictionary of
        values for the attribute. If node_text is not a key in the
        dictionary, a default value specified in the dictionary itself will
        be used. The node_text will be converted to lowercase, such that
        supplying a dictionary with lowercase keys makes this method 
        case-insensitive.

        Args:
            'attr': the name of the attribute to be set, which is
                also the node tag.
            'node_text': the text of the node whose tag  is 'attr'
            'values': dictionary of values, where at least one key
                is "Default", whose value is the key for the default value
                in the dictionary. Note that the keys should be lowercase.
        """
        # check that the dict keys are lowercase
        assert set([v.lower() for v in values.keys()]) == set(values.keys())
        try:
            default = values["default"]
        except KeyError as e:
            cl_str = str(self.__class__.__name__)
            m = f"{e}\nIn {cl_str}, value dictionary for {attr} must include" +\
                "the key \'Default\', where the value is the key of" +\
                "the default value in the dictionary."
            raise KeyError(m)

        try:
            setattr(self, attr, values[node_text.lower()])
        except KeyError as er:
            self.logger.warning(
                f"{er}\n {attr} value {node_text} should be in {values.keys()}"
                f"\nKeeping default {default} value {values[default]}"
            )
            setattr(self, attr, values[default])

    def __repr__(self):
        """
        Overwrite in other instruments if more detailed info is desired
        """
        return self.__class__.__name__

class Instrument(XMLLoader):
    
    def __init__(self, pxi, expected_root, node: ET.Element = None):
        """
        Constructor for the Instrument abstract base class
        
        Args:
            'pxi': reference to the parent PXI instance
            'expectedRoot': the xml tag corresponding to your instrument. This 
                should be in the xml sent by CsPy to talk to setup this device.
            'node': xml node if available. if passed, self.load_xml is called in __init__
        """
        super().__init__(node)
        self.pxi = pxi
        self.pxi.devices.append(self) # Tell PXI it created this instance
        self.expectedRoot = expected_root
        self.enable = False
        self.is_initialized = False
        self._name = self.__class__.__name__

    @property
    def name(self):
        return self._name
    
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

    @property
    def exit_measurement(self) -> bool:
        return self.pxi.exit_measurement

    @exit_measurement.setter
    def exit_measurement(self, value):
        self.pxi.exit_measurement = value
   
    @abstractmethod
    def load_xml(self, node: ET.Element):
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """

        if not (self.exit_measurement or self.stop_connections):
            return

        as_ms = f"node to open camera is tagged {node.tag}. Must be tagged {self.expectedRoot}"
        assert node.tag == self.expectedRoot, as_ms

    @abstractmethod
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return