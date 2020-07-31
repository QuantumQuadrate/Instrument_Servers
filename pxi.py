"""
PXI class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For receiving xml-wrapped messages from CsPy over a TCP/IP connection,
updating the relevant PXI device classes with the parsed xml, and returning
responses from hardware to CsPy. 
"""

## modules
import logging
import colorlog
import threading
import xml.etree.ElementTree as ET
from typing import Tuple
from queue import Queue, Empty
from time import perf_counter_ns
from typing import List

## misc local classes
from instrument import XMLLoader, Instrument
from keylistener import KeyListener
from pxierrors import XMLError, HardwareError, PXIError

## local device classes
from hsdio import HSDIO
# from hamamatsu import Hamamatsu
from analogin import AnalogInput
from analogout import AnalogOutput
from digitalin import TTLInput
# from digitalout import DAQmxDO
from tcp import TCP


class PXI:
    """
    PXI Class. TODO: write docstring
    
    Attributes:
    
    """
    help_str = ("At any time, type... \n" +
                " - 'h to see this message again \n" +
                " - 'r' to reset the connection to CsPy \n" +
                " - 'd' to toggle the server DEBUG level logging \n" +
                " - 'q' to stop the connection and close this server.")

    def __init__(self, address: Tuple[str, int]):
        self.root_logger = logging.getLogger() # root_logger
        self._root_logging_lvl_default = self.root_logger.level
        self.sh = self.root_logger.handlers[0] # stream_handler
        self._sh_lvl_default = self.sh.level

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler('spam.log')
        fh.setLevel(logging.DEBUG)
        self.logger.addHandler(fh)
        self._stop_connections = False
        self._reset_connection = False
        self._exit_measurement = False
        self.cycle_continuously = False
        self.return_data = b""
        self.return_data_queue = b""
        self.measurement_timeout = 0
        self.keylisten_thread = None
        self.command_queue = Queue(0)  # 0 indicates no maximum queue length enforced.
        self.element_tags = []  # for debugging
        self.devices = []

        # instantiate the device objects
        self.hsdio = HSDIO(self)
        self.tcp = TCP(self, address)
        self.analog_input = AnalogInput(self)
        self.analog_output = AnalogOutput(self)
        self.ttl = TTLInput(self)
        # self.daqmx_do = DAQmxDO(self)
        # self.hamamatsu = Hamamatsu(self)
        # TODO: implement these classes
        # self.counters = None  # Counters()

    @property
    def stop_connections(self) -> bool:
        return self._stop_connections

    @stop_connections.setter
    def stop_connections(self, value):
        self._stop_connections = value

    @property
    def reset_connection(self) -> bool:
        return self._reset_connection

    @reset_connection.setter
    def reset_connection(self, value):
        self._reset_connection = value

    @property
    def exit_measurement(self) -> bool:
        return self._exit_measurement

    @exit_measurement.setter
    def exit_measurement(self, value):
        self._exit_measurement = value

    @property
    def active_devices(self):
        """
        Number of devices that were successfully initialized
        """
        return sum(dev.is_initialized for dev in self.devices)
        
    @property
    def root_logging_lvl_default(self):
        """
        The default root logging level for this server
        """
        return self._root_logging_lvl_default
        
    @property
    def sh_lvl_default(self):
        """
        The default stream handler level for this server
        """
        return self._sh_lvl_default

    def queue_command(self, command):
        self.command_queue.put(command)

    def launch_network_thread(self):
        self.tcp.launch_network_thread()

    def launch_experiment_thread(self):
        """
        Launch a thread for the main experiment loop

        Thread target method = self.command_loop
        """
        self.experiment_thread = threading.Thread(
            target=self.command_loop,
            name='Experiment Thread'
        )
        self.experiment_thread.setDaemon(False)
        self.experiment_thread.start()

    def command_loop(self):
        """
        Update devices with xml from CsPy, and get and return data from devices

        Pop a command from self.command_queue on each iteration, parse the xml
        in that command, and update the instruments accordingly. When the queue
        is empty, try to receive measurements from the data if cycling
        continuously.

        This function handles the switching between updating devices and
        getting data from them, while the bulk of the work is done in the
        hierarchy of methods in self.parse_xml and self.measurement.
        """

        while not (self.stop_connections or self.exit_measurement):
            try:
                # dequeue xml; non-blocking
                xml_str = self.command_queue.get(block=False, timeout=0)
                self.parse_xml(xml_str)

            except Empty:
                self.exit_measurement = False
                self.return_data = b""  # clear the return data

                if self.cycle_continuously and self.active_devices > 0:
                    self.logger.debug("Entering cycle continously...")
                    # This method returns the data
                    self.return_data_queue = self.measurement()

    def launch_keylisten_thread(self):
        """
        Launch a KeyListener thread to get key presses in the command line
        """
        self.keylisten_thread = KeyListener(self.on_key_press)
        self.keylisten_thread.setDaemon(True)
        self.logger.info("starting keylistener")
        self.keylisten_thread.start()

    def parse_xml(self, xml_str: str):
        """
        Initialize the device instances and other settings from queued xml
        
        Loop over highest tier of xml tags with the root tag='LabView' in the 
        message received from CsPy, and call the appropriate device class accordingly. the xml is popped 
        from a queue, which updates in the network_loop whenever a valid 
        message from CsPy is received. 
        
        Args:
            'xml_str': (str) xml received from CsPy in the receive_message method
        """

        self.exit_measurement = False
        self.element_tags = []  # clear the list of received tags

        # get the xml root
        root = ET.fromstring(xml_str)
        if root.tag != "LabView":
            self.logger.warning("Not a valid msg for the pxi")

        else:
            # loop non-recursively over children in root to setup device
            # hardware and other server settings
            for child in root:

                self.element_tags.append(child)

                try:

                    if child.tag == "measure":
                        # if no data available, take one measurement. Otherwise,
                        # use the most recent data.
                        if self.return_data_queue == b"":
                            self.measurement()
                        else:
                            self.return_data = self.return_data_queue
                            pass

                    elif child.tag == "pause":
                        # TODO: set state of server to 'pause';
                        # i don't know if this a feature that currently gets used,
                        # so might be able to omit this.
                        pass

                    elif child.tag == "run":
                        # TODO: set state of server to 'run';
                        # i don't know if this a feature that currently gets used,
                        # so might be able to omit this.
                        pass

                    elif child.tag == "HSDIO":
                        # setup the HSDIO
                        self.hsdio.load_xml(child)
                        self.logger.info("HSDIO XML loaded")
                        self.hsdio.init()
                        self.logger.info("HSDIO hardware initialized")
                        self.hsdio.update()
                        self.logger.info("HSDIO hardware updated")
                        self.logger.info(f"HSDIO.enable = {self.hsdio.enable}")

                    elif child.tag == "TTL":
                        self.ttl.load_xml(child)
                        self.logger.info("TTLInput XML loaded")
                        self.ttl.init()
                        self.logger.info("TTLInput hardware initialized")

                    elif child.tag == "DAQmxDO":
                        # self.daqmx_do.load_xml(child)
                        # self.daqmx_do.init()
                        pass

                    elif child.tag == "timeout":
                        try:
                            # get timeout in [ms]
                            self.measurement_timeout = 1000 * float(child.text)
                        except ValueError as e:
                            msg = f"{e} \n {child.text} is not valid" + \
                                  f"text for node {child.tag}"
                            raise XMLError(self, child, message=msg)

                    elif child.tag == "cycleContinuously":
                        cycle = False
                        if child.text.lower() == "true":
                            cycle = True
                        self.cycle_continuously = cycle

                    elif child.tag == "camera":
                        # set up the Hamamatsu camera
                        # self.hamamatsu.load_xml(child)  # Raises ValueError
                        # self.hamamatsu.init()  # Raises IMAQErrors
                        pass
                    
                    elif child.tag == "AnalogOutput":
                        # set up the analog_output
                        self.analog_output.load_xml(child)
                        self.logger.info("AnalogOutput XML loaded")
                        self.analog_output.init()
                        self.logger.info("AnalogOutput initialized")
                        self.analog_output.update()
                        self.logger.info("AnalogOutput hardware updated")
                    
                    elif child.tag == "AnalogInput":
                        # set up the analog_input
                        self.analog_input.load_xml(child)
                        self.analog_input.init()
                    
                    elif child.tag == "Counters":
                    #     # TODO: implement counters class
                    #     # set up the counters
                    #     # self.counters.load_xml(child)
                    #     # self.counters.init()
                        pass
                    
                    # # might implement, or might move RF generator functionality to
                    # # CsPy based on code used by Hybrid.
                    elif child.tag == "RF_generators":
                        pass

                    else:
                        self.logger.warning(f"Node {child.tag} received is not a valid" +
                                            f"child tag under root <{root.tag}>")

                # I do not catch AssertionErrors. The one at the top of load_xml in every 
                # device class can only occur if the device is passed the wrong xml node, 
                # which can never occur in pxi.parse_xml, as we check the tag before 
                # instantiating a device. those assertions are there in case someone down the 
                # road does something more careless. 
                except (XMLError, HardwareError) as e:
                    self.handle_errors(e)

        # send a message back to CsPy
        self.tcp.send_message(self.return_data)

        # clear the return data
        self.return_data = b""
        self.return_data_queue = b""

    def data_to_xml(self) -> str:
        """
        Get xml-formatted data string from device measurements

        Return the data as an xml string by calling the device class is_out
        methods.

        Returns:
            'return_data': concatenated string of xml-formatted data
        """

        return_data = b""

        # the devices which have a method named 'data_out' which returns a str
        devices = [
            # self.hamamatsu,
            # self.counters, #TODO: implement
            self.ttl,
            self.analog_input
            # self.demo # not implemented, and debatable whether it needs to be
        ]
        
        for dev in devices:
            if dev.is_initialized:
                try:
                    return_data += dev.data_out()
                except HardwareError as e:
                    self.handle_errors(e)

        self.return_data = return_data
        return return_data

    def measurement(self) -> str:
        """
        Return a queue of the acquired responses queried from device hardware

        Returns:
            'return_data': string of concatenated responses received from the
                device classes
        """

        if not (self.stop_connections or self.exit_measurement):
            self.reset_data()
            self.system_checks()
            self.start_tasks()

            _is_done = False
            _is_error = False

            ## timed loop to frequently check if tasks are done
            tau = 10  # loop period in [ms]
            scl = 1e-6  # scale factor to convert ns to ms
            t0 = perf_counter_ns()  # integer ns. reference point is undefined.
            while not (_is_done or _is_error or self.stop_connections
                       or self.exit_measurement):
                try:
                    _is_done = self.is_done()

                except HardwareError as e:
                    self.handle_errors(e)

                # sleep until the outer loop iteration has taken at least 1 ms
                while True:
                    dt = perf_counter_ns() - t0
                    if dt * scl > tau:  # compare time in ms
                        t0 = perf_counter_ns()
                        break

            try:
                self.get_data()
                self.system_checks()
                self.stop_tasks()
                return_data = self.data_to_xml()
                return return_data

            except Exception as e:  # TODO: make less general
                self.logger.warning(f"Error encountered {e}\nNo data returned.")
                self.handle_errors(e)
                return ""

    def reset_data(self):
        """
        Resets data on devices which need to be reset.

        For now, only applies to TTL
        """
        try:
            self.ttl.reset_data()
        except HardwareError as e:
            self.handle_errors(e)

    def system_checks(self):
        """
        Check devices.

        For now, only applies to TTL
        """
        try:
            self.ttl.check()
        except HardwareError as e:
            self.handle_errors(e)

    # wrap batch_method_call calls in convenience functions

    def start_tasks(self, handle_error=True):
        """
        Start measurement and output tasks for relevant devices
        """

        # devices which have a method 'start'
        devices = [
            self.hsdio,
            # self.daqmx_do,
            self.analog_input,
            self.analog_output
            # self.counters # TODO: implement Counters.start
        ]

        self.batch_method_call(devices, 'start', handle_error)
        # self.reset_timeout()  # TODO : Implement or discard

    def stop_tasks(self, handle_error=True):
        """
        Stop measurement and output tasks for relevant devices
        """

        # devices which have a method 'stop'
        devices = [
            self.hsdio,
            # self.daqmx_do,
            self.analog_input,
            self.analog_output
            # self.counters # TODO: implement Counters.stop
        ]

        self.batch_method_call(devices, 'stop', handle_error)
        
    def close_tasks(self, handle_error=True):
        """
        Close references to tasks for relevant devices
        """

        # devices which have a method 'stop'
        devices = [
            self.hsdio,
            # self.daqmx_do,
            self.analog_input,
            self.analog_output,
            self.ttl
            # self.counters # TODO: implement Counters.stop
        ]

        self.batch_method_call(devices, 'close', handle_error)

    def get_data(self, handle_error=True):
        """
        Get data from the devices
        """

        # devices which have a method 'get_data'
        devices = [
            # self.hamamatsu,
            self.analog_input,
            # self.counters  # TODO: implement Counters.get_data
        ]

        self.batch_method_call(devices, 'get_data', handle_error)

    def is_done(self) -> bool:
        """
        Check if devices running processes are done yet

        Loops over the device classes and calls the instance's is_done method
        for each device capable of running a process and breaks when a process
        is found to not be done.

        Returns:
            done
                'done': will return True iff all the device processes are done.
        """

        done = True
        if not (self.stop_connections or self.exit_measurement):

            # devices which have a method named 'is_done' that returns a bool
            devices = [
                self.hsdio,
                self.analog_output,
                self.analog_input,
                # self.daqmx_do
            ]

            try:
                for dev in devices:
                    if dev.is_initialized:
                        if not dev.is_done():
                            done = False
                            break
            except HardwareError as e:
                self.handle_errors(e)
                return done

        return done

    def reset_timeout(self):
        """
        Seems to change a global variable 'Timeout Elapses at' to the current time + timeout
        Will that work here?
        Returns:

        """
        # TODO: Implement
        pass

    def on_key_press(self, key: str):
        """
        Determines what happens for key presses in the command prompt.

        This method to be passed into the KeyListener instance to be called
        when keys are pressed.

        Args:
            'key': the returned key from msvcrt.getwch(), e.g. 'h'
        """

        if key == 'h': # show the help str
            self.logger.info(self.help_str)

        if key == 'r': # reset the connection
            self.logger.info("Connection reset by user.")
            self.reset_connection = True

        if key == 'd': # toggle debug/info level root logging
            if self.root_logger.level != logging.DEBUG:
                self.root_logger.setLevel(logging.DEBUG)
            else:
                self.root_logger.setLevel(self.root_logging_lvl_default)
                self.logger.info("set the root level logging to default")
                
            if self.sh.level != logging.DEBUG:
                self.sh.setLevel(logging.DEBUG)
            else:
                self.sh.setLevel(self.sh_lvl_default)
                self.logger.info("set the stream handler level logging to default")
                
            self.logger.debug("Logging level is now DEBUG")

            
        elif key == 'q':
            self.logger.info("Connection stopped by user. Closing server.")
            self.stop()

        else:
            self.logger.info("Not a valid keypress. Type \'h\' for help.")

    def handle_errors(self, error: Exception, traceback_str: str = ""):
        """
        Handle errors caught in the PXI instance

        Error handling philosophy:
            I. The class where the error originated should log a useful
                message detailing the source of the error
            II. If error should halt instrument activity, error should be raised
                to pxi class. Use logger.error(msg,exc_info=True) to log error
                with traceback.
            III. If error should not halt instrument activity, use
                logger.warning(msg,exc_info=t/f) (t/f = with/without traceback)
            IV. When error is raised to pxi class, this function should be
                called. A message will be logged to the terminal output as well
                as sent to CsPy, warning the user that an error has occurred
                and that the PXI settings should be updated.
            V. The current measurement cycle should be aborted, and restarted
                if self.cycle_continuously == True. Device where error occurred
                should be excluded from the measurement cycle until it has been
                reinitialized. I.e., devices which read/write signals (e.g.
                TTLInput, HSDIO, etc) should continue to cycle if they can
            VI. The errors raised in the device classes can should be classified
                coarsely, as many errors should result in the same handling
                behavior in this function (e.g. all error types pertaining to an XML
                initialization failure should result in a message urging the user to
                check the XML in CsPy and reinitialize the device). Specific
                error types handled here are HardwareError and XMLError, defined
                in pxierrors.py

        Args:
            error : The error that was raised. Maybe it's useful to keep it around
            traceback_str : string useful for traceback
        """

        # NOTE:
        # This code is not a janitor, your mother/father, etc. If your device soiled itself, it is your
        # responsibility to clean up the problem where it occurred. The code that follows is only
        # intended to change the state the of the server and/or log a report of what happened,
        # in response to whatever mess was made.

        
        self.logger.warning("PXIError encountered. Closing the problematic tasks.")
        
        if isinstance(error, XMLError):
            self.logger.error(traceback_str + "\n" + error.message + "\n" +
                              "Fix the pertinent XML in CsPy, then try again.")
            self.cycle_message(error.device)
            self.reset_exp_thread()

        elif isinstance(error, HardwareError):
            self.logger.error(traceback_str + "\n" + error.message)
            self.cycle_message(error.device)
            self.stop_tasks(handle_error=False)  # stop all current measurement tasks
            error.device.close() # close the reference to the problematic device
            self.reset_exp_thread() # this stalls the program currently

        # If not a type of error we anticipated, raise it.
        # else:
            # raise error

    def cycle_message(self, dev: XMLLoader):
        """
        Log a message about the status of the server cycling. 
        
        Args:
            dev: the device instance where the problem occurred
        """
        if self.cycle_continuously:
            self.logger.warning(f"The server will now cycle, but without {dev}")
        else:
            self.logger.info(f"The server is not taking data. Cycle continuously to resume, but without {dev}")

    def reset_exp_thread(self):
        """
        Restart experiment thread after current measurement ends
        """
        # self.logger.info("Waiting for the experiment thread to end...")
        # self.exit_measurement = True
        # while self.experiment_thread.is_alive():
            # pass
        # self.experiment_thread.join()
        self.logger.info("Restarting current experiment thread...")
        self.exit_measurement = False
        
        # overwrite the existing thread ref. might be a better way to do this.
        self.launch_experiment_thread() 
        self.logger.info("Experiment thread relaunched")

    def batch_method_call(
            self,
            device_list: List[Instrument],
            method: str,
            handle_error: bool = True
    ):
        """
        Call a method common to several device classes

        Given a list of device instances, assumed to have method 'method' as
        well as bool parameter 'is_initialized', 'method' will be called for
        each instance.

        For now, it is assumed that 'method' takes no arguments, and does
        does not return anything.

        Args:
            device_list: list of device instances
            method: name of the method to be called. make sure every device
                in device list has a method with this name.
            handle_error: Should self.handle_errors() be called to deal with
                errors during this operation?
        """

        # only iterate over initialized devices
        for dev in filter(lambda x: x.is_initialized, device_list):
            try:
                getattr(dev, method)()  # call the method
            except AttributeError as ae:
                self.logger.exception(ae)
                self.logger.warning(f'{dev} does not have method \'{method}\'')
            except HardwareError as he:
                self.logger.info(
                    f"Error {he} encountered while performing {dev}.{method}()"
                    f"handle_error = {handle_error}")
                if handle_error:
                    self.handle_errors(he)

    def stop(self):
        """
        Nicely shut down this server
        """
        self.logger.info(f"The following devices will be stopped: {self.devices}")
        self.stop_tasks()
        self.close_tasks()
        self.exit_measurement = True
        self.tcp.stop_connections = True

        # self.experiment_thread.join()
        # experiment_thread is the only user thread; other threads are daemon.