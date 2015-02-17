# Built-in modules
import logging
import random
import string
import http.client
import ipaddress
import struct
import urllib.request
import urllib.parse

# Extern modules
import bencodepy

## Communicating with a torrent tracker
class TrackerCommunicator:
	## Initialize a tracker
	#  @param peer_id Own peer id
	#  @param announce_url The announce URL representing the tracker
	def __init__(self, peer_id, announce_url):
		self.peer_id = peer_id
		self.announce_url = announce_url
	
	## Issue a HTTP GET request on the announce URL
	#  @param info_hash Info hash for the desired torrent
	#  @return Tuples list of IPv4 or IPv6 addresses and port numbers
	# TODO raise TrackerErrors where appropriate
	def get_peers(self, info_hash):
		# Assemble tracker request
		request_parameters = {'info_hash': info_hash, 'peer_id': self.peer_id, 'port': '30301', 'uploaded': '0', 'downloaded': '0', 'left': '23'}
		request_parameters['compact'] = '1'
		request_parameters_optional = {'ip': None, 'event': None}
		request_parameters_encoded = urllib.parse.urlencode(request_parameters)
		request_parameters_bytes = request_parameters_encoded
		request_url = self.announce_url + '?' + request_parameters_bytes
		logging.debug('Request URL is ' + request_url)

		# Issue GET request
		http_response = urllib.request.urlopen(request_url)
		response_bencoded = http_response.read()
		if http_response.status == http.client.OK:
			logging.info('HTTP response status code is OK')
		else:
			raise TrackerException('HTTP response status code is ' + http_response.status)
		http_response.close()

		# Decode response
		response = bencodepy.decode(response_bencoded)
		if b'failure reason' in response:
			failure_reason_bytes = response[b'failure reason']
			failure_reason = failure_reason_bytes.decode()
			logging.error('Query failed: ' + failure_reason)
			sys.exit(1)

		# Extract request interval
		# TODO interval is not exported at the moment
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
			try:
				peer_ip = str(ipaddress.ip_address(raw_peer[0]))
			except ValueError as err:
				logging.warning('Tracker sent invalid ip address: ' + str(err))
				continue
			peer_port_tuple = struct.unpack("!H", raw_peer[1])
			peer_port = peer_port_tuple[0]
			peer_ips.append((peer_ip, peer_port))

		# Return combined IPv4 and IPv6 list
		return peer_ips

## Exception for bad tracker response
class TrackerError(Exception):
	pass

## Generate a random peer id without client software information
#  @return A random peer id as a string
def generate_peer_id():
	possible_chars = string.ascii_letters + string.digits
	peer_id_list = random.sample(possible_chars, 20)
	peer_id = ''.join(peer_id_list)
	logging.info('Generated peer id is ' + peer_id)
	return peer_id

