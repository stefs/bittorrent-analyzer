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

	## Issue a request for peers to the tracker
	#  @param info_hash Info hash for the desired torrent
	#  @exception TrackerError
	def issue_request(self, info_hash):
		parsed = urllib.parse.urlparse(self.announce_url)
		if parsed.scheme in ["http", "https"]:
			self._http_request(info_hash)
		elif parsed.scheme == "udp":
			self._udp_request(info_hash)
		else:
			raise TrackerError('Unsupported protocol: {}'.format(parsed.scheme))

	## Issue a HTTP GET request on the announce URL
	#  @param info_hash Info hash for the desired torrent
	#  @exception TrackerError
	def _http_request(self, info_hash):
		# Assemble tracker request
		request_parameters = {'info_hash': info_hash, 'peer_id': self.peer_id, 'port': '30301', 'uploaded': '0', 'downloaded': '0', 'left': '23'}
		request_parameters['compact'] = '1'
		request_parameters_optional = {'ip': None, 'event': None}
		request_parameters_encoded = urllib.parse.urlencode(request_parameters)
		request_parameters_bytes = request_parameters_encoded
		request_url = self.announce_url + '?' + request_parameters_bytes
		logging.debug('Request URL is ' + request_url)

		# Issue GET request
		try:
			with urllib.request.urlopen(request_url) as http_response:
				if http_response.status == http.client.OK:
					logging.info('HTTP response status code is OK')
					response_bencoded = http_response.read()
				else:
					raise TrackerError('HTTP response status code is ' + str(http_response.status))
		except (urllib.error.URLError, http.client.HTTPException) as err:
			raise TrackerError('Get request failed: ' + str(err))

		# Decode response
		try:
			self.response = bencodepy.decode(response_bencoded)
		except bencodepy.exceptions.DecodingError as err:
			raise TrackerError('Unable to decode response: ' + str(err))
		if b'failure reason' in self.response:
			failure_reason_bytes = self.response[b'failure reason']
			failure_reason = failure_reason_bytes.decode()
			raise TrackerError('Tracker responded with failure reason: ' + str(failure_reason))

	## Issue announce request according to according to http://www.bittorrent.org/beps/bep_0015.html
	#  @param info_hash Info hash for the desired torrent
	def _udp_request(self, info_hash):
		raise NotImplementedError # TODO
		# Send connect request

		# Parse connection id from connect response

		# Send announce request

		# Pase announce response

	## Extract recommended request interval from response
	#  @return Recommended request interval in seconds
	#  @exception TrackerError
	#  @note Call issue_request method first
	def get_interval(self):
		try:
			interval = self.response[b'interval']
		except KeyError as err:
			raise TrackerError('Tracker did not send a recommended request interval: ' + str(err))

		if type(interval) is int:
			logging.info('Recommended request interval is ' + str(interval/60) + ' minutes')
			return interval
		else:
			raise TrackerError('Tracker sent invalid request interval')

	## Extract minimum request interval from response if present, since this is an optional value
	#  @return Minimum request interval in seconds or None
	#  @note Call issue_request method first
	def get_min_interval(self):
		try:
			min_interval = self.response[b'min interval']
		except KeyError as err:
			logging.info('Tracker did not send a minimum request interval: ' + str(err))
			return None

		if type(min_interval) is int:
			logging.info('Minimum request interval in is ' + str(min_interval/60) + ' minutes')
			return min_interval
		else:
			logging.warning('Tracker sent invalid minimum request interval')
			return None

	## Extract peer list from response
	#  @return Tuples list of IPv4 or IPv6 addresses and port numbers
	#  @exception TrackerError
	#  @note Call issue_request method first
	def get_peers(self):
		# Extract list of IPv4 peers in byte form
		try:
			peers_bytes = self.response[b'peers']
		except KeyError as err:
			raise TrackerError('Tracker did not send any peers: ' + str(err))
		ipv4_peers_count = int(len(peers_bytes) / 6)
		peer_bytes = list()
		for peer in range(0, ipv4_peers_count):
			peer_start_byte = peer * 6
			peer_ip_bytes = peers_bytes[peer_start_byte:peer_start_byte + 4]
			peer_port_bytes = peers_bytes[peer_start_byte + 4:peer_start_byte + 6]
			peer_bytes.append((peer_ip_bytes, peer_port_bytes))

		# Extract list of IPv6 peers in byte form
		ipv6_peers_count = 0
		if b'peers6' in self.response:
			peers_bytes = self.response[b'peers6']
			ipv6_peers_count = int(len(peers_bytes) / 18)
			for peer in range(0, ipv6_peers_count):
				peer_start_byte = peer * 18
				peer_ip_bytes = peers_bytes[peer_start_byte:peer_start_byte + 16]
				peer_port_bytes = peers_bytes[peer_start_byte + 16:peer_start_byte + 18]
				peer_bytes.append((peer_ip_bytes, peer_port_bytes))
		logging.info('Received number of IPv4 peers is ' + str(ipv4_peers_count) + ', number of IPv6 peers is ' + str(ipv6_peers_count))

		# Parse IP adresses and ports
		peer_ips = list()
		for raw_peer in peer_bytes:
			try:
				peer_ip = str(ipaddress.ip_address(raw_peer[0]))
			except ValueError as err:
				logging.warning('Tracker sent invalid ip address: ' + str(err))
			else:
				peer_port_tuple = struct.unpack("!H", raw_peer[1])
				peer_port = peer_port_tuple[0]
				peer_ips.append((peer_ip, peer_port))

		# Return combined IPv4 and IPv6 list
		#import random # debug
		#peer_ips = random.sample(peer_ips, 8) # debug
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

