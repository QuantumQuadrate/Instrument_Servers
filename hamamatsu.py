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
                   
    def __init__(self):
    
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
        self.forceImagesToU16 = 
        
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
        
        def set_by_dict(attr, node_text, values, default):
            """
            Set the class attribute based on the node_text. 
            
            
            Args:
                'attr': (str) the name of the attribute to be set, which is
                    also the node tag. 
                'node_text': the text of the node whose tag  is 'attr'
                'values': (dict) dictionary of values
                'default: the key in values corresponding to the default value
            """
            
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
                    set_by_dict(child.tag, child.text, {"Negative": "ATP N",
                                "Positive": "ATP P"}, "Positive")

                elif child.tag == "externalTriggerMode":
                    set_by_dict(child.tag, child.text, {"Edge":"EMD E",
                                "Synchronous Readout": "EMD S", 
                                "Level":"EMD L"}, "EMD L")

                elif child.tag == "scanSpeed":
                    set_by_dict(child.tag, child.text, {"Slow":"SSP S",
                            "Middle": "SSP M", "High":"SSP H"}, "High")                
                        
                elif child.tag == "lowLightSensitivity":
                    set_by_dict(child.tag, child.text, {"5x": "LLS1", 
                                "13x": "LLS2", "21x": "LLS3", "Off": "LLS 0"},
                                "Off")
 
                elif child.tag == "externalTriggerSource":
                    set_by_dict(child.tag, child.text, {
                                "CameraLink Interface": "ESC I", 
                                "Multi-Timing I/O Pin": "ESC M",
                                "BNC on Power Supply": "ESC B"}, 
                                "BNC on Power Supply")
  
                elif child.tag == "cooling":
                    set_by_dict(child.tag, child.text, {"On": "CSW O",
                                "Off", "CSW F"}, "Off")
                    
                elif child.tag == "fan":
                    set_by_dict(child.tag, child.text, {"On": "FAN O",
                                "Off", "FAN F"}, "Off")
                    
                elif child.tag == "scanMode":
                    set_by_dict(child.tag, child.text, {"Super Pixel": "SMD S",
                                "Sub-array", "SMD A", "Normal": "SMD N"}, 
                                "Normal")
                    
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
        
        make appropriate calls to c functions wrapped in python to initialize
        the camera hardware from the class attributes set in Hamamatsu.load_xml
        """
    
        pass
    