###############################################################################
## pseudocode architecture for HSDIO class
###############################################################################


class HSDIO(Instrument): # could inherit from an Instrument class if helpful

	def __init__(self):
		
		# waveform obj has arrays of certain dimensions to be filled with 
		# waveform data received from cspy
		self.waveformArr = [{name: Waveform()}] # maybe specify array length? 
		
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
		
		# trigger settings -- could make a trigger class
		self.trigger = {'wait for start trigger': False, 
						'source': 'PFI0',
						'edge': 'rising edge',
						'description' : ""}
		self.scriptTriggerArr = [trigger settings like above]
		
		# instrument handles. not really sure what these are yet
		self.instrumentHandles = []
		
		# whether or not we've actually populated the attributes above
		self.isInitialized = False 
	
	def load_xml(self, node):
		"""
		iterate through node's children and parse xml by tag to update HSDIO
		device settings
		"""
		
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
		
		
		
		