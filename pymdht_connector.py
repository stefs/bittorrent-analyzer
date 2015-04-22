# Built-in modules
import telnetlib
import threading
import logging

# Project modules
from error import *

# Threadsafe pymdht telnet communication
class DHT:
	## Construct a telnet controller for the given port
	#  @param control_port Telnet port to connect to
	#  @param timeout Timeout for node communication
	#  @exception DHTError
	def __init__(self, control_port, timeout):
		self.timeout = timeout
		try:
			self.dht = telnetlib.Telnet('localhost', control_port, self.timeout)
		except ConnectionRefusedError as err:
			raise DHTError('Cound not connect to telnet server at port {}: {}'.format(control_port, err))
		self.lock = threading.Lock()
		self.is_shutdown = False

	## Issue lookup for given info hash
	#  @param info_hash_hex Hex string representing the info hash
	#  @param bt_port Own BitTorrent listening port to be announced to nodes
	#  @return List of ip port tuples of peers
	#  @exception DHTError
	def get_peers(self, info_hash_hex, bt_port=None):
		# Test type of hash
		assert isinstance(info_hash_hex, str), 'info_hash_hex must be a string'

		# Receive peers
		if bt_port is None:
			bt_port = 0
		dht_response = list()
		request_line = '0 OPEN 0 HASH {} {}\n'.format(info_hash_hex.upper(), bt_port) # TODO use existing channel?
		logging.info('DHT lookup request: {}'.format(request_line.rstrip('\n')))
		with self.lock:
			try:
				self.dht.write(request_line.encode())
				while not self.is_shutdown:
					line = self.dht.read_until(b'\n', self.timeout)
					if line == b'':
						continue
					line = line.decode().rstrip('\r\n')
					dht_response.append(line)
					if 'CLOSE' in line:
						break
			except (OSError, EOFError) as err:
				raise DHTError('Telnet write failed: {}'.format(err))

		# Parse peers
		peers = list()
		for line in dht_response:
			if 'PEER' in line:
				ip_port = line.split(' ')[-1].split(':')
				peers.append((ip_port[0], int(ip_port[1])))
			elif not 'OPEN' in line and not 'CLOSE' in line:
				logging.error('Unexpected telnet line: {}'.format(line))
		logging.info('DHT lookup ended with {} peers'.format(len(peers)))
		return peers

	## Send STATS command for debug purposes
	def print_stats(self):
		try:
			self.dht.write(b'STATS\n')
		except (OSError, EOFError) as err:
			logging.warning('Telnet write failed: {}'.format(err))
		else:
			logging.info('Sent STATS command to DHT node')

	## Exit pymdht node and close telnet connection
	#  @param is_final Sends KILL instead of EXIT command
	def close(self, is_final=False):
		self.is_shutdown = True
		cmd = 'KILL' if is_final else 'EXIT'
		with self.lock:
			try:
				self.dht.write('{}\n'.format(cmd).encode())
			except OSError as err:
				logging.warning('Failed to send {} command: {}'.format(cmd, err))
			else:
				logging.info('Sent {} command to DHT node'.format(cmd))
			#self.dht.close() # TODO necessary? # debug

