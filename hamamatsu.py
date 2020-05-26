"""
Hamamatsu class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

For parsing XML strings which specify the settings for the Hamamatsu C9100-13
camera and initialization of the hardware of said camera. 
"""


from ctypes import *
import numpy as np
import xml.etree.ElementTree as ET
from ni_imaq import NIIMAQSession, IMAQError
import re
import logging
import struct
from tcp import TCP
from recordclass import recordclass as rc
from instrument import Instrument

class Hamamatsu(Instrument):
    # TODO : Make this inherit from instrument class
    """
    Class to control the operation of the Hamamatsu camera using the NI IMAQ drivers

    could inherit from a Camera class if we choose to move
    control of other cameras (e.g. Andor) over to this server
    And/or having a parent class would shorten the code here.
    """

    # dictionaries of allowed values for class attributes. note that the key
    # 'Default' has a value which is the key for the default value to be used
    # in the dictionary
    SCAN_MODE_VALUES = {"Super Pixel": "SMD S", "Sub-array": "SMD A",
                        "Normal": "SMD N", "Default": "Normal"}
    FAN_VALUES = {"On": "FAN O", "Off": "FAN F", "Default": "Off"}
    COOLING_VALUES = {"On": "CSW O", "Off": "CSW F", "Default": "Off"}
    EXT_TRIG_SOURCE_VALUES = {"CameraLink Interface": "ESC I",
                              "Multi-Timing I/O Pin": "ESC M",
                              "BNC on Power Supply": "ESC B",
                              "Default": "BNC on Power Supply"}
    EXT_TRIG_SOURCE_MODE_VALUES = {"Edge": "EMD E",
                                   "Synchronous Readout": "EMD S",
                                   "Level": "EMD L", "Default": "EMD L"}
    LL_SENSITIVITY_VALUES = {"5x": "LLS1", "13x": "LLS2", "21x": "LLS3",
                             "Off": "LLS 0", "Default": "Off"}
    SCAN_SPEED_VALUES = {"Slow": "SSP S", "Middle": "SSP M", "High": "SSP H",
                         "Default": "High"}
    TRIG_POLARITY_VALUES = {"Negative": "ATP N", "Positive": "ATP P",
                            "Default": "Positive"}

    SubArray = rc('SubArray', ('left', 'top', 'width', 'height'))
    FrameGrabberAqRegion = rc('FrameGrabberAqRegion', ('left', 'right', 'top', 'bottom'))

    def __init__(self, pxi, node: ET.Element = None):
        super().__init__(pxi, "camera", node)
        self.measurement_success = False  # Tracks whether self.last_measurement is useful.

        # Labview Camera variables
        self.is_initialized = False
        self.num_images = 0
        self.shots_per_measurement = 0
        self.camera_roi_file_refnum = 0
        # Labview Hamamatsu variables
        # TODO : @Juan compile descriptions of settings set bellow for ease of use later
        self.enable = False  # called "use camera?" in labview
        self.analog_gain = 0  # 0-5
        self.exposure_time = 0  # can be scientific format
        self.em_gain = 0  # 0-255
        self.trigger_polarity = self.TRIG_POLARITY_VALUES[
            self.TRIG_POLARITY_VALUES["Default"]
        ]  # positive by default
        self.external_trigger_mode = self.EXT_TRIG_SOURCE_MODE_VALUES[
            self.EXT_TRIG_SOURCE_MODE_VALUES["Default"]
        ]  # level by default
        self.scan_speed = self.SCAN_SPEED_VALUES[self.SCAN_SPEED_VALUES["Default"]]  # high by default
        self.external_trigger_source = self.EXT_TRIG_SOURCE_VALUES[
            self.EXT_TRIG_SOURCE_MODE_VALUES["Default"]
        ]
        self.scan_mode = self.SCAN_MODE_VALUES[self.SCAN_MODE_VALUES["Default"]]
        self.super_pixel_binning = ""  # WHERES. MY. SUPER. SUIT?
        # Uses uint16 in labview, use ints here, cast where necessary
        self.sub_array = self.SubArray(0, 0, 0, 0)
        self.num_img_buffers = 0  # imageBuffers in labview; renamed by tag name.
        self.shots_per_measurement = 2
        self.images_to_U16 = False
        self.low_light_sensitivity = self.LL_SENSITIVITY_VALUES[
            self.LL_SENSITIVITY_VALUES["Default"]
        ]
        self.cooling = self.COOLING_VALUES[self.COOLING_VALUES["Default"]]
        self.fan = self.FAN_VALUES[self.FAN_VALUES["Default"]]
        # Uses int32 in labview, use ints here, cast where necessary
        self.fg_acquisition_region = self.FrameGrabberAqRegion(0, 0, 0, 0)
        self.session = NIIMAQSession()
        self.last_frame_acquired = -1
        self.camera_temp: float = 0.0
        # Holds data from previous measurement in 3D array (shots,x,y)
        self.last_measurement = np.array([])

    def load_xml(self, node: ET.Element):
        """
        parse xml by tag to initialize Hamamatsu class attributes

        Args:
            'node': node with tag="camera"
        """

        # in the labview class, all of the settings that get updated here are
        # appended to a settings array. the only purpose of that array is for
        # viewing the settings on the front panel by reading out the array,
        # so i have opted to not include said array.

        for child in node:
            if type(child) == ET.Element:
                # handle each tag by name:
                try:
                    if child.tag == "version":
                        # labview code checks if camera settings are from
                        # "2015.05.24", which is hardcoded. probably don't need
                        # this case?
                        # TODO : Check if this info is used anywhere in labview
                        pass
                    elif child.tag == "enable":
                        self.enable = self.str_to_bool(child.text)

                    elif child.tag == "analogGain":
                        gain = self.str_to_int(child.text)
                        as_ms = f"analogGain = {gain}\n analogGain must be between 0  and 5"
                        assert 0 < gain < 5, as_ms
                        self.analog_gain = gain

                    elif child.tag == "exposureTime":
                        # can convert scientifically-formatted numbers - good
                        self.exposure_time = self.str_to_float(child.text)

                    elif child.tag == "EMGain":
                        gain = self.str_to_int(child.text)
                        as_ms = f"EMGain is {gain}\n EMGain must be between 0 and 255"
                        assert 0 < gain < 255, as_ms
                        self.em_gain = gain

                    elif child.tag == "triggerPolarity":
                        self.set_by_dict("trigger_polarity", child.text, self.TRIG_POLARITY_VALUES)

                    elif child.tag == "externalTriggerMode":
                        self.set_by_dict("external_trigger_mode",
                                         child.text,
                                         self.EXT_TRIG_SOURCE_MODE_VALUES
                                         )

                    elif child.tag == "scanSpeed":
                        self.set_by_dict("scan_speed", child.text, self.SCAN_SPEED_VALUES)

                    elif child.tag == "lowLightSensitivity":
                        self.set_by_dict(
                            "low_light_sensitivity",
                            child.text,
                            self.LL_SENSITIVITY_VALUES
                        )

                    elif child.tag == "externalTriggerSource":
                        self.set_by_dict(
                            "external_trigger_source",
                            child.text,
                            self.EXT_TRIG_SOURCE_VALUES
                        )

                    elif child.tag == "cooling":
                        self.set_by_dict("cooling", child.text, self.COOLING_VALUES)

                    elif child.tag == "fan":
                        self.set_by_dict("fan", child.text, self.FAN_VALUES)

                    elif child.tag == "scanMode":
                        self.set_by_dict("scan_mode", child.text, self.SCAN_MODE_VALUES)

                    elif child.tag == "superPixelBinning":
                        self.super_pixel_binning = child.text

                    elif child.tag == "subArrayLeft":
                        self.sub_array.left = self.str_to_int(child.text)

                    elif child.tag == "subArrayTop":
                        self.sub_array.top = self.str_to_int(child.text)

                    elif child.tag == "subArrayWidth":
                        self.sub_array.width = self.str_to_int(child.text)

                    elif child.tag == "subArrayHeight":
                        self.sub_array.height = self.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionLeft":
                        self.fg_acquisition_region.left = self.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionTop":
                        self.fg_acquisition_region.top = self.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionRight":
                        self.fg_acquisition_region.right = self.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionBottom":
                        self.fg_acquisition_region.bottom = self.str_to_int(child.text)

                    elif child.tag == "numImageBuffers":
                        self.num_img_buffers = self.str_to_int(child.text)

                    elif child.tag == "shotsPerMeasurement":
                        self.shots_per_measurement = self.str_to_int(child.text)

                    elif child.tag == "forceImagesToU16":
                        self.images_to_U16 = self.str_to_bool(child.text)

                    else:
                        self.logger.warning(f"Node {child.tag} is not a valid Hamamatsu attribute")
                except AssertionError as e:
                    # This should reduce code duplication
                    self.logger.error(e, exc_info=True)
                    raise

    def init(self):
        """
        initialize the Hamamatsu camera's hardware 
        
        Generates an imaq session and initializes the imaq acquisition parameters, as well as the
        hamamatsu acquisition parameters.

        This function should only be called after load_xml has been called at least once.
        """
        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return

        if self.session.session_id.value != 0:
            self.session.close()

        self.is_initialized = False

        try:
            # "img0" really shouldn't be hard-coded but it is in labview so we keep for now
            self.session.open_interface("img0")
            self.session.open_session()
        except IMAQError as e:
            self.logger.error(e.message, exc_info=True)
            raise

        # call the Hamamatsu serial function to set the Hamamatsu settings
        try:
            self.session.hamamatsu_serial(self.cooling, self.cooling)
            self.session.hamamatsu_serial(self.fan, self.fan)
            self.session.hamamatsu_serial(self.scan_speed, self.scan_speed)

            self.session.hamamatsu_serial(
                self.external_trigger_source,
                self.external_trigger_source)

            # set trigger mode to external
            # TODO : set this mode by xml parameter
            self.session.hamamatsu_serial("AMD E", "AMD E")

            # set the external trigger mode
            self.session.hamamatsu_serial(
                self.external_trigger_mode,
                self.external_trigger_mode
            )

            self.session.hamamatsu_serial(
                self.trigger_polarity,
                self.trigger_polarity
            )

            # labview uses "Number to Fraction String Format VI" to convert the
            # exposure time to a string; as far as I can tell this formatting
            # accomplishes the same.
            exposure = "AET\s{.6f}".format(self.exposure_time)
            self.session.hamamatsu_serial(exposure, exposure)

            # labview uses "Number to Decimal String VI" to convert the
            # EMGain to a string; as far as I can tell this formatting
            # accomplishes the same thing in this use case
            emgain = f"EMG\s{self.em_gain}"
            self.session.hamamatsu_serial(emgain, emgain)

            analog_gain = f"CEG\s{self.analog_gain}"
            self.session.hamamatsu_serial(analog_gain,analog_gain)

            self.read_camera_temp()

            # last frame acquired. first actual frame will be zero.
            self.last_frame_acquired = -1

            self.session.hamamatsu_serial(self.scan_mode, self.scan_mode)

            if self.scan_mode in self.SCAN_MODE_VALUES.values():

                if self.scan_mode == "SMD S":  # superPixelBinning

                    self.session.hamamatsu_serial(
                        self.super_pixel_binning,
                        self.super_pixel_binning
                    )

                elif self.scan_mode == "SMD A":  # sub-array

                    sub_array_left = ("SHO\s" +
                                      str(self.sub_array.left))

                    self.session.hamamatsu_serial(
                        sub_array_left,
                        sub_array_left
                    )

                    sub_array_top = ("SVO\s" +
                                     str(self.sub_array.top))

                    self.session.hamamatsu_serial(
                        sub_array_top,
                        sub_array_top
                    )

                    sub_array_width = ("SHW\s" +
                                       str(self.sub_array.width))

                    self.session.hamamatsu_serial(
                        sub_array_width,
                        sub_array_width
                    )

                    sub_array_height = ("SVW\s" +
                                        str(self.sub_array.height))

                    self.session.hamamatsu_serial(
                        sub_array_height,
                        sub_array_height
                    )
            # default is to do nothing
        except IMAQError as e:
            ms = f"{e.message}\nError writing camera settings. Many camera settings likely not set."
            self.logger.error(ms, exc_info=True)
            raise

        try:
            self.session.set_roi(self.fg_acquisition_region)
        except IMAQError as e:
            ms = f" {e.message}\nError: ROI not set correctly"
            self.logger.warning(ms, exc_info=True)

        try:
            self.session.setup_buffers(num_buffers=self.num_img_buffers)
        except IMAQError as e:
            ms = f"{e.message}\nBuffer list not initialized correctly"
            self.logger.error(ms, exc_info=True)
            raise

        # session attributes set in set_roi
        self.last_measurement = np.zeros(
            (
                self.shots_per_measurement,
                self.session.attributes("ROI Width"),
                self.session.attributes("ROI Height")
            ),
            dtype=np.uint16
        )
        self.is_initialized = True
        self.num_images = 0
        self.start()

    def start(self):
        """
        Starts the data acquisition and outputs acquisition status to log
        """

        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return
        # begin asynchronous acquisition
        try:
            self.session.session_acquire(asynchronous=True)
        except IMAQError as e:
            self.logger.error(f"{e.message}\n Error beginning asynchronous acquisition", exc_info=True)
            raise

        try:
            err_c, trig_mode = self.session.hamamatsu_serial("?AMD")
        except IMAQError as e:
            self.logger.warning(e.message)
            trig_mode = "ERROR GETTING TRIG MODE"
        '''
        This function is called in labview and these variables are set (locally?) but they're not used in the scope, 
        just broken out as indicators. I wonder if scope in labview is somehow different from what I imagine
        '''
        try:
            err_c, acquiring, last_buffer_index, last_buffer_number = self.session.status()
        except IMAQError as e:
            self.logger.warning(e.message)
            acquiring = "ERROR GETTING ACQUIRING STATUS"
            last_buffer_number = "ERROR GETTING LAST BUFFER NUMBER"

        self.logger.debug(f"trig mode = {trig_mode}\n"
                          f"acquiring? = {acquiring}\n"
                          f"last buffer acquired image number = {last_buffer_number}")

    def minimal_acquire(self):
        """
        Writes data from session's image buffers to local image array (self.last_measurement)

        Currently reads data from all buffers not previously read. If there is a timing issue then
        number of buffers will not necessarily coincide with the number of shots per measurement.
        Currently user is warned of this scenario through logger but more robust error handling may
        be desired - Juan
        """
        self.measurement_success = False
        if self.stop_connections or self.reset_connection:
            return

        if not self.enable:
            return

        try:
            er_c, session_acquiring, last_buf_ind, last_buf_num = self.session.status()
        except IMAQError as e:
            ms = f"{e.message}\nError Reading out session status during measurement"
            self.logger.error(ms, exc_info=True)
            raise

        bf_dif = last_buf_num - self.last_frame_acquired
        not_enough_buffers = bf_dif > self.num_img_buffers

        self.logger.debug(f"Last Frame : {self.last_frame_acquired}\n"
                          f"New Frame : {last_buf_num}\n"
                          f"Difference : {bf_dif}")
        try:
            assert session_acquiring, "In session.status() NOT acquiring"
        except AssertionError as e:
            self.logger.error(e, exc_info=True)
            raise

        as_ms = "The number of images taken exceeds the number of buffers alloted." + \
                "Images have been lost.  Increase the number of buffers."
        buf_num_ok = last_buf_num != self.last_frame_acquired and not_enough_buffers
        try:
            assert buf_num_ok and last_buf_num != -1, as_ms
        except AssertionError as e:
            self.logger.error(e, exc_info=True)
            raise

        frame_ind = self.last_frame_acquired
        # Warn user of previously silent failure mode.
        if bf_dif != self.shots_per_measurement:
            self.logger.warning(
                f"buffers to be read this measurement : {bf_dif} != "
                f"self.shots_per_measurement : {self.shots_per_measurement}"
            )

        for i in range(bf_dif):
            frame_ind += 1
            self.logger.debug("Acquiring a new available image\n"
                              f" Reading buffer number {frame_ind}")
            try:
                er_c, bf_ind, img = self.session.extract_buffer(frame_ind)
            except IMAQError as e:
                self.logger.error(
                    f"{e.message}\nError acquiring buffer number {frame_ind} measurement abandoned",
                    exc_info=True
                )
                raise
            self.last_measurement[i, :, :] = img

        # Make certain the type is correct before passing this on to CsPy
        self.measurement_success = True
        self.last_measurement = self.last_measurement.astype(np.uint16)
        self.last_frame_acquired = frame_ind
        self.read_camera_temp()

    def read_camera_temp(self):
        """
        Reads the camera temperature, sets self.cameraTemp to the new value
        """
        if self.stop_connections or self.reset_connection:
            return

        if self.enable:
            msg_in = "?TMP"
            try:
                er_c, msg_out = self.session.hamamatsu_serial(msg_in)
            except IMAQError as e:
                self.logger.warning(
                    f"{e.message}\nError reading camera temperature",
                    exc_info=True)
                self.camera_temp = np.inf
                return

            m = re.match(r"TMP (\d+)\.(\d+)", msg_out)
            self.camera_temp = float("{}.{}".format(m.group(1), m.group(2)))

        else:
            self.camera_temp = np.inf

    def data_out(self) -> str:
        """
        Returns a formatted string of relevant hamamatsu data to be written to hdf5 fike
        Returns: formatted data string
        """
        if self.stop_connections or self.reset_connection:
            return ""

        if not self.enable:
            return ""

        # Deal with the case where the last call to minimal acquire was unsuccessful
        if not self.measurement_success:
            return ""

        hm = "Hamamatsu"
        hm_str = ""
        sz = self.last_measurement.shape
        hm_str += TCP.format_data(f"{hm}/numShots", f"{sz[0]}")
        hm_str += TCP.format_data(f"{hm}/rows", f"{sz[1]}")
        hm_str += TCP.format_data(f"{hm}/columns", f"{sz[2]}")

        for shot in range(sz[0]):
            flat_ar = np.reshape(self.last_measurement[shot, :, :], sz[1]*sz[2])
            tmp_str = u16_ar_to_str(flat_ar)
            hm_str += TCP.format_data(f"{hm}/shots/{shot}", tmp_str)

        hm_str += TCP.format_data(f"{hm}/temperature", "{:.3f}".format(self.camera_temp))

        return hm_str


def u16_ar_to_str(ar: np.ndarray) -> str:  # Should the type hint on the return be modified?
    """
    Converts ar to a string encoded as useful for parsing xml messages sent back to cspy

    Args:
        ar : input array. should be 1D ndarray
    Returns:
        string that's parsable by cspy xml reciever
    """
    return struct.pack(f"!{len(ar)}H", *ar)
