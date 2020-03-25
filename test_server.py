import socket
import logging
import colorlog


def setup_logging_handlers():
    """
    This function sets up the error logging to the console. Logging
    can be set up at the top of each file by doing:
    import logging
    logger = logging.getLogger(__name__)
    """
    # get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # set up logging to console for INFO and worse
    sh = colorlog.StreamHandler()
    sh.setLevel(logging.INFO)

    sh_formatter = colorlog.ColoredFormatter("%(log_color)s%(levelname)-8s - "
                                             "%(name)-25s - %(threadName)-15s -"
                                             " %(asctime)s - %(cyan)s \n  "
                                             "%(message)s\n",
                                             datefmt=None,
                                             reset=True,
                                             log_colors={
                                                         'DEBUG':    'cyan',
                                                         'INFO':     'green',
                                                         'WARNING':  'yellow',
                                                         'ERROR':    'red',
                                                         'CRITICAL': 'red,'
                                                                     'bg_white',
                                                         },
                                             secondary_log_colors={},
                                             style='%'
                                             )
    sh.setFormatter(sh_formatter)

    # put the handlers to use
    root_logger.addHandler(sh)


if __name__ == '__main__':

    setup_logging_handlers()
    logger = logging.getLogger(__name__)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    hostname = 'localhost'
    # 9000 for DDS, 9001 for PXI
    port = 9001

    address = (hostname, port)

    logger.info(f'starting up on {hostname} port {port}')
    sock.bind(address)
    maximum_simultaneous_connections = 1
    sock.listen(maximum_simultaneous_connections)

    while True:
        connection, client_address = sock.accept()
        logger.info(f"Receiving connection from {client_address}")
        try:
            # Read first 4 bytes looking for a specific message header
            connection.settimeout(0.3)
            header = connection.recv(4)
            logger.info(f"header was read as {header}")
            if header == b'MESG':
                logger.info("We got a message! now to handle it.")
                # Assume next 4 bytes contains the length of the remaining message
                length_bytes = connection.recv(4)
                length = int.from_bytes(length_bytes, byteorder='big')
                logger.info(f"I think the message is {length} bytes long.")
                connection.settimeout(20)
                message = connection.recv(length)
                if len(message) == length:
                    logger.info("message received with expected length. Sending it back.")
                    # echo the message back since we haven't implemented actual handling yet
                    connection.sendall(header + length_bytes + message)
                else:
                    logger.info(f"Something went wrong, I only found {len(message)} bytes to read!")
            else:
                logger.info("We appear to have received junk. Clearing buffer.")
                connection.settimeout(0.01)
                more_to_clear = True
                while more_to_clear:
                    more_to_clear = not connection.recv(4096) == ''
        except TimeoutError as e:
            logger.exception(e)
        except Exception as e:
            logger.exception(e)
        finally:
            logger.info("Closing the connection so I can receive another one.")
            connection.close()

