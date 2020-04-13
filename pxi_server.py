###############################################################################
## pseudocode architecture for porting LabVIEW PXI server to python
###############################################################################

#### initialization

# instantiate an Experiment
experiment = Experiment(necessary_exp_params) # necessary_exp_params from CsPy
instruments = ['HSDIO', 'DAQmx', ... etc]

# instantiate each instrument, with reference to the experiment
hsdio = HSDIO(experiment) 
daqmx = DAQmx(experiment)
	

cycleContinuously = False
queudReturnData = "" 

timeout = 0

# the xml tags that the server recognizes
allowed_tags = ['HSDIO', 'DAQmxDO', 'TTL', 'cycleContinuously', 'timeout', 
				'camera', 'AnalogOutput', 'AnalogInput', 'Counters', 'piezo',
				'RF_generators', 'measure'] 

# this line should be in the receiving code somewhere, not here
commmandQueue = Queue(commands) # message from CsPy

#### two loops run in parallel: the command loop, and network loop
# wrapping these in functions might not make the most sense in the
# actual implementation but I'm doing to to show explicitly they 
# shoul be called in different threads

def network_loop(ip, port):
	
	sock = Socket(ip, port) # create a socket
	
	while True: # wait for a connection
		
		connected = sock.listen_f or_connection() 
		
		while connected:
		
			sock.listen_for_xml()
			connected = is_stop() # false if server stopped
			connected = is_restart() # false if server restarted

def command_loop():
# this does all of the communication with the physical instruments:
# HSDIO, AO/I, DAQmx, cameras, etc 
	while not Stop:
		
		try:
			queueItem = dequeue(commandQueue) # pop first queue item from queue
		except TimeOutException:
			timeout = 1
			
		if not timeout: 
			xml_nodes = code to parse the xml to get xml_nodes by tag
			for node in xml_nodes:
				if node.tag in allowed_tags:
					# case statements for what to do for each tag. a couple 
					# examples:
					
					if tag == 'HSDIO':			
						hsdio.load_xml(node)
						hsdio.init() # not necessarily the constructor...
						hsdio.update()
						
					elif tag == 'TTL':
						ttl.init(node)
						ttl.update()
						
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
		
		if cycleContinuously:

if __name__ == 'main':

	#### initialization

	# instantiate an Experiment
	experiment = Experiment(necessary_exp_params) # necessary_exp_params from CsPy
	instruments = ['HSDIO', 'DAQmx', ... etc]

	# instantiate each instrument, with reference to the experiment
	hsdio = HSDIO(experiment) 
	daqmx = DAQmx(experiment)
		

	cycleContinuously = False
	queudReturnData = "" 

	timeout = 0

	# the xml tags that the server recognizes
	allowed_tags = ['HSDIO', 'DAQmxDO', 'TTL', 'cycleContinuously', 'timeout', 
					'camera', 'AnalogOutput', 'AnalogInput', 'Counters', 'piezo',
					'RF_generators', 'measure'] 

	commmandQueue = Queue(commands)  # i think this defaults to something and
									 # can be updated in command_loop
	


	# on thread1:
	network_loop()
	
	# on thread2:
	command_loop()