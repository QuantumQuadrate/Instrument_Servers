"""
Hamamatsu class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

For parsing XML strings which specify the settings for the Hamamatsu C9100-13
camera and initialization of the hardware of said camera. 
"""

from ctypes import * # open to suggestions on making this better with minimal obstruction to workflow
import numpy as np
import xml.etree.ElementTree as ET

class Hamamatsu: '''could inherit from a Camera class if we choose to move 
                    control of other cameras (e.g. Andor) over to this server
                    And/or having a parent class would shorten the code here. 
                 '''
                 
    # dictionaries of allowed values for class attributes. note that the key
    # 'Default' has a value which is the key for the default value to be used
    # in the dictionary
    scanModeValues = {"Super Pixel": "SMD S","Sub-array", "SMD A", 
                      "Normal": "SMD N", "Default": "Normal"}
    fanValues = {"On": "FAN O", "Off": "FAN F", "Default": "Off"}
    coolingValues = {"On": "CSW O", "Off": "CSW F", "Default": "Off"}
    externalTriggerSourceValues = {"CameraLink Interface": "ESC I", 
                                   "Multi-Timing I/O Pin": "ESC M",
                                   "BNC on Power Supply": "ESC B", 
                                   "Default": "BNC on Power Supply"}
    externalTriggerModeValues = {"Edge":"EMD E",
                                 "Synchronous Readout": "EMD S", 
                                 "Level":"EMD L", "Default": "EMD L"}
    lowLightSensitivityValues = {"5x": "LLS1", "13x": "LLS2", "21x": "LLS3",
                                 "Off": "LLS 0", "Default": "Off"}
    scanSpeedValues = {"Slow":"SSP S", "Middle": "SSP M", "High":"SSP H",
                       "Default": "High"}
    triggerPolarityValues = {"Negative": "ATP N", "Positive": "ATP P", 
                             "Default": "Positive"}
    
    
                   
    def __init__(self):

        # TODO : @Juan create static class variables to map settings to Hamamatsu-Compatible settings
        # TODO : @Juan compile descriptions of settings set bellow for ease of use later
        self.enable = False # called "use camera?" in labview
        self.analogGain = 0 # 0-5
        self.exposureTime = 0 # can be scientific format
        self.EMGain = 0 # 0-255
        self.triggerPolarity = "ATP P" # positive by default
        self.externalTriggerMode = "EMD L" # level by default
        self.scanSpeed = "SSP H" # high by default
        self.lowLightSensitivity =
        self.externalTriggerSource = 
        self.cooling = 
        self.fan = 
        self.scanMode = 
        self.superPixelBinning = # WHERES. MY. SUPER. SUIT?
        self.numImageBuffers = # imageBuffers in labview; renamed by tag name.
        self.shotsPerMeasurement = 
        self.forceImagesToU16 = False
        
        # these things are implemented with their own classes in labview, 
        # could do that here too. 
        self.cameraSubArrayAcquistionRegion = CameraSubArrayAcquistionRegion
        self.frameGrabberAcquisitionRegion = FrameGrabberAcquistionRegion()
        
       
    def load_xml(self, node):
        """
		parse xml by tag to initialize Hamamatsu class attributes
		
        Args:
            'node': xml.etree.ElementTree.Element node with tag="camera"
		"""
        
        def set_by_dict(attr, node_text, values):
            """
            Set the class a attribute attr based on the node_text
            
            Class attribute is set based on node_text, using a dictionary of 
            values for the attribute. If node_text is not a key in the
            dictionary, a default value specified in the dictionary itself will
            be used. 
            
            Args:
                'attr': (str) the name of the attribute to be set, which is
                    also the node tag. 
                'node_text': the text of the node whose tag  is 'attr'
                'values': (dict) dictionary of values, where at least one key
                    is "Default", whose value is the key for the default value
                    in the dictionary
            """
            try: 
                default = values["Default"] # the key for the default value
            except KeyError: 
                # TODO: replace with logger
                print(f"Value dictionary for Hamamatsu.{attr} must include"+
                       "the key \'Default\', where the value is the key of"+ 
                       "the default value in the dictionary.")
            
            if node_text in values:
                setattr(self, attr, values[node_text])
            else:
                # TODO: replace with logger
                print(f"Invalid {attr} setting {node_text}; using {default} "+ 
                      f"({values[default]}) instead.")
                setattr(self, attr, values[default])
                
		
		assert node.tag == "camera", "This XML is not tagged for the camera"
		
        # in the labview class, all of the settings that get updated here are
        # appended to a settings array. the only purpose of that array is for
        # viewing the settings on the front panel by reading out the array, 
        # so i have opted to not include said array. 
		for child in node:

			if type(child) == ET.Element:
				
				# handle each tag by name:
                if child.tag == "version":
                    # TODO: labview code checks if camera settings are from 
                    # "2015.05.24", which is hardcoded. probably don't need
                    # this case?
                    pass
                elif child.tag == "enable":
                    enable = False
                    if child.text.lower() == "true":
                        enable = True
					self.enable = enable
                    
                elif child.tag == "analogGain":
                    try: 
                        gain = float(child.text)
                        assert 0 < gain < 5, ("analogGain must be between 0 "+
                                              " and 5")
                        self.analogGain = gain
                    except:
                        #TODO replace with logger
                        print("analogGain was given a non-numeric value!")
                        
                elif child.tag == "exposureTime":
                    try: 
                        # can convert scientifically-formatted numbers - good
                        self.exposureTime = float(child.text)
                    except:
                        #TODO: replace with logger
                        print("exposureTime was given a non-numeric value!")
                        
                elif child.tag == "EMGain":
                     try: 
                        gain = float(child.text)
                        assert 0 < gain < 255, ("EMGain must be between 0 "+
                                              " and 255")
                        self.EMGain = gain
                    except:
                        #TODO: replace with logger
                        print("EMGain was given a non-numeric value!")
                    
                elif child.tag == "triggerPolarity":
                    set_by_dict(child.tag, child.text, triggerPolarityValues)

                elif child.tag == "externalTriggerMode":
                    set_by_dict(child.tag, child.text, )

                elif child.tag == "scanSpeed":
                    set_by_dict(child.tag, child.text, scanSpeedValues)                
                        
                elif child.tag == "lowLightSensitivity":
                    set_by_dict(child.tag, child.text, lowLightSensitivityValues)
 
                elif child.tag == "externalTriggerSource":
                    set_by_dict(child.tag, child.text, 
                                externalTriggerSourceValues)
  
                elif child.tag == "cooling":
                    set_by_dict(child.tag, child.text, coolingValues)
                    
                elif child.tag == "fan":
                    set_by_dict(child.tag, child.text, fanValues)
                    
                elif child.tag == "scanMode":
                    set_by_dict(child.tag, child.text, scanModeValues)
                    
                elif child.tag == "superPixelBinning":
                    self.superPixelBinning = child.text
                    
                elif child.tag == "subArrayLeft":
                    try:
                        self.cameraSubArrayAcquistionRegion.left = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "subArrayTop":
                    try:
                        self.cameraSubArrayAcquistionRegion.top = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "subArrayWidth":
                    try:
                        self.cameraSubArrayAcquistionRegion.width = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "subArrayHeight":
                    try:
                        self.cameraSubArrayAcquistionRegion.height = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "frameGrabberAcquisitionRegionLeft":
                    try:
                        self.frameGrabberAcquisitionRegion.left = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                    
                elif child.tag == "frameGrabberAcquisitionRegionTop":
                    try:
                        self.frameGrabberAcquisitionRegion.top = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "frameGrabberAcquisitionRegionRight":
                    try:
                        self.frameGrabberAcquisitionRegion.right = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "frameGrabberAcquisitionRegionBottom":
                    try:
                        self.frameGrabberAcquisitionRegion.bottom = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "numImageBuffers":
                    try:
                        self.numImageBuffers = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                    
                elif child.tag == "shotsPerMeasurement":
                    try:
                        self.shotsPerMeasurement = float(child.text)
                    except: # TODO put typecast error here
                        # TODO replace with logger
                        print(f"{child.tag} value {child.text} is non-numeric!")
                        
                elif child.tag == "forceImagesToU16":
                    force = False
                    if child.text.lower() == "true":
                        force = True
					self.forceImagesToU16 = force
                    
                else:
                    # TODO: replace with logger
                    print(f"Node {child.tag} is not a valid Hamamatsu "+ 
                           "attribute")

            
    def init(self):
        """
        initialize the Hamamatsu camera's hardware 
        
        make appropriate calls to dlls wrapped in python to initialize the 
        camera hardware from the class attributes set in Hamamatsu.load_xml
        """

        if self.enable:
            
            ## reset the IMAQSession 
            
            #TODO: Juan
            if self.imaqSession is not None:
                # self.session.close()
                # IMAQSession.dispose(destroyOldImages=True) # classmethod
                pass
            
            #TODO: Juan 
            # self.session = IMAQSession("img0")
            """
            Args: 
                "interface name": (str); "img0" here
            """
            
            ## call the Hamamatsu setup functions, i.e. python-wrapped dllsn
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(self.cooling, self.cooling, error_in)
            """
            note: the session reference is required, but i doubt it needs to
            be an explicitly passed parameter... the serial method can probably
            just reference the hamamatsu's current session instance internally.
            in any case, i have opted to not type session ref in the args of 
            calls to serial below.
            
            Args: 
                "Session reference"
                "Connection to send": (str)
                "Expected Response": (str) <-- this looks like it is optional, 
                    as it is unused in the camera temp request
                "Error":
            Returns:
                "Error"
                "Session reference" 
            """
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(self.fan, self.fan, error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(self.scanSpeed, self.scanSpeed, error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(self.fan, self.fan, error_in)
           
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(self.externalTriggerSource, 
            #             self.externalTriggerSource, error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # set trigger mode to external
            # in the labview code, the self.externalTriggerMode is set to
            # "EMD L" by default, but the actual triggering is set to "AMD E"
            # which isn't even an option for the externalTriggerMode attribute.
            # idk why this discrepancy is here but might be worth investigating 
            #
            # self.session.serial("AMD E", "AMD E", error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # see above comment; i guess these are different things, but the 
            # nomenclature is confusing as both calls appear to be configuring
            # external triggering. a clarifying comment in the code would help.
            # self.session.serial(self.externalTriggerMode, 
            #                     self.externalTriggerMode, error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(self.triggerPolarity, self.triggerPolarity, 
            #                       error_in)
            
            # labview uses "Number to Fraction String Format VI" to convert the
            # exposure time to a string; as far as I can tell this str() cast 
            # accomplishes the same thing in this use case
            exposure = "AET\s" + str(self.exposureTime)
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(exposure, exposure, error_in)
            
            # labview uses "Number to Decimal String VI" to convert the
            # EMGain to a string; as far as I can tell this str() cast 
            # accomplishes the same thing in this use case
            emgain = "EMG\s" + str(self.EMGain)
            # TODO: Juan. "Hamamatsu_serial VI"
            # self.session.serial(emgain, emgain, error_in)
            
            analog_gain = f"CEG\s{self.analogGain}"
            # TODO: Juan. "Hamamatsu_serial VI"
            # set exposure time
            # self.session.serial(analog_gain, analog_gain, error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # read camera temperature
            # self.session.serial("?TMP", error_in)
            
            # TODO: Juan. "Hamamatsu_serial VI"
            # scan mode
            # self.session.serial(self.scanMode, self.scanMode, error_in)
            
            if self.scanMode in scanModeValues.values():
                
                if self.scanMode = "SMD S": # superPixelBinning
                    
                    # TODO: Juan. "Hamamatsu_serial VI"
                    # self.session.serial(self.superPixelBinning, self.superPixelBinning,
                    #             error_in)
                    
                elif self.scanMode = "SMD A": # sub-array
                
                    subArrayLeft = ("SHO\s"+
                                    str(CameraSubArrayAcquistionRegion.left))
                    # TODO: Juan. "Hamamatsu_serial VI"
                    # self.session.serial(subArrayLeft, subArrayLeft, error_in)
                    
                    subArrayTop = ("SVO\s"+
                                   str(CameraSubArrayAcquistionRegion.top))
                    # TODO: Juan. "Hamamatsu_serial VI"
                    # self.session.serial(self.superPixelBinning, self.superPixelBinning,
                    #             error_in)
                    
                    subArrayWidth = ("SHW\s"+
                                    str(CameraSubArrayAcquistionRegion.width))
                    # TODO: Juan. "Hamamatsu_serial VI"
                    # self.session.serial(subArrayWidth, subArrayWidth, error_in)
                    
                    subArrayHeight = ("SVW\s"+
                                     str(CameraSubArrayAcquistionRegion.height))
                    # TODO: Juan. "Hamamatsu_serial VI"
                    # self.session.serial(subArrayHeight, subArrayHeight, error_in)
                
            # default is to do nothing
            
            # TODO: Juan - "IMAQ Configure List VI"
            # https://documentation.help/NI-IMAQ-VI/IMAQ_Configure_List.html
            """
            Configures a buffer list to be used in an acquisition.
            
            Args:
                'Region of interest': (int32) Region of Interest is defined by an
                    array of four elements [Left, Top, Right, Bottom]. You must set
                    the width [Right-Left] to a multiple of eight. If Region of 
                    Interest is not connected or empty, the entire acquisition 
                    window is captured.
                'IMAQSession in'
                'Continuous?': int value, e.g. from an enum variable like 
                    {'One-Shot': 0, 'Continuous': 1}
                'Number of buffers' (u32), e.g. from an enum variable like
                    {'System': 0, 'Onboard': 1}
                'error_in'
                'MemoryLocation'
                
            Returns:
                'IMAQSession out'
            """
            roi = [self.frameGrabberAcquistionRegion.Top,
                   self.frameGrabberAcquistionRegion.Left,
                   self.frameGrabberAcquistionRegion.Right,
                   self.frameGrabberAcquistionRegion.Bottom]
                   
            #TODO: don't hardcode numbers here; enter from a value dict
            self.session.IMAQConfigureList(roi, 1, numImageBuffers, 0)

