#!/usr/bin/python3

# Built-in modules
import argparse
import time
import logging
import urllib.request
import urllib.parse
import random
import string
import sys
import http.client
import ipaddress
import struct

# Extern modules
import bencodepy

# Project modules
import peer_wire_protocol
import torrent_operator

# Intro
logging.basicConfig(level = logging.INFO)

# Argument parsing
parser = argparse.ArgumentParser(description='Analyzer of BitTorrent trackers and peers', epilog='Stefan Schindler, 2015')
parser.add_argument('-t', '--torrent', required=True, help='Specifies the torrent file to be examined', metavar='filename', dest='torrent_file')
args = parser.parse_args()
args_dict = vars(args)

# Extract announce URL and info hash
torrent = torrent_operator.torrent_file(args_dict['torrent_file'])
announce_url = torrent.get_announce_url()
info_hash = torrent.get_info_hash()

# Generate peer id
possible_chars = string.ascii_letters + string.digits
peer_id_list = random.sample(possible_chars, 20)
peer_id = ''.join(peer_id_list)
logging.info('Generated peer id is ' + peer_id)

# Assemble tracker request
request_parameters = {'info_hash': info_hash, 'peer_id': peer_id, 'port': '30301', 'uploaded': '0', 'downloaded': '0', 'left': '23'}
request_parameters['compact'] = '1'
request_parameters_optional = {'ip': None, 'event': None}
request_parameters_encoded = urllib.parse.urlencode(request_parameters)
request_parameters_bytes = request_parameters_encoded
request_url = announce_url + '?' + request_parameters_bytes
logging.info('Request URL is ' + request_url)

# Issue GET request
http_response = urllib.request.urlopen(request_url)
response_bencoded = http_response.read()
if http_response.status == http.client.OK:
	logging.info('HTTP response status code is OK')
else:
	logging.error('HTTP response status code is ' + http_response.status)
	sys.exit(1)
http_response.close()

# Decode response
response = bencodepy.decode(response_bencoded)
if b'failure reason' in response:
	failure_reason_bytes = response[b'failure reason']
	failure_reason = failure_reason_bytes.decode()
	logging.error('Query failed: ' + failure_reason)
	sys.exit(1)

# Extract request interval
interval = response[b'interval']
logging.info('Recommended request interval in seconds is ' + str(interval))

# Extract list of IPv4 peers in byte form
peers_bytes = response[b'peers']
peers_count = int(len(peers_bytes) / 6)
peer_bytes = []
for peer in range(0, peers_count):
	peer_start_byte = peer * 6
	peer_ip_bytes = peers_bytes[peer_start_byte:peer_start_byte + 4]
	peer_port_bytes = peers_bytes[peer_start_byte + 4:peer_start_byte + 6]
	peer_bytes.append((peer_ip_bytes, peer_port_bytes))
logging.info('Received number of IPv4 peers is ' + str(peers_count))

# Extract list of IPv6 peers in byte form
peers_bytes = response[b'peers6']
peers_count = int(len(peers_bytes) / 18)
for peer in range(0, peers_count):
	peer_start_byte = peer * 18
	peer_ip_bytes = peers_bytes[peer_start_byte:peer_start_byte + 16]
	peer_port_bytes = peers_bytes[peer_start_byte + 16:peer_start_byte + 18]
	peer_bytes.append((peer_ip_bytes, peer_port_bytes))
logging.info('Received number of IPv6 peers is ' + str(peers_count))

# Parse IP adresses and ports
peer_ips = []
for raw_peer in peer_bytes:
	peer_ip = str(ipaddress.ip_address(raw_peer[0]))
	peer_port_tuple = struct.unpack("!H", raw_peer[1])
	peer_port = peer_port_tuple[0]
	peer_ips.append((peer_ip, peer_port))
logging.info('Total number of received peers is ' + str(len(peer_ips)))

# Assemble peer handshake
handshake = peer_wire_protocol.pack_handshake(peer_id, info_hash)
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

