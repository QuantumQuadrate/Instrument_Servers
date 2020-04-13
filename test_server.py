import logging
import colorlog
from pxi import PXI


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
    print("zero")
    setup_logging_handlers()
    logger = logging.getLogger(__name__)
    print("one")
    
    #TODO: add config file to write this too and check config file in future
    port = 9001
    logger.info(f"Default port={port}. \n Hit \'Enter\' for host=localhost "+
                "(default), any other key to use host=\'\'")
    host_choice = input()
    if host_choice == "":
        hostname = "localhost"
    else: 
        hostname = ""
    address = (hostname, port)

    logger.info(f'starting up on {hostname} port {port}')
    print("two")
    experiment = PXI(address)
    experiment.launch_keylisten_thread()
    logger.info(PXI.help_str)
    
    
    experiment.launch_network_thread()
    experiment.launch_experiment_thread()
    print("three")




