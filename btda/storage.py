# Built-in modules
import logging
import socket
import datetime
import ipaddress
import os
import resource
import time

# Extern modules
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import geoip2.database
import maxminddb.errors

# Project modules
import config
from util import *

# Create declarative base class, from which table classes are inherited
Base = sqlalchemy.ext.declarative.declarative_base()

## Declarative class for peer session table
class Peer(Base):
	__tablename__ = 'peer'

	# Types according to http://docs.sqlalchemy.org/en/rel_0_9/core/type_basics.html#generic-types
	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	client = sqlalchemy.Column(sqlalchemy.types.String)
	continent = sqlalchemy.Column(sqlalchemy.types.String)
	country = sqlalchemy.Column(sqlalchemy.types.String)
	latitude = sqlalchemy.Column(sqlalchemy.types.Float)
	longitude = sqlalchemy.Column(sqlalchemy.types.Float)
	first_pieces = sqlalchemy.Column(sqlalchemy.types.Integer)
	last_pieces = sqlalchemy.Column(sqlalchemy.types.Integer)
	first_seen = sqlalchemy.Column(sqlalchemy.types.Integer)
	last_seen = sqlalchemy.Column(sqlalchemy.types.Integer)
	max_speed = sqlalchemy.Column(sqlalchemy.types.Float)
	visits = sqlalchemy.Column(sqlalchemy.types.Integer)
	source = sqlalchemy.Column(sqlalchemy.types.Enum('tracker', 'incoming', 'dht'))
	torrent = sqlalchemy.Column(sqlalchemy.types.Integer)

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
	gigabyte = sqlalchemy.Column(sqlalchemy.types.Float)

## Declarative class for request table
class Request(Base):
	__tablename__ = 'request'

	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	timestamp = sqlalchemy.Column(sqlalchemy.types.Integer)
	source = sqlalchemy.Column(sqlalchemy.types.Enum('tracker', 'incoming', 'dht'))
	received_peers = sqlalchemy.Column(sqlalchemy.types.Integer)
	duplicate_peers = sqlalchemy.Column(sqlalchemy.types.Integer)
	seeders = sqlalchemy.Column(sqlalchemy.types.Integer)
	completed = sqlalchemy.Column(sqlalchemy.types.Integer)
	leechers = sqlalchemy.Column(sqlalchemy.types.Integer)
	duration_sec = sqlalchemy.Column(sqlalchemy.types.Float)
	torrent = sqlalchemy.Column(sqlalchemy.types.Integer)

## Declarative class for statistic table
class Statistic(Base):
	__tablename__ = 'statistic'

	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	timestamp = sqlalchemy.Column(sqlalchemy.types.Integer)
	peer_queue = sqlalchemy.Column(sqlalchemy.types.Integer)
	visited_queue = sqlalchemy.Column(sqlalchemy.types.Integer)
	unique_incoming = sqlalchemy.Column(sqlalchemy.types.Integer)
	success_active = sqlalchemy.Column(sqlalchemy.types.Integer)
	thread_workload = sqlalchemy.Column(sqlalchemy.types.Float)
	load_average = sqlalchemy.Column(sqlalchemy.types.Float)
	memory_mb = sqlalchemy.Column(sqlalchemy.types.Float)
	server_threads = sqlalchemy.Column(sqlalchemy.types.Integer)
	evaluator_threads = sqlalchemy.Column(sqlalchemy.types.Integer)

