#!/usr/bin/env python3
audsize = None
fastplay = 262
ppq = 8
#ppq = 220

import sys
import struct
import re
import math

data = sys.stdin.buffer.read()

m = re.search(b'\xFF',data)

m = re.search(b'(\r?\n)((\r?\n)|(\xff))', data, re.MULTILINE)

if(m == None):
	print("bad format", file=sys.stderr)
	sys.exit(1)

NL = m.group(1)

if(m.group(3) != None):
	header = data[:m.start()]
	data = data[m.end(3):]
elif(m.group(4) != None):
	header = data[:m.start()]
	data = data[m.end(1):]

m = re.search(b'\\bAUDSIZE\s+(\d+)\\b', header)
if(m):
	audsize = int(m.group(1).decode())
m = re.search(b'\\bFASTPLAY\s+(\d+)\\b', header)
if(m):
	fastplay = int(m.group(1).decode())

m = re.search(b'\\bSTEREO\\b', header)
stereo = True if(m) else False

if(audsize == None):
	audsize = 18 if(stereo) else 9

if(data[0] == 0xff and data[1] == 0xff):
	data = data[2:]
	if(data[0] == 0x0 and data[1] == 0x0 and (data[1] != 0 or data[2] != 0)):
		data = data[4:]

burstclock = 3579545 if 0 == 262 % fastplay else 3546894

def audf_to_midi_note_bend(audf, use15k = False):
	if(audf == 0): return 127, 16383
	if(audf == 1): return 127, 16382

	f = burstclock/(114 if use15k else 28)/(audf + 1)/4
	note = int((12.0*math.log(f/440)/math.log(2.0)) + 69.5)
	if(note > 127): note = 127
	note_f = 440.0 * math.pow(2.0, (note-69)/12)
	bend = int(8192.5+4096*12*math.log(f/note_f)/math.log(2))
	if(bend > 16383): bend = 16383
	return note, bend

print("0, 0, Header, 1, 1, " + str(ppq))
print("1, 0, Start_track")
print("1, 0, Tempo, " + str(int(60000000*ppq/((burstclock/114/2/fastplay)*60))))

if(stereo):
	for v in range(4):
		print(f"1, 0, Control_c, {v}, 10, 0")
	for v in range(4, 8):
		print(f"1, 0, Control_c, {v}, 10, 127")

last_audf = [ -1, -1, -1, -1, -1, -1, -1, -1]
last_audc = [ -1, -1, -1, -1, -1, -1, -1, -1]
last_note = [ 0, 0, 0, 0, 0, 0, 0, 0]

pure1 = 80
dist17 = 116 # 117 116 113 47
dist_inst = {
	0: 113, # 17 + 5
	1: 114, 3: 114, # 5
	2: 115, # 5 + 4
	4: 117, #17
	5: pure1, 7: pure1, # pure
	6: 116, # 4
}

t = 0
while(len(data)):
	line = data[0:audsize]
	data = data[audsize:]

	for v in range(0,8 if stereo else 4):
		p = v // 4
		audctl = line[p * 9 + 8]
		audf = line[p + (v<<1)]
		note, bend = audf_to_midi_note_bend(audf, audctl & 1)
		audc = line[(p + (v<<1))+1]
		dist = audc >>5
		vol = (audc & 0xf) <<3
		if(audf == 0): vol = 0

		if(last_audf[v] == audf and last_audc[v] == audc):
			continue

		if(last_audc[v] >>5 != dist):
			print("1, " + str(t) + ", Program_c, " + str(v) + ", " + str(dist_inst[dist]))

		# bend and audf changed
		if(bend != 8192 and last_audf[v] != audf): print("1, " + str(t) + ", Pitch_bend_c, " + str(v) + ", " + str(bend))

		# audf changed or dist change
		if((last_audf[v] != audf or last_audc[v] >> 5 != dist)):
			if(last_note[v] > 0):
				print("1, " + str(t) + ", Note_off_c, " + str(v) + ", " +str(last_note[v])+ ", " + str(127))
			print("1, " + str(t) + ", Note_on_c, " + str(v) + ", " +str(note)+ ", " + str(vol))
			last_audf[v] = audf
			last_note[v] = note
		# volume went to 0, audf, dist unchanged
		elif(vol == 0):
			print("1, " + str(t) + ", Note_off_c, " + str(v) + ", " +str(note)+ ", " + str(127))
			last_note[v] = -1
		# only volume changed
		elif(last_audc[v] & 0xf != vol):
			print("1, " + str(t) + ", Poly_aftertouch_c, " + str(v) + ", " +str(note)+ ", " + str(vol))
		last_audc[v] = audc

	t = t+1

print("1, " + str(t) + ", End_track")
print("0, 0, End_of_file")
