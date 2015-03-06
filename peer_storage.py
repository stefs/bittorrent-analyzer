# Built-in modules
import logging
import time
import os
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
	country = sqlalchemy.Column(sqlalchemy.types.String)
	first_pieces = sqlalchemy.Column(sqlalchemy.types.Integer)
	last_pieces =  sqlalchemy.Column(sqlalchemy.types.Integer)
	first_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	last_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	max_speed = sqlalchemy.Column(sqlalchemy.types.Float)
	visits = sqlalchemy.Column(sqlalchemy.types.Integer)
	active = sqlalchemy.Column(sqlalchemy.types.Boolean)
	torrent = sqlalchemy.Column(sqlalchemy.types.Integer) # TODO foreign key of torrent

## Handling database access with SQLAlchemy
class PeerDatabase:
	## Prepare SQLAlchemy backend
	#  @exception DatabaseError
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

		# Open MaxMind GeoIP2 database from http://dev.maxmind.com/geoip/geoip2/geolite2/
		# according to http://geoip2.readthedocs.org/en/latest/#database-example
		geoip2_country_location = 'input/GeoLite2-Country.mmdb'
		try:
			self.reader = geoip2.database.Reader(geoip2_country_location)
		except (FileNotFoundError, maxminddb.errors.InvalidDatabaseError) as err:
			raise DatabaseError('Failed to open geolocation database: ' + str(err))
		logging.debug('Opened GeoIP2 database at ' + geoip2_country_location)

	## Returnes thread safe scoped session object according to http://docs.sqlalchemy.org/en/rel_0_9/orm/contextual.html
	def get_session(self):
		# Create session factory class
		session_factory = sqlalchemy.orm.sessionmaker(bind=self.engine)

		# Return thread local proxy
		return sqlalchemy.orm.scoped_session(session_factory)

	## Store a peer's statistic
	#  @param peer Peer named tuple
	#  @param torrent Database ID of the related torrent
	#  @param session Database session, must only be used in one thread
	#  @return Peer named tuple with peer.key filled
	def store(self, peer, torrent, session): # partial_ip, id, bitfield, pieces, hostname, country, torrent):
		# Check if this is a new peer
		if peer.key is None:
			# Get meta data
			country = self.get_country_by_ip(peer.ip_address)
			logging.info('Country is ' + country[0] + ', ' + country[1])
			host = get_short_hostname(peer.ip_address)
			logging.info('Host name is ' + host)
			partial_ip = anonymize_ip(peer.ip_address)
			logging.info('Anonymized ip address is ' + partial_ip)
			timestamp = datetime.datetime.utcnow()

			# Write to database
			new_peer = Peer(partial_ip=partial_ip, peer_id=peer.id, host=host, country=country[0],
					first_pieces=peer.pieces, last_pieces=peer.pieces, first_seen=timestamp, last_seen=timestamp,
					max_speed=0, visits=1, active=peer.active, torrent=torrent)
			session.add(new_peer)
			session.commit()

			# Return Peer with key
			database_id = new_peer.id
			logging.info('Stored new peer with database id ' + str(database_id))
			*old_peer, key = peer
			return peer_wire_protocol.Peer(*old_peer, key=database_id)

		# Update former stored peer
		else:
			# Get and delete old entry
			database_peer = session.query(Peer).filter_by(id=peer.key).first()
			session.delete(database_peer)

			# Calculate max download speed
			timestamp = datetime.datetime.utcnow()
			time_delta = timestamp - database_peer.last_seen
			time_delta_seconds = time_delta.total_seconds()
			pieces_delta = peer.pieces - database_peer.last_pieces
			pieces_per_second = pieces_delta / time_delta_seconds
			logging.info('Download speed since last visit is ' + str(pieces_per_second) + ' pieces per second')

			# Update peer
			database_peer.last_pieces = peer.pieces
			database_peer.last_seen = timestamp
			database_peer.visits += 1
			if pieces_per_second > database_peer.max_speed:
				database_peer.max_speed = pieces_per_second

			# Store updated peer
			session.add(database_peer)
			session.commit()
			logging.info('Updated peer with database id ' + str(peer.key))
			return peer

	## Uses a local GeoIP2 database to geolocate an ip address
	#  @param ip_address The address in question
	#  @return Two letter ISO country code or an empty string
	def get_country_by_ip(self, ip_address):
		try:
			response = self.reader.country(ip_address)
		except geoip2.errors.AddressNotFoundError as err:
			logging.warning('IP address is not in the database: ' + str(err))
			return ''
		else:
			return response.country.iso_code, response.country.name

	## Relase resources
	def close(self):
		# Close GeoIP2 database reader
		self.reader.close()
		logging.info('GeoIP2 database closed')
		logging.info('Results written to ' + self.database_path)

## Indicates database related errors
class DatabaseError(Exception):
	pass

## Get the host via reverse DNS
#  @param ip_address The address in question
#  @return Hostname with TLD and SLD or empty string
def get_short_hostname(ip_address):
	try:
		long_host = socket.gethostbyaddr(ip_address)[0]
	except OSError as err:
		logging.warning('Get host by address failed: ' + str(err))
		return ''
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
	
