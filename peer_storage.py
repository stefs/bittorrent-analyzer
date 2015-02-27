# Built-in modules
import logging
import time
import os
import socket
import datetime
import collections

# Extern modules
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import geoip2.database

# Create named tuple
CachedPeer = collections.namedtuple('CachedPeer', 'revisit ip_address port id bitfield pieces key')

# Create declarative base class, from which table classes are inherited
Base = sqlalchemy.ext.declarative.declarative_base()

# Declarative class for peer session table
class Peer(Base):
	__tablename__ = 'peer'
	
	# Types according to http://docs.sqlalchemy.org/en/rel_0_9/core/type_basics.html#generic-types
	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	partial_ip = sqlalchemy.Column(sqlalchemy.types.String)
	peer_id = sqlalchemy.Column(sqlalchemy.types.Binary)
	host = sqlalchemy.Column(sqlalchemy.types.String)
	country = sqlalchemy.Column(sqlalchemy.types.String)
	first_pieces = sqlalchemy.Column(sqlalchemy.types.Integer)
	last_pieces =  sqlalchemy.Column(sqlalchemy.types.Integer)
	first_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	last_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	max_speed = sqlalchemy.Column(sqlalchemy.types.Float)
	visits = sqlalchemy.Column(sqlalchemy.types.Integer)
	torrent = sqlalchemy.Column(sqlalchemy.types.Integer) # TODO foreign key of torrent

## Handling database access with SQLAlchemy
class PeerDatabase:
	## Prepare SQLAlchemy backend
	def __init__(self):
		# Create engine, usable with SQLAlchemy Expression Language, used via SQLAlchemy Object Relational Mapper
		directory = 'output/'
		if not os.path.exists(directory):
			os.makedirs(directory)
		time_string = time.strftime('%Y-%m-%d_%H-%M-%S')
		self.database_path = 'sqlite:///' + directory + time_string + '.sqlite'
		self.engine = sqlalchemy.create_engine(self.database_path, echo=False) # echo enables debug output

		# Create empty tables
		Base.metadata.create_all(self.engine)

	## Open GeoIP2 database
	def __enter__(self):
		# Open MaxMind GeoIP2 database from http://dev.maxmind.com/geoip/geoip2/geolite2/
		# according to http://geoip2.readthedocs.org/en/latest/#database-example
		geoip2_country_location = 'input/GeoLite2-Country.mmdb'
		self.reader = geoip2.database.Reader(geoip2_country_location)
		logging.debug('Opened GeoIP2 database at ' + geoip2_country_location)
		
		# Enter method returns self to with-target
		return self
	
	## Returnes thread safe scoped session object according to http://docs.sqlalchemy.org/en/rel_0_9/orm/contextual.html
	def get_session(self):
		# Create session factory class
		session_factory = sqlalchemy.orm.sessionmaker(bind=self.engine)
		
		# Return thread local proxy
		return sqlalchemy.orm.scoped_session(session_factory)

	## Store new peer statistic
	#  @param peer CachedPeer named tuple
	#  @param torrent Database ID of the related torrent
	#  @param session Database session, must only be used in one thread
	#  @return Returns database id of peer, if peer.key is None
	def store(self, peer, torrent, session): # partial_ip, id, bitfield, pieces, hostname, country, torrent):
		# Check if this is a new peer
		if peer.key is None:
			# Get two letter ISO country code via GeoIP2
			try:
				response = self.reader.country(peer.ip_address)
			except geoip2.errors.AddressNotFoundError as err:
				logging.warning('IP address is not in the database: ' + str(err))
				country = ''
			else:
				country = response.country.iso_code
				logging.info('Country is ' + country + ', ' + response.country.name)

			# Get the host via reverse DNS
			try:
				long_host = socket.gethostbyaddr(peer.ip_address)[0]
			except OSError as err:
				logging.warning('Get host by address failed: ' + str(err))
				host = ''
			else:
				host_list = long_host.split('.')
				host = host_list[-2] + '.' + host_list[-1]
				logging.info('Host name is ' + host)
		
			# Anonymize IP address
			# TODO according to https://support.google.com/analytics/answer/2763052?hl=en
			partial_ip = peer.ip_address
			
			# Get a now timestamp
			timestamp = datetime.datetime.utcnow()

			# Write to database
			new_peer = Peer(partial_ip=partial_ip, peer_id=peer.id, host=host, country=country,
					first_pieces=peer.pieces, last_pieces=peer.pieces, first_seen=timestamp, last_seen=timestamp,
					max_speed=0, visits=1, torrent=torrent)
			session.add(new_peer)
			session.commit()
			
			# Return CachedPeer with key
			database_id = new_peer.id
			logging.info('Stored new peer with database id ' + str(database_id))
			return database_id
			
		# Update former stored peer
		else:
			# Get and delete old entry
			database_peer = session.query(Peer).filter_by(id=peer.key).first()
			session.delete(database_peer) # debug
			
			# Calculate max download speed
			timestamp = datetime.datetime.utcnow()
			time_delta = timestamp - database_peer.last_seen
			time_delta_seconds = time_delta.total_seconds()
			pieces_delta = peer.pieces - database_peer.last_pieces
			pieces_per_second = pieces_delta / time_delta_seconds
			logging.info('Download speed since last visit is ' + str(pieces_per_second) + ' pieces per second')

			# Update old peer
			database_peer.last_pieces = peer.pieces
			database_peer.last_seen = timestamp
			database_peer.visits += 1
			if pieces_per_second > database_peer.max_speed:
				database_peer.max_speed = pieces_per_second
			
			# Store updated peer
			session.add(database_peer)
			session.commit()
			logging.info('Updated peer with database id ' + str(peer.key)) # debug
		
	## Relase resources
	def __exit__(self, exception_type, exception_value, traceback):
		# Close GeoIP2 database reader
		self.reader.close()
		logging.info('GeoIP2 database closed')
		logging.info('Results written to ' + self.database_path)

# Indicates database related errors
class DatabaseError(Exception):
	pass

