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
parser.add_argument('-r', '--revisit', type=float, default='15', help='Time delay for revisiting unfinished peers in minutes', metavar='<minutes>')
parser.add_argument('--dht-node', type=int, help='Integrate an already running DHT node with the given UDP port', metavar='<port>')
parser.add_argument('--dht-control', type=int, help='Use an already running DHT node over the given localhost telnet port', metavar='<port>')
parser.add_argument('--dht-interval', type=int, default=15, help='Time delay between contacting the DHT in minutes', metavar='<minutes>')
parser.add_argument('-d', '--debug', action='store_true', help='Write log messages to stdout instead of a file and include debug messages')
args = parser.parse_args()

# Check argument plausibility
if args.jobs is None and args.port is None:
	parser.error('Please enable active and/or passive peer evaluation via commandline switches')
if args.dht_node is not None and args.dht_control is None:
	parser.error('When using a DHT node specify also the telnet control port')

# Set output path
directory = 'output/'
if not os.path.exists(directory):
	os.makedirs(directory)
output = directory + time.strftime('%Y-%m-%d_%H-%M-%S') + '_' + os.uname().nodename

# Configure logging
logging_config = {'format': '[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', 'datefmt': '%Hh%Mm%Ss'}
if args.debug:
	logging_config['level'] = logging.DEBUG
else:
	logging_config['level'] = logging.INFO
	logfile = output + '.log'
	print('Log is written to file ' + logfile)
	logging_config['filename'] = logfile
logging.basicConfig(**logging_config)
logging.info('Command line arguments are {}'.format(args))

# Analysis routine
try:
	with peer_analyzer.SwarmAnalyzer(args.revisit, args.timeout, output) as analyzer:
		# Import torrents from directory
		analyzer.import_torrents()

		# Handle evaluated peers
		analyzer.start_peer_handler()

		# Integrate DHT node
		if args.dht_node is not None:
			analyzer.start_dht(args.dht_node, args.dht_control, args.dht_interval) # start before evaluation, they announce node port

		# Start passive evaluation server
		if args.port is not None:
			analyzer.start_passive_evaluation(args.port)

		# Start active evaluator threads
		if args.jobs is not None:
			analyzer.start_tracker_requests(args.interval) # start after passive, needs bt_port
			analyzer.start_active_evaluation(args.jobs)

		# Wait for termination
		try:
			print('End with Ctrl+C')
			logging.info('End with "kill -SIGINT {}"'.format(os.getpid()))
			while True:
				time.sleep(1024)
		except KeyboardInterrupt:
			print('Please wait for termination ...')
			logging.info('Received interrupt signal, exiting')
except peer_analyzer.AnalyzerError as err:
	logging.critical(str(err))
	raise SystemExit
finally:
	analyzer.log_statistics()
print('Finished')

