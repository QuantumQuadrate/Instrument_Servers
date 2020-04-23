"""
AnalogOutput class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

"""

import nidaqmx
import numpy as np
import xml.etree.ElementTree as ET
import csv
from io import StringIO


class AnalogOutput:
    
    def __init__(self):

        self.enable = False
        #self.physicalChannels = ""
        #self.minValue = 
        #self.maxValue

        self.startTrigger = StartTrigger()


    # TODO: good candidate for a unit test
    def wave_from_str(self, wave_str, delim=' '):
        """
        Efficiently build waveform from a string

        Args:
            'wave_str': (str) a (possibly multi-line) string of space-delimited
                float-convertable values. 
            'delim': (str, optional) the value delimiter. ' ' by default
        Returns:
            'wave_arr': (np.ndarray, float) the waveform with one row per line 
                in wave_str, and one column per value in a line
        """

        with StringIO(wstr) as f:
            reader = csv.reader(f, delimiter=delim)
            cols = len(next(reader))
            #print(f"cols={cols}") # DEBUG
            try:
                rows = sum([1 for row in reader]) + 1
            except StopIteration:
                rows = 1
                #print(f"rows={rows}") # DEBUG
            wave_arr = np.empty((rows, cols), float)
    
        with StringIO(wstr) as f:
            reader = csv.reader(f, delimiter=delim)
            for i,row in enumerate(reader):
                #print(row, len(row),'\n') # DEBUG
                wave_arr[i,:] = row
        #print(wave) # DEBUG

        return wave_arr


    def str_to_bool(boolstr):
        """ 
        return True or False case-insensitively for a string 'true' or 'false'

        Args: 
            'boolstr': string to be converted; not case-sensitive
        Return:
            'boolean': True or False. 
        """

        boolstr = boolstr.lower()
        if boolstr == "true":
            return True
        elif boolstr == "false":
            return False
        else:
            print("Expected a string 'true' or 'false' but received {boolstr}")
            raise


    def load_xml(self, node):
        """
        Initialize AnalogOutput instance attributes with xml from CsPy

        Expects node.tag == "AnalogOutput"

        Args:
            'node': type is ET.Element. tag should be "HSDIO"
        """
        
        assert node.tag == "AnalogOutput"

        for child in node: 

            # not sure if this is necessary... could probably remove
            if type(child) == ET.Element:

                if child.tag == "enable":
                    self.enable = str_to_bool(child.text)

                elif child.tag == "physicalChannels":
                    self.physicalChannels = child.text

                elif child.tag == "minimum":
                    self.minValue = float(child.text)

                elif child.tag == "maximum":
                    self.maxValue = float(child.text)

                elif child.tag == "clockRate":
                    self.sampRate = float(child.text) # samples per second in LabVIEW

                elif child.tag == "waveform":
                    self.waveforms = wave_from_str(child.text)

                elif child.tag == "waitForStartTrigger":
                    self.waitForStartTrig = str_to_bool(child.text)

                elif child.tag == "exportStartTrigger":
                    self.exportStartTrig = str_to_bool(child.text)

                elif child.tag == "triggerSource":
                    self.startTrigSource = child.text

                elif child.tag == "exportStartTriggerDestination":
                    self.exportTrigger.outputTerminal = child.text # TODO implement the exportTrigger

                elif child.tag == "triggerEdge":
                    try:
                        self.startTrigger.edge = StartTrigger.ao_edges[child.text]
                    except KeyError as e:
                        # TODO: replace with logger
                        print(f"Not a valid {child.tag} value {child.text} \n {e}")
                        raise

                # TODO: external clock could be a class as in LabVIEW. TBD.
                elif child.tag == "useExternalClock":
                    self.useExternalClock = str_to_bool(child.text)

                elif child.tag == "externalClockSource":
                    self.externalClockSource = child.text

                elif child.tag == "maxExternalClockRate":
                    self.externalClockRateMax = float(child.text)

                else:
                    # TODO: replace with logger
                    print(f"Unrecognized XML tag {child.tag} in <AnalogOutput>")


    def init(self):
        pass


    def update(self):
        pass
 