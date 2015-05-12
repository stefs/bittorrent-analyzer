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
import traceback

# Project modules
import peer_wire_protocol
from error import *

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
	source = sqlalchemy.Column(sqlalchemy.types.Enum('tracker', 'incoming', 'dht')) # TODO database should have enum support
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
	complete_threshold = sqlalchemy.Column(sqlalchemy.types.Integer)
	filepath = sqlalchemy.Column(sqlalchemy.types.String)
	display_name = sqlalchemy.Column(sqlalchemy.types.String)

## Declarative class for requests table
class Request(Base):
	__tablename__ = 'request'

	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	source = sqlalchemy.Column(sqlalchemy.types.Enum('tracker', 'incoming', 'dht'))
	received_peers = sqlalchemy.Column(sqlalchemy.types.Integer)
	duplicate_peers = sqlalchemy.Column(sqlalchemy.types.Integer)
	timestamp = sqlalchemy.Column(sqlalchemy.types.DateTime)
	duration_sec = sqlalchemy.Column(sqlalchemy.types.Float)

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
		self.geoipdb_closed = False
		logging.debug('Opened GeoIP2 database')

		# Create session factory class
		session_factory = sqlalchemy.orm.sessionmaker(bind=self.engine)

		# Create scoped session factory class according to
		# http://docs.sqlalchemy.org/en/rel_0_9/orm/contextual.html#thread-local-scope
		self.Session = sqlalchemy.orm.scoped_session(session_factory)

	## Store a peer's statistic
	#  @param peer Peer named tuple
	#  @return Database id if peer is new, None else
	#  @exception DatabaseError
	def store_peer(self, peer):
		# Get thread-local session
		session = self.Session()

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
					max_speed=None, visits=1, source=peer.source.name, torrent=peer.torrent)
			try:
				session.add(new_peer)
				session.commit()
			except Exception as err:
				session.rollback()
				tb = traceback.format_tb(err.__traceback__)
				raise DatabaseError('{} during store new peer: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))

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
			try:
				session.add(database_peer)
				session.commit()
			except Exception as err:
				session.rollback()
				tb = traceback.format_tb(err.__traceback__)
				raise DatabaseError('{} during update peer: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))
			logging.info('Updated peer with database id {}'.format(peer.key))

	## Uses a local GeoIP2 database to geolocate an ip address
	#  @param ip_address The address in question
	#  @return Tuple of location information or None
	def get_place_by_ip(self, ip_address):
		if self.geoipdb_closed:
			logging.critical('Called get_place_by_ip after close')
			return None, None, None
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
	#  @param dn Display name of torrent
	#  @return Database id
	#  @exception DatabaseError
	def store_torrent(self, torrent, path, dn):
		# Get thread-local session
		session = self.Session()

		# Write to database
		new_torrent = Torrent(announce_url=torrent.announce_url, info_hash=torrent.info_hash,
				info_hash_hex=torrent.info_hash_hex, pieces_count=torrent.pieces_count,
				piece_size=torrent.piece_size, complete_threshold=torrent.complete_threshold,
				filepath=path, display_name=dn)
		try:
			session.add(new_torrent)
			session.commit()
		except Exception as err:
			session.rollback()
			tb = traceback.format_tb(err.__traceback__)
			raise DatabaseError('{} during torrent storing: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))

		# Return Torrent with key
		database_id = new_torrent.id
		logging.info('Stored {} with database id {}'.format(torrent, database_id))
		return database_id

	## Store statistics about a request for new peers
	#  @param source A peer_analyzer.Source enum
	#  @param received_peers Number of received peers
	#  @param duplicate_peers Number of duplicate peers
	#  @param duration Duration in seconds
	#  @exception DatabaseError
	def store_request(self, source, received_peers, duplicate_peers, duration):
		# Get thread-local session
		session = self.Session()

		# Write to database
		new_request = Request(source=source.name,
				received_peers=received_peers,
				duplicate_peers=duplicate_peers,
				timestamp=datetime.datetime.utcnow(),
				duration_sec=duration)
		try:
			session.add(new_request)
			session.commit()
		except Exception as err:
			session.rollback()
			tb = traceback.format_tb(err.__traceback__)
			raise DatabaseError('{} during request storing: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))
		logging.info('Stored {} request: {} peers received, {} duplicates, took {} seconds'.format(source.name, received_peers, duplicate_peers, duration))

	## Relase resources
	def close(self):
		# Close GeoIP2 database reader
		self.reader.close()
		self.geoipdb_closed = True
		logging.info('GeoIP2 database closed')
		logging.info('Results written to {}'.format(self.database_path))

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
		try:
			return host_list[-2] + '.' + host_list[-1]
		except IndexError:
			try:
				return host_list[-1]
			except IndexError:
				return None

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
	
