#!/usr/bin/env python3

# Built-in modules
import argparse
import logging
import struct
import threading
import math
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

# Assemble peer handshake
handshake = peer_wire_protocol.pack_handshake(own_peer_id, info_hash)

## Calculates the number of bytes deeded to store some bits
#  @param bits Number of input bits
#  @return Number of output bits
def bytes_needed(bits):
	return math.ceil(bits / 8)

## Connects to peer and reconstructs bitfield out of all messages received
#  @param peer CachedPeer tuple
#  @param pieces_number Number of pieces contained in this torrent, minimum 1
#  @param timeout Timeout in seconds for the network connection
#  @return Received peer ID and bitfield as a tuple
def get_peer_bitfield(peer, pieces_number, timeout):
	# Collect all messages from peer
	messages = list()
	try:
		# Use peer_session in with clause to ensure socket close
		with peer_wire_protocol.PeerSession(peer, timeout) as session:
			# Exchange handshakes
			session.send_bytes(handshake)
			received_peer_id = session.receive_handshake(info_hash)[0]

			# Receive messages until timeout or error # TODO set limit
			while True:
				message = session.receive_message()
				messages.append(message)
	except peer_wire_protocol.PeerError as err:
		if messages:
			logging.info('Connection terminated: ' + str(err))
		else:
			raise

	# Evaluate messages
	bitfield = bytearray(pieces_number)
	bitfield_count = have_count = other_count = 0
	for message in messages:
		# Store bitfields
		if message[0] == 5:
			# Check for correct length of bytes
			needed_bytes = bytes_needed(pieces_number)
			if len(message[1]) != needed_bytes:
				logging.warning('Peer sent invalid bitfield of length ' + str(len(message[1])) + ', expected was ' + str(needed_bytes))
				continue

			# Check for correct sparse zero bits in last byte
			zeros_count = needed_bytes * 8 - pieces_number
			zeros_mask = 2 ** zeros_count - 1
			masked_padding = message[1][-1] & zeros_mask
			if masked_padding != 0:
				logging.warning('Peer sent invalid bitfield with padding bits ' + str(masked_padding) + ' instead of zeros')
				continue

			# Assign new bitfield
			bitfield = bytearray(message[1])
			bitfield_count += 1

		# Note have messages in local bitfield
		elif message[0] == 4:
			piece_index_tuple = struct.unpack('>I', message[1])
			piece_index = piece_index_tuple[0]
			if piece_index <= pieces_number:
				set_bit_at_index(bitfield, piece_index)
				have_count += 1
			else:
				logging.warning('Peer sent a have message with out of bounds piece index')
		
		# Unknown or other message
		else:
			other_count += 1
	
	# Return peer_id and bitfield
	logging.info('Number of valid messages received: ' + str(bitfield_count) + ' bitfield, ' + str(have_count) + ' have, ' + str(other_count) + ' other')
	return (received_peer_id, bitfield)

## Sets a bit at a given index in a given bitfield on true
#  @param bitfield The bitfield to be altered as a bytearray
#  @param index The position to be changed, 0 refers to highest bit of first byte
#  @warn The bitfield parameter must be a bytearray, not of the bytes type, not of type string
def set_bit_at_index(bitfield, index):
	# Devide index in byte index (0123...) and bit index (76543210)
	byte_index = int(index / 8)
	bit_index = 8 - index % 8

	# Alter affected byte
	byte_before = bitfield[byte_index]
	byte_after = byte_before | bit_index
	logging.debug('Bit ' + str(index) + ' equals bit ' + str(bit_index) + ' in byte ' + str(byte_index) + ', converted ' + str(byte_before) + ' to ' + str(byte_after))

	# Write back
	bitfield[byte_index] = byte_after
	return bitfield

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
		
			# Receive bitfield and peer_id
			peer_tuple = (peer.ip_address, peer.port)
			try:
				peer_id, bitfield = get_peer_bitfield(peer_tuple, pieces_number, args.timeout)
			except peer_wire_protocol.PeerError as err:
				logging.warning('Peer evaluation failed: ' + str(err))
				peers.add_error(peer)

			# Catch all exceptions to enable ongoing analysis
			except Exception as err:
				logging.critical('Unexpected error during peer evaluation: ' + str(err))
				traceback.print_tb(err.__traceback__)
			else:
				peer = peer_management.CachedPeer(peer.ip_address, peer.port, peer_id, bitfield)

				# Catch all exeptions for debug purposes only
				try: # debug
					peers.add_success(peer, pieces_number)
				except Exception as err: # debug
					logging.critical('Unexpected error during peer save process: ' + str(err)) # debug
			finally:
				# Allows Queue.join()
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

