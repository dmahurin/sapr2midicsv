#!/usr/bin/env python3

import sys
import struct
import re
import math

ppq = None
fastplay = None
output_t = 0
prev_t = 0

MAX_VOICES = 16
notes = [ None ] * MAX_VOICES
dist = [ None ] * MAX_VOICES
vol = [ 0 ] * MAX_VOICES
bends = [8192 ] * MAX_VOICES

def to_audf(note, bend, use_15k):
	if(note == None): return 0
	if(note == 127 and bend == 16383): return 0
	if(note == 127 and bend == 16382): return 1

	burstclock = 3579545 if 0 == 262 % fastplay else 3546894

	f = 440.0*pow(2,(note-69+((bend-8192)/4096))/12)
	
	return int(burstclock / (114 if use_15k else 28) / f / 4 - 0.5)

def to_dist(inst):
	if(inst == 0 or inst == 80):
		return 5
	elif(inst == 116):
		return 6;
	elif(inst == 117):
		return 4
	elif(inst == 114):
		return 1
	elif(inst == 115):
		return 2
	elif(inst == 113):
		return 0
	return 5

def to_audc(dist, vol):
	return (dist << 5) | (vol & 0xf)

def tempo_to_fastplay(tempo):
	if 312 == int(float(tempo)/ppq*60/60000000/114/2*3546894+0.5):
		return 312
	return int(float(tempo)/ppq*60/60000000/114/2*3579545.0+0.5)

def output(t):
	for i in range(t):
		use_15k = [ False ] * (MAX_VOICES // 4)
		for v in range(MAX_VOICES):
			if None is notes[v]: break
			if (notes[v] < 47 or (notes[v] == 47 and to_audf(notes[v], bends[v], False) != 255)): use_15k[v>>2] = True
		for v in range(MAX_VOICES):
			# if no data for voice, fill in with zeros or break at pokey boundary (every 4)
			if None is notes[v] or None is dist[v]:
				if 0 == (v & 3): break
				dist[v] = 0

			audf = to_audf(notes[v], bends[v], use_15k[v>>2])
			audc = to_audc(dist[v], vol[v])
			# write audctl every forth voice
			sys.stdout.buffer.write(bytes([audf,audc]))
			if 3 == (v & 3):
				sys.stdout.buffer.write(bytes([1 if use_15k[v>>2] else 0]))

for line in sys.stdin:
	line = line.rstrip('\n').replace(', ', ',').split(',')

	t = int(line[1])
	if(t != prev_t):
		if(fastplay == None or ppq == None):
			print("no header/tempo", file=sys.stderr)
			sys.exit(1)
		if(prev_t == 0):
			sys.stdout.buffer.write(b"SAP\r\n")
			if notes[4] is not None:  sys.stdout.buffer.write(b"STEREO\r\n")
			sys.stdout.buffer.write(b"TYPE R\r\n")
			sys.stdout.buffer.write(b"FASTPLAY " + bytes(str(fastplay), 'UTF-8')+b"\r\n")
			sys.stdout.buffer.write(bytes([0xff,0xff]))
		output(t - prev_t)
		prev_t = t
	command = line[2]
	if(command == 'Header'):
		ppq = int(line[5])
		tempo = 60000000/120
		fastplay = tempo_to_fastplay(tempo)
	elif(command == 'Tempo'):
		tempo = int(line[3])
		fastplay = tempo_to_fastplay(tempo)
	elif(command == 'Start_track'):
		pass # TODO: implement multi-track SAP-R
	elif(command == 'Program_c'):
		channel = int(line[3])
		inst = int(line[4])
		dist[channel] = to_dist(inst)
	elif(command == 'End_track'):
		pass # TODO: implement multi-track SAP-R
	elif(command == 'Pitch_bend_c'):
		channel = int(line[3])
		bend = int(line[4])
		bends[channel] = bend
	elif(command == 'Note_off_c'):
		channel = int(line[3])
		note = int(line[4])
		velocity = int(line[5])
		vol[channel] = 0
	elif(command == 'Note_on_c' or command == 'Poly_aftertouch_c'):
		channel = int(line[3])
		note = int(line[4])
		velocity = int(line[5])
		vol[channel] = velocity >> 3
		notes[channel] = note
