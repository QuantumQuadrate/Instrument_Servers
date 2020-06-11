"""
Waveform classes for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Authors: Preston Huft, Juan Bohorquez
"""

from __future__ import annotations
from ctypes import *
import numpy as np
from abc import ABC, abstractmethod
import logging
import xml.etree.ElementTree as ET
from typing import List, Tuple
from pxierrors import XMLError

class Waveform(ABC): # should this be an XMLLoader?
    """
    The base class for Waveform data types for the PXI Server. 
    
    Methods that have the 'abstractmethod' decorator are abstract and must be 
    implemented explicitly in the child class. 
    """

    def __init__(self, name="", transitions=None, states=None, data_format=None):
        self.name = name
        self.transitions = transitions
        self._length = 0
        self.states = states
        self.data_format = data_format
        self.wvfm = None
        
    @abstractmethod
    def init_from_xml(self, node): # equivalent to load waveform in labVIEW
        """ 
        Initialize attributes of waveform from xml
        
        Args:
            'node' is of type xml.etree.ElementTree.Element, with tag="waveform"
        """
    
        waveform_attrs = node
        for child in waveform_attrs:
            
            try:
            
                if child.tag == "name":
                    self.name = child.text

                elif child.tag == "transitions":
                    # TODO get the transitions from xml
                    # TODO optionally set the length parameter:
                    # self.length = len(self.transitions)
                    pass

                elif child.tag == "states":
                    # TODO get the states from xml 
                    pass

                else:
                     # TODO: do something like the following with a logger in your class:
                    # print("Invalid Waveform attribute")
                    pass
            
            except Exception:
                raise XMLError(self, child)
            
    @property
    def length(self) -> int:
        """
        return the number of transitions in this waveform
        
        If the waveform is uncompressed, this is equal to number of samples that
        will be written per channel
        """
        assert self.transitions is not None, """Tried to read number of waveform
                                                         transitions, but transitions have not 
                                                         been supplied yet!"""
        return self._length
        
    @length.setter
    def length(self, value):
        self._length = value
                                    
    def __repr__(self):  # mostly for debugging
        return (f"Waveform(name={self.name}, transitions={self.transitions}, "
                f"states={self.states}")
                
        
class DAQmxDOWaveform(Waveform):
    """
    Waveform class for use in the DAQmxDO class
    """
    
    def __init__(self, name="", transitions=None, states=None, data_format=None):
        super().__init__(name, transitions, states, data_format)
        self.logger = logging.getLogger(str(self.__class__))
        
    def init_from_xml(self, node):  # equivalent to load waveform in labVIEW
        """ 
        Initialize attributes of waveform from xml
        
        Args:
            'node' is of type xml.etree.ElementTree.Element, with tag="waveform"
        """
    
        waveform_attrs = node
        for child in waveform_attrs:
            
            try:
                if child.tag == "name":
                    self.name = child.text

                elif child.tag == "transitions":
                    t = np.array([x for x in child.text.split(" ")], 
                                 dtype=c_uint32)
                    self.transitions = t
                    self.length = len(self.transitions)

                elif child.tag == "states":
                    states = np.array([[int(x) for x in line.split(" ")]
                                      for line in child.text.split("\n")],
                                      dtype=c_uint32)
                    self.states = states

                else:
                    self.logger.warning("Invalid Waveform attribute")
                    
            except ValueError:
                raise XMLError(self, child)


