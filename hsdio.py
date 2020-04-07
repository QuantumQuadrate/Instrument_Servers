"""
HSDIO class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft, Juan Bohorquez

For parsing XML strings which specify triggers and waveforms to be loaded to National
Instruments HSDIO hardware. 
"""

from ctypes import * # open to suggestions on making this better with minimal obstruction to workflow
import numpy as np
import xml.etree.ElementTree as ET
import os
import struct
import platform # for checking the os bit
from ni_hsdio import NiHsdio

## local class imports
from trigger import Trigger, StartTrigger
from waveform import Waveform

class HSDIO: # could inherit from an Instrument class if helpful
	
	if platform.machine().endswith("64"):
		programsDir32 = "Program Files (x86)"
	else:
		programsDir32 = "Program Files"

	dllpath32 = os.path.join(f"C:\{programsDir32}\IVI Foundation\IVI\Bin", "niHSDIO.dll")
	dllpath64 = os.path.join("C:\Program Files\IVI Foundation\IVI\Bin", "niHSDIO_64.dll")

	def __init__(self):

		'''
		This is taken care of inside of ni_hsdio now
		# Quick test for bitness
		self.bitness = struct.calcsize("P") * 8
		if self.bitness == 32:
			# Default location of the 32 bit dll
			self.hsdio = CDLL(self.dllpath32)
		else:
			# Default location of the 64 bit dll
			self.hsdio = CDLL(self.dllpath64)
		'''

		## device settings
		# TODO: could make an attribute with these settings in a dictionary
		# and then settings can be updated by calling a settings function with
		# kwargs
		self.enablePulses = False
		self.resourceNames = np.array([], dtype=str)
		self.clockRate = 2*10**7 # 20 MHz
		self.hardwareAlignmentQuantum = 1 # (in samples)
		self.activeChannels = np.array([], dtype=c_int32)
		self.initialStates = np.array([], dtype=str)
		self.idleStates = np.array([], dtype=str)
		self.pulseGenScript = """script script 1
								      wait 1
								   end script"""
		self.scriptTriggers = []

		# These two have are related to one another, each session is attached to a handle, each handle can support man
		# sessions. Sessions now have an attribute HsdioSession.handle (a python string)
		self.instrumentHandles = []  # array to hold instrument handles
		self.session = []  # array to hold HsdioSession objects

		self.waveformArr = []

		
		# whether or not we've actually populated the attributes above
		self.isInitialized = False 
		
	def load_xml(self, node):
		"""
		iterate through node's children and parse xml by tag to update HSDIO
		device settings
		'node': type is ET.Element. tag should be "HSDIO"
		"""
		
		assert node.tag == "HSDIO", "This XML is not tagged for the HSDIO"
		
		for child in node:
			
			# the LabView code ignores non-element nodes. not sure if this 
			# equivalent
			if type(child) == ET.Element:
				
				# handle each tag by name:
				if child.tag == "enable":
					self.print_txt(child) # DEBUGGING
					self.enablePulses = bool(child.text)
				
				elif child.tag == "description":
					self.print_txt(child) # DEBUGGING
					self.description = child.text
				
				elif child.tag == "resourceName":
					self.print_txt(child) # DEBUGGING
					resources = np.array(child.text.split(","))
					self.resourceNames = resources
					
				elif child.tag == "clockRate":
					clockRate = float(child.text)
					self.print_txt(child) # DEBUGGING
					self.clockRate = clockRate
					
				elif child.tag == "hardwareAlignmentQuantum":
					self.print_txt(child) # DEBUGGING
					self.hardwareAlignmentQuantum = child.text
				
				elif child.tag == "triggers":
					self.print_txt(child) # DEBUGGING
					
					if type(child) == ET.Element:
						
						trigger_node = child
												
						# for each line of script triggers
						for child in trigger_node:
							
							if type(child) == ET.Element:
								
								trig = Trigger()
								trig.init_from_xml(child)
								self.scriptTriggers.append(trig)
					  
				elif child.tag == "waveforms":

					#self.print_txt(child) #HUGE WAVEFORM STRING PLZ BE CAREFUL
					print("found a waveform") #TODO: change to logger
	
					# TODO: wrap in load waveform xml
					wvforms_node = child
	
					# for each waveform
					for wvf_child in wvforms_node:
				
						if type(wvf_child) == ET.Element:
																					
							if wvf_child.tag == "waveform":

								wvform = Waveform()
								wvform.init_from_xml(wvf_child)
								self.waveformArr.append(wvform)
								
				elif child.tag == "script":
					self.print_txt(child) # DEBUGGING
					self.pulseGenScript
					
				elif child.tag == "startTrigger":
					self.startTrigger = StartTrigger()
					self.startTrigger.init_from_xml(child)
									
				elif child.tag == "InitialState":
					self.print_txt(child) # DEBUGGING
					self.initialStates = np.array(child.text.split(","))
				
				elif child.tag == "IdleState":
					self.print_txt(child) # DEBUGGING
					self.idleStates = np.array(child.text.split(",")) 
				
				elif child.tag == "ActiveChannels":
					self.print_txt(child) # DEBUGGING
					self.activeChannels = np.array(child.text.split("\n")) 
				
				else:
					# TODO: replace with logging
					print("Not a valid XML tag for HSDIO initialization")
					
		# TODO: replace with logging
		print("HSDIO XML Loaded")
		
					
	def init(self):
		"""
		set up the triggering, initial states, script triggers, etc
		"""
		
		if self.isInitialized:
			
			for instrument in self.instruments:
				self.niHSDIO.abort()
				self.niHSDIO.close()
				pass
				
				# TODO: Juan - niHSDIO Abort VI
				# TODO: Juan - niHSDIO Close VI
				
				# i think this should clear the list of instrumentHandles too.
				# in LabView the handle gets passed in/out of the above VIs.
				# maybe just reset the array after the loop:
				# Its worth considering how these handles are being populated - Juan

			self.instrumentHandles = [] # reset
							
		self.instrumentHandles.append("")
		
		if self.enablePulses:
				
			iterables = zip(self.idleStates, self.initalStates,
							self.activeChannels, self.resourceNames)
			for idle_state,init_state,chan_list,resource in iterables:
				
				# TODO: Juan - niHSDIO Init Generation Session VI
				# 	args: resource name = resource
				
				# TODO: Juan - niHSDIO Assign Dynamic Channels VI
				#	args: channel list = chan_list

				# TODO: Juan - niHSDIO Configure Sample Clock
				#	args: resource name = resource
				#		  clock rate = self.clockRate,
				#		  clock source = "OnBoardClock"
				
				# TODO: Juan - niHSDIO Configure Generation Mode VI
				#	args: resource name = resource
				#	      generation mode = c_int32(15) 
				# note: 14 to waveform, 15 corresponds to scripted
				
				# TODO: Juan - niHSDIO Configure Initial State (String) VI
				#	args: resource name = resource
				#		  initial state = init_state,
				#		  channel list = chan_list
				
				# TODO: Juan - niHSDIO Configure Idle State (String) VI
				#	args: resource name = resource
				#		  generation mode = c_int32(15) 
				
				for trig in self.scriptTriggers:
					
					# implement this in a better way so not hardcoding the numeric code
					if trig.type == c_uint32(1): # Level type
					
						# TODO: Juan - niHSDIO Configure Trigger (Level) VI
						# 	args: source (PFI 0): str, edge (rising): c_int32(1)
						
					else: # Edge type is default when initialized
						
						# TODO: Juan - niHSDIO Configure Trigger (Edge) VI
						# 	args: source (PFI 0): str, edge (rising): c_int32(1)					
				
				self.instrumentHandles.append(resource)
				
		self.isInitialized = True
	
	def update(self):
		""" 
		write waveforms to the PC memory 
		"""
		
		waveform_arr = self.waveformArr # each waveform is dict-like
		pulse_gen = self.pulseGenScript
					  
		for wf in waveform_arr:
			pass
			# write each waveform wf to the PC memory: (or not actually according to Juan)
			
			#TODO : Juan call the c function: niHSDIO_WriteNamedWaveformWDT
			#http://zone.ni.com/reference/en-XX/help/370520P-01/hsdiocref/cvinihsdio_writenamedwaveformwdt/
			
			#this function is wrapped in a VI, the functionality is explained here:
			#http://zone.ni.com/reference/en-XX/help/370520P-01/hsdio/writing_waveforms_to_your_instrument/
			
	def settings(self, wf_arr, wf_names):
		pass
		# the labview code has HSDIO.settings specifically for reading out the 
		# settings on the front panel. for debugging, we could just have this
		# log certain HSDIO attributes 
		
		# log stuff, call settings in the server code for debugging?
		
	def print_txt(self, node): # for debugging
		print(f"{node.tag} = {node.text}") # TODO replace with logging
		
	def chk(self,er_code):
		"""
		Checks the error state of your session and prints (should become logs) 
		the error/warning message and code (if not an all good)
		"""
		codebf = c_int32("")

		hsdio.niHSIDO_GetError(self.vi,byref(codebf))

