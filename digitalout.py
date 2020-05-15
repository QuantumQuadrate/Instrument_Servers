"""
DAQmx Digital Output class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

#### modules
import nidaqmx
from nidaqmx.constants import Edge, LineGrouping
import xml.etree.ElementTree as ET
import numpy as np
import logging

#### local imports
from trigger import StartTrigger
from waveform import DAQmxDOWaveform
from instrument import Instrument
from instrumentfuncs import str_to_bool

class DAQmxDO(Instrument):

    def __init__(self, pxi):
        super().__init__(pxi, "DAQmxDO")
        self.logger = logging.getLogger(str(self.__class__))        
        self.physicalChannels = None
        self.startTrigger = StartTrigger()
        
    
    def load_xml(self, node):
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
                    
                        if node.text == "waitForStartTrigger":
                            self.startTrigger.waitForStartTrigger = str_to_bool(child.text)
                        elif child.text == "source":
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
                    self.waveform.samplesPerChannel = self.waveform.length # the number of transitions
                    
                    # reverse each state array 
                    self.numChannels = len(self.waveform.states[0])
                    self.data = np.empty((self.samplesPerChannel, self.numChannels))
                    for i, state in enumerate(self.waveform.states):
                        self.data[i] = np.flip(state)
                            
                else:
                    self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
                    
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if not (self.stop_connections or self.reset_connection):
            
             if self.enable:

                # Clear old task
                if self.task != None:
                    self.task.close()

                self.task = nidaqmx.Task() # might be task.Task()
                
                # Create digital out virtual channel
                self.task.do_channels.add_do_chan(
                    lines=self.physicalChannels, 
                    name_to_assign_to_lines="",
                    line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                
                # Setup timing. Use the onboard clock
                self.task.timing.cfg_samp_clk_timing(
                    rate=self.clockRate, 
                    active_edge=Edge.RISING, # default
                    sample_mode=AcquisitionType.FINITE, # default
                    samps_per_chan=samplesPerChannel) 
                    
                # Optionally set up start trigger
                if self.startTrigger.waitForStartTrigger:
                    self.task.start_trigger.cfg_dig_edge_start_trig(
                        trigger_source=self.startTrigger.source,
                        trigger_edge=self.startTrigger.edge)
                                                        
                # Write digital waveform 1 chan N samp
                self.task.write(
                    self.data, 
                    auto_start=AUTO_START_UNSET, #default
                    timeout=10.0) # default
                    
                self.isInitialized = True
                
                
    def is_done(self) -> bool:
        """
        Check if the tasks being run are completed
        
        Return:
            'done': True if tasks completed, connection was stopped or reset, or
                self.enable is False. False otherwise.
        """
        
        done = True
        if not (self.stop_connections or self.reset_connection) and self.enable:
        
            # check if NI task is dones
            done = self.task.is_task_done()
            
        return done
                

    # TODO: call in PXI.start_tasks  
    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.reset_connection) and self.enable:
            self.task.start()
            
    # TODO: call in PXI.stop_tasks  
    def stop(self):
        """
        Stop the task
        """
        
        if self.enable:
            self.task.stop()