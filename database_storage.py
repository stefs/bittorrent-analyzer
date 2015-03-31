# Built-in modules
import logging
import socket
import datetime
import ipaddress

# Extern modules
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import geoip2.database
import maxminddb.errors

# Project modules
import peer_wire_protocol

# Create declarative base class, from which table classes are inherited
Base = sqlalchemy.ext.declarative.declarative_base()

## Declarative class for peer session table
class Peer(Base):
	__tablename__ = 'peer'

	# Types according to http://docs.sqlalchemy.org/en/rel_0_9/core/type_basics.html#generic-types
	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	partial_ip = sqlalchemy.Column(sqlalchemy.types.String)
	peer_id = sqlalchemy.Column(sqlalchemy.types.Binary)
	host = sqlalchemy.Column(sqlalchemy.types.String)
	city = sqlalchemy.Column(sqlalchemy.types.String)
	country = sqlalchemy.Column(sqlalchemy.types.String)
	continent = sqlalchemy.Column(sqlalchemy.types.String)
	first_pieces = sqlalchemy.Column(sqlalchemy.types.Integer)
	last_pieces =  sqlalchemy.Column(sqlalchemy.types.Integer)
	first_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	last_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	max_speed = sqlalchemy.Column(sqlalchemy.types.Float)
	visits = sqlalchemy.Column(sqlalchemy.types.Integer)
	source = sqlalchemy.Column(sqlalchemy.types.Integer)
	torrent = sqlalchemy.Column(sqlalchemy.types.Integer) # TODO foreign key of torrent


## Declarative class for torrent table
class Torrent(Base):
	__tablename__ = 'torrent'

	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	announce_url = sqlalchemy.Column(sqlalchemy.types.String)
	info_hash = sqlalchemy.Column(sqlalchemy.types.Binary)
	info_hash_hex = sqlalchemy.Column(sqlalchemy.types.String)
	pieces_count = sqlalchemy.Column(sqlalchemy.types.Integer)
	piece_size = sqlalchemy.Column(sqlalchemy.types.Integer)
	filepath = sqlalchemy.Column(sqlalchemy.types.String)

