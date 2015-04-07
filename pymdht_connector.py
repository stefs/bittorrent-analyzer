import telnetlib
import threading

# Threadsafe pymdht telnet communication
class DHT:
	## Construct a telnet controller for the given port
	#  @param control_port Telnet port to connect to
	def __init__(self, control_port):
		try:
			# TODO assure telnet is only reachable on locally
			self.dht = telnetlib.Telnet(host='localhost', port=control_port)
		except ConnectionRefusedError as err:
			raise DHTError('Cound not connect to DHT telnet control server at port {}: {}'.format(control_port, err))
		self.lock = threading.Lock()

	## Issue lookup for given info hash
	#  @param info_hash_hex Hex string representing the info hash
	#  @return List of ip port tuples of peers
	def get_peers(self, info_hash_hex):
		with self.lock:
			try:
				self.dht.write('0 OPEN 0 HASH {} 0'.format(info_hash_hex.encode()) # debug
				dht_response = self.dht.read_until(b'CLOSE')
			except OSError:
				logging.error('Could not write to DHT telnet control')

	## Insert nodes in routing table
	#  @param nodes List of ip port tuples of nodes
	def add_nodes(self, nodes):
		raise NotImplementedError

	## Kill pymdht node and close telnet connection
	def shutdown(self):
		with self.lock:
			try:
				self.dht.write(b'KILL')
			except OSError as err:
				logging.warning('Failed to send KILL command: {}'.format(err))
			self.dht.close() # TODO necessary?
			self.dht.close() # debug

# Indicates an pymdht error
class DHTError(Exception):
	pass

