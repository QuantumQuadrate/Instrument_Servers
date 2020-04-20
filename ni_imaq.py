"""
NI_IMAQ c dll wrapping class and session handler for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

Wraps the native NI_IMAQ functions defined in the niimaq.dll file and track the session and
interface data.
"""

from ctypes import *
import os
from typing import Tuple


class FrameBuffer:

    FRAME_LOCATIONS = {"IMG_HOST_FRAME" : c_uint32(0),
                       "IMG_DEVICE_FRAME": c_uint32(1)}

    def __init__(
            self,
            buffer_addr: c_void_p,
            where: c_uint32,
            name: str = None,
    ):
        """
        Initialize the FrameBuffer
        Args:
            buffer_addr : address of memory location on PC or NI device
            where : location of the buffer pointer
                c_uint(0) : IMG_HOST_FRAME = located in PC memory
                c_uint(1) : IMG_DEVICE_FRAME = located in NI device memory
                if where is IMG_DEVICE_FRAME do not attempt to access buffer_addr
            name : name or id to identify the buffer pointer uniquely
        """
        assert where in self.FRAME_LOCATIONS.values()
        self.where = where
        self.buffer_addr = buffer_addr
        self.name = name

    def get_buffer(self):
        """

        Returns:
            either the buffer address pointer corresponding to this

        """
        if self.where == self.FRAME_LOCATIONS["IMG_DEVICE_FRAME"]:
            return None
        return self.buffer_addr.value


