"""
Command line tool for testing CsPy Modules
"""


# built-in 
import re
import xml.etree.ElementTree as ET
from ctypes import *

# third-party
from recordclass import recordclass as rc # for Trigger, Waveform types
import numpy as np # for arrays
import click

# local module imports
from pxi import *
from tcp import *
from trigger import *
from waveform import *
from hsdio import *
from analogout import *
from analogin import *
from digitalout import *
from hamamatsu import *

pxi = None

# name should be the lowercase version of the xml tag
allowed_devs = ['hsdio', 
                       'analogoutput', 
                       'analoginput', 
                       'daqmxdo', 
                       'ttl', 
                       'camera', 
                       'counters',
                       'rf_generators']

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
    
    
def call_method(funcname, instance, args=None):
    """
    Test if funcname is a function of instance, and call it if so. 
    Args:
        'funcname': name of function supposedly belonging to instance 
        'instance': instance of a class being tested
    """
    if funcname in dir(instance):
        func = getattr(instance, funcname)
        if args is None:
            func()
        else:
            func(*args)   
    else:
        print(f'\'{funcname}\' is not a method of {instance.__class__}')
    
@click.command()
@click.option('--dev', help='lowercase device name, e.g. \'hsdio\'')
@click.option('--func', help='function belonging to device instance, e.g. \'init\'')
def testdevice(device, method):
    """
    run device.method
    """
    
    assert device in allowed_devs, (f"\'{device}\' is not a valid device name."+ 
        f"\n Recognized device names are \n {allowed_devs} \n"+
        "You may have to add your device to \'allowed_devs\' in this tool")
        
    args = None
        
    for child in root:
    
        if method == 'init':
            args = child
            
        if method == 'all':
            pass # option to test all methods somehow by looping through
            
        elif child.tag == "HSDIO" :
            hsdio = HSDIO(pxi)
            call_method(method, hsdio, args)
            
        elif child.tag == "TTL"  and child.tag.lower() == device:
            ttl = DigitalIn(pxi)
            call_method(method, ttl, args)
            
            
        elif child.tag == "DAQmxDO" and child.tag.lower() == device:
            # TODO: implement DAQmxDO class
            # self.daqmxdo.load_xml(child)
            # self.daqmxdo.init() # called setup in labview
            pass

        elif child.tag == "camera" and child.tag.lower() == device:
            pass
            # set up the Hamamatsu camera
            # self.hamamatsu.load_xml(child)
            # self.hamamatsu.init()

        elif child.tag == "AnalogOutput" and child.tag.lower() == device:
            # TODO: implement analog_output class
            # set up the analog_output
            # self.analog_output.load_xml(child)
            # self.analog_output.init() # setup in labview
            # self.analog_output.update()
            pass

        elif child.tag == "AnalogInput" and child.tag.lower() == device:
            # TODO: implement analog_input class
            # set up the analog_input
            # self.analog_input.load_xml(child)
            # self.analog_input.init()
            pass

        elif child.tag == "Counters" and child.tag.lower() == device:
            # TODO: implement counters class
            # set up the counters
            # self.counters.load_xml(child)
            # self.counters.init()
            pass

        # might implement, or might move RF generator functionality to
        # CsPy based on code used by Hybrid.
        elif child.tag == "RF_generators" and child.tag.lower() == device:
            pass
        
            ## non-device things that could be tested
            
            """
            if child.tag == "measure":
                if self.return_data_queue.empty():
                    # if no data ready, take one measurement
                    self.measurement()
                else:
                    pass
                    # Cast return_data_queue to a string? in labview the
                    # global "Return Data" is simply assigned the value of
                    # "Return Data Queue", despite the fact that the latter
                    # is a Queue instance and the former is filled elsewhere
                    # with a string built from concatenated xml.
                    #
                    # self.return_data_str = str(return_data_queue

            elif child.tag == "pause":
                # TODO: set state of server to 'pause';
                # i don't know if this a feature that currently gets used,
                # so might be able to omit this.
                pass

            elif child.tag == "run":
                # TODO: set state of server to 'run';
                # i don't know if this a feature that currently gets used,
                # so might be able to omit this.
                pass
                
            elif child.tag == "timeout" and child.tag.lower() == device:
                try:
                    # get timeout in [ms]
                    self.measurement_timeout = 1000 * float(child.text)
                except ValueError as e:
                    self.logger.error(f"{e} \n {child.txt} is not valid " +
                                      f"text for node {child.tag}")

            elif child.tag == "cycleContinuously" and child.tag.lower() == device:
                cycle = False
                if child.text.lower() == "True":
                    cycle = True
                self.cycle_continuously = cycle
            """
        else:
            print(f"Node {child.tag} received is not a valid" +
                    f"child tag under root <{root.tag}>")    


if __name__ == "__main__":

    ## get xml from a file containing message from Rb's CsPy
    msg = msg_from_file()[0]
    root = ET.fromstring(msg)
    print(root)    
    if root.tag != "LabView":
        print("Not a valid msg for the pxi")
        
    ## set up a pxi instance
    port = 9001
    hostname = "localhost"
    address = (hostname, port)

    print(f'starting up on {hostname} port {port}')
    experiment = PXI(address)

    