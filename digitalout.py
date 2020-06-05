"""
DAQmx Digital Output class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

#### modules
import nidaqmx
from nidaqmx.constants import Edge, LineGrouping
from nidaqmx.errors import DaqError, DaqWarning, DaqResourceWarning
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
        self.l
        self.physicalChannels = None
        self.startTrigger = StartTrigger()
        
    
    def load_xml(self, node):
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """
        
        assert node.tag == self.expectedRoot, "expected node"+ 
            f" <self.expectedRoot> but received <node.tag>"

        for child in node: 
            
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
                        self.startTrigger.wait_for_start_trigger = str_to_bool(child.text)
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

                try:
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
                    if self.startTrigger.wait_for_start_trigger:
                        self.task.start_trigger.cfg_dig_edge_start_trig(
                            trigger_source=self.startTrigger.source,
                            trigger_edge=self.startTrigger.edge)
                                                            
                    # Write digital waveform 1 chan N samp
                    self.task.write(
                        self.data, 
                        auto_start=AUTO_START_UNSET, #default
                        timeout=10.0) # default
            
            except DaqError as e:
                msg = 'DAQmxDO hardware initialization failed'
                raise DaqError(e.message+msg, e.error_code)
                
            except DaqWarning as e:
                self.logger.warning(str(e.message))
            
            self.isInitialized = True
                
                
    def is_done(self) -> bool:
        """
        Check if the tasks being run are completed
        
        Return:
            'done': True if tasks completed, connection was stopped or reset, 
                self.enable is False, or an NIDAQmx exception/warning occurred.
                False otherwise.
        """
        
        done = True
        if not (self.stop_connections or self.reset_connection) and self.enable:
        
            # check if NI task is dones
            try:
                done = self.task.is_task_done()
            except DaqError as e:
                msg = 'DAQmxDO check for task completion failed'
                raise DaqError(e.message+msg, e.error_code)
                
            except DaqWarning as e:
                self.logger.warning(str(e.message))
            
        return done
                

    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.reset_connection) and self.enable:
            
            try:
                self.task.start()
            except DaqError as e:
                msg = 'DAQmxDO failed to start task'
                raise DaqError(e.message+msg, e.error_code)
                
            except DaqWarning as e:
                self.logger.warning(str(e.message))
            
    def stop(self):
        """
        Stop the task
        """
        
        if self.enable:
            try:
                self.task.stop()
            except DaqError as e:
                msg = 'DAQmxDO failed while attempting to stop current task'
                raise DaqError(e.message+msg, e.error_code)
                
            except DaqWarning as e:
                self.logger.warning(str(e.message))