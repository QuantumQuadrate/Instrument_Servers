import socket
import struct
import logging
import threading
from time import time
from datetime import datetime


class TCP:

    def __init__(self, pxi, address):
        self.logger = logging.getLogger(str(self.__class__))
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind(address)
        self.listening_socket.listen(100)
        self.current_connection = None
        self.network_thread = None
        self.pxi = pxi
        self.seeking_connection = False
        self.last_xml = ""

    @property
    def reset_connection(self) -> bool:
        return self.pxi.reset_connection

    @reset_connection.setter
    def reset_connection(self, value):
        self.pxi.reset_connection = value

    @property
    def stop_connections(self) ->bool:
        return self.pxi.stop_connections

    @stop_connections.setter
    def stop_connections(self, value):
        self.pxi.stop_connections = value

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

        self.logger.info("Entering Network Loop")
        while not self.stop_connections:
            self.reset_connection = False

            # TODO: entering q in cmd line should terminate this process
            self.logger.info("Attempting to accept connection request.")
            self.seeking_connection = True
            self.current_connection, client_address = self.listening_socket.accept()
            self.seeking_connection = False
            self.logger.info(f"Started connection with {client_address}")
            while not (self.pxi.reset_connection or self.stop_connections):
                try:
                    self.receive_message()
                except socket.timeout:
                    pass
                except ConnectionResetError as e:
                    self.logger.warning(e)
                    self.pxi.reset_connection = True
                    self.logger.info("Connection reset")
                    
            self.logger.info(f"Closing connection with {client_address}")
            self.current_connection.close()
        self.logger.info("Closing Networking Thread")
        self.listening_socket.close()

    def receive_message(self):
        """
        listens for a message from cspy over the network.

        messages from cspy are encoded in the following way:
            message = b'MESG' + str(len(body)) + body

        """
        # Read first 4 bytes looking for a specific message header
        header = self.current_connection.recv(4)
        self.logger.debug(f"header was read as {header}")
        if header == b'MESG':
            self.logger.info("We got a message! now to handle it.")
            # Assume next 4 bytes contains the length of the remaining message
            length_bytes = self.current_connection.recv(4)
            length = int.from_bytes(length_bytes, byteorder='big')
            self.logger.debug(f"I think the message is {length} bytes long.")
            self.current_connection.settimeout(20)
            bytes_remaining = length
            message = ''

            while bytes_remaining > 0:
                snippet = self.current_connection.recv(bytes_remaining)
                bytes_remaining -=  len(snippet)
                message += TCP.bytes_to_str(snippet)
            if message != "<LabView><measure/></LabView>":
                self.last_xml = message
            
            if len(message) == length:
                self.logger.debug("message received with expected length.")
                self.pxi.queue_command(message)
            else:
                self.logger.warning(f"Something went wrong,"
                                 f" I only found {len(message)} bytes to read!")
        else:
            self.logger.info("We appear to have received junk. Clearing buffer.")
            self.current_connection.settimeout(0.01)
            try:
                while not (self.reset_connection or self.stop_connections):
                    junk = self.current_connection.recv(4096)
                    if junk == b"":
                        break
            except socket.timeout:
                pass
            finally:
                self.reset_connection = True
                self.logger.info("reset connection true")
                
                
    def send_message(self, msg_str=None):
        """
        Send a message back to CsPy via the current connection.

        Args:
            msg_str: The body of the message to send to CsPy
        """
        
        if not self.stop_connections: # and msg_str:
            try:
                self.logger.debug("encoding message")
                encoded = b"MESG"+TCP.format_message(msg_str)
                self.current_connection.send(encoded)
                self.logger.info("message sent")
            except Exception:
                self.logger.exception("Issue sending message back to CsPy.")
                self.reset_connection = True
        else:
            self.logger.warning("tried to send a message but the connection is stopped :'(")

            
    def xml_to_file(self):
        """
        print last xml to a file
        """
        fname = "xml_" + (datetime.now()).strftime("%Y%m%d_%H_%M_%S") + ".txt"
        with open(fname, 'w') as f:
            f.write(self.last_xml)
        return fname
            
            
    def abort(self):
        kill_socket = socket.socket()
        kill_socket.connect(('127.0.0.1', 9000))
        kill_socket.close()

    
    @staticmethod
    def format_message(message) -> bytes:
        """
        Formats a message according to how CsPy expects to receive it. This is done by pre-prending
        the length of the message to the message in byte form
        Args:
            message : message to be sent

        Returns:
            formatted message string
        """
        if isinstance(message, str):
            message = message.encode()
        return struct.pack('!L', len(message)) + message


    @staticmethod
    def format_data(name, data) -> bytes:
        """
        Formats a bit of data according to how CsPy expects to receive it.
        Args:
            name: A description of the data
            data: The data to be send to CsPy

        Returns:
            formatted string that CsPy can parse
        """
        return TCP.format_message(name)+TCP.format_message(data)

    @staticmethod
    def bytes_to_str(data) -> str:
        return ''.join(map(chr, data))