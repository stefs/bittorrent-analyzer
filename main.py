#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import struct
import threading
import traceback

# Project modules
import torrent_file
import tracker_request
import peer_wire_protocol
import peer_management

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015')
parser.add_argument('-f', '--file', required=True, help='Torrent file to be examined', metavar='<filename>')
parser.add_argument('-t', '--timeout', type=int, default='10', help='Timeout in seconds for network connections', metavar='<seconds>')
parser.add_argument('-l', '--loglevel', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Level of detail for log messages', metavar='<level>')
parser.add_argument('-j', '--jobs', type=int, default='1', help='Number of threads used for peer connections', metavar='<number>')
args = parser.parse_args()

# Set logging level
numeric_level = getattr(logging, args.loglevel)
logging.basicConfig(format='[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', datefmt='%Hh%Mm%Ss', level = numeric_level)

# Log arguments
logging.info('Analyzing peers of torrent file ' + args.file)
logging.info('Timeout for network operations is ' + str(args.timeout) + ' seconds')
logging.info('Logging messages up to ' + args.loglevel + ' level')
logging.info('Connecting to peers in ' + str(args.jobs) + ' threads')

# Extract announce URL and info hash
# TODO expect exceptions
torrent = torrent_file.TorrentParser(args.file)
announce_url = torrent.get_announce_url()
info_hash = torrent.get_info_hash()
pieces_number = torrent.get_pieces_number()

# Get peers from tracker
own_peer_id = tracker_request.generate_peer_id()
tracker = tracker_request.TrackerCommunicator(own_peer_id, announce_url)
peer_ips = tracker.get_peers(info_hash)

# Create peer cache
with peer_management.PeerCache(0) as peers:
	# Fill with initial peers
	for peer_ip in peer_ips:
		peers.add_new(peer_ip)

	## Worker method to be started as a thread
	def worker():
		# Ends when daemon thread dies
		while True:
			# Get new peer
			peer = peers.in_progress.get()
			peer_tuple = (peer.ip_address, peer.port)
		
			# Receive messages and peer_id
			try:
				# Use peer_session in with clause to ensure socket close
				with peer_wire_protocol.PeerSession(peer_tuple, args.timeout, info_hash, own_peer_id) as session: # OSError
					peer_id = session.exchange_handshakes()[0] # OSError, PeerError
					messages = session.receive_all_messages(100)
			except (OSError, peer_wire_protocol.PeerError) as err:
				logging.warning('Peer evaluation failed: ' + str(err))
			except Exception as err:
				# Catch all exceptions to enable ongoing analysis
				logging.critical('Unexpected error during peer evaluation: ' + str(err))
				traceback.print_tb(err.__traceback__)
			
			# Calculate and save results
			else:
				bitfield = peer_wire_protocol.bitfield_from_messages(messages, pieces_number)
				peer = peer_management.CachedPeer(peer.ip_address, peer.port, peer_id, bitfield)

				# Catch all exeptions for debug purposes only
				try: # debug
					peers.add_success(peer, pieces_number)
				except Exception as err: # debug
					logging.critical('Unexpected error during peer save process: ' + str(err)) # debug
					traceback.print_tb(err.__traceback__)

			# Queue.task_done() to allow Queue.join()
			finally:
				peers.in_progress.task_done()

	# Create thread pool
	for i in range(args.jobs):
		# Create a thread with worker callable
		thread = threading.Thread(target=worker)
		# Thread dies when main thread exits, requires Queue.join()
		thread.daemon = True
		# Start thread
		thread.start()

	# Wait for all peers to be parsed
	# TODO allow connection termination in subthreads when main thread terminates (e.g. on KeyboardInterrupt) via signal.signal
	peers.in_progress.join()

logging.info('Number of error peers is ' + str(len(peers.error)))
logging.info('Number of finished peers is ' + str(peers.finished_count))

