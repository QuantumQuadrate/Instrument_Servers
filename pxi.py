"""
PXI class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

For receiving xml-wrapped messages from CsPy over a TCP/IP connection,
updating the relevant PXI device classes with the parsed xml, and returning
responses from hardware to CsPy. 
"""

'''
general TODOs and ideas:
- could decorate methods like is_done with a timeout method
- could implement error handling and checking whether connection has been 
    stopped or restarted with a decorator
- error object to bundle exception/error message returned with a boolean? 
    would be useful in loops that should exit on exception raised
'''

#### modules
import socket
import logging
import threading
import xml.etree.ElementTree as ET
from typing import Tuple
from queue import Queue, Empty

#### misc local classes
from keylistener import KeyListener

#### local device classes
from hsdio import HSDIO
#from hamamatsu import Hamamatsu
from tcp import TCP


class PXI:
    
    help_str = ("At any time, type... \n"+
	            " - \'h\' to see this message again \n"+
				" - \'r\' to reset the connection to CsPy \n"+
				" - \'q\' to stop the connection and close this server.")

    def __init__(self, address: Tuple[str, int]):
        self.logger = logging.getLogger(str(self.__class__))
        self._stop_connections = False
        self._reset_connection = False
        self.cycle_continuously = True
        self.exit_measurement = False

        self.keylisten_thread = None

        # queues. 0 indicates no maximum queue length enforced.
        self.command_queue = Queue(0)
        self.return_data_queue = Queue(0)

        self.return_data_str = ""  # this seems to exist primarily for debugging

        self.element_tags = []  # for debugging

        # instantiate the device objects
        self.hsdio = HSDIO(self)
        self.tcp = TCP(self, address)
        self.hamamatsu = Hamamatsu()
        self.analog_input = AnalogOutput(self)
        self.analog_output = AnalogInput(self)
        self.ttl = TTLInput(self)
        self.daqmx_do = DAQmxDO(self)
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
        in that command, and update the instruments accordingly. When th queue
        is empty, try to receive measurements from the data if cycling
        continuously.

        This function handles the switching between updating devices and
        getting data from them, while the bulk of the work is done in the
        hierarchy of methods in self.parse_xml and self.measurment.
        """

        while not self.stop_connections:
            try:
                # dequeue xml; non-blocking
                xml_str = self.command_queue.get(block=False, timeout=0)
                self.parse_xml(xml_str)

            except Empty:
                # TODO add these variables to constructor
                self.exit_measurement = False
                self.return_data_str = ""  # reset the list

                if self.cycle_continuously:
                    # This method returns the data as well as updates
                    # 'return_data_str', so having a return in this method
                    # seems uneccesary
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

                if child.tag == "measure":
                    if self.return_data_queue.empty():
                        # if no data ready, take one measurement
                        self.measurement()
                    else:
                        pass
                        # Cast return_data_queue to a string? in labview the
                        # global "Return Data" is simply assigned the value of
                        # "Return Data Queue", despite the fact that the latter
                        # is a Queue instance and the former is filled elsewhere
                        # with a string built from concatenated xml.
                        #
                        # self.return_data_str = str(return_data_queue

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
                    # self.hsdio.load_xml(child)
                    # self.hsdio.init()
                    # self.hsdio.update()
                    pass
                elif child.tag == "TTL":
                    # self.ttl.load_xml(child)
                    # self.ttl.init()
                    pass
                elif child.tag == "DAQmxDO":
                    # self.daqmxdo.load_xml(child)
                    # self.daqmxdo.init() # called setup in labview
                    pass
                elif child.tag == "timeout":
                    try:
                        # get timeout in [ms]
                        self.measurement_timeout = 1000 * float(child.text)
                    except ValueError as e:
                        self.logger.error(f"{e} \n {child.txt} is not valid " +
                                          f"text for node {child.tag}")

                elif child.tag == "cycleContinuously":
                    cycle = False
                    if child.text.lower() == "True":
                        cycle = True
                    self.cycle_continuously = cycle

                elif child.tag == "camera":
                    pass
                    # set up the Hamamatsu camera
                    # self.hamamatsu.load_xml(child)
                    # self.hamamatsu.init()

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
                    self.logger.warning(f"Node {child.tag} received is not a valid" +
                                        f"child tag under root <{root.tag}>")

        # TODO: some sort of error handling. could have several try/except
        # blocks in the if/elifs above

        # TODO: implement send message
        # send a message back to CsPy
        self.tcp.send_message()

        # clear the return data
        self.return_data_str = ""
        self.return_data_queue = Queue(0)

    def data_to_xml(self):
        """
        Convert responses from devices to xml and append to self.return_data_str

        This method both returns the xml data as a string, and updates the PXI
        instance variable 'return_data_str', where xml data comes from the
        device classes is_out methods.

        Returns:
            'return_data_str': (str) concatenated string of xml-formatted data
        """

        return_data_str = ""

        '''
        Once all data_out methods are implemented, could do something like this:
        
        # the devices that have a data_out method
        data_devices = [self.counters, self.ttl, self.analog_input]

        for dev in data_devices:
            try:
                self.return_data_str += dev.data_out()
            except Exception as e:
                self.logger.error(f"encountered error in {dev}.data_out: \n {e}")
        '''
        
        
        #return_data_str += self.hamamatsu.data_out()  # TODO : Implement
        return_data_str += self.counters.data_out()
        return_data_str += self.ttl.data_out()
        return_data_str += self.analog_input.data_out()
        #return_data_str += self.demo.data_out()  # TODO : Implement

        return return_data_str

    def measurement(self):
        """
        Return a queue of the acquired responses queried from device hardware

        Returns:
            'return_data_queue': (Queue) the responses received from the device
                classes
        """

        return_data = ""
        if not (self.stop_connections or self.exit_measurement):
            self.reset_data()
            self.system_checks()
            self.start_tasks()  # TODO : Implement

            _is_done = False
            _is_error = False
            # TODO : labview uses timed loop with 1kHz clock and dt=10 ms.
            # How precise does this loop need to be?
            # loop until pulse output is completed
            while not (_is_done or _is_error or self.stop_connections
                       or self.exit_measurement):
                _is_done, error_out = self.is_done()
                # _is_error = error_out["IsError?"] # TODO implement somehow

            self.get_data()
            self.system_checks()
            self.stop_tasks()  # TODO: implement
            return_data = self.data_to_xml()
        return return_data

    def reset_data(self):
        """
        Resets data on devices which need to be reset.

        For now, only applies to TTL
        """
        self.ttl.reset_data() 

    def system_checks(self):
        """
        Check devices. 
        
        For now, only applies to TTL
        """
        self.ttl.check() 

    def start_tasks(self):
        """
        Start measurement and output tasks for relevant devices
        """
        # self.counters.start()  # TODO : Implement
        self.daqmx_do.start()  
        self.hsdio.start()  
        self.analog_input.start()
        self.analog_output.start()
        # self.reset_timeout()  # TODO : Implement. need to discuss how we want to handle timing

    def stop_tasks(self):
        """
        Stop measurement and output tasks for relevant devices
        """
        # self.counters.stop()  # TODO : Implement
        self.hsdio.stop()  
        self.daqmx_do.stop()
        self.analog_input.stop()
        self.analog_output.stop() 

    def get_data(self):
        # self.counters.get_data()
        # self.hamamatsu.minimal_acquire()  # TODO : Implement
        self.analog_input.get_data()

    def is_done(self) -> bool:
        """
        Check if devices running processes are done yet

        Loops over the device classes and calls the instance's is_done method
        for each device capable of running a process and breaks when a process
        is found to not be done.

        Returns:
            'done': will return True iff all the device processes are done.
        """

        done = True
        if not (self.stop_connections or self.exit_measurement):
            devices = [
                self.hsdio, 
                self.analog_output, 
                self.analog_input, 
                self.daqmx_do]

            # loop over devices which have is_done method
            for dev in devices:
                if not dev.is_done():
                   done = False
                   break
                   
        return done, 0 # why is there a zero here?

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