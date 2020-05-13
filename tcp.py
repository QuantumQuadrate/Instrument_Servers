import socket
import struct
import logging
import threading


class TCP:

    def __init__(self, pxi, address):
        self.logger = logging.getLogger(str(self.__class__))
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.bind(address)
        self.listening_socket.listen(100)
        self.current_connection = None
        self.network_thread = None
        self.pxi = pxi

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
            self.logger.info("attempting to accept connection request.")
            self.current_connection, client_address = self.listening_socket.accept()
            self.logger.info(f"Started connection with {client_address}")
            while not (self.pxi.reset_connection or self.stop_connections):
                try:
                    self.receive_message()
                except socket.timeout:
                    pass
            self.logger.info(f"Closing connection with {client_address}")
            self.current_connection.close()

    def receive_message(self):
        """
        listens for a message from cspy over the network.

        messages from cspy are encoded in the following way:
            message = b'MESG' + str(len(body)) + body

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
                self.pxi.queue_command(message)
            else:
                self.logger.info(f"Something went wrong,"
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
        if not self.stop_connections and msg_str:
            self.current_connection.send(f"{b'MESG'}{struct.pack('!L', len(msg_str))}{msg_str}")
