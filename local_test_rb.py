# built-in 
import re
import xml.etree.ElementTree as ET
from ctypes import *

# third-party
from recordclass import recordclass as rc # for Trigger, Waveform types
import numpy as np # for arrays

# local module imports
from trigger import Trigger, StartTrigger
from waveform import Waveform
from hsdio import HSDIO

def msg_from_file(file="to_pxi.txt"): # 
	msgs = []
	with open(file) as f:
		lines = f.readlines()
		for line in lines:
			if "NEW MESSAGE" in line:
				msgs.append('')
				continue
			msgs[-1] += line
	return msgs

if __name__ == "__main__":
	msg = msg_from_file()[0]
	root = ET.fromstring(msg)
	print(root)
	if root.tag != "LabView":
		print("Not a valid msg for the pxi")

	for child in root:
		if child.tag == "HSDIO":
			print("Attempting to instantiate HSDIO...")
			hsdio = HSDIO()
			print("HSDIO instantiated! \n Calling HSDIO.load_xml...")
			hsdio.load_xml(child)
			print("HSDIO XML loaded! \n Calling HSDIO.init...")
			hsdio.init()
			print("HSDIO initialized!")