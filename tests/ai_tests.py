"""
Tests for AnalogInput class methods
"""
import xml.etree.ElementTree as ET
from analogin import AnalogInput

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
		if child.tag == "AnalogInput":
			print("Attempting to instantiate AnalogInput as ai...")
			ai = AnalogInput()
			print("AnalogInput instantiated! \n Calling ai.load_xml...")
			ai.load_xml(child)
			print("AnalogInput initialized! \n Calling ai.init...")
			ai.init() # This fails on my laptop. Error seems to say it looks for a local file but can't find it. 
                      # Might work on PC that can talk to the AI hardware. - Preston
			print("AnalogInput updated")