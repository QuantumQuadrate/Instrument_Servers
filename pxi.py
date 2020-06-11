"""
PXI class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For receiving xml-wrapped messages from CsPy over a TCP/IP connection,
updating the relevant PXI device classes with the parsed xml, and returning
responses from hardware to CsPy. 
"""

"""
general TODOs and ideas:
- reset_connection never gets used here, as far as I can tell. maybe TCP references it?
- there should be a way to re-start the measurement loop after an error is hit.
the best way might be to close the thread running it and call launch_experiment_thread
again 
- could decorate methods like is_done with a timeout method
"""

## modules
import socket
import logging
import threading
import xml.etree.ElementTree as ET
from typing import Tuple
from queue import Queue, Empty
from time import perf_counter_ns

## misc local classes
from keylistener import KeyListener
from pxierrors import XMLError, HardwareError, TimeoutError

## local device classes
from hsdio import HSDIO, HSDIOError
from hamamatsu import Hamamatsu, IMAQError
from tcp import TCP


# TODO : Should this inherit from XMLLoader? <-- i'm on board with this. - Preston
class PXI:
    
    help_str = ("At any time, type... \n" +
                " - \'h\' to see this message again \n" +
                " - \'r\' to reset the connection to CsPy \n" +
                " - \'q\' to stop the connection and close this server.")

    def __init__(self, address: Tuple[str, int]):
        self.logger = logging.getLogger(str(self.__class__))
        self._stop_connections = False
        self._reset_connection = False
        self._stop_measurement = False
        self.cycle_continuously = True
        self.exit_measurement = False
        self.return_data = ""
        self.queued_return_data = ""
        self.measurement_timeout = 0

        self.keylisten_thread = None

        # queues. 0 indicates no maximum queue length enforced.
        self.command_queue = Queue(0)
        self.return_data_queue = Queue(0)

        self.return_data_str = ""  # this seems to exist primarily for debugging

        self.element_tags = []  # for debugging

        # instantiate the device objects
        self.hsdio = HSDIO(self)
        self.tcp = TCP(self, address)
        self.analog_input = AnalogOutput(self)
        self.analog_output = AnalogInput(self)
        self.ttl = TTLInput(self)
        self.daqmx_do = DAQmxDO(self)
        self.hamamatsu = Hamamatsu(self)
        # TODO: implement these classes
        self.counters = None  # Counters()

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
    def stop_measurement(self) -> bool:
        return self._stop_measurement
        
    @stop_measurement.setter
    def stop_measurement(self, value):
        self._stop_measurement = value

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
        Update devices with xml from CsPy and, get and return data from devices

        Pop a command from self.command_queue on each iteration, parse the xml
        in that command, and update the instruments accordingly. When the queue
        is empty, try to receive measurements from the data if cycling
        continuously.

        This function handles the switching between updating devices and
        getting data from them, while the bulk of the work is done in the
        hierarchy of methods in self.parse_xml and self.measurement.
        """

        while not self.stop_connections or self.stop_measurement:
            try:
                # dequeue xml; non-blocking
                xml_str = self.command_queue.get(block=False, timeout=0)
                self.parse_xml(xml_str)

            except Empty:
                self.exit_measurement = False
                self.return_data_str = ""  # reset the list

                if self.cycle_continuously:
                    # This method returns the data as well as updates
                    # 'return_data_str'
                    return_data_str = self.measurement()

    def launch_keylisten_thread(self):
        """
        Launch a KeyListener thread to get key pressses in the command line
        """
        self.keylisten_thread = KeyListener(self.on_key_press)
        self.keylisten_thread.setDaemon(True)
        self.logger.info("starting keylistener")
        self.keylisten_thread.start()

    def parse_xml(self, xml_str):
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
            self.logger.info("Not a valid msg for the pxi")

        else:
            # loop non-recursively over children in root
            for child in root:
            
                self.element_tags.append(child)

                try:
                
                    if child.tag == "measure":
                        if self.return_data_queue.empty():
                            # if no data ready, take one measurement
                            self.measurement()
                        else:
                            # TODO: do something here?
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
                        # set up the HSDIO
                        self.hsdio.load_xml(child)
                        self.hsdio.init()
                        self.hsdio.update()
                        
                    elif child.tag == "TTL":
                        # self.ttl.load_xml(child)
                        # self.ttl.init()
                        pass
                        
                    elif child.tag == "DAQmxDO":
                        # self.daqmxdo.load_xml(child)
                        # self.daqmxdo.init()
                        pass

                    elif child.tag == "timeout":
                        try:
                            # get timeout in [ms]
                            self.measurement_timeout = 1000*float(child.text)
                        except ValueError as e:
                            msg = f"{e} \n {child.text} is not valid "+
                                              f"text for node {child.tag}"
                            raise XMLError(self, msg)

                    elif child.tag == "cycleContinuously":
                        cycle = False
                        if child.text.lower() == "True":
                            cycle = True
                        self.cycle_continuously = cycle

                    elif child.tag == "camera":
                        # set up the Hamamatsu camera
                        self.hamamatsu.load_xml(child)  # Raises ValueError
                        self.hamamatsu.init()  # Raises IMAQErrors

                    elif child.tag == "AnalogOutput":
                        # set up the analog_output
                        # self.analog_output.load_xml(child)
                        # self.analog_output.init() # setup in labview
                        # self.analog_output.update()
                        pass

                    elif child.tag == "AnalogInput":
                        # set up the analog_input
                        # self.analog_input.load_xml(child)
                        # self.analog_input.init()
                        pass

                    elif child.tag == "Counters":
                        # TODO: implement counters class
                        # set up the counters
                        # self.counters.load_xml(child)
                        # self.counters.init()
                        pass

                    # might implement, or might move RF generator functionality to
                    # CsPy based on code used by Hybrid.
                    elif child.tag == "RF_generators":
                        pass

                    else:
                        self.logger.warning(f"Node {child.tag} received is not a valid"+
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
        self.return_data = ""
        self.return_data_queue = Queue(0)

    def data_to_xml(self): # TODO: this does not do what the docstring says. 
        """
        Convert responses from devices to xml and append to self.return_data_str

        This method both returns the xml data as a string, and updates the PXI
        instance variable 'return_data_str', where xml data comes from the
        device classes is_out methods.

        Returns:
            'return_data_str': (str) concatenated string of xml-formatted data
        """

        return_data_str = ""

        # the devices which have a method named 'data_out' which returns a str
        devices = [
            self.hamamatsu, 
            self.counters,
            self.ttl,
            self.analog_input
            # self.demo # not implemented, and debatable whether it needs to be
        ]
        
        for dev in devices:
            if dev.isInitialized: 
                return_data_str += self.dev.data_out()

        return return_data_str

    def measurement(self):
        """
        Return a queue of the acquired responses queried from device hardware

        Returns:
            'return_data_queue': (Queue) the responses received from the device
                classes
        """

        if not (self.stop_connections or self.exit_measurement):
            self.reset_data()
            self.system_checks()
            self.start_tasks()

            _is_done = False
            _is_error = False
           
            ## timed loop to frequently check if tasks are done
            tau = 10 # loop period in [ms]
            scl = 1e-6 # scale factor to convert ns to ms
            t0 = perf_counter_ns() # integer ns. reference point is undefined.             
            while not (_is_done or _is_error or self.stop_connections
                       or self.exit_measurement):
                _is_done = self.is_done()              
                
                # sleep until this iteration has taken at least 1 ms
                while True:
                    dt = perf_counter_ns() - t0
                    if dt*scl > tau: # compare time in ms
                        t0 = perf_counter_ns()
                        break

            self.get_data()
            self.system_checks()
            self.stop_tasks()
            return_data = self.data_to_xml()
            return return_data

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
            
    """
    many of the following methods have a generalizable format, and could easily
    be replaced with a general method which would have the following signature:
    
    device_method_call(device_list: List[Instrument], method_name: str)
    
    this would sacrifice some transparency but would be cleaner and lend to 
    easier implementation of similar methods in the future. thoughts?
    """


    def start_tasks(self):
        """
        Start measurement and output tasks for relevant devices
        """

        if not (self.stop_connections or self.exit_measurement):

            # devices which have a method 'start'
            devices = [
                self.hsdio,
                self.daqmx_do,
                self.analog_input,
                self.analog_output
                # self.counters # TODO: implement Counters.start
            ]
            
            for dev in devices:
                if dev.isInitialized:
                    try: 
                        dev.stop()
                    except HardwareError as e:
                        self.handle_errors(e)
            
            # self.reset_timeout()  # TODO : Implement. we still need to discuss how we want to handle timing

    def stop_tasks(self):
        """
        Stop measurement and output tasks for relevant devices
        """
        
        # devices which have a method 'stop'
        devices = [
            self.hsdio, 
            self.daqmx_do,
            self.analog_input,
            self.analog_output
            # self.counters # TODO: implement Counters.stop
        ]
        
        for dev in devices:
            if dev.isInitialized:
                try: 
                    dev.stop()
                except HardwareError as e:
                    self.handle_errors(e)
                    
                    
    def get_data(self):
        """
        Get data from the devices
        """
    
        if not (self.stop_connections or self.exit_measurement):
        
            try:
                # self.counters.get_data() # TODO: implement
                self.hamamatsu.minimal_acquire()
                self.analog_input.get_data()
            except HardwareError as e:
                self.handle_errors(e)
        

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
                self.daqmx_do
            ]

            try:
                for dev in devices:
                    if dev.isInitialized:
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

    def on_key_press(self, key):
        """
        Determines what happens for key presses in the command prompt.

        This method to be passed into the KeyListener instance to be called
        when keys are pressed.

        Args:
            'key': the returned key from msvcrt.getwch(), e.g. 'h'
        """

        # self.logger.info(f"{key} was pressed")

        if key == 'h':
            self.logger.info(self.help_str)

        if key == 'r':
            self.logger.info("Connection reset by user.")
            self.reset_connection = True

        elif key == 'q':
            self.logger.info("Connection stopped by user. Closing server.")
            # self.keylisten_thread.end()
            self.stop_connections = True

        else:
            self.logger.info("Not a valid keypress. Type \'h\' for help.")

    # This decorator could be a nice way of handling timeouts across this class
    # without the need to put time.time calls explicitly in loops in various
    # methods, although that could be done. This would return a wrapper that
    # would probably have to do something like run the decorated function in
    # a different thread than the timer so it could stop that thread when the
    # time runs out; maybe there's a nicer way to do this. open to suggestions.
    @classmethod
    def master_timeout(func):
        """
        Check if function call in PXI class takes longer than a maximum time

        To be used as a decorator for functions in this class to
        """
        pass

    def handle_errors(self, error, traceback_str=None):
        """
        General Error handling philosophy for errors from instruments:
            Instrument should log any error with a useful message detailing the source of the error
                at the lowest level
            If error should halt instrument activity, error should be raised to pxi class
                Use logger.error(msg,exc_info=True) to log error with traceback
            If error should not halt instrument activity, use logger.warning(msg,exc_info=t/f)
                (t/f = with/without traceback)
            When error is raised to pxi class, this function should be called
            This function should send a message to the terminal output as well as to cspy, warning
                the user that an error has occurred and that the PXI settings should be updated
            The acquisition of data should stop, data sent back should be empty or useless
            Devices which output signals (e.g Analog out, hsdio) should continue to cycle if they
                can
            Self.is_error should be set to True, regular operation can only resume once it is set
                to false when PXI settings have been updated
            
        Essentially everything that Juan describes above has been accomplished, with the exception 
        (hehe) of an 'is_error' attribute. If such a parameter was set, I'm not sure what it would 
        accomplish: the isInitialized parameter gets set to false if the initialization fails. we could 
        that parameter to false in case of a hardware error too, and then the device will not be
        included in subsequent measurement cycles until the error is resolved (of course, the user 
        will know about the error through the detailed logging). Maybe we want to recurringly 
        log an error message until said error has been fixed? that seems annoying. 

        Args:
            error : The error that was raised. Maybe it's useful to keep it around
            traceback_str : string useful for traceback
        """
        
        # NOTE:
        # This code is not a janitor, your mother/father, etc. If your device soiled itself, it is your
        # responsibility to clean up the problem where it occurred. The code that follows is only
        # intended to change the state the of the server and/or log a report of what happened,
        # in response to whatever mess was made. 
            
           
        """
        handle errors according to type. in principle, all errors should be 
        classifiable by these types, or maybe an additional type or two is
        needed. 
        
        In each case, 
        1) log the error message. should include action to be taken
        2) log a message giving the state of the server now (e.g. we'll cycle but w/o the dev. that failed)
        3) anything else that needs to be done
        4) call the function that cycles the exp. 
        """
        
        # maybe there are some cases when we would want to overwrite or add to
        # the detailed message already acquired where the exception arose?
        if traceback_str != None:
            error.message = traceback_str # i'm open to suggestions here
         
        if isinstance(error, XMLError):
            self.logger.error(error.message + "\n Fix the pertinent XML in CsPy, then try again.")
            self.cycle_message(error.device)
            self.reset_exp_thread()
 
        elif isinstance(error, HardwareError):
            self.logger.error(error.message)
            self.cycle_message(error.device)
            self.reset_exp_thread()
            
        elif isinstance(error, TimeoutError):
            # TODO: log and handle timeout error
            pass 
            
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
        self.stop_measurement = True
        self.experiment_thread.join() 
        self.stop_measurement = False
        self.launch_experiment_thread()