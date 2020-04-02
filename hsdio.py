###############################################################################
## pseudocode architecture for HSDIO class
###############################################################################
# I'll start to fill in the gaps to make this functioning code - Juan

from ctypes import * # open to suggestions on making this better with minimal obstruction to workflow
import xml.etree.ElementTree as ET
import os
import struct

## local class imports
from trigger import Trigger
from waveform import Waveform

class HSDIO(Instrument): # could inherit from an Instrument class if helpful

	dllpath32 = os.path.join("C:\Program Files (x86)\IVI Foundation\IVI\Bin", "niHSDIO.dll")
	dllpath64 = os.path.join("C:\Program Files\IVI Foundation\IVI\Bin", "niHSDIO_64.dll")

	def __init__(self):

		# Quick test for bitness
		self.bitness = struct.calcsize("P") * 8
		if self.bitness == 32:
			# Default location of the 32 bit dll
			self.hsdio = CDLL(self.dllpath32)
		else:
			# Default location of the 64 bit dll
			self.hsdio = CDLL(self.dllpath64)


		# waveform obj has arrays of certain dimensions to be filled with
		# waveform data received from cspy
		self.waveformArr = [] 

		
		## device settings
		self.enablePulses = False
		self.resourceNames = []
		self.clockRate = 2*10**7 # 20 MHz
		self.hardwareAlignmentQuantum = 1 # (in samples)
		self.activeChannels = []
		self.initialStates = []
		self.idleStates = []
		self.pulseGenScript = """script script 1 
								      wait 1
								   end script"""
		
		self.scriptTriggers = []
		
		# instrument handles. not really sure what these are yet
		self.instrumentHandles = []
		
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
			
			# the LabView code ignores non-element nodes. not sure if this equivalent
			if type(child) == ET.Element:
				
				# handle each tag by name:
				if child.tag == "enable":
					print_txt(child) # DEBUGGING
					self.enablePulses = bool(child.text)
				
				elif child.tag == "description":
					print_txt(child) # DEBUGGING
					self.description = child.text
				
				elif child.tag == "resourceName":
					print_txt(child) # DEBUGGING
					resources = child.text.split(",")
					self.resourceNames = resources
					
				elif child.tag == "clockRate":
					clockRate = float(child.text)
					print_txt(child) # DEBUGGING
					self.clockRate = clockRate
					
				elif child.tag == "hardwareAlignmentQuantum":
					print_txt(child) # DEBUGGING
					self.hardwareAlignmentQuantum = child.text
				
				elif child.tag == "triggers":
					print_txt(child) # DEBUGGING
					
					if type(child) == ET.Element:
						
						trigger_node = child
												
						# for each line of script triggers
						for child in trigger_node:
							
							if type(child) == ET.Element:
								
								trig = Trigger()
								trig.init_from_xml(child)
								self.scriptTriggers.append(trig)
					  
				elif child.tag == "waveforms":

					#print_txt(child) # HUGE WAVEFORM STRING PLZ BE CAREFUL
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
				
	def init(self):
		"""
		set up the triggering, initial states, script triggers, etc
		"""
		
		if self.isInitialized:
			return
		
		# do stuff; several calls to c functions
		
		self.isInitialized = True
	
	def update(self):
		""" 
		write waveforms to the PC memory 
		"""
		
		waveform_arr = self.waveformArr # each waveform is dict-like
		pulse_gen = self.pulseGenScript
					  
		for wf in waveform_arr:
			# write each waveform wf to the PC memory: (or not actually according to Juan)
			
			#call the c function: niHSDIO_WriteNamedWaveformWDT 
			#http://zone.ni.com/reference/en-XX/help/370520P-01/hsdiocref/cvinihsdio_writenamedwaveformwdt/
			
			#this function is wrapped in a VI, the functionality is explained here:
			#http://zone.ni.com/reference/en-XX/help/370520P-01/hsdio/writing_waveforms_to_your_instrument/
			
	def settings(self, wf_arr, wf_names):
		# the labview code has HSDIO.settings specifically for reading out the 
		# settings on the front panel. for debugging, we could just have this
		# log certain HSDIO attributes 
		
		# log stuff, call settings in the server code for debugging?
		
	def chk(self,er_code):
		"""
		Checks the error state of your session and prints (should become logs) the error/warning message and code (if
		not an all good)
		"""
		codebf = c_int32("")

		hsdio.niHSIDO_GetError(self.vi,byref(codebf))

