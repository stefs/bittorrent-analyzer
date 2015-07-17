# Built-in modules
import logging
import random
import http.client
import ipaddress
import struct
import urllib.request
import urllib.parse
import socket

# Project modules
import config
from util import *

# Extern modules
import bencodepy

## Communicating with a torrent tracker
class TrackerCommunicator:
	## Initialize a tracker
	#  @param peer_id Own peer id
	#  @param announce_url The announce URL representing the tracker
	#  @param total_pieces Number of total pieces of the torrent
	def __init__(self, peer_id, announce_url, total_pieces):
		self.peer_id = peer_id
		self.announce_url = announce_url
		self.first_announce = True
		logging.info('Port {} will be announced'.format(config.bittorrent_listen_port))

		# Faked transmission statistics as factors
		self.downloaded = int(config.fake_downloaded_stat * total_pieces)
		self.left = int(config.fake_left_stat * total_pieces)
		self.uploaded = int(config.fake_uploaded_stat * total_pieces)
		logging.info('Will announce {} downloaded, {} left, {} uploaded'.format(self.downloaded, self.left, self.uploaded))

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
		self.first_announce = False
		ips = parse_ips(ip_bytes)
		return interval, ips

	## Issue a HTTP GET request on the announce URL
	#  @param info_hash Info hash for the desired torrent
	#  @return Request interval, ip-port bytes block
	#  @exception TrackerError
	def _http_request(self, info_hash):
		# Assemble tracker request
		request_parameters = {'info_hash': info_hash, 'peer_id': self.peer_id, 'port': config.bittorrent_listen_port,
				'uploaded': str(self.uploaded), 'downloaded': str(self.downloaded), 'left': str(self.left)}
		request_parameters['compact'] = '1'
		if self.first_announce:
			request_parameters['event'] = 'started'
		request_parameters_encoded = urllib.parse.urlencode(request_parameters)
		request_url = self.announce_url + '?' + request_parameters_encoded
		logging.debug('Request URL is ' + request_url)

		# Issue GET request
		try:
			with urllib.request.urlopen(request_url, timeout=config.network_timeout) as http_response:
				if http_response.status == http.client.OK:
					logging.info('HTTP response status code is OK')
					response_bencoded = http_response.read()
				else:
					raise TrackerError('HTTP response status code is {}'.format(http_response.status))
		except (urllib.error.URLError, http.client.HTTPException) as err:
			raise TrackerError('Get request failed: ' + str(err))

		# Decode response
		try:
			response = bencodepy.decode(response_bencoded)
		except bencodepy.exceptions.DecodingError as err:
			raise TrackerError('Unable to decode response: {}'.format(err))
		logging.debug('Tracker response: {}'.format(response))
		if b'failure reason' in response:
			failure_reason = response[b'failure reason'].decode()
			raise TrackerError('Tracker responded with failure reason: {}'.format(failure_reason))

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
			raise TrackerError('Tracker did not send any peers: {}'.format(err))
		return interval, ip_bytes

	## Issue announce request according to http://www.bittorrent.org/beps/bep_0015.html
	#  and https://github.com/erindru/m2t/blob/75b457e65d71b0c42afdc924750448c4aaeefa0b/m2t/scraper.py
	#  @param info_hash Info hash for the desired torrent
	#  @exception OSError, TrackerError
	#  @return Request interval, ip-port bytes block
	def _udp_request(self, info_hash):
		# Establish connection
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(config.network_timeout)
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
			logging.warning('Bad UDP tracker connect response')

		# Send announce request
		transaction_id = udp_transaction_id()
		event = 2 if self.first_announce else 0
		req = struct.pack('!qii20s20sqqqiiiih', connection_id, 0x1, transaction_id, info_hash, self.peer_id.encode(),
				self.downloaded, self.left, self.uploaded,
				event, 0x0, 0x0, -1, config.bittorrent_listen_port)
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

	## Issue a request for download statistics to the tracker
	#  @param info_hash Info hash for the desired torrent
	#  @return seeders, completed, leechers
	#  @exception TrackerError
	def scrape_request(self, info_hash):
		# Assemble scrape URL
		scrape_url = self.announce_url.replace('announce', 'scrape')
		if 'scrape' not in scrape_url:
			raise TrackerError('Unable to assemble scrape URL')
		parsed = urllib.parse.urlparse(scrape_url)

		# Split on scheme
		if parsed.scheme in ["http", "https"]:
			return self._http_scrape(scrape_url, info_hash)
		elif parsed.scheme == "udp":
			try:
				return self._udp_scrape(scrape_url, info_hash)
			except (OSError, TrackerError) as err:
				raise TrackerError('UDP tracker request failed: {}'.format(err))
		else:
			raise TrackerError('Unsupported protocol: {}'.format(parsed.scheme))

	## Issue a HTTP GET request on the scrape URL
	#  @param info_hash Info hash for the desired torrent
	#  @return seeders, completed, leechers
	#  @exception TrackerError
	def _http_scrape(self, scrape_url, info_hash):
		# Assemble tracker request
		request_parameters = {'info_hash': info_hash}
		request_parameters_encoded = urllib.parse.urlencode(request_parameters)
		request_url = scrape_url + '?' + request_parameters_encoded
		logging.debug('Scrape URL is ' + request_url)

		# Issue GET request
		try:
			with urllib.request.urlopen(request_url, timeout=config.network_timeout) as http_response:
				if http_response.status == http.client.OK:
					logging.info('HTTP response status code is OK')
					response_bencoded = http_response.read()
				else:
					raise TrackerError('HTTP response status code is {}'.format(http_response.status))
		except (urllib.error.URLError, http.client.HTTPException) as err:
			raise TrackerError('Get request failed: ' + str(err))

		# Decode response
		try:
			response = bencodepy.decode(response_bencoded)
		except bencodepy.exceptions.DecodingError as err:
			raise TrackerError('Unable to decode response: {}'.format(err))
		logging.debug('Tracker response: {}'.format(response))
		if b'failure reason' in response:
			failure_reason = response[b'failure reason'].decode()
			raise TrackerError('Tracker responded with failure reason: {}'.format(failure_reason))

		# Extract file item
		try:
			item = response[b'files'][info_hash]
		except KeyError as err:
			raise TrackerError('Info hash not found')

		# Extract attributes
		try:
			seeders = item[b'complete']
		except KeyError as err:
			raise TrackerError('Complete value not found')
		try:
			completed = item[b'downloaded']
		except KeyError as err:
			raise TrackerError('Downloaded value not found')
		try:
			leechers = item[b'incomplete']
		except KeyError as err:
			raise TrackerError('Incomplete value not found')
		return seeders, completed, leechers

	## Issue scrape request
	#  @param info_hash Info hash for the desired torrent
	#  @return Request interval, ip-port bytes block
	#  @exception OSError, TrackerError
	def _udp_scrape(self, scrape_url, info_hash):
		# Establish connection
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(config.network_timeout)
		parsed_tracker = urllib.parse.urlparse(scrape_url)
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
			logging.warning('Bad UDP tracker connect response')

		# Send scrape request
		transaction_id = udp_transaction_id()
		req = struct.pack('!qii20s', connection_id, 0x2, transaction_id, info_hash)
		logging.debug('Scrape request is {}'.format(req))
		sock.sendto(req, conn)

		# Parse scrape response
		buf = sock.recvfrom(2048)[0]
		if len(buf) < 8:
			raise TrackerError('Wrong length scrape response: {}'.format(len(buf)))
		action = struct.unpack_from('!i', buf)[0]
		res_transaction_id = struct.unpack_from('!i', buf, 4)[0]
		if res_transaction_id != transaction_id:
			raise TrackerError('Transaction ID doesn\'t match in connection response! Expected {}, got {}'.format(
					transaction_id, res_transaction_id))
		if action == 0x3:
			raise TrackerError('Error while trying to get a connection response: {}'.format(error))
		elif action != 0x2:
			raise TrackerError('Wrong action received after announce request: {}'.format(action))

		# Extract desired information
		seeders = struct.unpack_from('!i', buf, 8)[0]
		completed = struct.unpack_from('!i', buf, 12)[0]
		leechers = struct.unpack_from('!i', buf, 16)[0]
		return seeders, completed, leechers

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
			logging.warning('Tracker sent invalid ip address: {}'.format(err))
			continue
		peer_port = struct.unpack("!H", ip_bytes[offset+4:offset+6])[0]
		ips.append((peer_ip, peer_port))
	return ips
