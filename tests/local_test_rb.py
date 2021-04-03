"""
Code for running modular tests for the PXI server instrument classes
"""

#### built-in modules
import re
import xml.etree.ElementTree as ET
from ctypes import *

#### third-party modules
from typing import Tuple
import numpy as np # for arrays

#### local class imports
from pxi import PXI
from hsdio import HSDIO
from analogin import AnalogInput
from analogout import AnalogOutput
from digitalout import DAQmxDO
# from hamamatsu import Hamamatsu
from trigger import *
from waveform import *


def msg_from_file(file="to_pxi.txt"): #
    msgs = []
    with open(file) as f:
        lines = f.readlines()
        for line in lines:
            if "NEW MESSAGE" in line:
                msgs.append('')
                continue
            msgs[-1] += line
    return msgs
    

def hsdio_tests(pxi, node):
    """
    setup tests to run below
    
    Args:
        'pxi': an instance of PXI
    """
    
    devname = "HSDIO"
    
    print(f"Attempting to instantiate {devname}...")
    hsdio = HSDIO(pxi)
    print(f"{devname} instantiated! \n Calling {devname}.load_xml...")
    hsdio.load_xml(node)
    print(f"{devname} XML loaded! \n Calling {devname}.init...")
    hsdio.init()
    print(f"{devname} initialized! \n Calling {devname}.update...")
    hsdio.update()
    print(f"{devname} updated")
    
    
def daqmxdo_tests(pxi, node):
    """
    setup tests to run below
    
    Args:
        'pxi': an instance of PXI
    """
    
    devname = "DAQMX_DO"
    
    print(f"Attempting to instantiate {devname}...")
    do = DAQmxDO(pxi)
    print(f"{devname} instantiated! \n Calling {devname}.load_xml...")
    do.load_xml(node)
    print(f"{devname} XML loaded! \n Calling {devname}.init...")
    do.init()
    print(f"{devname} initialized!")
    
    
def ao_tests(pxi, node):
    """
    setup tests to run below
    
    Args:
        'pxi': an instance of PXI
    """
    devname = "AnalogOutput"
    
    print(f"Attempting to instantiate {devname}...")
    ao = AnalogOutput(pxi)
    print(f"{devname} instantiated! \n Calling {devname}.load_xml...")
    ao.load_xml(node)
    print(f"{devname} XML loaded! \n Calling {devname}.init...")
    ao.init()
    print(f"{devname} initialized! \n Calling {devname}.update...")
    ao.update()
    print(f"{devname} updated")
    
    
def ai_tests(pxi, node):
    """
    setup tests to run below
    
    Args:
        'pxi': an instance of PXI
    """
    devname = "AnalogInput"
    
    print(f"Attempting to instantiate {devname}...")
    ai = AnalogInput(pxi)
    print(f"{devname} instantiated! \n Calling {devname}.load_xml...")
    ai.load_xml(node)
    print(f"{devname} XML loaded! \n Calling {devname}.init...")
    ai.init()
    print(f"{devname} initialized!")
    
    

class DummyPXI:
    """
    Dummy PXI class. Contains only bare minimum requirements for offline testing
    or testing when no device hardware is present. 
    """
    
    def __init__(self, address: Tuple[str, int]):
            self._stop_connections = False
            self._reset_connection = False
            self.cycle_continuously = True
            self.exit_measurement = False
            
            self.hsdio = HSDIO(self)
            self.hamamatsu = None # Hamamatsu()
            # TODO: implement these classes
            self.counters = None  # Counters()
            self.analog_input = None  # AnalogOutput(self)
            self.analog_output = None  # AnalogInput(self)
            self.ttl = None  # TTL()
            self.daqmx_do = None # DAQMX_DO()

    @property
    def stop_connections(self) -> bool:
        return self._stop_connections

    @stop_connections.setter
    def stop_connections(self, value):
        self._stop_connections = value

    @property
    def reset_connection(self) -> bool:
        return self._reset_connection

    @reset_connection.setter
    def reset_connection(self, value):
        self._reset_connection = value


if __name__ == "__main__":

    #### test setup
    # get xml from file
    msg = msg_from_file()[0]
    root = ET.fromstring(msg)
    print(root)
    if root.tag != "LabView":
        print("Not a valid msg for the pxi")
        raise
    
    # {device: skip}. set skip to False to run those device tests
    skiplist = {
        "HSDIO": True, # works, 12 May '20
        "Counters": True,
        "TTL": True,
        "DAQmxDO": True, # works up to hardware test, 12 May '20
        "AnalogOutput": True, # works up to hardware test, 12 May '20
        "AnalogInput": False, # works up to hardware test, 12 May '20
        "RF_generators": True}
        
    # instantiate the PXI
    port=9001
    hostname="localhost"
    pxi = DummyPXI((port, hostname))
        
    #### run tests for each device
    # loop over xml tags and call desired tests
    for child in root:
        if child.tag == "HSDIO" and not skiplist[child.tag]:
            hsdio_tests(pxi, child)
            
        elif child.tag == "Counters" and not skiplist[child.tag]:
            pass
            
        elif child.tag == "TTL" and not skiplist[child.tag]:
            pass
            
        elif child.tag == "DAQmxDO" and not skiplist[child.tag]:
            daqmxdo_tests(pxi, child)
            
        elif child.tag == "AnalogInput" and not skiplist[child.tag]:
            ai_tests(pxi, child) # TODO implement
            
        elif child.tag == "AnalogOutput" and not skiplist[child.tag]:
            ao_tests(pxi, child)
            
        elif child.tag == "RF_generators" and not skiplist[child.tag]:
            pass
            