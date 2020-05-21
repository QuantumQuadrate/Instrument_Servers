"""
NI_IMAQ c dll wrapping class and session handler for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

Wraps the native NI_IMAQ functions defined in the niimaq.dll file and track the session and
interface data.
"""

from ctypes import *
import logging
import os
from ctypes import c_uint32
from typing import Tuple, Callable, TypeVar
import numpy as np
from recordclass import recordclass as rc
import re


class IMAQError(Exception):
    """
    Exception raised for errors coming from NI IMAQ drivers

    Attributes:
        __error_code : Integer code representing the error state
        __message : message corresponding to code with some traceback info
    """
    def __init__(self,error_code,message):
        self.__error_code = error_code
        self.__message = message

    @property
    def error_code(self):
        return self.__error_code

    @property
    def message(self):
        return self.__message


class NIIMAQSession:

    # Class variables to store constants inside niimaq.h. ==========================================

    # timeout values
    IMG_TIMEOUT_INFINITE = int(0xFFFFFFFF)

    # imgSessionExamineBufferConstants
    IMG_LAST_BUFFER = int(0xFFFFFFFE)
    IMG_OLDEST_BUFFER = int(0xFFFFFFFD)
    IMG_CURRENT_BUFFER = int(0xFFFFFFFC)

    # buffer location specifier
    IMG_HOST_FRAME = 0
    IMG_DEVICE_FRAME = 1

    _IMG_BASE = int(0x3FF60000)

    # Buffer command keys
    IMG_CMD_LOOP = _IMG_BASE + int(0x02)
    IMG_CMD_NEXT = _IMG_BASE + int(0x01)
    IMG_CMD_PASS = _IMG_BASE + int(0x04)
    IMG_CMD_STOP = _IMG_BASE + int(0x08)
    IMG_CMD_INVALID = _IMG_BASE + int(0x10)  # Reserved for internal use in c dll

    BUFFER_COMMANDS = {
        "Loop": IMG_CMD_LOOP,
        "Next": IMG_CMD_NEXT,
        "Pass": IMG_CMD_PASS,
        "Stop": IMG_CMD_STOP,
    }

    # Buffer Element Specifier keys
    IMG_BUFF_ADDRESS = _IMG_BASE + int(0x007E)          # void*
    IMG_BUFF_COMMAND = _IMG_BASE + int(0x007F)          # uInt32
    IMG_BUFF_SKIPCOUNT = _IMG_BASE + int(0x0080)        # uInt32
    IMG_BUFF_SIZE = _IMG_BASE + int(0x0082)             # uInt32
    IMG_BUFF_TRIGGER = _IMG_BASE + int(0x0083)          # uInt32
    IMG_BUFF_NUMBUFS = _IMG_BASE + int(0x00B0)          # uInt32
    IMG_BUFF_CHANNEL = _IMG_BASE + int(0x00Bc)          # uInt32
    IMG_BUFF_ACTUALHEIGHT = _IMG_BASE + int(0x0400)     # uInt32

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
    IMG_ATTR_ROI_WIDTH = _IMG_BASE + int(0x01A66)
    IMG_ATTR_ROI_HEIGHT = _IMG_BASE + int(0x01A76)
    IMG_ATTR_BYTESPERPIXEL = _IMG_BASE + int(0x00666)
    IMG_ATTR_ROI_LEFT = _IMG_BASE + int(0x01A4)
    IMG_ATTR_ROI_TOP = _IMG_BASE + int(0x01A5)
    IMG_ATTR_ACQ_IN_PROGRESS = _IMG_BASE + int(0x0074)
    IMG_ATTR_LAST_VALID_FRAME = _IMG_BASE + int(0x00BA)  # cumulative buffer index (frame #)
    IMG_ATTR_LAST_VALID_BUFFER = _IMG_BASE + int(0x0077)  # Last valid Buffer index

    # dict of img keys corresponding to uint32 variables. Be careful of typing when adding variables
    # to dicts
    IMG_ATTRIBUTES_UINT32 = {
        "ROI Width": IMG_ATTR_ROI_WIDTH,
        "ROI Height": IMG_ATTR_ROI_HEIGHT,
        "Bytes Per Pixel": IMG_ATTR_BYTESPERPIXEL,
        "ROI Left": IMG_ATTR_ROI_LEFT,
        "ROI Top": IMG_ATTR_ROI_TOP,
        "Acquiring": IMG_ATTR_ACQ_IN_PROGRESS,  # Not reliable after the function call
        "Last Frame": IMG_ATTR_LAST_VALID_FRAME,  # Not reliable after the function call
        "Last Buffer Index": IMG_ATTR_LAST_VALID_BUFFER  # Not reliable after the function call
    }

    # Add all keys from ATTRIBUTE dicts to this array
    ATTRIBUTE_KEYS = IMG_ATTRIBUTES_UINT32.keys()

    # Sub array acquisition RecordClasses for TypeHint convenience =================================

    SubArray = rc('SubArray', ('left', 'top', 'width', 'height'))
    FrameGrabberAqRegion = rc('FrameGrabberAqRegion', ('left', 'right', 'top', 'bottom'))

    ROI = TypeVar("ROI", SubArray, FrameGrabberAqRegion)

    def __init__(self):
        self.logger = logging.getLogger(str(self.__class__))

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
        self.buff_list_init = False  # Has the buffer list been created and initialized?

        # dict of values mapped to keys
        self.attributes = {}

    def check(
            self,
            error_code: int,
            traceback_msg: str = None
    ):
        """
        Checks error_code with self.imaq to get out a descriptive error message
        and logs errors or warnings  if operation was unsuccessful. If the
        operation caused an IMAQ error and IMAQError is raised.

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

        if error_code < 0:
            self.logger.error(message)
            raise IMAQError(error_code, message)
        else:
            self.logger.warning(message)

    def open_interface(
            self,
            dev_addr: str,
            check_error: bool = True
    ) -> int:
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
            check_error: bool = True
    ) -> int:
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
            check_error: bool = True
    ) -> int:
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

        # instance variable maintenance
        self.session_id = c_uint32(0)
        if free_resources:
            self.buflist_id = c_uint32(0)
            self.buffers = []
            self.num_buffers = 0
            self.buffer_size = 0
            self.buff_list_init = False

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="close interface")

        return error_code

    def session_configure(
            self,
            check_error: bool = True
    ):
        """
        Configures hardware in preparation for an acquisision using self.buflist_id.

        Upon successfull completion of this call, you can call self.session_aquire()

        wraps imgSessionConfigure()
        Args:
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgSessionConfigure(
            self.session_id,  # SESSION_ID
            self.buflist_id   # BUFLIST_ID
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg=f"session configure"
            )

        return error_code

    def session_acquire(
            self,
            asynchronous: bool,
            callback: Callable[[c_uint32, c_int32, c_uint32, c_void_p], c_uint32] = None,
            check_error: bool = True
    ):
        """
        Starts an acquisition to the buffers in self.buflist_id.

        Acquisition can be started synchronously or asynchronously.

        wraps imgSessionAcquire

        Args:
            asynchronous : asynchronous flag. If False, this function does not return until the
                acquisition completes
            callback : A pointer to a c function that serves as a callback function. If asynchronous
                is True, the callback functiono is called under one of the following two conditions:
                    * If the acquisition is non-continuous, the callback is called when all buffers
                        acquired
                    * If the acquisition is continuous, the callback is called after each buffer
                        becomes available.
                    If None is passed Null will be passed to imgSessionAcquire and no function will
                        be called (and that's very ok)
                    Note : For non-continuous acquisitions, the callback function must return zero.
                    For continuous acquisitions, the return value of the callback function
                    determines the behavior of the driver for subsequent buffer completions. Return
                    zero to disregard future buffer complete notifications. Return a non-zero value
                    to continue to receive callbacks.
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgSessionAcquire(
            self.session_id,
            c_uint32(asynchronous),
            callback
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg=f"session acquire"
            )

    def get_attribute(
            self,
            attribute: str,
            check_error: bool = True
    ) -> int:
        """
        Reads the attribute value and writes it to the appropriate self.attributes key

        wraps imgGetAttribute
        Args:
            attribute : string indicating which attribute to be read, valid values listed in
                NiImaqSession.ATTRIBUTE_KEYS
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """
        assert attribute in self.ATTRIBUTE_KEYS, f"{attribute} not a valid attribute"

        # This should become an elif block to breakout different attribute dicts
        if attribute in self.IMG_ATTRIBUTES_UINT32.keys():
            attr = c_uint32(self.IMG_ATTRIBUTES_UINT32[attribute])
            attr_bf = c_uint32(0)
        else:
            attr = c_void_p(0)
            attr_bf = c_void_p(0)
            print("You should not be here. Is the elif breakout complete?")

        error_code = self.imaq.imgGetAttribute(
            self.session_id,  # SESSION_ID or INTERFACE_ID
            attr,             # uInt32
            byref(attr_bf),   # void*, typing depends on attr
        )

        self.attributes[attribute] = attr_bf

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg=f"get attribute\n attribute : {attribute}")

        return error_code

    def set_attribute2(
            self,
            attribute: str,
            value,
            check_error: bool = True
    ) -> int:
        """
        Sets an attribute value in the imaq c dll and sets the corresponding attribute
        in the self.attributes dict

        wraps imgSetAttribute2()
        Args:
            attribute : string indicating which attribute to be read, valid values listed in
                NiImaqSession.ATTRIBUTE_KEYS

            value (variable type): value to be set to attribute. Typing listed in NiImaqSession
                type list names. Type conversion between python types and c types
                are done internally.
                 e.g : NiImaqSession.IMG_ATTRIBUTES_UINT32 maps attributes stored, set and returned
                    as c_uint32()s. To set one of these attributes using this function pass a python
                    int or any variable which can be safely (and accurately) cast as a c_int32().

            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """
        assert attribute in self.ATTRIBUTE_KEYS, f"{attribute} not a valid attribute"

        if attribute in self.IMG_ATTRIBUTES_UINT32.keys():
            attr = c_uint32(self.IMG_ATTRIBUTES_UINT32[attribute])
            attr_val = c_uint32(value)
        else:
            attr = c_void_p(0)
            attr_val = c_void_p(0)
            print("You should not be here. Is the elif breakout complete?")

        error_code = self.imaq.imgSetAttribute2(
            self.session_id,  # SESSION_ID
            attr,             # uInt32
            attr_val          # variable argument
        )

        self.attributes[attr] = attr_val
        if error_code != 0 and check_error:
            msg = f"set attribute 2\n attribute : {attribute} value : {value}"
            self.check(error_code, traceback_msg=msg)

        return error_code

# Buffer Management function Wrappers --------------------------------------------------------------

    def dispose_buffer(
            self,
            buffer_pt: c_void_p,  # TODO : Not sure this will work? - Juan
            check_error: bool = True
    ) -> int:
        """
        Disposes of the buffer pointed to by buf_addr.

        wraps imgDisposeBuffer

        Args:
            buffer_pt : a pointer to an area of memory that stores the buffer address

            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgDisposeBuffer(
            buffer_pt  # void*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="Dispose Buffer")

        return error_code

    def dispose_buffer_list(
            self,
            free_resources: bool = True,
            check_error: bool = True
    ) -> int:
        """
        Disposes of either buffers created by self.create_buffer_list() and the buffer list
        specified by self.buflist_id, or of only the buffer list

        wraps imgDisposeBufList()
        Args:
            free_resources : Determines whether both the buffers and the buffer list are disposed
                or only the buffer list will be disposed. If True, the function disposes of all
                driver-allocated buffers assigned to this list in addition to the buffer list. If

            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgDisposeBufList(
            self.buflist_id,          # BUFLIST_ID
            c_uint32(free_resources)  # uInt32
        )

        if error_code == 0:
            self.buflist_id = c_uint32(0)
            if free_resources:
                self.buffers = [c_void_p(0)]*self.num_buffers
            self.buff_list_init = False

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="Dispose Buffer List")

        return error_code

    def create_buffer_list(
            self,
            no_elements: int,
            check_error: bool = True
    ) -> int:
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

        if self.buflist_id != c_uint32(0):
            # Make sure buffer list data and memory is cleared safely before making a new one
            self.dispose_buffer_list()

        error_code = self.imaq.imgCreateBufList(
            c_uint32(no_elements),  # uInt32
            byref(self.buflist_id)  # BUFLIST_ID*
        )

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="create_buffer_list")
        if error_code == 0:
            self.num_buffers = no_elements
            self.buffers = [c_void_p(0)]*self.num_buffers  # Initialize a buffer list of a given size

        return error_code

    def create_buffer(
            self,
            system_memory: bool = True,
            buffer_size: int = 0,
            check_error: bool = True
    ) -> Tuple[int, c_void_p]:
        """
        Creates a frame buffer based on the ROI in this session. If bufferSize is 0, the buffer
        size is computed internally as follows:
            [ROI height]x[rowPixels]x[number of bytes per pixel]

        The function returns an error if the buffer size is smaller than the minimum buffer size
        required by the session.

        Appends buffer pointer to end of self.frame_buffers

        Wraps the imgCreateBuffer() function
        Args:
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

        buffer_pt = c_void_p(0)
        error_code = self.imaq.imgCreateBuffer(
            self.session_id,        # SESSION_ID
            where,                  # uInt32
            c_uint32(buffer_size),  # uInt32
            byref(buffer_pt)        # void**
        )

        # self.frame_buffers.append(buffer_pointer) # Not sure we want this yet

        if error_code != 0 and check_error:
            self.check(error_code, traceback_msg="create buffer")

        return error_code, buffer_pt

    def set_buf_element2(
            self,
            element: int,
            item_type: str,
            value: c_uint32,
            check_error: bool = True
    ) -> int:
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
            self.buflist_id,                         # BUFLIST_ID
            c_uint32(element),                       # uInt32
            c_uint32(self.ITEM_TYPES_2[item_type]),  # uInt32
            value                                    # variable argument
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg=f"set_buf_element2\nitem_type :{item_type}\nvalue : {value}"
            )

        return error_code

    def examine_buffer(
            self,
            which_buffer: int,
            check_error: bool = True
    ) -> Tuple[int, int, c_void_p]:
        """
        Extracts an image from a live acquisition.

        This function locks an image out of a continuous loop sequence (continuous loop/ ring
        acquisition) when you are using a ring (continuous) sequence. If the requested image has
        been acquired and exists in memory, the function returns that image immediately. If the
        requested image has not yet been acquired, the function does not return until the image has
        been acquired or the timeout period has expired. If the requested image has already been
        overwritten, the function returns the most current image. If the buffer remains extracted
        long enough that the acquisition hardware wraps around the buffer lis and encounters the
        extracted buffer again, the acquisition will stall, increment the last fram count, and the
        extracted buffer will not be overwritten.

        wraps imgSessionExamineBuffer2

        Args:
            which_buffer : cumulative buffer number of image to extract.
                Pass NiImageSession.IMG_CURRENT_BUFFER to get the buffer that is currently being
                extracted

            check_error : should the check() function be called once operation has completed

        Returns:
            (error_code, bf_num, bf_addr)
                error code : error code which reports status of operation.

                    0 = Success, positive values = Warnings,
                    negative values = Errors
                bf_num : cumulative number of the returned image
                bf_addr : address to locked image buffer
        """

        bf_num = c_uint32(0)
        bf_addr = c_void_p(0)

        error_code = self.imaq.imgSessionExamineBuffer2(
            self.session_id,            # SESSION_ID
            c_uint32(which_buffer),     # uInt32
            bf_num,                     # void*
            byref(bf_addr)              # void**
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg=f"examine_buffer\n"
                              f"buffer index :{which_buffer}\n"
                              f"buffer read : {bf_num.value}"
            )

        return error_code, bf_num.value, bf_addr

    def release_buffer(
            self,
            check_error: bool = True
    ) -> int:
        """
        Releases an image that was previously held with self.examine_buffer.

        This function has the effect of re_entering an image into a continuous ring buffer pool
        after analysis.

        wraps imgSessionReleaseBuffer

        Args:
            check_error : should the check() function be called once operation has completed

        Returns:
            error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        error_code = self.imaq.imgSessionReleaseBuffer(
            self.session_id  # SESSION_ID
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg="release_buffer"
            )

        return error_code

    def session_copy_buffer(
            self,
            buf_index: int,
            wait_for_next: bool,
            check_error: bool = True
    ) -> Tuple[int, np.ndarray]:
        """
        copies session image data to a use buffer

        wraps imgSessionCopyBuffer

        Args:
            buf_index : a valid buffer list index from which to copy
            wait_for_next : if False, the buffer is copied immediately, otherwise the buffer is
                copied once the current acquisition is complete.
            check_error : should the check() function be called once operation has completed

        Returns:
            (error_code, img)
                error_code : error code which reports status of operation.

                    0 = Success, positive values = Warnings,
                    negative values = Errors
                img_array : numpy array of image data in ints
                    if error_code is less than 0, returns None
                    Shape = (self.attributes["Width"], self.attributes["Height"]
        """

        assert buf_index < self.num_buffers, \
            f"buf_index {buf_index} must be less than num_buffers {self.num_buffers}"

        self.compute_buffer_size()  # Make sure our info on size is up to date (should be unnecessary)
        bf_size = self.attributes["ROI Width"]*self.attributes["ROI Height"]
        if self.attributes["Bytes Per Pixel"].value == 8:
            bf_pt = (c_uint8 * bf_size)()
        elif self.attributes["Bytes Per Pixel"].value == 16:
            bf_pt = (c_uint16 * bf_size)()
        elif self.attributes["Bytes Per Pixel"].value == 32:
            bf_pt = (c_uint32 * bf_size)()
        else:
            raise ValueError("I'm not sure how you got here. Good job! - Juan")

        error_code = self.imaq.imgSessionCopyBuffer(
            self.session_id,         # SESSION_ID
            c_uint32[buf_index],     # uInt32
            bf_pt,                   # void*
            c_int32(wait_for_next)  # Int32
        )

        if error_code != 0 and check_error:
            self.check(
                error_code,
                traceback_msg=f"session copy buffer"
            )
        if error_code < 0:
            return error_code, None

        img_array = np.ctypeslib.as_array(bf_pt)
        img_array = np.reshape(
            img_array,
            (self.attributes["ROI Height"].value, self.attributes["ROI Width"].value)
        )
        return error_code, img_array

# Non-Wrapper functions ----------------------------------------------------------------------------

    def status(self) -> Tuple[int, bool, int, int]:
        """
        Returns status information about the acquisition, such as the state of the acquisition and
        the last valid buffer acquired

        Returns:
            error_code, session acquiring, last valid bufffer index, last valid buffer number
                error_code : int
                Session Acquiring : Boolean
                Last Valid Buffer Index: Int, buffer list index of last acquired image
                Last Valid Buffer Number: Int, cumulative number of last acquired image
        """

        er_ret = (True, -1, -1)  # Useless data returned in case of an error when getting attributes
        er_1 = self.get_attribute("Acquiring")
        if er_1 != 0:
            return (er_1,) + er_ret
        er_2 = self.get_attribute("Last Frame")
        if er_2 != 0:
            return (er_2,) + er_ret
        er_3 = self.get_attribute("Last Buffer Index")
        if er_3 != 0:
            return (er_3,) + er_ret

        acquiring = bool(self.attributes["Acquiring"].value)
        last_buffer_index = self.attributes["Last Buffer Index"].value
        last_buffer_number = self.attributes["Last Frame"].value

        return 0, acquiring, last_buffer_index, last_buffer_number

    def compute_buffer_size(self) -> Tuple[int,c_uint32]:
        """
        Sets self.buffer_size to the required size and returns self.buffer_size

        Returns:
            (error_code,bf_size)
            error_code : error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
            bf_size :  size of the image buffer required for acquisition in this session
                in number of bytes needed.

        """

        er_1 = self.get_attribute("Bytes Per Pixel")
        if er_1 != 0:
            return er_1, c_uint32(-1)
        er_2 = self.get_attribute("ROI Width")
        if er_2 != 0:
            return er_2, c_uint32(-1)
        er_3 = self.get_attribute("ROI Height")
        if er_3 != 0:
            return er_3, c_uint32(-1)

        width = self.attributes["ROI Width"]
        height = self.attributes["ROI Height"]
        bytes_per_pix = self.attributes["Bytes Per Pixel"]

        self.buffer_size = width*height*bytes_per_pix
        return 0, self.buffer_size

    def setup_buffers(
            self,
            num_buffers: int
    ):
        """
        Initializes buffer array and buffer list for acquisition
        If all calls to imaq are successful self.buf_list_init should be True, otherwise
        it will be False
        """

        self.create_buffer_list(num_buffers)
        for buf_num in range(self.num_buffers):
            # Based on c ll ring example  -------------------

            self.compute_buffer_size()
            erc, self.buffers[buf_num] = self.create_buffer()
            self.set_buf_element2(
                buf_num,
                "Address",
                self.buffers[buf_num]
            )
            self.set_buf_element2(
                buf_num,
                "Size",
                c_uint32(self.buffer_size)
            )
            if buf_num == self.num_buffers - 1:
                buf_cmd = self.BUFFER_COMMANDS["Loop"]
            else:
                buf_cmd = self.BUFFER_COMMANDS["Next"]
            self.set_buf_element2(
                buf_num,
                "Command",
                c_uint32(buf_cmd)
            )
        self.buff_list_init = True

    def set_roi(
            self,
            roi: ROI,
    ) -> int:
        """
        Sets the session roi based on the aquisition_region dict
        Args:
            roi : recordclass that stores ROI parameters
        Returns:
            error_code : error code which reports status of operation.

                0 = Success, positive values = Warnings,
                negative values = Errors
        """

        msg = repr(type(roi))
        m = re.match(r".*\.(.*)'>", msg)
        if m.group(1) == "FrameGrabberAqRegion":
            width = roi.right - roi.left
            height = roi.bottom - roi.top
        elif m.group(1) == "SubArray":
            width = roi.width
            height = roi.height
        else:
            raise TypeError("Must pass in FrameGrabberAqRegion of SubArray object")
        top = roi.top
        left = roi.left
        self.get_attribute("ROI Width")
        acq_width = self.attributes["ROI Width"]

        self.get_attribute("ROI Height")
        acq_height = self.attributes["ROI Height"]

        if width < acq_width:
            self.set_attribute2("ROI Width", c_uint32(width))

        if height < acq_height:
            self.set_attribute2("ROI Height", c_uint32(height))

        self.set_attribute2("ROI Left", left)

        self.set_attribute2("ROI Top", top)

        return 0

    def extract_buffer(
            self,
            buf_num
    ) -> Tuple[int, int, np.ndarray]:
        """
        Extracts the image data from a buffer during acquisition.

        The buffer is extracted from the acquisition and protected from being overwritten during the
        operation of this function. The buffer data is copied into a numpy array and the buffer is
        reinserted into the buffer list. When this function is called any currently extracted buffer
        is reinserted into the buffer list.

        If the acquisition hardware wraps around the buffer list and encounters the extracted buffer
        while the buffer remains extracted, the acquisition will stall, increment the lost frame
        count, and the extracted buffer is reinserted into the buffer list.
        Args:
            buf_num : cumulative buffer number of image to extract. Pass
                NiImageSession.IMG_CURRENT_BUFFER to get the buffer that is currently being
                extracted
        Returns:
            (error_code, last_buffer, img_array)
                error_code : error code which reports status of operation.

                    0 = Success, positive values = Warnings,
                    negative values = Errors
                last_buffer : cumulative number of the returned image
                img_array : numpy array of image data in ints
                    if error_code les than 0, returns None
                    Shape = (self.attributes["Width"], self.attributes["Height"]
        """

        self.compute_buffer_size()  # to be extra sure certain attributes are set correctly
        pix = self.attributes["ROI Width"] * self.attributes["ROI Height"]

        err_c, last_buffer, img_addr = self.examine_buffer(buf_num)

        if err_c < 0:
            # make sure buffers aren't being held irresponsibly
            self.release_buffer()
            return err_c, last_buffer, None

        if self.attributes["Bytes Per Pixel"] == 8:
            bf_type = c_uint8*pix
        elif self.attributes["Bytes Per Pixel"] == 16:
            bf_type = c_uint16 * pix
        else:  # Assuming these are the only values bytes per pixel can take
            bf_type = c_uint32 * pix
        img_bf = bf_type()

        # Not sure this is the most efficient way of doing this but I could
        # do this on my laptop 10^6 times in 3 sec. Should be fast enough -Juan

        # make a shallow copy of the array as a numpy array
        shallow = np.ctypeslib.as_array(img_addr, shape=pix)
        # make a deep copy
        img_ar = shallow.astype(int)
        # release the buffer, we have the data we need
        self.release_buffer()

        img_ar = np.reshape(img_ar, (self.attributes["ROI Width"], self.attributes["ROI Height"]))
        return err_c, last_buffer, img_ar

    def hamamatsu_serial(
            self,
            command: str,
            expected_response: str = "Nothing",
            timeout: int = 10000,
            check_error: bool = True
    ) -> Tuple[int, str]:
        """
        Writes data to the hamamatsu serial port.

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
            return error_code, "Error"

        str_bf = create_string_buffer(b"", bf_size.value)
        error_code = self.imaq.imgSessionSerialRead(
            self.session_id,  # SESSION_ID
            str_bf,           # void*
            byref(bf_size),   # uInt32*
            c_int32(timeout)  # Int32
        )

        if error_code != 0 and check_error:
            self.check(error_code, f"imaq serial read command {command}")
            return error_code, "Error"

        '''
        Not 100% on why this is here but it's done in the labview. In labview it's added to the 
        error tracker wire. Here I'm just printing(logging) a warning, maybe this should raise an 
        error instead. It should be treated consistently with check() at least
        '''
        enc_rsp = str_bf.value
        if expected_response == "Nothing" or enc_exp_rsp == enc_rsp:
            return error_code, enc_rsp
        er_msg = f"Serial write {command}. Expected Response {enc_exp_rsp}\n Got {enc_rsp}\n"
        self.logger.warning(er_msg)
        return error_code, enc_rsp




