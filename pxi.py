# general todos:
# TODO: make a command queue for storing messages received from CsPy
# TODO: make a return data variable for storing messages from hardware to be 
# sent to CsPy over the return connection

import socket
from typing import Tuple
import logging
import threading


class PXI:

    def __init__(self, address: Tuple[str, int]):
        self.logger = logging.getLogger(str(self.__class__))
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind(address)
        self.listening_socket.listen()

        # TODO: Make a method to change stop_connections and reset_connections
        # TODO: These are the backend variables normally adjusted by clicking on the GUI
        # TODO: In the LabVIEW program
        self.stop_connections = False
        self.reset_connection = False
        self.current_connection = None
        self.last_received_xml = ""

        self.network_thread = None

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

    def network_loop(self):
        """
        Check for incoming connections and messages on those connections
        """
        while not self.stop_connections:
            self.reset_connection = False
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
			
	def command_loop(self)
		"""
		TODO: pop a command from the command queue on each iteration, parse
		the xml in that command, and update the instruments accordingly. 
		TODO: after xml is handled in a particular iteration, send return data
		back to cspy over the TCP connection.
		"""

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
				# TODO slap this boi on the back of a commands queue.
				# or could return the messsage and queue it outside.
.
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



