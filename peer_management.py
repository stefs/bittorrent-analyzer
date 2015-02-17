# Built-in modules
import logging
import queue
import collections
import socket

# Project modules
import peer_storage

# Extern modules
import geoip2.database

## Create named tuple
CachedPeer = collections.namedtuple('CachedPeer', 'ip_address port id bitfield')

## Cache of peers in different conection and progress states
#  @warn Not threadsafe, calls must be guarded with locks
# TODO make threadsafe, especially peer_storage.PeerDatabase
class PeerCache:
	## Initialization of a cache for peers
	def __init__(self, torrent_id):
		# Store torrent id associated with this peer cache
		self.torrent_id = torrent_id
		
	## Open GeoIP2 database
	def __enter__(self):
		# Open MaxMind GeoIP2 database from http://dev.maxmind.com/geoip/geoip2/geolite2/
		# according to http://geoip2.readthedocs.org/en/latest/#database-example
		geoip2_country_location = 'input/GeoLite2-Country.mmdb'
		self.reader = geoip2.database.Reader(geoip2_country_location)
		logging.debug('Opened GeoIP2 database at ' + geoip2_country_location)

		# Lists with CachedPeer tuples used at runtime
		self.in_progress = queue.Queue()
		self.error = list()
		self.finished_count = 0
		
		# Storage database for export purposes
		self.database = peer_storage.PeerDatabase()

		# Enter method returns self to with-target
		return self

	## Add a new peer with unknown connectivity status
	#  @param peer Tuple of IP address and port number
	def add_new(self, peer):
		new_peer = CachedPeer(peer[0], peer[1], id=b'', bitfield=b'')
		self.in_progress.put(new_peer)

	## Add a peer to whom a successfull connection was established and evaluate the bitmap
	def add_success(self, peer, pieces_number):
		# Count finished pieces
		pieces_count = 0
		for byte in peer.bitfield:
			pieces_count += count_bits(byte)
		percentage = round(pieces_count * 100 / pieces_number)
		remaining = pieces_number - pieces_count
		logging.info('Peer reports to have ' + str(pieces_count) + ' pieces, ' + str(remaining) + ' remaining, equals ' + str(percentage) + '%')
		
		# Get two letter ISO country code via GeoIP2
		try:
			response = self.reader.country(peer.ip_address)
		except geoip2.errors.AddressNotFoundError as err:
			logging.warning('IP address is not in the database: ' + str(err))
			country_code = ''
		else:
			country_code = response.country.iso_code
			logging.info('Country is ' + country_code + ', ' + response.country.name)

		# Get the ISP via reverse DNS
		try:
			host = socket.gethostbyaddr(peer.ip_address)[0]
		except OSError as err:
			logging.warning('Get host by address failed: ' + str(err))
			host = ''
		else:
			logging.info('Host name is ' + host)
		# TODO only keep last two parts
		
		# Anonymize IP address
		# TODO
		anonymized_ip = peer.ip_address

		# Store finished peer in database
		if pieces_count == pieces_number:
			self.finished_count += 1
		self.database.store_peer(anonymized_ip, peer.id, peer.bitfield, pieces_count, host, country_code, self.torrent_id)

		# Put peer in progress back in the list and store in database
		#else:
		#	# TODO put with wait
		#	self.in_progress.put(peer)

	## Add a peer to whom communication failed
	def add_error(self, peer):
		self.error.append(peer)
	
	## Relase resources
	def __exit__(self, exception_type, exception_value, traceback):
		# Close GeoIP2 database reader
		self.reader.close()
		logging.debug('GeoIP2 database closed')
	
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

