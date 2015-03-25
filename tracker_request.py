# Built-in modules
import logging
import random
import string
import http.client
import ipaddress
import struct
import urllib.request
import urllib.parse
import socket

# Extern modules
import bencodepy

## Communicating with a torrent tracker
class TrackerCommunicator:
	## Initialize a tracker
	#  @param peer_id Own peer id
	#  @param announce_url The announce URL representing the tracker
	#  @param timeout Timeout for network operations in seconds
	#  @param port Port number to be announced to trackers
	def __init__(self, peer_id, announce_url, timeout, port=None):
		self.peer_id = peer_id
		self.announce_url = announce_url
		self.timeout = timeout
		self.port = 0 if port is None else port # TODO how react trackers to a zero port?

	## Issue a request for peers to the tracker
	#  @param info_hash Info hash for the desired torrent
	#  @return Request interval, ip-port list
	#  @exception TrackerError
	def announce_request(self, info_hash):
		parsed = urllib.parse.urlparse(self.announce_url)
		if parsed.scheme in ["http", "https"]:
			interval, ip_bytes = self._http_request(info_hash)
		elif parsed.scheme == "udp":
			try:
				interval, ip_bytes = self._udp_request(info_hash)
			except (OSError, TrackerError) as err:
				raise TrackerError('UDP tracker request failed: {}'.format(err))
		else:
			raise TrackerError('Unsupported protocol: {}'.format(parsed.scheme))
		ips = parse_ips(ip_bytes)
		#ips = random.sample(ips, 8) # debug
		return interval, ips

	## Issue a HTTP GET request on the announce URL
	#  @param info_hash Info hash for the desired torrent
	#  @return Request interval, ip-port bytes block
	#  @exception TrackerError
	def _http_request(self, info_hash):
		# Assemble tracker request
		request_parameters = {'info_hash': info_hash, 'peer_id': self.peer_id, 'port': self.port,
				'uploaded': '0', 'downloaded': '0', 'left': '23'} # TODO how to tamper the stats?
		request_parameters['compact'] = '1'
		request_parameters_optional = {'ip': None, 'event': None}
		request_parameters_encoded = urllib.parse.urlencode(request_parameters)
		request_parameters_bytes = request_parameters_encoded
		request_url = self.announce_url + '?' + request_parameters_bytes
		logging.debug('Request URL is ' + request_url)

		# Issue GET request
		try:
			with urllib.request.urlopen(request_url, timeout=self.timeout) as http_response:
				if http_response.status == http.client.OK:
					logging.info('HTTP response status code is OK')
					response_bencoded = http_response.read()
				else:
					raise TrackerError('HTTP response status code is ' + str(http_response.status))
		except (urllib.error.URLError, http.client.HTTPException) as err:
			raise TrackerError('Get request failed: ' + str(err))

		# Decode response
		try:
			response = bencodepy.decode(response_bencoded)
		except bencodepy.exceptions.DecodingError as err:
			raise TrackerError('Unable to decode response: ' + str(err))
		if b'failure reason' in response:
			failure_reason_bytes = response[b'failure reason']
			failure_reason = failure_reason_bytes.decode()
			raise TrackerError('Tracker responded with failure reason: ' + str(failure_reason))

		# Extract request interval
		try:
			interval = response[b'interval']
		except KeyError as err:
			interval = 0
		if type(interval) is not int:
			interval = 0

		# Extract list of IPv4 peers in byte form
		try:
			ip_bytes = response[b'peers']
		except KeyError as err:
			raise TrackerError('Tracker did not send any peers: ' + str(err))
		return interval, ip_bytes

	## Issue announce request according to according to http://www.bittorrent.org/beps/bep_0015.html
	#  and https://github.com/erindru/m2t/blob/75b457e65d71b0c42afdc924750448c4aaeefa0b/m2t/scraper.py
	#  @param info_hash Info hash for the desired torrent
	#  @exception OSError, TrackerError
	#  @return Request interval, ip-port bytes block
	def _udp_request(self, info_hash):
		# Establish connection
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(self.timeout)
		parsed_tracker = urllib.parse.urlparse(self.announce_url)
		conn = (socket.gethostbyname(parsed_tracker.hostname), parsed_tracker.port)

		# Send connect request
		connection_id = 0x41727101980
		action = 0x0
		transaction_id = udp_transaction_id()
		req = struct.pack('!qii', connection_id, action, transaction_id)
		sock.sendto(req, conn)

		# Parse connection id from connect response
		buf = sock.recvfrom(2048)[0]
		if len(buf) < 16:
			raise TrackerError('Wrong length connect response: {}'.format(len(buf)))
		action = struct.unpack_from('!i', buf)[0]
		res_transaction_id = struct.unpack_from('!i', buf, 4)[0]
		if res_transaction_id != transaction_id:
			raise TrackerError('Transaction ID doesn\'t match in connection response! Expected {}, got {}'.format(
					transaction_id, res_transaction_id))
		if action == 0x0:
			connection_id = struct.unpack_from('!q', buf, 8)[0]
		elif action == 0x3:
			error = struct.unpack_from('!s', buf, 8)
			raise TrackerError('Error while trying to get a connection response: {}'.format(error))
		else:
			pass

		# Send announce request
		transaction_id = udp_transaction_id()
		port = 0 if self.port is None else self.port
		req = struct.pack('!qii20s20sqqqiiiih', connection_id, 0x1, transaction_id, info_hash, self.peer_id.encode(),
				0x0, 0x0, 0x0, # downloaded, left, uploaded # TODO how to tamper these stats?
				0x0, 0x0, 0x0, -1, port)
		logging.debug('Announce request is {}'.format(req))
		sock.sendto(req, conn)

		# Parse announce response
		buf = sock.recvfrom(2048)[0]
		if len(buf) < 20:
			raise TrackerError('Wrong length announce response: {}'.format(len(buf)))
		elif len(buf) == 2048:
			logging.warning('Receive buffer may be too small')
		action = struct.unpack_from('!i', buf)[0]
		res_transaction_id = struct.unpack_from('!i', buf, 4)[0]
		if res_transaction_id != transaction_id:
			raise TrackerError('Transaction ID doesn\'t match in connection response! Expected {}, got {}'.format(
					transaction_id, res_transaction_id))
		if action == 0x3:
			raise TrackerError('Error while trying to get a connection response: {}'.format(error))
		elif action != 0x1:
			raise TrackerError('Wrong action received after announce request: {}'.format(action))

		# Extract desired information
		interval = struct.unpack_from('!i', buf, 8)[0]
		ip_bytes = buf[20:]
		return interval, ip_bytes

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

## Generate a transaction id for udp tracker protocol
#  @return Transaction id
def udp_transaction_id():
	return int(random.randrange(0, 255))

## Parses bytes to ip addresses and ports
#  @param ip_bytes Input block
#  @return list of ip port tuples
def parse_ips(ip_bytes):
	peers_count = int(len(ip_bytes) / 6)
	ips = list()
	for peer in range(0, peers_count):
		offset = peer * 6
		try:
			peer_ip = str(ipaddress.ip_address(ip_bytes[offset:offset+4]))
		except ValueError as err:
			logging.warning('Tracker sent invalid ip address: ' + str(err))
			continue
		peer_port = struct.unpack("!H", ip_bytes[offset+4:offset+6])[0]
		ips.append((peer_ip, peer_port))
	return ips

