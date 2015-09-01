#!/usr/bin/env python3

import csv
import sys

filename_in1 = sys.argv[1]
filename_in2 = sys.argv[2]
filename_out = sys.argv[3]

with open(filename_out, mode='w', newline='') as outfile:
	writer = csv.writer(outfile)
	with open(filename_in1) as infile:
		reader = csv.reader(infile)
		for index, row in enumerate(reader):
			if not index:
				length_check = len(row)
			elif len(row) != length_check:
				raise Exception('changed length in {} line {}'.format(filename_in1, index+1))
			writer.writerow(row)
	with open(filename_in2) as infile:
		reader = csv.reader(infile)
		for index, row in enumerate(reader):
			if len(row) != length_check:
				raise Exception('changed length in {} line {}'.format(filename_in2, index+1))
			row[0] = int(row[0]) + 10
			writer.writerow(row)
