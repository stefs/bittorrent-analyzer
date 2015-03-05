#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import threading
import time

# Project modules
import peer_analyzer
import peer_storage
import torrent_file

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('torrent', help='File system path to the torrent file to be examined', metavar='<torrent>')
parser.add_argument('-j', '--jobs', type=int, default='1', help='Number of threads used for peer connections', metavar='<number>')
parser.add_argument('-t', '--timeout', type=int, default='10', help='Timeout in seconds for network connections', metavar='<seconds>')
parser.add_argument('-d', '--delay', type=float, default='10', help='Time delay for revisiting unfinished peers in minutes', metavar='<minutes>')
parser.add_argument('-i', '--interval', type=float, help='Time delay between asking the tracker server for new peers in minutes, defaults to a value recommended by the tracker server', metavar='<minutes>')
parser.add_argument('-l', '--loglevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Level of detail for log messages', metavar='<level>')
args = parser.parse_args()

# Set logging level
numeric_level = getattr(logging, args.loglevel)
logging.basicConfig(format='[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', datefmt='%Hh%Mm%Ss', level = numeric_level)

# Log arguments
logging.info('Analyzing peers of torrent file ' + args.torrent)
logging.info('Timeout for network operations is ' + str(args.timeout) + ' seconds')
logging.info('Logging messages up to ' + args.loglevel + ' level')
logging.info('Connecting to peers in ' + str(args.jobs) + ' threads')
logging.info('Time delay for revisiting unfinished peers is ' + str(args.delay) + ' minutes')
if args.interval is None:
	logging.info('The interval between asking the tracker for new peers will be extracted from the tracker\'s response')
else:
	logging.info('The interval between asking the tracker for new peers is ' + str(args.interval) + ' minutes')
logging.info('The identifier for the main thread is ' + str(threading.get_ident()))

# Create new database
with peer_storage.PeerDatabase() as database:
	# Import torrent file
	try:
		torrent = torrent_file.import_torrent(args.torrent)
	except torrent_file.FileError as err:
		logging.error('Could not import torrent file: ' + str(err))
		raise SystemExit

	# Initialize SwarmAnalyzer
	try:
		analyzer = peer_analyzer.ActiveAnalyzer(database, torrent, args.delay, args.timeout)
	except peer_analyzer.AnalyzerError as err:
		logging.error(str(err))
		raise SystemExit

	# Start worker threads
	analyzer.start_threads(args.jobs)

	while True:
		# Request new peers
		analyzer.get_new_peers()

		# Calculate interval
		try:
			interval = analyzer.get_interval(args.interval)
		except peer_analyzer.AnalyzerError as err:
			logging.error(str(err))
			raise SystemExit

		# Wait accordingly
		try:
			time.sleep(interval)
		except KeyboardInterrupt as err:
			# TODO allow socket.close and session.close in subthreads via a signal
			logging.info('Received interrupt signal, exiting')
			analyzer.log_statistics()
			raise SystemExit

