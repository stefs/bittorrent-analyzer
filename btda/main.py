#!/usr/bin/env python3

# Built-in modules
import argparse

# Project modules
import analyzer

# Argument parsing
parser = argparse.ArgumentParser(description='BitTorrent Download Analyzer', epilog='Stefan Schindler, 2015')
parser.add_argument('-a', '--active', action='store_true', help='Actively contact peers in multiple threads')
parser.add_argument('-p', '--passive', action='store_true', help='Passive peer evaluation by listening for incoming connections')
parser.add_argument('-d', '--dht', action='store_true', help='Integrate an already running DHT node')
parser.add_argument('-g', '--debug', action='store_true', help='Write log messages to stdout instead of a file and include debug messages')
args = parser.parse_args()

# Check argument plausibility
if not args.active and not args.passive:
	parser.error('Please enable active and/or passive peer evaluation')

# Analysis routine
with analyzer.SwarmAnalyzer(args.debug) as app:
	# Indicate initialization process
	print('Initialize evaluation process ...')

	# Import torrents
	app.import_magnets()
	app.import_torrents()
	app.torrent_duplicates()

	# Requesting new peers
	app.start_tracker_requests()
	if args.dht:
		app.start_dht_requests()

	# Actively contact and evaluate peers
	if args.active:
		app.start_active_evaluation()

	# Evaluate incoming peers
	if args.passive:
		app.start_passive_evaluation()

	# Store evaluated peers in database
	app.start_peer_handler()

	# Store connection statistics in database
	app.log_connection_stats()

	# Wait for termination
	print('Evaluation running, end with Ctrl+C')
	app.wait_for_sigint()
