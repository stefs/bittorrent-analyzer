#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import time
import os

# Project modules
import peer_analyzer

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-j', '--jobs', type=int, help='Active peer evaluation using the specified number of threads', metavar='<number>')
parser.add_argument('-i', '--interval', type=float, default=15, help='Time delay between asking the tracker server for new peers in minutes', metavar='<minutes>')
parser.add_argument('-p', '--port', type=int, help='Passive peer evaluation of incoming peers at the specified port number', metavar='<port>')
parser.add_argument('-t', '--timeout', type=int, default='10', help='Timeout in seconds for network connections', metavar='<seconds>')
parser.add_argument('-d', '--delay', type=float, default='15', help='Time delay for revisiting unfinished peers in minutes', metavar='<minutes>')
parser.add_argument('-l', '--loglevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Level of detail for log messages', metavar='<level>') # TODO change to DEBUG or INFO
args = parser.parse_args()

# Check argument plausibility
if args.jobs is None and args.port is None:
	parser.error('Please enable active and/or passive peer evaluation via commandline switches')

# Set output path
directory = 'output/'
if not os.path.exists(directory):
	os.makedirs(directory)
output = directory + time.strftime('%Y-%m-%d_%H-%M-%S') + '_' + os.uname().nodename

# Configure logging
numeric_level = getattr(logging, args.loglevel)
filename_arg = dict()
if args.loglevel != 'DEBUG':
	logfile = output + '.log'
	print('Log is written to file ' + logfile)
	filename_arg['filename'] = logfile
logging.basicConfig(format='[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', datefmt='%Hh%Mm%Ss', level=numeric_level, **filename_arg)
logging.info('Logging messages up to ' + args.loglevel + ' level')

# Analysis routine
try:
	with peer_analyzer.SwarmAnalyzer(args.delay, args.timeout, output) as analyzer:
		analyzer.import_torrents()
	
		# Start database archiver
		analyzer.start_database_archiver()

		# Start active evaluator threads
		if args.jobs is not None:
			analyzer.start_tracker_requests(args.interval)
			analyzer.start_active_evaluation(args.jobs)

		# Start passive evaluation server
		if args.port is not None:
			analyzer.start_passive_evaluation(args.port)

		# Wait for termination
		try:
			print('End with Ctrl+C or interrupt signal')
			while True:
				time.sleep(1024)
		except KeyboardInterrupt:
			print('Please wait for termination ...')
			logging.info('Received interrupt signal, exiting')
except peer_analyzer.AnalyzerError as err:
	logging.error(str(err))
	raise SystemExit
else:
	analyzer.log_statistics()