## Handling database access with SQLAlchemy
class Database:
	## Prepare SQLAlchemy backend
	#  @param output Output path with filename without file extension
	#  @exception DatabaseError
	def __init__(self, output):
		# Log SQLAlchemy version
		logging.info('SQLAlchemy is version {}'.format(sqlalchemy.__version__))

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

		# Commit timer
		self.last_peer_commit = 0

	## Store a peer's statistic
	#  @param peer Peer named tuple
	#  @return Database id if peer is new, None else
	#  @exception DatabaseError
	def store_peer(self, peer):
		# Get thread-local session
		session = self.Session()

		# Commit if necessary
		now = time.perf_counter()
		if now - self.last_peer_commit > 10:
			self.last_peer_commit = now
			try:
				session.commit()
			except Exception as err:
				session.rollback()
				raise DatabaseError('{} during 10 sec peer commit: {}'.format(type(err).__name__, err))

		# Check if this is a new peer
		if peer.key is None:
			# Get meta data
			location = self.get_place_by_ip(peer.ip_address)
			timestamp = datetime.datetime.now()
			client = client_from_peerid(peer.id)

			# Write to database
			new_peer = Peer(client=client, continent=location[0], country=location[1],
					latitude=location[2], longitude=location[3], first_pieces=peer.pieces,
					last_pieces=None, first_seen=int(timestamp.timestamp()),
					last_seen=None, max_speed=None, visits=1,
					source=peer.source.name, torrent=peer.torrent)
			try:
				session.add(new_peer)
				session.commit()
			except Exception as err:
				session.rollback()
				raise DatabaseError('{} during store new peer: {}'.format(type(err).__name__, err))

			# Return database id
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
			timestamp = datetime.datetime.now()
			time_delta = timestamp - datetime.datetime.fromtimestamp(database_peer.last_seen)
			time_delta_seconds = time_delta.total_seconds()
			pieces_delta = peer.pieces - database_peer.last_pieces
			pieces_per_second = pieces_delta / time_delta_seconds
			logging.debug('Download speed since last visit is {} pieces per second'.format(pieces_per_second))

			# Update peer
			database_peer.last_pieces = peer.pieces
			database_peer.last_seen = int(timestamp.timestamp())
			database_peer.visits += 1
			if database_peer.max_speed is None or pieces_per_second > database_peer.max_speed:
				database_peer.max_speed = pieces_per_second

			# Store updated peer
			try:
				session.add(database_peer)
			except Exception as err:
				session.rollback()
				raise DatabaseError('{} during update peer: {}'.format(type(err).__name__, err))
			logging.debug('Updated peer with database id {}'.format(peer.key))

	## Uses a local GeoIP2 database to geolocate an ip address
	#  @param ip_address The address in question
	#  @return Tuple of location information or None
	def get_place_by_ip(self, ip_address):
		if self.geoipdb_closed:
			logging.critical('Called get_place_by_ip after close')
			return None, None, None, None
		try:
			response = self.reader.city(ip_address)
		except geoip2.errors.AddressNotFoundError as err:
			logging.warning('IP address is not in the database: {}'.format(err))
			return None, None, None, None
		else:
			logging.debug('Location of ip address is {}, {}, {}'.format(response.city.name, response.country.name, response.continent.name))
			return response.continent.code, response.country.iso_code, response.location.latitude, response.location.longitude

	## Store a given torrent in the database
	#  @param torrent Torrent named tuple
	#  @param path File system path the torrent file was located
	#  @param dn Display name of torrent
	#  @return Database id
	#  @exception DatabaseError
	def store_torrent(self, torrent, path, dn):
		# Get thread-local session
		session = self.Session()

		# Calculate size in gigabytes
		gb = (torrent.pieces_count * torrent.piece_size) / 10 ** 9

		# Write to database
		new_torrent = Torrent(announce_url=','.join(torrent.announce_url), info_hash=torrent.info_hash,
				info_hash_hex=torrent.info_hash_hex, pieces_count=torrent.pieces_count,
				piece_size=torrent.piece_size, complete_threshold=torrent.complete_threshold,
				filepath=path, display_name=dn, gigabyte=gb)
		try:
			session.add(new_torrent)
			session.commit()
		except Exception as err:
			session.rollback()
			raise DatabaseError('{} during torrent storing: {}'.format(type(err).__name__, err))

		# Return Torrent with key
		database_id = new_torrent.id
		logging.info('Stored {} with database id {}'.format(torrent, database_id))
		return database_id

	## Store statistics about a request for new peers
	#  @param source A peer_analyzer.Source enum
	#  @param received_peers Number of received peers
	#  @param duplicate_peers Number of duplicate peers
	#  @param duration Duration in seconds
	#  @param torrent Corresponding torrent ID
	#  @exception DatabaseError
	def store_request(self, source, received_peers, duplicate_peers, seeders, completed, leechers, duration, torrent):
		# Get thread-local session
		session = self.Session()

		# Write to database
		new_request = Request(timestamp=int(datetime.datetime.now().timestamp()),
				source=source.name,
				received_peers=received_peers,
				duplicate_peers=duplicate_peers,
				seeders=seeders,
				completed=completed,
				leechers=leechers,
				duration_sec=duration,
				torrent=torrent)
		try:
			session.add(new_request)
			session.commit()
		except Exception as err:
			session.rollback()
			raise DatabaseError('{} during request storing: {}'.format(type(err).__name__, err))
		logging.info('Stored {} request: {} peers received, {} duplicates, took {} seconds'.format(source.name, received_peers, duplicate_peers, duration))

	## Store statistics about peers
	#  @param peer_queue Currently number of peers in queue
	#  @param unique_incoming Seen unique incoming peers
	#  @param visited_queue Length of the visited peers queue
	#  @param success_active Active evaluations successful
	#  @param thread_workload Percentage of active time between 0 and 1
	#  @param server_threads Number of currently active server threads
	#  @param evaluator_threads Number of currently active evaluator threads
	#  @exception DatabaseError
	def store_statistic(self, peer_queue, visited_queue, unique_incoming, success_active, thread_workload, server_threads, evaluator_threads):
		# Get thread-local session
		session = self.Session()

		# Determine system load
		try:
			load = os.getloadavg()[2]
		except OSError:
			load = None
		try:
			memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000
		except OSError:
			memory = None

		# Write to database
		new_statistic = Statistic(timestamp=int(datetime.datetime.now().timestamp()),
				peer_queue=peer_queue,
				visited_queue=visited_queue,
				unique_incoming=unique_incoming,
				success_active=success_active,
				thread_workload=thread_workload,
				load_average=load,
				memory_mb=memory,
				server_threads=server_threads,
				evaluator_threads=evaluator_threads)
		try:
			session.add(new_statistic)
			session.commit()
		except Exception as err:
			session.rollback()
			raise DatabaseError('{} during statistic storing: {}'.format(type(err).__name__, err))
		logging.info('Stored peer statistic')

	## Relase resources
	def close(self):
		# Close GeoIP2 database reader
		self.reader.close()
		self.geoipdb_closed = True
		logging.info('GeoIP2 database closed')
		logging.info('Results written to {}'.format(self.database_path))

## Parse client code from peer id, according to BEP 20
#  @param Raw peer id
#  @return String of client code with only ASCII or None
def client_from_peerid(peer_id):
	try:
		return str(peer_id[0:8], encoding='ascii')
	except (KeyError, ValueError):
		return None
