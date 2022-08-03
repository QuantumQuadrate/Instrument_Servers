"""
Counters and Counter class for the PXI Server
SaffmanLab, University of Wisconsin - Madison
"""
# modules
import xml.etree.ElementTree as ET
import nidaqmx
from nidaqmx.constants import Edge, AcquisitionType, CountDirection
from nidaqmx.errors import DaqError, DaqWarning
from nidaqmx.error_codes import DAQmxErrors, DAQmxWarnings
from typing import List
import numpy as np
import struct

# local files
from instruments.instrument import Instrument
from pxierrors import XMLError, HardwareError
from tcp import TCP


class Counter(Instrument):
    """Class to interface with a single counter""" 
    def __init__(self, pxi, name, node: ET.Element = None):
        self._name = name  # Doing this twice on purpose
        super().__init__(pxi, node)
        self._name = name
        self.data: List[int] = [0]

        self.counter_source = ""
        self.clock_source = ""
        self.clock_rate = ""
        self.__task = None

    @property
    def task(self) -> nidaqmx.Task:
        return self.__task

    @task.setter
    def task(self, new_task):
        if new_task is not None and not isinstance(new_task, nidaqmx.Task):
            raise ValueError(f"Counter.task must be set to an nidamx.Task object or to None")
        if self.__task is not None:
            # Gently close out of existing task
            self.stop()
            self.close()
        self.__task = new_task

    def load_xml(self, node: ET.Element):

        if self.stop_connections or self.exit_measurement:
            return

        for child in node:
            try:
                if child.tag == "counter_source":
                    self.counter_source = child.text
                elif child.tag == "clock_source":
                    self.clock_source = child.text
                elif child.tag == "clock_rate":
                    self.clock_rate = float(child.text)
                else:
                    self.logger.warning(f"Unrecognized tag '{child.tag}' in counter {self.name}")
            except ValueError:
                raise XMLError(self, child)

    def init(self):
        self.is_initialized = False

        if self.stop_connections or self.reset_connection or not self.enable:
            return

        try:
            self.logger.debug(f"{self} init")
            self.task = nidaqmx.Task()

            self.task.ci_channels.add_ci_count_edges_chan(
                counter=self.counter_source,
                edge=Edge.RISING,
                initial_count=0,
                count_direction=CountDirection.COUNT_UP
            )

            self.task.timing.cfg_samp_clk_timing(
                rate=self.clock_rate,
                source=self.clock_source,
                active_edge=Edge.RISING,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=1000
            )
        except DaqError:
            self.stop()
            self.close()
            msg = f"\nCounter {self.name} task initialization failed"
            raise HardwareError(self, task=self.task, message=msg)

        self.is_initialized = True

    def get_data(self):
        self.logger.debug("getting data")
        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            # I think the number_of_samples_per_channel setting here mimics the labview behavior
            #   but we may want to set the read_all_avail_samp property to true for the task.
            #   -Juan
            self.logger.debug(f"{self} get_data")
            self.logger.debug(f"\tOld data = {self.data}")
            self.data = self.task.read(
                number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                timeout=0)
            self.logger.debug(f"\tNew data data = {self.data}")
            if not self.data:
                self.logger.warning("No data collected")
                self.data = [0]
        except DaqError:
            self.stop()
            self.close()
            msg = f"\nCounter {self.name} failed to get data from it's task"
            raise HardwareError(self, task=self.task, message=msg)

    def start(self):
        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            self.logger.debug(f"{self} Start")
            self.task.start()
            
        except DaqError as e:
            self.logger.exception(f"Error in start task\n{e}")
            self.stop()
            self.close()
            msg = f"\nCounter {self.name} failed to start it's task"
            raise HardwareError(self, task=self.task, message=msg)

    def stop(self):
        """
        Stop the task
        """
        if self.task is not None:
            msg = ""
            try:
                try:
                    self.logger.debug(f"{self} stop")
                    self.task.stop()
                    
                except DaqWarning as e:
                    if e.error_code == DAQmxWarnings.STOPPED_BEFORE_DONE.value:
                        pass
                                            
                self.task.stop()
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                    msg = f'\n {self.__class__.__name__} failed to stop current task'
                    self.logger.warning(msg)
                    self.logger.exception(e)

    def is_done(self) -> bool:
        """
        Check if the task has been completed
        Returns:
            True if self.enable if false, or either self.exit_measurement or self.stop_connections
                are true, or if the task is completed. False otherwise
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return True

        try:
            self.logger.debug(f"{self} is_done")
            done = self.task.is_task_done()
            return done
        except DaqError as e:
            if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                self.stop()
                self.close()
                msg = f"\nCounter {self.name} check for task completion failed"
                raise HardwareError(self, task=self.task, message=msg)

    def close(self):
        """
        Close the task
        """
        self.logger.debug(f"{self} close")
        if self.task is not None:

            self.is_initialized = False
            try:
                
                self.task.close()
            except DaqError as e:
                if not e.error_code == DAQmxErrors.INVALID_TASK.value:
                    msg = f'\nCounter {self.name} failed to close current task'
                    self.logger.warning(msg)
                    self.logger.exception(e)

    def __repr__(self):
        if hasattr(self, "name"):
            return self.name
        else:
            return self.__class__.__name__


class Counters(Instrument):
    """
    Class to control all counters
    """
    def __init__(self, pxi):
        super().__init__(pxi, "counters")

        self.data_string: bytes = b""
        self.counters: List[Counter] = []

    @property
    def data(self) -> List[List[int]]:
        """
        Should be a rectangular 2D array of counter data.
        Indexing should match indexing for self.counters
        Computed on the fly for more flexibility"""
        return [counter.data for counter in self.counters]

    def check_init(self):
        """
        Can we override an attribute with a property? making self.is_initialized
        a property here would be cool, and would save us all those try-finally blocks
        further down
        """
        self.is_initialized = all([counter.is_initialized for counter in self.counters])

    def load_xml(self, node: ET.Element):
        if self.stop_connections or self.exit_measurement:
            return

        self.logger.debug("Counters load_xml")
        for child in node:
            try:
                if child.tag == "enable":
                    self.enable = Instrument.str_to_bool(child.text)
                elif child.tag == "counters":
                    for counter_node in child:
                        this_counter = None
                        for counter in self.counters:
                            if counter.name == counter_node.tag:
                                self.logger.debug(f"Comparing counter {counter.name} with tag {counter_node.tag}")
                                this_counter = counter
                                break
                        if this_counter is None:
                            this_counter = Counter(
                                self.pxi,
                                counter_node.tag,
                                counter_node
                            )
                            this_counter.load_xml(counter_node)
                            this_counter.enable = self.enable
                            self.counters.append(this_counter)
                        
                elif child.tag == "version":
                    pass
                else:
                    self.logger.warning(f"Unrecognized XML tag \'{child.tag}\' in <{self.expectedRoot}>")
            except (ValueError, TypeError):
                raise XMLError(self, child)

    def init(self):
        """
        Initialize our counters
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            self.logger.debug(f"Counters init. Initializing counters {self.counters}")
            for counter in self.counters:
                
                counter.init()
        finally:
            self.check_init()

    def is_done(self) -> bool:
        """
        Check that all tasks are done
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return True

        try:
            done = all([counter.is_done() for counter in self.counters])
        finally:
            self.check_init()

        return done

    def start(self):
        """
        Start all tasks
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            for counter in self.counters:
                counter.start()
        finally:
            self.check_init()

    def stop(self):
        """
        Stop all tasks
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            for counter in self.counters:
                counter.stop()
        finally:
            self.check_init()

    def close(self):
        """
        Close out all tasks
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            for counter in self.counters:
                counter.close()
        finally:
            self.check_init()

    def get_data(self):
        """
        Get data from all of our counters
        """

        if self.stop_connections or self.exit_measurement or not self.enable:
            return

        try:
            for counter in self.counters:
                counter.get_data()
        finally:
            self.check_init()

    def data_out(self) -> bytes:
        """
        Formats the data bytes string for the counters and returns the result
        Returns:
            formatted data bytes string
        """
        if self.stop_connections or self.exit_measurement or not self.enable:
            return b""

        try:
            data_shape = np.array(self.data).shape
            flat_data = np.reshape(self.data, np.prod(data_shape)) # nD data --> 1D data
            self.logger.debug(f"data_shape = {data_shape}\nflat_data = {flat_data}")
            shape_str = ",".join([str(x) for x in data_shape])

            data_bytes = struct.pack(f"!{len(flat_data)}L", *flat_data)

            self.data_string = (TCP.format_data('counter/dimensions', shape_str))
            self.data_string += (TCP.format_data('counter/data', data_bytes))
        except Exception as e:
            self.logger.exception(f"Error formatting data for counters.\n{e}", exc_info=True)

        self.logger.debug(f"data string  = {self.data_string}")
        return self.data_string
