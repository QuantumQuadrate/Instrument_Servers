###############################################################################
## pseudocode architecture for Experiment class
###############################################################################

class Experiment:

	def __init__(self):
		#initialize the various devices
		self.hsdio = HSDIO()
		self.daqmx = DAQmx()
		self.ao = AnalogOutput()
		self.ai = AnalogInput()
		self.ttl = TTL() 
		self.settings = # not sure where settings come from
		
	def parse_xml(self, xml_nodes):
		# explore only the tier of nodes under <LabView> (root of xml tree),
		# rather than search recursively. grandchildren are checked by devices
		for node in xml_nodes: 
			if node.tag in allowed_tags:
				# case statements for what to do for each tag. a couple 
				# examples:
				
				if tag == 'HSDIO':			
					self.hsdio.load_xml(node)
					self.hsdio.init() # not necessarily the constructor...
					self.hsdio.update()
					
				elif tag == 'TTL':
					self.ttl.init(node)
					self.ttl.update()
					
				elif tag == 'cycleContinuously':
					cycleContinuously == bool(node.text)
					
				elif tag == 'camera':
					# load camera stuff. similar calls as in TTL block
					
				elif tag == 'measure':
					if queudReturnData != "":
						experiment.Measurement()
					
				# etc.. for each allowed tag. they're all pretty similar calls.
				# building the actual functions that get called is the 
				# non-trivial part
			else:
				logger.warning("unrecognized xml tag in <LabView>: "+node.tag)