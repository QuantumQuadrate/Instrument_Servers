from ctypes import c_uint32

class Trigger:
	""" Trigger data type for PXI server """
	
	types = {"Edge": c_uint32(0),
			 "Level": c_uint32(1)}
	edges = {"Rising Edge": c_uint32(0),
			 "Falling Edge": c_uint32(1)}
	levels = {"High Level": c_uint32(0),
			  "Low Level": c_uint32(1)}
	
	def __init__(self, trig_id="", source="", trig_type=types["Edge"], 
				 edge=edges["Rising Edge"], level=levels["High Level"]):
		
		self.id = trig_id
		self.source = source # PFI 0
		self.type = trig_type
		self.edge = edge
		self.level = level
		
	def init_from_xml(self, node):
		"""
		Initialize trigger attributes from xml text.
		'node' should have parent with tag="triggers"
		"""
		
		if child.tag == "id": 
			trig.id = child.text # script trigger 0

		elif child.tag == "source":
			trig.source = child.text # PFI 0

		elif child.tag == "type":

			if child.text == "level":
				trig.type = Trigger.types["Level"]

			# else, stick with default initialization

		elif child.tag == "edge":

			if child.text == "Falling Edge":
				trig.edge = Trigger.edges["Falling Edge"]
				pass

			# else, stick with default initialization

		elif child.tag == "level":

			if child.text == "Low Level":
				trig.level = Trigger.levels["Low Level"]
				pass
			
		else:
			# TODO: replace with logger
			print("Not a valid trigger attribute") 
		
	def __repr__(self): # mostly for debugging
		return (f"Trigger(id={self.id}, source={self.source}, "
				f"type={self.type}, edge={self.edge}, level={self.level})")