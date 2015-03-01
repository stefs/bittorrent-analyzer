#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import struct
import threading
import traceback
import queue
import time
import random

# Project modules
import torrent_file
import tracker_request
import peer_wire_protocol
import peer_storage

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

# Extract announce URL and info hash
try:
	torrent = torrent_file.TorrentParser(args.file)
	announce_url = torrent.get_announce_url()
	info_hash = torrent.get_info_hash()
	pieces_number = torrent.get_pieces_number()
except torrent_file.FileError as err:
	logging.error('Bad torrent file: ' + str(err))
	raise SystemExit

# Get peers from tracker
own_peer_id = tracker_request.generate_peer_id()
tracker = tracker_request.TrackerCommunicator(own_peer_id, announce_url)
try:
	peer_ips = tracker.get_peers(info_hash)
except (tracker_request.TrackerError) as err:
	logging.error('Unable to get peers from tracker: ' + str(err))
	raise SystemExit
#peer_ips = random.sample(peer_ips, 5) # debug

# Statistic counters
statistic_lock = threading.Lock()
revisit_count = error_count = store_count = 0

# Create peer cache
in_progress = queue.PriorityQueue()
for peer_ip in peer_ips:
	new_peer = peer_storage.CachedPeer(revisit=0, ip_address=peer_ip[0], port=peer_ip[1], id=None, bitfield=None, pieces=None, key=None)
	in_progress.put(new_peer)

## Returns the numbers of bits set in an integer
#  @param byte An arbitrary integer between 0 and 255
#  @return Count of 1 bits in the binary representation of byte
def count_bits(byte):
	assert 0 <= byte <= 255, 'Only values between 0 and 255 allowed'
	mask = 1
	count = 0
	for i in range(0,8):
		masked_byte = byte & mask
		if masked_byte > 0:
			count += 1
		mask *= 2
	return count

# Create new database
with peer_storage.PeerDatabase() as database:
	## Worker method to be started as a thread
	#  @param SQLAlchemy database scoped session object
	def worker(database_session):
		# Log thread id
		logging.info('The identifier for this worker thread is ' + str(threading.get_ident()))
		# Ends when daemon thread dies
		while True:
			# Get new peer
			peer = in_progress.get()
			if peer.key is not None:
				logging.info('Revisiting peer with database id ' + str(peer.key))
				global revisit_count
				with statistic_lock:
					revisit_count += 1
		
			# Delay evaluation
			delay = peer.revisit - time.perf_counter()
			if delay > 0:
				logging.info('Delaying peer evaluation for ' + str(delay) + ' seconds ...')
				time.sleep(delay)
	
			# Receive messages and peer_id
			peer_tuple = (peer.ip_address, peer.port)
			try:
				# Use peer_session in with clause to ensure socket close
				with peer_wire_protocol.PeerSession(peer_tuple, args.timeout, info_hash, own_peer_id) as session:
					peer_id = session.exchange_handshakes()[0]
					messages = session.receive_all_messages(100)
			except peer_wire_protocol.PeerError as err:
				global error_count
				with statistic_lock:
					error_count += 1
				logging.warning('Peer evaluation failed: ' + str(err))
			except Exception as err:
				# Catch all exceptions to enable ongoing analysis
				logging.critical('Unexpected error during peer evaluation: ' + str(err))
				traceback.print_tb(err.__traceback__)
			else:
				# Receive bitfield
				bitfield = peer_wire_protocol.bitfield_from_messages(messages, pieces_number)
			
				# Count finished pieces
				pieces_count = 0
				for byte in bitfield:
					pieces_count += count_bits(byte)
				percentage = int(pieces_count * 100 / pieces_number)
				remaining = pieces_number - pieces_count
				logging.info('Peer reports to have ' + str(pieces_count) + ' pieces, ' + str(remaining) + ' remaining, equals ' + str(percentage) + '%')
				
				# Save results
				delay_seconds = args.delay * 60
				revisit_time = time.perf_counter() + delay_seconds
				peer = peer_storage.CachedPeer(revisit_time, peer.ip_address, peer.port, peer_id, bitfield, pieces_count, peer.key)
				try:
					database_id = database.store(peer, 0, database_session) # TODO give torrent id
				except Exception as err:
					database_session.rollback()
					logging.critical('Unexpected error during database update: ' + str(err))
					raise
				global store_count
				with statistic_lock:
					store_count += 1

				
				# Remember database id if necesarry
				if peer.key is None:
					*old_peer, key = peer
					peer = peer_storage.CachedPeer(*old_peer, key=database_id)
				
				# Write back in progress peers, discard finished ones
				if remaining > 0:
					in_progress.put(peer)
				
			# Queue.task_done() to allow Queue.join()
			in_progress.task_done()

	# Create thread pool
	for i in range(args.jobs):
		# Get thread safe session object
		database_session = database.get_session()
		# Create a thread with worker callable and pass it it's own session
		thread = threading.Thread(target=worker, args=(database_session,))
		# Thread dies when main thread exits, requires Queue.join()
		thread.daemon = True
		# Start thread
		thread.start()

	try:
		# Wait for all peers to be parsed
		in_progress.join()
	except KeyboardInterrupt as err:
		logging.info('Caught keyboard interrupt, exiting')
		# TODO allow socket.close and session.close in subthreads via a signal
	else:
		logging.info('Evaluation finished, exiting')
	finally:
		# Log some statistics
		logging.info('Number of revisited peers is ' + str(revisit_count))
		logging.info('Number of failed peer evaluations is ' + str(error_count))
		logging.info('Database access count is ' + str(store_count))

