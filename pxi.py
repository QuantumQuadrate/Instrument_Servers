# general todos:
# TODO: make a return data variable for storing messages from hardware to be 
# sent to CsPy over the return connection

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
        self.return_data = Queue(0) #TODO: this terrible nomenclature, used in labview
        
        self.element_tags = [] # for debugging
        
        # instantiate the device objects
        self.hsdio = HSDIO()
        self.hamamatsu = Hamamatsu()
        #TODO:
        #self.counters = Counters()
        #self.analog_input
        #self.analog_output
        #self.ttl = 

    def launch_experiment_thread(self):
        """
        TODO: make target method for this launcher
        """
        pass

    def launch_network_thread(self):
        self.network_thread = threading.Thread(
            target=self.network_loop,
            name='Network Thread'
        )
        self.network_thread.setDaemon(False)
        self.network_thread.start()
    
    def launch_keylisten_thread(self):
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
        TODO: pop a command from the command queue on each iteration, parse
        the xml in that command, and update the instruments accordingly. 
        TODO: after xml is handled in a particular iteration, send return data
        back to cspy over the TCP connection.
        """
        
        while not self.stop_connections:

            try:
                # dequeue xml; non-blocking
                xml_str = self.command_queue.get(block=False, timeout=0)
                self.parse_xml(xml_str)
                
            except Empty:
                
                #TODO add these variables to constructor
                self.exit_measurement = False
                #self.return_data = [] # reset the list 
                
                if self.cycle_continuously:
                    pass 
                    
                    #TODO: implement this method
                    #self.return_data_queue = self.measurement()
        
    
    def parse_xml(self, xml_str):
        """
        initialize the device instances and other settings from queued xml
        
        loop over highest tier of xml tags with the root tag='LabView' in the 
        message received from CsPy, and call the appropriate device class accordingly. the xml is popped 
        from a queue, which updates in the network_loop whenever a valid 
        message from CsPy is received. 
        
        Args:
            'xml_str': (str) xml received from CsPy in the receive_message method
        """
        
        self.exit_measurement = False
        
        # get the xml root
        root = ET.fromstring(xml_str)
        if root.tag != "LabView":
            self.logger.info("Not a valid msg for the pxi")
            
        else:
            # loop non-recursively over children in root
            for child in root: 
            
                self.element_tags.append(child)
                
                # TODO: some of these are no longer used in current SaffmanLab
                # experiments, and could therefore be removed here.
            
                if child.tag == "measure":
                    if return_data_queue.empty():
                        # if no data ready, take one measurement
                        self.measurement()
                    else:
                        self.return_data = return_data_queue
                        
                if child.tag == "pause":
                    # TODO: set state of server to 'pause';
                    # i don't know if this a feature that currently gets used,
                    # so might be able to omit this. 
                    pass
                    
                if child.tag == "run":
                    # TODO: set state of server to 'run';
                    # i don't know if this a feature that currently gets used,
                    # so might be able to omit this. 
                    pass
                    
                if child.tag == "HSDIO":
                    # set up the HSDIO
                    self.hsdio.load_xml(child)
                    self.hsdio.init()
                    self.hsdio.update()
                    
                if child.tag == "TTL":
                    # TODO: implement TTL class
                    #self.ttl.load_xml(child)
                    #self.ttl.init()
                    pass
                if child.tag == "DAQmxDO":
                    # TODO: implement DAQmxDO class
                    #self.daqmxdo.load_xml(child)
                    #self.daqmxdo.init() # called setup in labview
                    pass
                if child.tag == "timeout":
                    try:
                        # get timeout in [ms]
                        self.measurement_timeout = 1000*float(child.text)
                    except ValueError as e:
                        self.logger.error(f"{e} \n {child.txt} is not valid "+
                                          f"text for node {child.tag}")
                    
                if child.tag == "cycleContinuously":
                    cycle = False
                    if child.text.lower() == "True":
                        cycle = True
                    self.cycle_continuously = cycle
                    
                if child.tag == "camera":
                    # set up the Hamamatsu camera
                    self.hamamatsu.load_xml(child)
                    self.hamamatsu.init()
                    
                if child.tag == "AnalogOutput":
                    # TODO: implement analog_output class
                    # set up the analog_output
                    #self.analog_output.load_xml(child)
                    #self.analog_output.init() # setup in labview
                    #self.analog_output.update()
                    pass
                    
                if child.tag == "AnalogInput":
                    # TODO: implement analog_input class
                    # set up the analog_input
                    #self.analog_input.load_xml(child)
                    #self.analog_input.init() 
                    pass
                    
                if child.tag == "Counters":
                    # TODO: implement counters class
                    # set up the counters
                    #self.counters.load_xml(child)
                    #self.counters.init() 
                    pass
                    
                # might implement, or might move RF generator functionality to
                # CsPy based on code used by Hybrid. 
                if child.tag == "RF_generators":
                    pass
                 
        
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

    
    def on_key_press(self, key):
        """
        Determines what happens for key presses in the command prompt.
        
        This method to be passed into the KeyListener instance to be called 
        when keys are pressed.
        
        Args:
            'key': the returned from msvcrt.getwch(), e.g. 'h'
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
