import logging
import colorlog
from pxi import PXI


def setup_logging_handlers() -> logging.Logger:
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
    return root_logger


if __name__ == '__main__':
    root_logger = setup_logging_handlers()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    #TODO: add config file to write this to and check config file in future
    port = 9000
    logger.info(f"Default port={port}. \n Hit \'Enter\' for host=localhost "+
                "(default), any other key then \'Enter\' to use host=\'\'")
    host_choice = input()
    if host_choice == "":
        hostname = "localhost"
        ip_str = "127.0.0.1"
    else: 
        hostname = ""
        ip_str = "0.0.0.0"
        
    address = (hostname, port)
    
    logger.info(f'listening on host={hostname} (ip={ip_str}) port={port}')
    experiment = PXI(address, root_logger=root_logger)
    experiment.launch_keylisten_thread()
    logger.info(PXI.help_str)

    experiment.launch_network_thread()
    experiment.launch_experiment_thread()