class HSDIOWaveform(Waveform):
    """
    Waveform class for use in the HSDIO class
    """
    
    def __init__(
            self,
            name="",
            transitions=None,
            states=None,
            data_format=None,
            node: ET.ElementTree = None
    ):
        super().__init__(name, transitions, states, data_format)
        self.logger = logging.getLogger(str(self.__class__))
        if self.states is not None and node is None:
            self.check_state_len()
        if node is not None:
            self.init_from_xml(node)

    def init_from_xml(self, node):  # equivalent to load waveform in labVIEW
        """     
        re-initialize attributes for existing Waveformfrom children of node. 
        'node' is of type xml.etree.ElementTree.Element, with tag="waveform"
        """
    
        waveform_attrs = node
        for child in waveform_attrs:
            
            try:
            
                if child.tag == "name":
                    self.name = child.text

                elif child.tag == "transitions":
                    t = np.array([x for x in child.text.split(" ")], 
                                 dtype=c_uint32)
                    self.transitions = t
                    self.length = len(self.transitions)

                elif child.tag == "states":
                    states = np.array([[int(x) for x in line.split(" ")]
                                      for line in child.text.split("\n")],
                                      dtype=c_uint32)
                    self.states = states
                    self.check_state_len()

                else:
                    self.logger.warning("Invalid Waveform attribute")
            
            except ValueError:
                raise XMLError(self, child)


    def decompress(
            self,
            data_format: str = "WDT",
            data_layout: bool = True
    ) -> Tuple[str, np.array]:
        """
        Decompresses the waveform based on the information in self.states and self.transitions.

        There should be a direct mapping of states in self.states to transitions in self.transitions
        decompress() should write the waveform into a 2D array such that each self.states[i] is
        first written on a row specified by self.transitions[i], and repeated up to row
        self.transitions[i+1]-1. The array is then flattened based on the input to data_layout.

        Args:
            data_format : Specifies the formatting of self.data to match with NI HSDIOs expected
                formatting options
                Defined values:
                * "WDT" - waveform data type, each index in array corresponds to an output state for
                    one channel at one sample. States can be [0 ,1 ,Z ,L ,H ,X] as defined in
                    niHSDIO.h, encoded as c_uint8(). This mode is required if states other than 0, 1
                    are to be used.
                    When this format is used, use HsdioSession.write_waveform_wdt() to write the
                    waveform to the HSDIO
                * "uInt32" - the 2D array is compressed to correspond to niHSDIO's U32 waveforms.
                    Each index in output array is a c_uint32(), which encodes the output state of
                    all HSDIO output channels (0-32). When this option is selected the data_layout
                    parameter does nothing, and is assumed to be True
                    When this format is used, use HsdioSession.write_wavefor_uint32() to write the
                    waveform to the HSDIO
                * NOT IMPLEMENTED POSSIBILITIES : U16, U8 These correspond to other niHSDIO write
                    waveform functions
            data_layout : Specifies the data layout expected by the write_waveform function.
                True - Values are grouped by sample. Consecutive samples in self.data are
                    such that the array contains the first sample from every signal in the
                    operation, then the second sample from every signal, up to the last sample from
                    every signal
                False - Values are grouped by channel. Consecutive samples in self.data are
                    such that the array contains all the samples from the first signal in the
                    operation. Then all the samples from the second signal, up to all samples from
                    the last signal.

        Returns:
            self.format (str): data encoding format
            self.data (np.array(c_uint8 or c_uint32)): uncompressed waveform data array

        """

        allowed_formats = ["WDT", "uInt32"]
        assert data_format in allowed_formats

        iterables = zip(self.states, self.transitions)
        if data_format == "WDT":

            t_old = self.transitions[0]
            s_old = self.states[0]
            wvfm = np.zeros((max(self.transitions), len(self.states[0])), dtype=c_uint8)
            for state, transition in iterables:
                for c in range(t_old, transition):
                    wvfm[c, :] = s_old
                t_old = transition
                s_old = state

            if data_layout:
                wvfm = wvfm.flatten()
            else:
                wvfm = wvfm.transpose().flatten()

        elif data_format == "uInt32":
            t_old = self.transitions[0]
            s_old = self.state_to_int32(self.states[0])
            wvfm = np.zeros(max(self.transitions), dtype=c_uint32)
            for state, transition in iterables:
                c_state = self.state_to_int32(state)
                for c in range(t_old, transition):
                    wvfm[c] = s_old
                t_old = transition
                s_old = c_state
        else:
            self.logger.error("You shouldn't be here, you used the wrong input for data_format")
            return data_format, None

        self.data_format = data_format
        self.wvfm = wvfm

        return self.data_format, self.wvfm

    def state_to_int32(self, state: [int]):
        """
        Converts state into a c_unit32() bit by bit.

        Args:
            state : 32 element long array of booleans (or ints that are only 0 and 1)
                to be converted into a c_uint32()

        Returns:
            c_state : c_unit32 encoding of state
        """
        state_int = 0
        for ele in state:
            state_int = (state_int << 1) | ele
        return c_uint32(state_int)

    def wave_split(self, flip: bool = True) -> List[HSDIOWaveform]:
        """
        splits a waveform object into a list of waveform objects with len() = dev. where dev is the
        number of hsdio devices receiving waveforms.

        The hsdioSession methods assume waveform data that is encoded for a maximum of 32 channels
        per device. The waveform information passed into the hsdio class via xml encodes data for
        all channels which will be operated on multiple devices. This function is intended to
        perform the necessary split of data by copying most of the Waveform object info into
        separate objects, with the states info split between them

        Args:
            flip : should the order of the channels in each new waveform be flipped?

        Returns:
            list of split up waveform objects
        """

        dev = int(len(self.states[0])/32)

        # mapping may be confused in practical order of devices, maybe flip comes before split?
        wave_array = []
        for d in range(dev):
            if flip:
                new_states = np.array([np.flip(state[d*32:(d+1)*32]) for state in self.states])
            else:
                new_states = np.array([state[d*32:(d+1)*32] for state in self.states])
            wave_array.append(
                HSDIOWaveform(
                    self.name,
                    self.transitions,
                    new_states,
                    self.data_format
                )
            )

        return wave_array

    def check_state_len(self):
        """
        checks that the states array
        Returns:

        """
        cl_str = str(self.__class__.__name__)
        state_len = self.states.shape[0]
        as_ms = f"{cl_str}.states.shape[0] = {state_len}; it's not divisible by 32! Expected " \
                f"channels per card to be 32."
        assert state_len % 32 == 0, as_ms
