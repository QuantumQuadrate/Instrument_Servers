from ctypes import c_uint32
import xml.etree.ElementTree as ET

"""
Trigger class for the PXI Server
SaffmanLab, University of Wisconsin - Madison

Author(s): Preston Huft
"""

class Trigger:
	""" Trigger data type for PXI server """
	# TODO: make these into ordered dicts or have someway
	types = {"Edge": c_uint32(0),
			 "Level": c_uint32(1)}
	edges = {"Rising Edge": c_uint32(12),
			 "Falling Edge": c_uint32(13)}
	levels = {"High Level": c_uint32(34),
			  "Low Level": c_uint32(35)}
	
	def __init__(self, trigID="", source="", trigType=types["Edge"], 
				 edge=edges["Rising Edge"], level=levels["High Level"]):
		
		self.trigID = trigID
		self.source = source # PFI 0
		self.trigType = trigType
		self.edge = edge
		self.level = level
		
	def init_from_xml(self, node):
		"""
		re-initialize attributes for existing Trigger from children of node. 
		'node' is of type xml.etree.ElementTree.Element, with tag="trigger"
		"""
		for child in node:
			
			if type(child) == ET.Element:
			
				if child.tag == "id": 
					self.trigID = child.text # script trigger 0

				elif child.tag == "source":
					self.source = child.text # PFI 0

				elif child.tag == "type":

					if child.text == "level":
						self.trigType = self.trigTypes["Level"]

					# else, stick with default initialization

				elif child.tag == "edge":

					if child.text == "Falling Edge":
						self.edge = self.edges["Falling Edge"]
						pass

					# else, stick with default initialization

				elif child.tag == "level":

					if child.text == "Low Level":
						self.level = self.levels["Low Level"]
						pass
					
				else:
					# TODO: replace with logger
					print("Not a valid trigger attribute") 
		
	def __repr__(self): # mostly for debugging
		return (f"Trigger(id={self.trigID}, source={self.source}, "
				f"type={self.trigType}, edge={self.edge}, level={self.level})")
				

# with some refactoring, this could inherit from Trigger
class StartTrigger: 

	edges = {"Rising Edge": c_uint32(0),
			 "Falling Edge": c_uint32(1)}

	def __init__(self, waitForStartTrigger=False, source="", description="", 
				 edge=edges["Rising Edge"]):
		self.waitForStartTrigger = waitForStartTrigger
		self.source = source
		self.description = description
		self.edge = edge
	
	def init_from_xml(self, node):
		"""
		re-initialize attributes for existing StartTrigger from children of node. 
		'node' is of type xml.etree.ElementTree.Element, with tag="startTrigger"
		"""
		
		for child in node:
			
			if type(child) == ET.Element: 
		
				if child.tag == "waitForStartTrigger":

					if child.text.lower() == "true":
						wait_bool = True
					else: # if it wasn't True, assume False
						wait_bool = False
					self.waitForStartTrigger = wait_bool
					
				elif child.tag == "source":
					self.source = child.text # PFI 0
					
				elif child.tag == "description":
					self.description = child.text
					
				elif child.tag == "edge":
					
					if child.text == "falling":
						self.edge = StartTrigger.edges["Falling"]
					elif child.text == "rising":
						# this is the default value, do nothing
						pass
					else:
						# TODO: replace with logger
						print("Invalid edge type for StartTrigger")
						
				else:
					print("Unrecognized XML tag for StartTrigger")
		
	
	def __repr__(self): # mostly for debugging
		return (f"StartTrigger(waitForStartTrigger={self.waitForStartTrigger}, "
				f"source={self.source}, description={self.description}, "
				f"edge={self.edge})")