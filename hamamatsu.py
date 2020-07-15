"""
Hamamatsu class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

For parsing XML strings which specify the settings for the Hamamatsu C9100-13
camera and initialization of the hardware of said camera. 
"""

import numpy as np
import xml.etree.ElementTree as ET
from ni_imaq import NIIMAQSession, SubArray, FrameGrabberAqRegion
import re
import struct
from tcp import TCP
from instrument import Instrument
from pxierrors import XMLError, IMAQError, HardwareError


class Hamamatsu(Instrument):
    """
    Class to control the operation of the Hamamatsu camera using the NI IMAQ drivers

    could inherit from a Camera class if we choose to move
    control of other cameras (e.g. Andor) over to this server
    And/or having a parent class would shorten the code here.
    """

    # dictionaries of allowed values for class attributes. note that the key
    # 'Default' has a value which is the key for the default value to be used
    # in the dictionary
    SCAN_MODE_VALUES = {"super pixel": "SMD S", "sub-array": "SMD A",
                        "normal": "SMD N", "default": "normal"}
    FAN_VALUES = {"on": "FAN O", "off": "FAN F", "default": "off"}
    COOLING_VALUES = {"on": "CSW O", "off": "CSW F", "default": "off"}
    EXT_TRIG_SOURCE_VALUES = {"cameralink interface": "ESC I",
                              "multi-timing i/o pin": "ESC M",
                              "bnc on power supply": "ESC B",
                              "default": "bnc on power supply"}
    EXT_TRIG_SOURCE_MODE_VALUES = {"edge": "EMD E",
                                   "synchronous readout": "EMD S",
                                   "level": "EMD L", "default": "level"}
    LL_SENSITIVITY_VALUES = {"5x": "LLS1", "13x": "LLS2", "21x": "LLS3",
                             "off": "LLS 0", "default": "off"}
    SCAN_SPEED_VALUES = {"slow": "SSP S", "middle": "SSP M", "high": "SSP H",
                         "default": "high"}
    TRIG_POLARITY_VALUES = {"negative": "ATP N", "positive": "ATP P",
                            "default": "positive"}

    # Error Codes ----------------------------------------------------------------------------------
    IMG_ERR_BINT = NIIMAQSession.IMG_ERR_BINT  # Invalid interface or session

    def __init__(self, pxi, node: ET.Element = None):
        self.measurement_success = False  # Tracks whether self.last_measurement is useful.

        # Labview Camera variables
        self.is_initialized = False
        self.num_images = 0
        self.camera_roi_file_refnum = 0
        # Labview Hamamatsu variables
        # TODO : @Juan compile descriptions of settings set bellow for ease of use later
        self.enable = False  # called "use camera?" in labview
        self.analog_gain = 0  # 0-5
        self.exposure_time = 0  # can be scientific format
        self.em_gain = 0  # 0-255
        self.trigger_polarity = self.TRIG_POLARITY_VALUES[
            self.TRIG_POLARITY_VALUES["default"]
        ]  # positive by default
        self.external_trigger_mode = self.EXT_TRIG_SOURCE_MODE_VALUES[
            self.EXT_TRIG_SOURCE_MODE_VALUES["default"]
        ]  # level by default
        self.scan_speed = self.SCAN_SPEED_VALUES[self.SCAN_SPEED_VALUES["default"]]
        self.external_trigger_source = self.EXT_TRIG_SOURCE_VALUES[
            self.EXT_TRIG_SOURCE_VALUES["default"]
        ]
        self.scan_mode = self.SCAN_MODE_VALUES[self.SCAN_MODE_VALUES["default"]]
        self.super_pixel_binning = ""  # WHERES. MY. SUPER. SUIT?
        # Uses uint16 in labview, use ints here, cast where necessary
        self.sub_array = SubArray(0, 0, 0, 0)
        self.num_img_buffers = 0  # imageBuffers in labview; renamed by tag name.
        self.shots_per_measurement = 2
        self.images_to_U16 = False
        self.low_light_sensitivity = self.LL_SENSITIVITY_VALUES[
            self.LL_SENSITIVITY_VALUES["default"]
        ]
        self.cooling = self.COOLING_VALUES[self.COOLING_VALUES["default"]]
        self.fan = self.FAN_VALUES[self.FAN_VALUES["default"]]
        # Uses int32 in labview, use ints here, cast where necessary
        self.fg_acquisition_region = FrameGrabberAqRegion(0, 0, 0, 0)
        self.session = NIIMAQSession()
        self.last_frame_acquired = -1
        self.camera_temp: float = 0.0
        # Holds data from previous measurement in 3D array (shots,x,y)
        self.last_measurement = np.array([])

        super().__init__(pxi, "camera", node)

    def load_xml(self, node: ET.Element):
        """
        parse xml by tag to initialize Hamamatsu class attributes

        Args:
            'node': node with tag="camera"
        """
        super().load_xml(node)

        if not (self.exit_measurement or self.stop_connections):

            for child in node:

                if self.exit_measurement or self.stop_connections:
                    break

                try:
                    # handle each tag by name:
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
                        self.exposure_time = float(child.text)

                    elif child.tag == "EMGain":
                        gain = self.str_to_int(child.text)
                        as_ms = f"EMGain is {gain}. EMGain must be between 0 and 255"
                        assert 0 <= gain <= 255, as_ms
                        self.em_gain = gain

                    elif child.tag == "triggerPolarity":
                        self.set_by_dict("trigger_polarity", child.text, self.TRIG_POLARITY_VALUES)

                    elif child.tag == "externalTriggerMode":
                        self.set_by_dict(
                            "external_trigger_mode",
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
                        self.sub_array.left = Instrument.str_to_int(child.text)

                    elif child.tag == "subArrayTop":
                        self.sub_array.top = Instrument.str_to_int(child.text)

                    elif child.tag == "subArrayWidth":
                        self.sub_array.width = Instrument.str_to_int(child.text)

                    elif child.tag == "subArrayHeight":
                        self.sub_array.height = Instrument.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionLeft":
                        self.fg_acquisition_region.left = Instrument.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionTop":
                        self.fg_acquisition_region.top = Instrument.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionRight":
                        self.fg_acquisition_region.right = Instrument.str_to_int(child.text)

                    elif child.tag == "frameGrabberAcquisitionRegionBottom":
                        self.fg_acquisition_region.bottom = Instrument.str_to_int(child.text)

                    elif child.tag == "numImageBuffers":
                        self.num_img_buffers = Instrument.str_to_int(child.text)

                    elif child.tag == "shotsPerMeasurement":
                        self.shots_per_measurement = Instrument.str_to_int(child.text)

                    elif child.tag == "forceImagesToU16":
                        self.images_to_U16 = Instrument.str_to_bool(child.text)

                    else:
                        self.logger.warning(f"Node {child.tag} is not a valid Hamamatsu attribute")

                except (KeyError, ValueError, AssertionError) as e:
                    raise XMLError(self, child, message=f"{e}")

    def init(self):
        """
        initialize the Hamamatsu camera's hardware 
        
        Generates an imaq session and initializes the imaq acquisition parameters, as well as the
        hamamatsu acquisition parameters.

        This function should only be called after load_xml has been called at least once.
        """

        super().init()

        if self.is_initialized:
            self.close()

        try:
            # "img0" really shouldn't be hard-coded but it is in labview so we keep for now
            self.session.open_interface("img0")
            self.session.open_session()
        except IMAQError as e:
            raise HardwareError(self, self.session, e.message)

        # call the Hamamatsu serial function to set the Hamamatsu settings
        try:
            self.session.hamamatsu_serial(self.fan, self.fan)
            self.session.hamamatsu_serial(self.fan, self.fan)
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
            exposure = "AET {:.3f}".format(self.exposure_time)
            self.session.hamamatsu_serial(exposure, exposure)
            # default is to do nothing

            # labview uses "Number to Decimal String VI" to convert the
            # EMGain to a string; as far as I can tell this formatting
            # accomplishes the same thing in this use case
            emgain = f"EMG {self.em_gain}"
            self.session.hamamatsu_serial(emgain, emgain)

            analog_gain = f"CEG {self.analog_gain}"
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

                    sub_array_left = ("SHO " +
                                      str(self.sub_array.left))

                    self.session.hamamatsu_serial(
                        sub_array_left,
                        sub_array_left
                    )

                    sub_array_top = ("SVO " +
                                     str(self.sub_array.top))

                    self.session.hamamatsu_serial(
                        sub_array_top,
                        sub_array_top
                    )

                    sub_array_width = ("SHW " +
                                       str(self.sub_array.width))

                    self.session.hamamatsu_serial(
                        sub_array_width,
                        sub_array_width
                    )

                    sub_array_height = ("SVW " +
                                        str(self.sub_array.height))

                    self.session.hamamatsu_serial(
                        sub_array_height,
                        sub_array_height
                    )

        except IMAQError as e:
            ms = f"{e}\nError writing camera settings. Many camera settings likely not set."
            raise HardwareError(self, self.session, ms)

        try:
            self.session.set_roi(self.fg_acquisition_region)
        except IMAQError as e:
            ms = f" {e}\nError: ROI not set correctly"
            raise HardwareError(self, self.session, ms)

        try:
            self.session.setup_buffers(num_buffers=self.num_img_buffers)
        except IMAQError as e:
            ms = f"{e}\nBuffer list not initialized correctly"
            raise HardwareError(self, self.session, ms)

        # session attributes set in set_roi
        self.last_measurement = np.zeros(
            (
                self.shots_per_measurement,
                self.session.attributes["ROI Width"],
                self.session.attributes["ROI Height"]
            ),
            dtype=np.uint16
        )
        self.is_initialized = True
        self.num_images = 0
        self.logger.info(f"Starting session {self.session}")
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
            ms = f"{e}\n Error beginning asynchronous acquisition"
            self.is_initialized = False
            raise HardwareError(self, self.session, ms)

        try:
            err_c, trig_mode = self.session.hamamatsu_serial("?AMD")
        except IMAQError as e:
            self.logger.warning(e)
            trig_mode = "ERROR GETTING TRIG MODE"
        '''
        This function is called in labview and these variables are set (locally?) but they're not 
        sed in the scope, just broken out as indicators. I wonder if scope in labview is somehow 
        different from what I imagine
        '''
        try:
            err_c, acquiring, last_buffer_index, last_buffer_number = self.session.status()
        except IMAQError as e:
            self.logger.warning(e)
            acquiring = "ERROR GETTING ACQUIRING STATUS"
            last_buffer_number = "ERROR GETTING LAST BUFFER NUMBER"

        self.logger.debug(f"trig mode = {trig_mode}\n"
                          f"acquiring? = {acquiring}\n"
                          f"last buffer acquired image number = {last_buffer_number}")

    def get_data(self):  # name change to comply with name/functionality convention used in pxi.py
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

        self.logger.info("Getting data!")
        try:
            er_c, session_acquiring, last_buf_ind, last_buf_num = self.session.status()
        except IMAQError as e:
            ms = f"{e}\nError Reading out session status during measurement"
            raise HardwareError(self, self.session, ms)

        bf_dif = last_buf_num - self.last_frame_acquired
        not_enough_buffers = bf_dif > self.num_img_buffers

        self.logger.debug(f"Last Frame : {self.last_frame_acquired}\n"
                          f"New Frame : {last_buf_num}\n"
                          f"Difference : {bf_dif}")

        assert session_acquiring, "In session.status() NOT acquiring"

        as_ms = "The number of images taken exceeds the number of buffers allotted." + \
                "Images have been lost.  Increase the number of buffers."
        buf_num_ok = last_buf_num != self.last_frame_acquired and not_enough_buffers
        assert buf_num_ok and last_buf_num != -1, as_ms

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
                ms = f"{e}\nError acquiring buffer number {frame_ind} measurement abandoned"
                raise HardwareError(self, self.session, ms)
            self.last_measurement[i, :, :] = img

        self.measurement_success = True
        # Make certain the type is correct before passing this on to CsPy
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
                    f"{e}\nError reading camera temperature",
                    exc_info=True)
                self.camera_temp = np.inf
                self.is_initialized = False
                return

            m = re.match(r"TMP (\d+)\.(\d+)", str(msg_out))
            try:
                self.camera_temp = float("{}.{}".format(m.group(1), m.group(2)))
            except AttributeError:
                self.camera_temp = np.inf
                self.logger.warning(
                    f"Could not read camera temperature. Returned value = {msg_out}"
                )

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

        try:
            hm = "Hamamatsu"
            hm_str = ""
            sz = self.last_measurement.shape
            hm_str += TCP.format_data(f"{hm}/numShots", f"{sz[0]}")
            hm_str += TCP.format_data(f"{hm}/rows", f"{sz[1]}")
            hm_str += TCP.format_data(f"{hm}/columns", f"{sz[2]}")

            for shot in range(sz[0]):
                if self.measurement_success:
                    flat_ar = np.reshape(self.last_measurement[shot, :, :], sz[1] * sz[2])
                else:
                    # A failed measurement returns useless data of all 0
                    flat_ar = np.zeroes(sz[1]*sz[2])
                tmp_str = u16_ar_to_bytes(flat_ar)
                hm_str += TCP.format_data(f"{hm}/shots/{shot}", tmp_str)

            hm_str += TCP.format_data(f"{hm}/temperature", "{:.3f}".format(self.camera_temp))

        except Exception as e:  # TODO : More specific error handling!
            self.logger.exception(f"Error formatting data from {self.__class__.__name__}")
            raise e

        return hm_str

    def close(self):
        """
        Closes the Hamamatsu Imaq session gracefully
        """
        try:
            self.logger.info(f"Closing session {self.session}")
            self.session.close(check_error=True)
        except IMAQError as e:
            # This error code indicates session/interface is invalid
            if e.error_code == self.IMG_ERR_BINT:
                self.logger.warning(
                    f"tried to close session {self.session} but it probably does not exist"
                )
            else:
                raise HardwareError(self, self.session, e.message)

        self.is_initialized = False


def u16_ar_to_bytes(ar: np.ndarray) -> bytes:
    """
    Converts ar to a string encoded as useful for parsing xml messages sent back to cspy

    Args:
        ar : input array. should be 1D ndarray
    Returns:
        string that's parsable by cspy xml receiver
    """
    return struct.pack(f"!{len(ar)}H", *ar)
