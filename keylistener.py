import msvcrt
from threading import Thread

class KeyListener(Thread):
	"""
	Thread class for getting keyboard input in Windows command prompt
	"""
	
	def __init__(self, on_key_press, quitch='q'):
		self.running = False
		self.on_key_press = on_key_press
		self.quitch = quitch
		super(KeyListener, self).__init__()
		
	def start(self):
		self.running = True
		
		while self.running: 
			key = msvcrt.getwch()
			
			self.on_key_press(key)
			if key == 'q': 
				self.running = False
									
	def end(self):
		"""End this thread"""
		self.running = False