#!/usr/bin/env python3

# Built-in modules
import argparse

# Project modules
import peer_analyzer

# Argument parsing
parser = argparse.ArgumentParser(description='BitTorrent Download Analyzer', epilog='Stefan Schindler, 2015')
parser.add_argument('-t', '--torrent', help='Read torrent files from the specified directory', metavar='<directory>')
parser.add_argument('-m', '--magnet', help='Read one magnet link per line from file instead torrent files', metavar='<filename>')
parser.add_argument('-a', '--active', type=int, help='Active peer evaluation using the specified number of threads', metavar='<threads>')
parser.add_argument('-p', '--passive', action='store_true', help='Passive peer evaluation by listening for incoming connections')
parser.add_argument('-d', '--dht', action='store_true', help='Integrate an already running DHT node')
parser.add_argument('-g', '--debug', action='store_true', help='Write log messages to stdout instead of a file and include debug messages')
args = parser.parse_args()

# Check argument plausibility
if args.torrent is None and args.magnet is None:
	parser.error('Please import torrents via torrent files or magnet links')
if args.active is None and not args.passive:
	parser.error('Please enable active and/or passive peer evaluation')
if args.magnet is not None and not args.dht:
	parser.error('Cannot use magnet links without DHT')

# Analysis routine
with peer_analyzer.SwarmAnalyzer(args.debug) as analyzer:
	# Import torrents
	if args.magnet is not None:
		analyzer.import_magnets(args.magnet)
	if args.torrent is not None:
		analyzer.import_torrents(args.torrent)

	# Requesting peers from tracker
	analyzer.start_tracker_requests()

	# Requesting peers from DHT
	if args.dht:
		analyzer.start_dht_requests()

	# Actively contact and evaluate peers
	if args.active is not None:
		analyzer.start_active_evaluation(args.active)

	# Evaluate incoming peers
	if args.passive:
		analyzer.start_passive_evaluation()

	# Store evaluated peers in database
	analyzer.start_peer_handler()

	# Wait for termination
	analyzer.wait_for_sigint()

