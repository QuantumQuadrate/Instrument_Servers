"""
DAQmx Digital Output class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""

# TODO: there exist DaqResourceWarning warnings that i neither handle nor log, 
# as it seems that the class merely points to a built-in Python ResourceWarning, 
# which is itself abstract. - Preston

## modules
import nidaqmx
from nidaqmx.constants import Edge, LineGrouping, AcquisitionType
from nidaqmx.errors import DaqError
import numpy as np
import logging

## local imports
from trigger import StartTrigger
from waveform import Waveform
from instrument import Instrument
from pxierrors import XMLError, HardwareError


class DAQmxDO(Instrument):

    def __init__(self, pxi):
        super().__init__(pxi, "DAQmxDO")
        self.logger = logging.getLogger(str(self.__class__))
        self.physicalChannels = None
        self.startTrigger = StartTrigger()
        self.task = None
        
    
    def load_xml(self, node):
        """
        Initialize the instrument class attributes from XML received from CsPy
        
         Args:
            'node': type is ET.Element. tag should match self.expectedRoot
            node.tag == self.expectedRoot
        """
        
        self.is_initialized = False
        
        assert node.tag == self.expectedRoot, "expected node"+\
            f" <{self.expectedRoot}> but received <{node.tag}>"

        for child in node: 
        
            try:
            
                if child.tag == "enable":
                    self.enable = Instrument.str_to_bool(child.text)
            
                elif child.tag == "resourceName":
                    self.physicalChannels = child.text
                
                elif child.tag == "clockRate":
                    self.clockRate = float(child.text)
                    
                elif child.tag == "startTrigger":

                    # This is modifying the definitions of the outer for loop child and node. This
                    # seems dangerous.
                    node = child
                    for child in node:
                    
                        if node.text == "waitForStartTrigger":
                            self.startTrigger.wait_for_start_trigger = Instrument.str_to_bool(child.text)
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
                                raise KeyError(f"Not a valid {child.tag} value {child.text} \n {e}")
                        else:
                            self.logger.warning(f"Unrecognized XML tag \'{node.tag}\' in <{child.tag}>")
                
                elif child.tag == "waveform":
                    self.waveform = Waveform()
                    self.waveform.init_from_xml(child)
                    self.samplesPerChannel = self.waveform.length # the number of transitions
                    
                    # reverse each state array 
                    self.numChannels = len(self.waveform.states[0])
                    self.data = np.empty((self.samplesPerChannel, self.numChannels))
                    for i, state in enumerate(self.waveform.states):
                        self.data[i] = np.flip(state)
                            
                else:
                    self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
            
            except (KeyError, ValueError):
                
                raise XMLError(self, child)
                
                    
    def init(self):
        """
        Initialize the device hardware with the attributes set in load_xml
        """
    
        if not (self.stop_connections or self.reset_connection) and self.enable:
            
                # Clear old task
                if self.task is not None:
                    try:
                        self.task.close()
                        
                    except DaqError:
                        # end the task nicely
                        self.stop()
                        self.close()
                        msg = '\n DAQmxDO failed to close current task'
                        raise HardwareError(self, task=self.task, message=msg)

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
                        samps_per_chan=self.samplesPerChannel) 
                        
                    # Optionally set up start trigger
                    if self.startTrigger.wait_for_start_trigger:
                        self.task.start_trigger.cfg_dig_edge_start_trig(
                            trigger_source=self.startTrigger.source,
                            trigger_edge=self.startTrigger.edge)
                                                            
                    # Write digital waveform 1 chan N samp
                    # by default, auto starts
                    self.task.write(
                        self.data, 
                        timeout=10.0) # default
            
                except DaqError:
                    # end the task nicely
                    self.stop()
                    self.close()
                    msg = '\n DAQmxDO hardware initialization failed'
                    raise HardwareError(self, task=self.task, message=msg)
                    
                self.is_initialized = True
                
                
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
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n DAQmxDO check for task completion failed'
                raise HardwareError(self, task=self.task, message=msg)
            
        return done
                

    def start(self):
        """
        Start the task
        """
        
        if not (self.stop_connections or self.reset_connection) and self.enable:
            
            try:
                self.task.start()
            except DaqError:
                # end the task nicely
                self.stop()
                self.close()
                msg = '\n DAQmxDO failed to start task'
                raise HardwareError(self, task=self.task, message=msg)

            
    def stop(self):
        """
        Stop the task
        """
        
        if self.enable:
            try:
                self.task.stop()
            except DaqError:
                msg = '\n DAQmxDO failed while attempting to stop current task'
                raise HardwareError(self, task=self.task, message=msg)
                
                
    def close(self):
        """
        Close the task
        """
        
        if self.task is not None:
            try:
                self.task.close()
                
            except DaqError:
                msg = '\n DAQmxDO failed to close current task'
                raise HardwareError(self, task=self.task, message=msg)