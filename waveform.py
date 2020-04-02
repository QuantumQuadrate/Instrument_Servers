from ctypes import c_uint32
import numpy as np

class Waveform:
	
	def __init__(self, name="", transitions=None, states=None):
		self.name = name
		self.transitions = transitions
		self.states = states
		
	def init_from_xml(self, node): # equivalent to load waveform in labVIEW
		""" 
		re-initialize attributes for existing Waveformfrom children of node. 
		'node' is of type xml.etree.ElementTree.Element, with tag="waveform"
		"""
	
		waveform_attrs = node
		for child in waveform_attrs:
			
			if child.tag == "name":
				self.name = child.text

			elif child.tag == "transitions":
				t = np.array([x for x in child.text.split(" ")], 
							 dtype=c_uint32)
				self.transitions = t

			elif child.tag == "states":
				states= np.array([[int(x) for x in line.split(" ")] 
								  for line in child.text.split("\n")],
								 dtype=c_uint32)
				self.states = states
			else:
				print("Invalid Waveform attribute") # TODO: replace with logger
					
	def __repr__(self): # mostly for debugging
		return (f"Waveform(name={selfname}, transitions={self.transitions}, "
				f"states={states}")