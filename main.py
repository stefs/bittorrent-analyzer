#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import time
import os

# Project modules
import peer_analyzer
import torrent_file

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('torrent', help='File system path to the torrent file to be examined', metavar='<torrent>')
parser.add_argument('-j', '--jobs', type=int, help='Active peer evaluation using the specified number of threads', metavar='<number>')
parser.add_argument('-i', '--interval', type=float, default=15, help='Time delay between asking the tracker server for new peers in minutes', metavar='<minutes>')
parser.add_argument('-p', '--port', type=int, help='Passive peer evaluation of incoming peers at the specified port number', metavar='<port>')
parser.add_argument('-t', '--timeout', type=int, default='10', help='Timeout in seconds for network connections', metavar='<seconds>')
parser.add_argument('-d', '--delay', type=float, default='15', help='Time delay for revisiting unfinished peers in minutes', metavar='<minutes>')
parser.add_argument('-l', '--loglevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Level of detail for log messages', metavar='<level>')
args = parser.parse_args()

# Check argument plausibility
if args.jobs is None and args.port is None:
	parser.error('Please enable active and/or passive peer evaluation via commandline switches')

# Set output path
directory = 'output/'
if not os.path.exists(directory):
	os.makedirs(directory)
output = directory + time.strftime('%Y-%m-%d_%H-%M-%S')

# Configure logging
numeric_level = getattr(logging, args.loglevel)
logfile = output + '.log'
logging.basicConfig(filename=logfile, format='[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', datefmt='%Hh%Mm%Ss', level=numeric_level)
print('Log is written to file ' + logfile)
logging.info('Logging messages up to ' + args.loglevel + ' level')

# Import torrent file
try:
	torrent = torrent_file.import_torrent(args.torrent)
except torrent_file.FileError as err:
	logging.error(str(err))
	raise SystemExit

# Create new database and initialize swarm analyzer
with peer_analyzer.SwarmAnalyzer(torrent, args.delay, args.timeout) as analyzer:
	# Start database archiver
	try:
		analyzer.start_database_archiver(output)
	except peer_analyzer.AnalyzerError as err:
		logging.error(str(err))
		raise SystemExit

	# Start active evaluator threads
	if args.jobs is not None:
		analyzer.start_tracker_requests(args.interval)
		analyzer.start_active_evaluation(args.jobs)

	# Start passive evaluation server
	if args.port is not None:
		try:
			analyzer.start_passive_evaluation(args.port)
		except peer_analyzer.AnalyzerError as err:
			logging.error(str(err))
			raise SystemExit

	# Wait for termination
	try:
		while True:
			time.sleep(1024)
	except KeyboardInterrupt:
		print('Please wait for termination ...')
		logging.info('Received interrupt signal, exiting')

# Print statistics
analyzer.log_statistics()

