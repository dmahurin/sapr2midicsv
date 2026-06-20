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

m = re.search(rb'\bAUDSIZE\s+(\d+)\b', header)
if(m):
	audsize = int(m.group(1).decode())
m = re.search(rb'\bFASTPLAY\s+(\d+)\b', header)
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

def audf_to_midi_note_bend(audf, use15k = False, high_clock = False, joined = False):
	if(audf == 0): return 127, 16383
	if(audf == 1): return 127, 16382

	if(high_clock):
		clock_div = 1
		div_add = 7 if joined else 4
	else:
		clock_div = 114 if use15k else 28
		div_add = 1

	f = burstclock/clock_div/(audf + div_add)/4
	note = int((12.0*math.log(f/440)/math.log(2.0)) + 69.5)
	if(note > 127): note = 127
	note_f = 440.0 * math.pow(2.0, (note-69)/12)
	bend = int(8192.5+4096*12*math.log(f/note_f)/math.log(2))
	if(bend < 0): bend = 0
	if(bend > 16383): bend = 16383
	return note, bend

def pokey_reg_index(pokey, channel):
	return pokey * 9 + channel * 2

def effective_voice(line, pokey, channel):
	audctl = line[pokey * 9 + 8]
	joined_12 = (audctl & 0x10) != 0
	joined_34 = (audctl & 0x08) != 0

	if(channel == 0 and joined_12):
		return 0, 0, audctl, False, False, True
	if(channel == 2 and joined_34):
		return 0, 0, audctl, False, False, True

	reg = pokey_reg_index(pokey, channel)
	audf = line[reg]
	audc = line[reg + 1]
	joined = False
	high_clock = False

	if(channel == 0):
		high_clock = (audctl & 0x40) != 0
	elif(channel == 1 and joined_12):
		high_clock = (audctl & 0x40) != 0
		audf = line[pokey_reg_index(pokey, 0)] + (audf << 8)
		joined = True
	elif(channel == 2):
		high_clock = (audctl & 0x20) != 0
	elif(channel == 3 and joined_34):
		high_clock = (audctl & 0x20) != 0
		audf = line[pokey_reg_index(pokey, 2)] + (audf << 8)
		joined = True

	return audf, audc, audctl, high_clock, joined, False

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
last_freq_key = [ None, None, None, None, None, None, None, None]

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
		ch = v & 3
		audf, audc, audctl, high_clock, joined, hidden = effective_voice(line, p, ch)
		freq_key = (audf, audctl & 1, high_clock, joined)
		note, bend = audf_to_midi_note_bend(audf, audctl & 1, high_clock, joined)
		dist = audc >>5
		vol = (audc & 0xf) <<3
		if(audf == 0): vol = 0

		if(hidden):
			if(last_note[v] > 0):
				print("1, " + str(t) + ", Note_off_c, " + str(v) + ", " +str(last_note[v])+ ", " + str(127))
			last_audf[v] = audf
			last_freq_key[v] = freq_key
			last_audc[v] = audc
			last_note[v] = -1
			continue

		if(last_freq_key[v] == freq_key and last_audc[v] == audc):
			continue

		if(last_audc[v] >>5 != dist):
			print("1, " + str(t) + ", Program_c, " + str(v) + ", " + str(dist_inst[dist]))

		# bend and audf changed
		if(bend != 8192 and last_freq_key[v] != freq_key): print("1, " + str(t) + ", Pitch_bend_c, " + str(v) + ", " + str(bend))

		# audf changed or dist change
		if((last_freq_key[v] != freq_key or last_audc[v] >> 5 != dist)):
			if(last_note[v] > 0):
				print("1, " + str(t) + ", Note_off_c, " + str(v) + ", " +str(last_note[v])+ ", " + str(127))
			print("1, " + str(t) + ", Note_on_c, " + str(v) + ", " +str(note)+ ", " + str(vol))
			last_audf[v] = audf
			last_freq_key[v] = freq_key
			last_note[v] = note
		# volume went to 0, audf, dist unchanged
		elif(vol == 0):
			print("1, " + str(t) + ", Note_off_c, " + str(v) + ", " +str(note)+ ", " + str(127))
			last_note[v] = -1
		# only volume changed
		elif((last_audc[v] & 0xf) << 3 != vol):
			print("1, " + str(t) + ", Poly_aftertouch_c, " + str(v) + ", " +str(note)+ ", " + str(vol))
		last_audc[v] = audc

	t = t+1

print("1, " + str(t) + ", End_track")
print("0, 0, End_of_file")
