"""
PXI class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Cody Poole, Preston Huft

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
from hamamatsu import Hamamatsu


class PXI:
    
    help_str = ("At any time, type... \n"+
	            " - \'h\' to see this message again \n"+
				" - \'r\' to reset the connection to CsPy \n"+
				" - \'q\' to stop the connection and close this server.")

    def __init__(self, address: Tuple[str, int]):
        self.logger = logging.getLogger(str(self.__class__))
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind(address)
        self.listening_socket.listen()

        self.stop_connections = False
        self.reset_connection = False
        self.current_connection = None
        self.cycle_continuously = True
        self.exit_measurement = False
        self.last_received_xml = ""

        self.network_thread = None
        self.keylisten_thread = None
        
        # queues. 0 indicates no maximum queue length enforced.
        self.command_queue = Queue(0) 
        self.return_data_queue = Queue(0)
        
        self.return_data_str = "" # this seems to exist primarily for debugging
        
        self.element_tags = [] # for debugging
        
        # instantiate the device objects
        self.hsdio = HSDIO()
        self.hamamatsu = Hamamatsu()
        # TODO: implement these classes
        #self.counters = Counters()
        #self.analog_input = AnalogOutput()
        #self.analog_output = AnalogInput()
        #self.ttl = TTL()

    def launch_experiment_thread(self):
        """
        Launch a thread for the main experiment loop

        Thread target method = self.command_loop
        """
        self.experiment_thread = threading.Thread(
            target=self.commmand_loop,
            name='Experiment Thread'
        )
        self.experiment_thread.setDaemon(False)
        self.experiment_thread.start()


    def launch_network_thread(self):
        self.network_thread = threading.Thread(
            target=self.network_loop,
            name='Network Thread'
        )
        self.network_thread.setDaemon(False)
        self.network_thread.start()

    
    def launch_keylisten_thread(self):
        """
        Launch a KeyListener thread to get key pressses in the command line
        """
        self.keylisten_thread = KeyListener(self.on_key_press)
        self.keylisten_thread.setDaemon(True)
        self.logger.info("starting keylistener")
        self.keylisten_thread.start()


    def network_loop(self):
        """
        Check for incoming connections and messages on those connections
        """

        self.logger.info("Entering Network Loop")
        while not self.stop_connections:
            self.reset_connection = False
            
            #TODO: entering q in cmd line should terminate this process
            self.current_connection, client_address = self.listening_socket.accept()
            self.logger.info(f"Started connection with {client_address}")
            while not (self.reset_connection or self.stop_connections):
                try:
                    self.receive_message()
                except socket.timeout:
                    pass
            self.logger.info(f"Closing connection with {client_address}")
            self.current_connection.close()
            self.current_connection.shutdown()
        

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

                #TODO add these variables to constructor
                self.exit_measurement = False
                self.return_data_str = "" # reset the list 
                
                if self.cycle_continuously:

                    # This method returns the data as well as updates 
                    # 'return_data_str', so having a return in this method
                    # seems uneccesary
                    return_data_str = self.measurement()
        
    
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
        self.element_tags = [] # clear the list of received tags
        
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
                        #self.return_data_str = str(return_data_queue
                        
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
                    # TODO: implement TTL class
                    #self.ttl.load_xml(child)
                    #self.ttl.init()
                    pass
                elif child.tag == "DAQmxDO":
                    # TODO: implement DAQmxDO class
                    #self.daqmxdo.load_xml(child)
                    #self.daqmxdo.init() # called setup in labview
                    pass
                elif child.tag == "timeout":
                    try:
                        # get timeout in [ms]
                        self.measurement_timeout = 1000*float(child.text)
                    except ValueError as e:
                        self.logger.error(f"{e} \n {child.txt} is not valid "+
                                          f"text for node {child.tag}")
                    
                elif child.tag == "cycleContinuously":
                    cycle = False
                    if child.text.lower() == "True":
                        cycle = True
                    self.cycle_continuously = cycle
                    
                elif child.tag == "camera":
                    # set up the Hamamatsu camera
                    self.hamamatsu.load_xml(child)
                    self.hamamatsu.init()
                    
                elif child.tag == "AnalogOutput":
                    # TODO: implement analog_output class
                    # set up the analog_output
                    #self.analog_output.load_xml(child)
                    #self.analog_output.init() # setup in labview
                    #self.analog_output.update()
                    pass
                    
                elif child.tag == "AnalogInput":
                    # TODO: implement analog_input class
                    # set up the analog_input
                    #self.analog_input.load_xml(child)
                    #self.analog_input.init() 
                    pass
                    
                elif child.tag == "Counters":
                    # TODO: implement counters class
                    # set up the counters
                    #self.counters.load_xml(child)
                    #self.counters.init() 
                    pass
                    
                # might implement, or might move RF generator functionality to
                # CsPy based on code used by Hybrid. 
                elif child.tag == "RF_generators":
                    pass
                    
                else:
                    logger.warning(f"Node {child.tag} received is not a valid"+
                                   f"child tag under root <{root.tag}>")
                 
        # TODO: some sort of error handling. could have several try/except 
        # blocks in the if/elifs above
        
        # TODO: implement send message
        # send a message back to CsPy
        self.send_message()
        
        # clear the return data
        self.return_data_str = ""
        self.return_data_queue = Queue(0)
        
    def receive_message(self):
        """
        listens for a message from cspy over the network.

        messages from cspy are encoded in the following way:
            message = 'MESG' + str(len(body)) + body

        """
        # Read first 4 bytes looking for a specific message header
        self.current_connection.settimeout(0.3)
        header = self.current_connection.recv(4)
        self.logger.info(f"header was read as {header}")
        if header == b'MESG':
            self.logger.info("We got a message! now to handle it.")
            # Assume next 4 bytes contains the length of the remaining message
            length_bytes = self.current_connection.recv(4)
            length = int.from_bytes(length_bytes, byteorder='big')
            self.logger.info(f"I think the message is {length} bytes long.")
            self.current_connection.settimeout(20)
            message = self.current_connection.recv(length)
            if len(message) == length:
                self.logger.info("message received with expected length.")
                self.last_received_xml = message
                
                # add message to queue; blocking if queue full, but max queue
                # size set to infinite so blocking shouldn't ever occur
                self.command_queue.put(message)

            else:
                self.logger.info(f"Something went wrong,"
                                 f" I only found {len(message)} bytes to read!")
        else:
            self.logger.info("We appear to have received junk. Clearing buffer.")
            self.current_connection.settimeout(0.01)
            try:
                while not (self.reset_connection or self.stop_connections):
                    if self.current_connection.recv(4096) == "":
                        break
            except socket.timeout:
                pass
            finally:
                self.reset_connection = True
                
        
    def send_message(self, msg_str=None):
        # if msg_str is none, just send the return data?        
        pass

    # This method returns the data as well as updates 
    # 'return_data_str', so having a return seems 
    # uneccesary
    @master_timeout()
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

        # the devices that have a data_out method
        data_spawns = [self.hamamatsu, self.counter, self.ttl, 
                       self.analog_input]

        for spawn in data_spawns:
            # TODO: implement data_out methods in the relevant classes
            self.return_data_str += spawn.data_out()

        return return_data_str

            
    @master_timeout()
    def measurement(self):
        """
        Return a queue of the acquired responses queried from device hardware
        
        Returns:
            'return_data_queue': (Queue) the responses received from the device
                classes
        """
        
        if not (self.stop_connections or self.exit_measurement):

            # TODO: implement these methods
            self.reset_data()
            self.system_check()
            self.start_tasks()

            _is_done = False
            _is_error = False
            # TODO:labview uses timed loop with 1kHz clock and dt=10 ms. 
            # loop until pulse output is completed
            while not (_is_done or _is_error or self.stop_connections 
                       or self.exit_measurement):
                
                _is_done, error_out = self.is_done()
                #_is_error = error_out["IsError?"] # TODO implement somehow

            self.get_data() # TODO: implement 
            self.system_checks() # TODO: implement 
            self.stop_tasks() # TODO: implement 
            self.data_to_xml()

    
    def get_data(self):
        pass


    def reset_data(self):
        pass


    def system_check(self):
        pass


    def start_tasks(self):
        pass


    @master_timeout()
    def is_done(self):
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

            devices = [self.hsdio, self.analog_ouput, self.analog_input]#, 
                       #self.daqmx_pulseout] # in labview daqmx_pulseout is 
                                             # distinct from the DAQmxDO class
            
            # loop over devices which have is_done method; could generalize to
            # explicitly listing devices above, but this is more transparent
            for dev in devices:
                pass
                #TODO implement is_done method in the relevant device classes
                #if not dev.is_done():
                #    done = False
                #    break
        return done

   
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