class HamamatsuSerialError(Exception):
    """
    Error to deal with Hamamatsu serial writing issues

    TODO : Is this the right way to define this???
    """
    def __init__(self, msg: str):
        """
        Args:
            msg: message tied to this serial error
        """
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class NiImaqSession:

    # timeout values
    IMG_TIMEOUT_INFINITE = int(0xFFFFFFFF, 16)  # found in niimaq.h

    # buffer location specifier
    IMG_HOST_FRAME = c_uint32(0)
    IMG_DEVICE_FRAME = c_uint32(1)

    _IMG_BASE = int(0x3FF60000,16)

    # Buffer command keys
    IMG_CMD_LOOP = _IMG_BASE + int(0x02, 16)
    IMG_CMD_NEXT = _IMG_BASE + int(0x01, 16)
    IMG_CMD_PASS = _IMG_BASE + int(0x04, 16)
    IMG_CMD_STOP = _IMG_BASE + int(0x08, 16)
    IMG_CMD_INVALID = _IMG_BASE + int(0x10, 16)  # Reserved for internal use in c dll

    BUFFER_COMMANDS = {
        "Loop": IMG_CMD_LOOP,
        "Next": IMG_CMD_NEXT,
        "Pass": IMG_CMD_PASS,
        "Stop": IMG_CMD_STOP,
    }

    # Buffer Element Specifier keys
    IMG_BUFF_ADDRESS = _IMG_BASE + int(0x007E, 16)          # void*
    IMG_BUFF_COMMAND = _IMG_BASE + int(0x007F, 16)          # uInt32
    IMG_BUFF_SKIPCOUNT = _IMG_BASE + int(0x0080, 16)        # uInt32
    IMG_BUFF_SIZE = _IMG_BASE + int(0x0082, 16)             # uInt32
    IMG_BUFF_TRIGGER = _IMG_BASE + int(0x0083, 16)          # uInt32
    IMG_BUFF_NUMBUFS = _IMG_BASE + int(0x00B0, 16)          # uInt32
    IMG_BUFF_CHANNEL = _IMG_BASE + int(0x00Bc, 16)          # uInt32
    IMG_BUFF_ACTUALHEIGHT = _IMG_BASE + int(0x0400, 16)     # uInt32

    # Valid for imgGetBufferElement
    ITEM_TYPES = {
        "ActualHeight": IMG_BUFF_ACTUALHEIGHT,
        "Address": IMG_BUFF_ADDRESS,
        "Channel": IMG_BUFF_CHANNEL,
        "Command": IMG_BUFF_COMMAND,
        "Size": IMG_BUFF_SIZE,
        "SkipCount": IMG_BUFF_SKIPCOUNT,
    }
    # Valid for imgSetBufferElement2 and set_buf_element2
    ITEM_TYPES_2 = {
        "Address": IMG_BUFF_ADDRESS,
        "Channel": IMG_BUFF_CHANNEL,
        "Command": IMG_BUFF_COMMAND,
        "Size": IMG_BUFF_SIZE,
        "SkipCount": IMG_BUFF_SKIPCOUNT,
    }

    # Attribute key ===========================================================================
    # Image Attribute keys --------------------------------------------------------------------
    # incomplete, add as they become relevant
    IMG_ATTR_ROI_WIDTH = _IMG_BASE + int(0x01A6, 16)
    IMG_ATTR_ROI_HEIGHT = _IMG_BASE + int(0x01A7, 16)
    IMG_ATTR_BYTESPERPIXEL = _IMG_BASE + int(0x0066, 16)

    # dict of img keys corresponding to uint32 variables. Be careful of typing when adding variables
    # to dicts
    IMG_ATTRIBUTES_UINT32 = {
        "ROI Width": IMG_ATTR_ROI_WIDTH,
        "ROI Height": IMG_ATTR_ROI_HEIGHT,
        "Bytes Per Pixel": IMG_ATTR_BYTESPERPIXEL
    }

    # Add all keys from ATTRIBUTE dicts to this array
    ATTRIBUTE_KEYS = IMG_ATTRIBUTES_UINT32.keys()

    def __init__(self):
        self.imaq = CDLL(os.path.join("C:\Windows\System32", "imaq.dll"))
        self.interface_id = c_uint32(0)
        self.session_id = c_uint32(0)

        '''
        List of frame buffer pointers. It's extremely important that all image buffers created are
        tracked here so that they can be cleared effectively and prevent memory leaks.
        '''
        self.buffers = []
        self.buflist_id = c_uint32(0)
        self.num_buffers = 0
        self.buffer_size = 0
        self.buflist_init = False  # Has the buffer list been created and initialized?

        # dict of values mapped to keys
        self.attributes = {}

    def check(
            self,
            error_code: int,
            traceback_msg: str = None):
        """
        Checks error_code with self.imaq to get out a descriptive error message and prints(logs)
        error/warning  if operation was unsuccessful
        TODO : Proper logging
        TODO : Proper traceback
        TODO : Raise Errors and Warnings where appropriate

        Args:
            error_code : error code which encodes status of operation.
                0 = Success, positive values = Warnings , negative values = Errors
            traceback_msg: message useful for traceback
        """
        if error_code == 0:
            return

        err_msg = c_char_p("".encode('utf-8'))

        self.imaq.imgShowError(
            error_code,  # IMG_ERR
            err_msg)     # char*

        if error_code < 0:
            code_type = "Error Code"
        elif error_code > 0:
            code_type = "Warning Code"
        else:
            code_type = ""
        if traceback_msg is None:
            message = f"{code_type} {error_code} :\n {err_msg}"
        else:
            message = f"{code_type} {error_code} in {traceback_msg}:\n {err_msg}"

        print(message)
        return

    def open_interface(
            self,
            dev_addr: str,
            check_error: bool = True) -> int:
        """
        Opens an ni-imaq interface by name as specified in Measurement & Automation Explorer (MAX).
        If it is successful, this function self.interface_id to a valid INTERFACE_ID

        Args:
            dev_addr : name of the interface to open as it shows up in NI MAX, such as img0, img1,
                and so on.
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        c_addr = c_char_p(dev_addr.encode('utf-8'))
        error_code = self.imaq.imgInterfaceOpen(
            c_addr,                   # char*
            byref(self.interface_id)  # INTERFACE_ID*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="open_interface")

        return error_code

    def open_session(
            self,
            check_error: bool = True) -> int:
        """
        Opens a session and sets a session ID.

        This function inherits all data associated with the given interface.

        if successful sets self.session_id to a valid SESSION_ID

        wraps imgSessionOpen()

        Args:
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgSessionOpen(
            self.interface_id,      # INTERFACE_ID
            byref(self.session_id)  # SESSION_ID*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="open_interface")

        return error_code

    def close(
            self,
            free_resources: bool = True,
            check_error: bool = True) -> int:
        """
        Closes both session and interface, releases all associated resources, and clears all buffers
        if free_resources is set to true.

        Note : I highly recommend keeping free_resources = True. - Juan

        wraps imgClose()

        Args:
            free_resources : should all resources associated with this interface and session be
                freed?
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        # close session
        error_code = self.imaq.imgClose(
            self.session_id,
            free_resources)
        self.session_id = c_uint32(0)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close session")
            return error_code

        # close interface
        error_code = self.imaq.imgClose(
            self.interface_id,
            free_resources)
        self.session_id = c_uint32(0)

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close interface")

        return error_code
# Buffer Management functions ----------------------------------------------------------------------

    def get_attribute(
            self,
            attribute: str,
            check_error: bool = True
    ):
        """
        Reads the attribute value and writes it to the appropriate self.attributes

        wraps imgGetAttribute
        Args:
            attribute : string indicating which attribute to be read
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """
        assert attribute in self.ATTRIBUTE_KEYS, f"{attribute} not a valid attribute"
        # This should become an elif block to breakout different types of attributes
        if attribute in self.IMG_ATTRIBUTES_UINT32.keys():
            attr = c_uint32(self.IMG_ATTRIBUTES_UINT32[attribute])
            attr_bf = c_uint32(0)
        else:
            return None  # to appease pycharm

        error_code = self.imaq.imgGetAttribute(
            self.session_id,  # SESSION_ID or INTERFACE_ID
            attr,             # uInt32
            byref(attr_bf),   # void*
        )

        self.attributes[attribute] = attr_bf

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg=f"get attribute {attribute}")

        return error_code

    def compute_buffer_size(self) -> c_uint32:
        """
        Sets self.buffer_size to the required size and returns self.buffer_size

        Returns:
            c_uint32 - size of the image buffer required for acquisition in this session

        """

        er_1 = self.get_attribute("Bytes Per Pixel")
        if er_1 != 0:
            return er_1
        er_2 = self.get_attribute("ROI Width")
        if er_2 != 0:
            return er_2
        er_3 = self.get_attribute("ROI Height")
        if er_3 != 0:
            return er_3

        width = self.attributes["ROI Width"]
        height = self.attributes["ROI Height"]
        bytes_per_pix = self.attributes["Bytes Per Pixel"]

        self.buffer_size = width*height*bytes_per_pix
        return self.buffer_size

    def dispose_buffer(
            self,
            buf_addr: c_void_p
    ):
        """
        TODO @Juan Finish this up man
        Disposes of the buffer pointed to by buf_addr.

        wraps imgCreateBuffer

        Args:
            buf_addr : a pointer to an area of memory that stores the new buffer address
        Returns:

        """

    def create_buffer_list(
            self,
            no_elements: int,
            check_error: bool = True
    ):
        """
        Creates a buffer list and stores it's location in self.buflist_id. The buffer list must be
        initalized before calling self.session_configure(). Yse self.set_buffer_element()
        to initialize the buffer list.

        Wraps imgCreateBufList()

        Args:
            no_elements : number of elements the created buffer list should contain
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgCreateBufList(
            c_uint32(no_elements),  # uInt32
            byref(self.buflist_id)  # BUFLIST_ID*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="create_buffer_list")
        self.num_buffers = no_elements
        self.buffers = [c_void_p]*self.num_buffers  # Initialize a buffer list of a given size

        return error_code

    def create_buffer(
            self,
            buffer_pt: c_void_p,  # TODO : Not sure this will work? - Juan
            system_memory: bool = True,
            buffer_size: int = 0,
            check_error: bool = True
    ) -> int:
        """
        Creates a frame buffer based on the ROI in this session. If bufferSize is 0, the buffer
        size is computed internally as follows:
            [ROI height]x[rowPixels]x[number of bytes per pixel]

        The function returns an error if the buffer size is smaller than the minimum buffer size
        required by the session.

        Appends buffer pointer to end of self.frame_buffers

        Wraps the imgCreateBuffer() function
        Args:
            buffer_pt : pointer to place in memory that will store the pointer
            system_memory : indicates if the buffer should be stored in system memory or in onboard
                memory on the image acquisition device as specified bellow:
                    True : buffer is created in the host computer memory
                    False : buffer is created in onboard memory. This feature is not available on
                    the NI NI PCI/PXI-1407, NI PCIe-1427, NI PCIe-1429, NI PCIe-1430, NI PCIe-1433,
                    and NI PXIe-1435 devices
            buffer_size : size of the buffer to be created, in bytes.

            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        if system_memory:
            where = self.IMG_HOST_FRAME
        else:
            where = self.IMG_DEVICE_FRAME

        error_code = self.imaq.imgCreateBuffer(
            self.session_id,        # SESSION_ID
            where,                  # uInt32
            c_uint32(buffer_size),  # uInt32
            byref(buffer_pt)   # void**
        )

        # self.frame_buffers.append(buffer_pointer) # Not sure we want this yet

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="create buffer")

        return error_code,buffer_pt

    def set_buf_element2(
            self,
            element: int,
            item_type: str,
            value,
            check_error: bool = True
    ):
        """
        Sets the value for a specified item_type for a buffer in a buffer list

        wraps imgSetBufferElement2()
        Args:
            element : index of element of self.buflist_id to be modified
            item_type : the parameter of the element to set.
                Allowed values:
                "Address" - Specifies the buffer address portion of a buffer list element.
                    data type = void*
                "Channel" - Specifies the channel from which to acquire an image.
                    data type = uInt32
                "Command" - Specifies the command portion of a buffer list element.
                    data type = uInt32
                "Size" - Specifies the size portion of a buffer list element (the buffer size).
                    Required for user-allocated buffers.
                    data type = uInt32
                "Skipcount" - Specifies the skip count portion of a buffer list element.
                    data type = uInt32

            value (variable): data to be written to the element. data type should match the expected
                item type

            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """
        msg = f"{item_type} is not a valid ITEM_TYPE\n valid item types {self.ITEM_TYPES_2.keys()}"
        assert item_type in self.ITEM_TYPES.keys(), msg

        error_code = self.imaq.imgSetBufferElement2(
            self.buflist_id,                       # BUFLIST_ID
            c_uint32(element),                     # uInt32
            c_uint32(self.ITEM_TYPES_2[item_type]),  # uInt32
            value                                  # variable argument
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg=f"set_buf_element2\nitem_type :{item_type}\nvalue : {value}"
            )

        return error_code

    def hamamatsu_serial(
            self,
            command: str,
            expected_response: str = "Nothing",
            timeout: int = 10000,
            check_error: bool = True
    ) -> Tuple[int, str]:
        """
        Writes data to the serial port.

        Serial communication parameters, such as baud rate, are set in the camera file associated
        with the session. You can adjust these communication parameters directly in the camera file.

        Args:
            command : command being written to the Hamamatsu via imaq
            expected_response : expected response from the ni imaq. If camera's response doesn't
                expected_response a warning is printed out.
                TODO : Make this either throw an error or a warning
                If set to "Nothing" no check is performed on the camera's response. Otherwise
            timeout : time, in miliseconds, for imaq to wait or the data to be written.
                Use IMG_TIMEOUT_INFINITE to wait indefinitely
            check_error :

            check_error : should the check() function be called once operation has completed

        Returns:
            [error_code, camera_response]
                error_code : error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
                camera_response : camera's response to command. encoded in utf-8
        """

        # add carriage return, ends all camera serial i/o
        c_cmd = c_char_p(f"{command}\r".encode('utf-8'))
        enc_exp_rsp = f"{expected_response}\r".encode('utf-8')

        bf_size = c_uint32(sizeof(c_cmd))

        error_code = self.imaq.imgSessionSerialWrite(
            self.session_id,   # SESSION_ID
            c_cmd,             # void*
            byref(bf_size),    # uInt32*
            c_int32(timeout),  # uInt32
        )

        if error_code != 0 and check_error:
            self.check(error_code, f"imaq serial write command {command}")
            return error_code

        str_bf = create_string_buffer(b"", bf_size.value)
        error_code = self.imaq.imgSessionSerialRead(
            self.session_id,  # SESSION_ID
            str_bf,           # void*
            byref(bf_size),   # uInt32*
            c_int32(timeout)  # Int32
        )

        '''
        Not 100% on why this is here but it's done in the labview. In labview it's added to the 
        error tracker wire. Here I'm just printing(logging) a warning, maybe this should raise an 
        error instead. It should be treated consistently with check() at least
        '''
        enc_rsp = str_bf.value
        if expected_response == "Nothing" and enc_exp_rsp == enc_rsp:
            return error_code, enc_rsp
        er_msg = f"Serial write {command}. Expected Response {enc_exp_rsp}\n Got {enc_rsp}\n"
        print(er_msg)  # TODO : use logging
        return error_code, enc_rsp




