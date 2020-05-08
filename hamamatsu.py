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
import re

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

        # Labview Camera variables
        self.is_initialized = False
        self.num_images = 0
        self.use_camera = False
        self.shots_per_measurement = 0
        self.camera_roi_file_refnum = 0
        # Laview Hamamatsu variables
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
        self.externalTriggerSource = self.externalTriggerSourceValues[
            self.externalTriggerModeValues["Default"]
        ]
        self.scanMode = self.scanModeValues[self.scanModeValues["Default"]]
        self.superPixelBinning = # WHERES. MY. SUPER. SUIT?
        # Dicts instead of classes to reduce complexity
        # Uses uint16 in labview, use ints here, cast where necessary
        self.cameraSubArrayAcquistionRegion = {
            "Left": 0,
            "Top": 0,
            "Width": 0,
            "Height": 0
        }
        self.numImageBuffers = 0 # imageBuffers in labview; renamed by tag name.
        self.shotsPerMeasurement = 2
        self.forceImagesToU16 = False
        self.lowLightSensitivity = self.lowLightSensitivityValues[
            self.lowLightSensitivityValues["Default"]
        ]
        self.cooling = self.coolingValues[self.coolingValues["Default"]] #Find default value
        self.fan = self.fanValues[self.fanValues["Default"]]
        # Uses int32 in labview, use ints here, cast where necessary
        self.frameGrabberAcquisitionRegion = {
            "Left":0,
            "Top":0,
            "Right":0,
            "Bottom":0
        }
        self.session = NiImaqSession()
        self.lastFrameAcquired = -1
        self.camera_temp = 0.0
        self.last_measurement = np.array([])  # Holds data from previous measurement in 3D array (shots,x,y)

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
            self.camera_temp = f"TMP {response:f}"

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

            self.session.set_roi(self.frameGrabberAcquisitionRegion)

            self.session.setup_buffers(num_buffers=self.numImageBuffers)
            if not self.session.get_buff_list_init():  # TODO : implement
                pass  # TODO : deal with this error case

            self.last_measurement = np.zeros(
                (
                    self.shotsPerMeasurement,
                    self.session.get_attribute("ROI Width"),
                    self.session.get_attribute("ROI Height")
                ),
                dtype = int
            )
            self.is_initialized = True
            self.num_images = 0
            self.use_camera = True
            self.start()

    def start(self):
        # TODO : Implement this
        # Starts with check for global "Exit Measurement". If Exit Measurement : return
        if not self.enable:
            return
        self.session.session_acquire(asynchronous=True)
        err_c, trig_mode = self.session.hamamatsu_serial("?AMD")
        '''
        This function is called in labview and these variables are set (locally?) but they're not used in the scope, 
        just broken out as indicators. I wonder if scope in labview is somehow different from what I imagine
        '''
        err_c, acquiring, last_buffer_index, last_buffer_number = self.session.status()
        pass

    def minimial_acquire(self):

        if not self.use_camera:
            return
        er_c, session_acquiring, last_buf_ind, last_buf_num = self.session.status()
        bf_dif = last_buf_num - self.lastFrameAcquired
        not_enough_buffers = bf_dif > self.numImageBuffers
        # Why is this in the labview code? Should be a flag for you verbose logging is maybe?
        if False:
            self.append_to_log(f"Last Frame : {self.lastFrameAcquired}\n"
                               f"New Frame : {last_buf_num}\n"
                               f"Difference : {bf_dif}")
        if not session_acquiring:
            er_msg = "In session.status() NOT acquiring."
            raise SomeError(er_msg)  # TODO : Replace placeholder
        if last_buf_num != self.lastFrameAcquired and last_buf_num != -1 and not_enough_buffers:
            er_msg = "The number of images taken exceeds the number of buffers alloted." + \
                "Images have been lost.  Increase the number of buffers."
            raise SomeError(er_msg)  # TODO : Replace placeholder
            # TODO : Use logger
        frame_ind = last_buf_ind
        for i in range(bf_dif):
            frame_ind = frame_ind + 1
            # Why is this in the labview code? Should be a flag for you verbose logging is maybe?
            if False:
                self.append_to_log("True: Acquiring a new image available\n"
                                   f" Reading buffer number {frame_ind}")
            er_c, bf_ind, img = self.session.extract_buffer(frame_ind)
            self.last_measurement[i,:,:] = img

        self.read_camera_temp()

        pass

    def read_camera_temp(self):
        """
        Reads the camera temperature, sets self.cameraTemp to the new value
        """

        if self.use_camera:
            msg_in = "?TMP"
            er_c, msg_out = self.session.hamamatsu_serial(msg_in)
            msg_out_fmt = "TMP {}"

            # TODO : parse out temp from string, cast to float
            m = re.match(r"Temp (\d+)\.(\d+)",msg_out)
            self.camera_temp = float("{}.{}".format(m.groups()[0],m.groups()[1]))

        else:
            self.camera_temp = np.inf

    def data_out(self):  # TODO : Implement
        """
        Should return a formatted data string
        Returns:

        """
        pass


                
                