## Handling database access with SQLAlchemy
class Database:
	## Prepare SQLAlchemy backend
	#  @param output Output path with filename without file extension
	#  @exception DatabaseError
	def __init__(self, output):
		# Create engine, usable with SQLAlchemy Expression Language, used via SQLAlchemy Object Relational Mapper
		self.database_path = 'sqlite:///{}.sqlite'.format(output)
		self.engine = sqlalchemy.create_engine(self.database_path, echo=False) # echo enables debug output

		# Create empty tables
		Base.metadata.create_all(self.engine)

		# Open MaxMind GeoIP2 database from http://dev.maxmind.com/geoip/geoip2/geolite2/
		# according to http://geoip2.readthedocs.org/en/latest/#database-example
		try:
			self.reader = geoip2.database.Reader('input/GeoLite2-City.mmdb')
		except (FileNotFoundError, maxminddb.errors.InvalidDatabaseError) as err:
			raise DatabaseError('Failed to open geolocation database: {}'.format(err))
		logging.debug('Opened GeoIP2 database')

	## Returnes thread safe scoped session object according to http://docs.sqlalchemy.org/en/rel_0_9/orm/contextual.html
	def get_session(self):
		# Create session factory class
		session_factory = sqlalchemy.orm.sessionmaker(bind=self.engine)

		# Return thread local proxy
		return sqlalchemy.orm.scoped_session(session_factory)

	## Store a peer's statistic
	#  @param peer Peer named tuple
	#  @param session Database session, must only be used in one thread
	#  @return Database id if peer is new, None else
	def store_peer(self, peer, session): # partial_ip, id, bitfield, pieces, hostname, country, torrent):
		# Check if this is a new peer
		if peer.key is None:
			# Get meta data
			location = self.get_place_by_ip(peer.ip_address)
			host = get_short_hostname(peer.ip_address)
			partial_ip = anonymize_ip(peer.ip_address)
			timestamp = datetime.datetime.utcnow()

			# Write to database
			new_peer = Peer(partial_ip=partial_ip, peer_id=peer.id, host=host, city=location[0], country=location[1], continent=location[2],
					first_pieces=peer.pieces, last_pieces=None, first_seen=timestamp, last_seen=None,
					max_speed=None, visits=1, source=peer.source, torrent=peer.torrent)
			session.add(new_peer)
			session.commit()

			# Return Peer with key
			database_id = new_peer.id
			logging.info('Stored new peer with database id {}'.format(database_id))
			return database_id

		# Update former stored peer
		else:
			# Get and delete old entry
			database_peer = session.query(Peer).filter_by(id=peer.key).first()
			session.delete(database_peer)

			# Copy first to last statistics on second visit
			if database_peer.last_pieces is None:
				database_peer.last_pieces = database_peer.first_pieces
				database_peer.last_seen = database_peer.first_seen

			# Calculate max download speed
			timestamp = datetime.datetime.utcnow()
			time_delta = timestamp - database_peer.last_seen
			time_delta_seconds = time_delta.total_seconds()
			pieces_delta = peer.pieces - database_peer.last_pieces
			pieces_per_second = pieces_delta / time_delta_seconds
			logging.info('Download speed since last visit is {} pieces per second'.format(pieces_per_second))

			# Update peer
			database_peer.last_pieces = peer.pieces
			database_peer.last_seen = timestamp
			database_peer.visits += 1
			if database_peer.max_speed is None or pieces_per_second > database_peer.max_speed:
				database_peer.max_speed = pieces_per_second

			# Store updated peer
			session.add(database_peer)
			session.commit()
			logging.info('Updated peer with database id {}'.format(peer.key))

	## Uses a local GeoIP2 database to geolocate an ip address
	#  @param ip_address The address in question
	#  @return Tuple of location information or None
	def get_place_by_ip(self, ip_address):
		try:
			response = self.reader.city(ip_address)
		except geoip2.errors.AddressNotFoundError as err:
			logging.warning('IP address is not in the database: {}'.format(err))
			return None, None, None
		else:
			logging.info('Location of ip address is {}, {}, {}'.format(response.city.name, response.country.name, response.continent.name))
			return response.city.name, response.country.iso_code, response.continent.code

	## Store a given torrent in the database
	#  @param torrent Torrent named tuple
	#  @param path File system path the torrent file was located
	#  @param session Database session
	#  @return Database id
	def store_torrent(self, torrent, path, session):
		# Write to database
		new_torrent = Torrent(announce_url=torrent.announce_url, info_hash=torrent.info_hash,
				info_hash_hex=torrent.info_hash_hex, pieces_count=torrent.pieces_count,
				piece_size=torrent.piece_size, filepath=path)
		session.add(new_torrent)
		session.commit()

		# Return Torrent with key
		database_id = new_torrent.id
		logging.info('Stored {} with database id {}'.format(torrent, database_id))
		return database_id

	## Relase resources
	def close(self):
		# Close GeoIP2 database reader
		self.reader.close()
		logging.info('GeoIP2 database closed')
		logging.info('Results written to {}'.format(self.database_path))

## Indicates database related errors
class DatabaseError(Exception):
	pass

## Get the host via reverse DNS
#  @param ip_address The address in question
#  @return Hostname with TLD and SLD or empty string or None
def get_short_hostname(ip_address):
	try:
		long_host = socket.gethostbyaddr(ip_address)[0]
	except OSError as err:
		logging.warning('Get host by address failed: {}'.format(err))
		return None
	else:
		host_list = long_host.split('.')
		return host_list[-2] + '.' + host_list[-1]

## Anonymize an IP address according to https://support.google.com/analytics/answer/2763052?hl=en
#  @param ip_address Not anonymized ip adderss
#  @return Anonymized ip address
def anonymize_ip(ip_address):
	ip = ipaddress.ip_address(ip_address)
	if ip.version == 4:
		network = ip_address + '/24'
		net = ipaddress.IPv4Network(network, strict=False)
	elif ip.version == 6:
		network = ip_address + '/48'
		net = ipaddress.IPv6Network(network, strict=False)
	return str(net.network_address)
	
