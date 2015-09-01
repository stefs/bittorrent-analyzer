#!/usr/bin/env python3

import sys

filename_in1 = sys.argv[1]
filename_in2 = sys.argv[2]
filename_out = sys.argv[3]
row_length = 3

values = dict()
def add(key, count):
	if key in values:
		values[key] += count
	else:
		values[key] = count

for filename in [filename_in1, filename_in2]:
	with open(filename) as infile:
		for index, line in enumerate(infile):
			cols = line.strip('\n').split(',')
			if len(cols) != row_length:
				raise Exception('bad length in {} line {}'.format(filename_in1, index+1))
			add(','.join(cols[0:len(cols)-1]), int(cols[-1]))

with open(filename_out, mode='w', newline='') as outfile:
	for key, count in values.items():
		outfile.write('{},{}\n'.format(key, count))
