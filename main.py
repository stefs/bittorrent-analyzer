#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import threading

# Project modules
import peer_analyzer
import peer_storage
import torrent_file
import tracker_request

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015')
parser.add_argument('-f', '--file', required=True, help='Torrent file to be examined', metavar='<filename>')
parser.add_argument('-t', '--timeout', type=int, default='10', help='Timeout in seconds for network connections', metavar='<seconds>')
parser.add_argument('-l', '--loglevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Level of detail for log messages', metavar='<level>')
parser.add_argument('-j', '--jobs', type=int, default='1', help='Number of threads used for peer connections', metavar='<number>')
parser.add_argument('-d', '--delay', type=float, default='10', help='Time delay for revisiting unfinished peers in minutes', metavar='<minutes>')
args = parser.parse_args()

# Set logging level
numeric_level = getattr(logging, args.loglevel)
logging.basicConfig(format='[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', datefmt='%Hh%Mm%Ss', level = numeric_level)

# Log arguments
logging.info('Analyzing peers of torrent file ' + args.file)
logging.info('Timeout for network operations is ' + str(args.timeout) + ' seconds')
logging.info('Logging messages up to ' + args.loglevel + ' level')
logging.info('Connecting to peers in ' + str(args.jobs) + ' threads')
logging.info('Time delay for revisiting unfinished peers is ' + str(args.delay) + ' minutes')
logging.info('The identifier for the main thread is ' + str(threading.get_ident()))

# Create new database
with peer_storage.PeerDatabase() as database:
	try:
		analyzer = peer_analyzer.SwarmAnalyzer(database, args.file, args.delay, args.timeout)
		analyzer.get_new_peers()
	except peer_analyzer.AnalyzerError as err:
		logging.error(str(err))
		raise SystemExit

	try:
		analyzer.run(args.jobs)
	except KeyboardInterrupt as err:
		# TODO allow socket.close and session.close in subthreads via a signal
		logging.info('Caught keyboard interrupt, exiting')
	else:
		# TODO allow session.close in subthreads via a signal
		logging.info('Evaluation finished, exiting')
	finally:
		analyzer.log_statistics()

