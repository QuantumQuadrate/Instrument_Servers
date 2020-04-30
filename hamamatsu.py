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
from ni_imaq import NiImaqSession

class Hamamatsu:
    """
    could inherit from a Camera class if we choose to move
    control of other cameras (e.g. Andor) over to this server
    And/or having a parent class would shorten the code here.
    """

    # dictionaries of allowed values for class attributes. note that the key
    # 'Default' has a value which is the key for the default value to be used
    # in the dictionary
    scanModeValues = {"Super Pixel": "SMD S","Sub-array": "SMD A",
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
        self.triggerPolarity = self.triggerPolarityValues[
            self.triggerPolarityValues["Default"]
        ]  # positive by default
        self.externalTriggerMode = self.externalTriggerModeValues[
            self.externalTriggerModeValues["Default"]
        ]  #level by default
        self.scanSpeed = self.scanSpeedValues[self.scanSpeedValues["Default"]]  # high by default
        self.lowLightSensitivity = self.lowLightSensitivityValues[
            self.lowLightSensitivityValues["Default"]
        ]
        self.externalTriggerSource = self.externalTriggerSourceValues[
            self.externalTriggerModeValues["Default"]
        ]
        self.cooling = self.coolingValues[self.coolingValues["Default"]] #Find default value
        self.fan = self.fanValues[self.fanValues["Default"]]
        self.scanMode = self.scanModeValues[self.scanModeValues["Default"]]
        self.superPixelBinning = # WHERES. MY. SUPER. SUIT?
        self.numImageBuffers = 0 # imageBuffers in labview; renamed by tag name.
        self.shotsPerMeasurement = 2
        self.forceImagesToU16 = False
        self.cameraTemp = 0.0
        self.lastFrameAcquired = -1
        
        # Dicts instead of classes to reduce complexity
        # Uses uint16 in labview, use ints here, cast where necessary
        self.cameraSubArrayAcquistionRegion = {
            "Left": 0,
            "Top": 0,
            "Width": 0,
            "Height": 0
        }
        # Uses int32 in labview, use ints here, cast where necessary
        self.frameGrabberAcquisitionRegion = {
            "Left":0,
            "Top":0,
            "Right":0,
            "Bottom":0
        }

        self.session = NiImaqSession()
       

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
                        gain = int(child.text)
                        assert 0 < gain < 5, ("analogGain must be between 0 "+
                                              " and 5")
                        self.analogGain = gain
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "exposureTime":
                    try: 
                        # can convert scientifically-formatted numbers - good
                        self.exposureTime = float(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise

                elif child.tag == "EMGain":
                    try:
                        # This is an int in labview, why was this set to a float?
                        # gain = float(child.text)
                        gain = int(child.text)
                        assert 0 < gain < 255, ("EMGain must be between and 255")
                        self.EMGain = gain
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                    
                elif child.tag == "triggerPolarity":
                    set_by_dict(child.tag, child.text, self.triggerPolarityValues)

                elif child.tag == "externalTriggerMode":
                    set_by_dict(child.tag, child.text, self.externalTriggerModeValues)

                elif child.tag == "scanSpeed":
                    set_by_dict(child.tag, child.text, self.scanSpeedValues)
                        
                elif child.tag == "lowLightSensitivity":
                    set_by_dict(child.tag, child.text, self.lowLightSensitivityValues)
 
                elif child.tag == "externalTriggerSource":
                    set_by_dict(child.tag, child.text, 
                                self.externalTriggerSourceValues)
  
                elif child.tag == "cooling":
                    set_by_dict(child.tag, child.text, self.coolingValues)
                    
                elif child.tag == "fan":
                    set_by_dict(child.tag, child.text, self.fanValues)
                    
                elif child.tag == "scanMode":
                    set_by_dict(child.tag, child.text, self.scanModeValues)
                    
                elif child.tag == "superPixelBinning":
                    self.superPixelBinning = child.text
                    
                elif child.tag == "subArrayLeft":
                    try:
                        self.cameraSubArrayAcquistionRegion["Left"] = int(child.text)
                    except ValueError as e: #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise

                elif child.tag == "subArrayTop":
                    try:
                        self.cameraSubArrayAcquistionRegion["Top"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "subArrayWidth":
                    try:
                        self.cameraSubArrayAcquistionRegion["Width"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "subArrayHeight":
                    try:
                        self.cameraSubArrayAcquistionRegion["Height"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "frameGrabberAcquisitionRegionLeft":
                    try:
                        self.frameGrabberAcquisitionRegion["Left"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                    
                elif child.tag == "frameGrabberAcquisitionRegionTop":
                    try:
                        self.frameGrabberAcquisitionRegion["Top"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "frameGrabberAcquisitionRegionRight":
                    try:
                        self.frameGrabberAcquisitionRegion["Right"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "frameGrabberAcquisitionRegionBottom":
                    try:
                        self.frameGrabberAcquisitionRegion["Bottom"] = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "numImageBuffers":
                    try:
                        self.numImageBuffers = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                    
                elif child.tag == "shotsPerMeasurement":
                    try:
                        # Why was this float?
                        self.shotsPerMeasurement = int(child.text)
                    except ValueError as e:  #
                        # TODO replace with logger
                        print(f"{e}\n{child.tag} value {child.text} is non-numeric!")
                        raise
                        
                elif child.tag == "forceImagesToU16":
                    force = False
                    if child.text.lower() == "true":
                        force = True
                    self.forceImagesToU16 = force
                    
                else:
                    # TODO: replace with logger
                    print(f"Node {child.tag} is not a valid Hamamatsu attribute")
            
    def init(self):
        """
        initialize the Hamamatsu camera's hardware 
        
        make appropriate calls to dlls wrapped in python to initialize the 
        camera hardware from the class attributes set in Hamamatsu.load_xml
        """

        if self.enable:

            if self.session.session_id.value != 0:
                self.session.close()

            if self.session.buff_list_init:
                self.session.dispose_buffer_list()

            #  "img0" really shouldn't be hard-coded but it is in labview so we keep for now
            self.session.open_interface("img0")
            self.session.open_session()
            
            ## call the Hamamatsu setup functions, i.e. python-wrapped dllsn
            self.session.hamamatsu_serial(self.cooling, self.cooling)

            self.session.hamamatsu_serial(self.fan,self.fan)
            self.session.hamamatsu_serial(self.scanSpeed,self.scanSpeed)

            self.session.hamamatsu_serial(
                self.externalTriggerSource,
                self.externalTriggerSource)

            # set trigger mode to external
            self.session.hamamatsu_serial("AMD E", "AMD E")

            # set the external trigger mode
            self.session.hamamatsu_serial(
                self.externalTriggerMode,
                self.externalTriggerMode
            )

            self.session.hamamatsu_serial(
                self.triggerPolarity,
                self.triggerPolarity
            )

            # labview uses "Number to Fraction String Format VI" to convert the
            # exposure time to a string; as far as I can tell this formatting
            # accomplishes the same.
            exposure = "AET\s{.6f}".format(self.exposureTime)
            self.session.hamamatsu_serial(exposure,exposure)
            
            # labview uses "Number to Decimal String VI" to convert the
            # EMGain to a string; as far as I can tell this formatting
            # accomplishes the same thing in this use case
            emgain = f"EMG\s{self.EMGain}"
            self.session.hamamatsu_serial(emgain,emgain)
            
            analog_gain = f"CEG\s{self.analogGain}"
            # set analog gain
            self.session.hamamatsu_serial(analog_gain,analog_gain)

            # read camera temperature
            error_code, response =  self.session.hamamatsu_serial("?TMP")
            self.cameraTemp = f"TMP {response:f}"

            # last frame acquired. first actual frame will be zero. 
            self.lastFrameAcquired = -1

            # set scan mode
            self.session.hamamatsu_serial(self.scanMode,self.scanMode)

            if self.scanMode in self.scanModeValues.values():
                
                if self.scanMode == "SMD S": # superPixelBinning

                    self.session.hamamatsu_serial(
                        self.superPixelBinning,
                        self.superPixelBinning
                    )
                    
                elif self.scanMode == "SMD A": # sub-array

                    sub_array_left = ("SHO\s"+
                                    str(self.cameraSubArrayAcquistionRegion["Left"]))

                    self.session.hamamatsu_serial(
                        sub_array_left,
                        sub_array_left
                    )

                    sub_array_top = ("SVO\s"+
                                   str(self.cameraSubArrayAcquistionRegion["Top"]))

                    self.session.hamamatsu_serial(
                        sub_array_top,
                        sub_array_top
                    )

                    sub_array_width = ("SHW\s"+
                                    str(self.cameraSubArrayAcquistionRegion["Width"]))

                    self.session.hamamatsu_serial(
                        sub_array_width,
                        sub_array_width
                    )

                    sub_array_height = ("SVW\s"+
                                     str(self.cameraSubArrayAcquistionRegion["Height"]))

                    self.session.hamamatsu_serial(
                        sub_array_height,
                        sub_array_height
                    )
            # default is to do nothing

            roi = self.frameGrabberAcquisitionRegion

            width = roi["Right"]-roi["Left"]
            height = roi["Bottom"]-roi["Top"]

            self.session.get_attribute("ROI Width")
            acq_width = self.session.attributes["ROI Width"]
            self.session.get_attribute("ROI Height")
            acq_height = self.session.attributes["ROI Height"]

            if width < acq_width:
                self.session.set_attribute2("ROI Width",c_uint32(width))
            if height < acq_height:
                self.session.set_attribute2("ROI Height",c_uint32(height))
            self.session.set_attribute2("ROI Left",roi["Left"])
            self.session.set_attribute2("ROI Top",roi["Top"])


            self.session.create_buffer_list(self.numImageBuffers)

            # set up the image buffers
            for buf_num in range(self.numImageBuffers):

                # Juan's outline based on c ll ring example  -------------------

                self.session.compute_buffer_size()
                erc, self.session.buffers[buf_num] = self.session.create_buffer()
                self.session.set_buf_element2(
                    buf_num,
                    "Address",
                    self.session.buffers[buf_num]
                )
                self.session.set_buf_element2(
                    buf_num,
                    "Size",
                    self.session.buffer_size
                )
                if buf_num == self.numImageBuffers-1:
                    buf_cmd = self.session.BUFFER_COMMANDS["Loop"]
                else:
                    buf_cmd = self.session.BUFFER_COMMANDS["Next"]
                self.session.set_buf_element2(
                    buf_num,
                    "Command",
                    c_uint32(buf_cmd)
                )
            self.session.buff_list_init = True



            '''
            This stuff below was expected to be in the for loop. It shadows the functionality of the
            corresponding for loop in the labview code, but the c code example deviates 
            significantly from this!
            TODO : @Juan - Take a closer look at the labview code and see if there's something your 
                copying of the c-loop missed!
                # labview formats i as a signed decimal integer here, but
                # ints formatted with d qualifier should just be ints.
                ringNum = f"LL Ring num {buf_num}" 
                
                # TODO: Juan - "IMAQ Create VI"
                # http://zone.ni.com/reference/en-XX/help/370281AG-01/imaqvision/imaq_create/
                """
                Creates a temporary memory location for an image
                
                Use IMAQ Create in conjunction with the IMAQ Dispose VI to 
                create or dispose of NI Vision images in LabVIEW.
                
                Args:
                    'Border size': (int32)  **this isn't wired in the labview
                        code, and a default value isn't specified, but i would
                        think it should default to 0** 
                        
                        determines the width, in pixels,
                        of the border to create around an image. These pixels
                        are used only for specific VIs. Create a border at the 
                        beginning of your application if an image is to be 
                        processed later using functions that require a border 
                        (for example, labeling and morphology). The default 
                        border value is 3. With a border of three pixels, you
                        can use kernels up to 7 × 7 with no change. If you plan
                        to use kernels larger than 7 × 7 in your process, 
                        specify a larger border when creating your image.
                        
                    'Image name': (str) is the name associated with the created 
                        image. Each image created must have a unique name.
                    'Error in': 
                    'Image Type': (u32), e.g. from enum like this:
                        {'Grayscale (U8)': 0, 'Grayscale (I16)': 1, 
                         'Grayscale' (SGL): 2, 'Complex (CSG)': 3,
                         'RGB (U32)': 4 ... ,
                         'Grayscale (U16)': 7}
                    
                Returns:
                    'New Image': the Image reference that is supplied as input
                        to all subsequent (downstream) functions used by NI 
                        Vision. Multiple images can be created in a LabVIEW 
                        application.
                    'Error out':
                """
                
                # border size = 0 (i'm guessing; see above)
                # image type is grayscale u16, or 7
                # TODO: could create dicts of possible values rather hardcode
                # these. in labview each returned image ref is appended to an
                # array and passed out, but it doesn't look like that array
                # is used anywhere. 
                image_ref = IMAQSession.create(0, ringNum, 7, error_in)
                
                # TODO: Juan - "IMAQ Configure Buffer VI"
                # https://documentation.help/NI-IMAQ-VI/IMAQ_Configure_Buffer.html
                """
                Configures individual buffers in the buffer list.
                
                Args: 
                    'channel' (int32 )
                    'skipcount' (u32)
                    'IMAQSession in'
                    'image in'
                    'buffer number' (u32)
                    'error in'
                    
                Returns: 
                    'IMAQSession out'
                    'error out'
                """
                # other params unused
                self.session.configureBuffer(image_ref, buf_num, error_in)
                
                self.cameraInit() # in labview this belongs to a camera class, 
                                  # and is Camera.initialize. the input is the
                                  # Hamamatsu instance. again, if we decide to
                                  # control other cameras here we could make an
                                  # a Camera base class. for now i'll just make
                                  # this a hamamatsu method.

                self.start()
            '''
           
    def serial(self):

    def cameraInit(self)
        pass
    
    
    def start(self):
        # TODO : Implement this
        if not self.enable:
            return
        self.session.session_acquire(asynchronous=True)
        err_c, trig_mode = self.session.hamamatsu_serial("?AMD")
        self.session.status() # TODO : Implement NiImaqSession.status()
        '''
        Returns status information about the acquisition, such as the state of the acquisition and 
        the last valid buffer acquired
        
        Returns:
            Session
            Acquiring : Boolean
            Last Valid Buffer Index: Int, buffer list index of last acquired image
            Last Valid Buffer Number: Int, cumulative number of last acquired image
        '''
        pass
                
                

