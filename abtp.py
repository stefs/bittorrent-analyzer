#!/usr/bin/python3

# Built-in modules
import argparse
import logging
#import sys # debug

# Project modules
import torrent_file
import tracker_request
import peer_wire_protocol
#import peer_management # debug

# Intro
logging.basicConfig(level = logging.INFO)

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015')
parser.add_argument('-t', '--torrent', required=True, help='Specifies the torrent file to be examined', metavar='filename', dest='torrent_file')
args = parser.parse_args()
args_dict = vars(args)

# Extract announce URL and info hash
torrent = torrent_file.torrent(args_dict['torrent_file'])
announce_url = torrent.get_announce_url()
info_hash = torrent.get_info_hash()

# Get peers from tracker
own_peer_id = tracker_request.generate_peer_id()
tracker = tracker_request.tracker(own_peer_id, announce_url)
peer_ips = tracker.get_peers(info_hash)

# Assemble peer handshake
handshake = peer_wire_protocol.pack_handshake(own_peer_id, info_hash)
logging.info('Prepared handshake is ' + str(handshake))

# Get bitmap from peers
for peer_ip in peer_ips:
	# Collect all messages from peer
	try:
		# Use peer_session in with clause to ensure socket close
		with peer_wire_protocol.peer_session(peer_ip) as session:
			# Exchange handshakes
			session.send_bytes(handshake)
			received_peer_id = session.receive_handshake(info_hash)
			logging.info('ID of connected peer is ' + str(received_peer_id))

			# Collect all messages from peer
			while session.has_message():
				message = session.receive_message()
				message_str = peer_wire_protocol.message_to_string(message, 80)
				logging.info('Received message: ' + message_str)
	except peer_wire_protocol.PeerFailure as err:
		logging.warning('Error during peer evaluation: ' + str(err))
	
# Put peer list in SQLight database
# TODO

