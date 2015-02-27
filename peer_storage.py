# Built-in modules
import logging
import time
import os
import socket

# Extern modules
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm
import geoip2.database

# Create declarative base class, from which table classes are inherited
Base = sqlalchemy.ext.declarative.declarative_base()

# Declarative class for peer session table
class Peer(Base):
	__tablename__ = 'peer'
	
	# Types according to http://docs.sqlalchemy.org/en/rel_0_9/core/type_basics.html#generic-types
	id = sqlalchemy.Column(sqlalchemy.types.Integer, primary_key=True)
	partial_ip = sqlalchemy.Column(sqlalchemy.types.String)
	peer_id = sqlalchemy.Column(sqlalchemy.types.Binary)
	bitfield = sqlalchemy.Column(sqlalchemy.types.Binary)
	progress = sqlalchemy.Column(sqlalchemy.types.Integer)
	isp = sqlalchemy.Column(sqlalchemy.types.String)
	country = sqlalchemy.Column(sqlalchemy.types.String)
	sessions = sqlalchemy.Column(sqlalchemy.types.Integer)
	first_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	last_seen = sqlalchemy.Column(sqlalchemy.types.DateTime)
	torrent = sqlalchemy.Column(sqlalchemy.types.Integer) # TODO foreign key of torrent

	# Return string representation of peer object
	def __repr__(self):
		parts = list()
		parts.append('<Peer(partial_ip=')
		parts.append(self.partial_ip)
		parts.append(', peer_id=')
		parts.append(str(self.peer_id))
		parts.append(', bitfield=')
		parts.append(str(self.bitfield))
		parts.append(', progress=')
		parts.append(str(self.progress))
		parts.append(', isp=')
		parts.append(self.isp)
		parts.append(', country=')
		parts.append(self.country)
		parts.append(', sessions=')
		parts.append(str(self.sessions))
		parts.append(', first_seen=')
		parts.append(str(self.first_seen))
		parts.append(', last_seen=')
		parts.append(str(self.last_seen))
		parts.append(', torrent=')
		parts.append(str(self.torrent))
		parts.append(')>')
		return ''.join(parts)

## Handling database access with SQLAlchemy
class PeerDatabase:
	## Prepare SQLAlchemy backend
	def __init__(self):
		# Create engine, usable with SQLAlchemy Expression Language, used via SQLAlchemy Object Relational Mapper
		directory = 'output/'
		if not os.path.exists(directory):
			os.makedirs(directory)
		time_string = time.strftime('%Y-%m-%d_%H-%M-%S')
		database_path = 'sqlite:///' + directory + time_string + '.sqlite'
		self.engine = sqlalchemy.create_engine(database_path, echo=False) # echo enables debug output
		logging.info('Writing results to ' + database_path)

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
	
	## Returnes thread safe scoped session object
	def get_session(self):
		# Create session factory class
		session_factory = sqlalchemy.orm.sessionmaker(bind=self.engine)
		
		# Return thread local proxy
		return sqlalchemy.orm.scoped_session(session_factory)

	## Store new peer statistic
	#  @param peer CachedPeer named tuple
	#  @param torrent Database ID of the related torrent
	#  @param session Database session, must only be used in one thread
	def store(self, peer, torrent, session): # partial_ip, id, bitfield, pieces, hostname, country, torrent):
		# Get two letter ISO country code via GeoIP2
		try:
			response = self.reader.country(peer.ip_address)
		except geoip2.errors.AddressNotFoundError as err:
			logging.warning('IP address is not in the database: ' + str(err))
			country = ''
		else:
			country = response.country.iso_code
			logging.info('Country is ' + country + ', ' + response.country.name)

		# Get the ISP via reverse DNS
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

		# Check types before export in database
		assert type(partial_ip) is str, 'partial ip is of type ' + str(type(partial_ip))
		assert type(peer.id) is bytes, 'peer id is of type ' + str(type(peer.id))
		assert type(peer.bitfield) is bytearray, 'bitfield is of type ' + str(type(peer.bitfield))
		assert type(peer.pieces) is int, 'pieces is of type ' + str(type(peer.pieces))
		assert type(host) is str, 'hostname is of type ' + str(type(host))
		assert type(country) is str, 'country is of type ' + str(type(country))
		assert type(torrent) is int, 'torrent is of type ' + str(type(torrent))
		
		# Write to database
		new_peer = Peer(partial_ip=partial_ip, peer_id=peer.id, progress=peer.pieces, isp=host, country=country, torrent=torrent)
		session.add(new_peer)
		session.commit()
		logging.info('Stored peer: ' + str(new_peer))

	## Relase resources
	def __exit__(self, exception_type, exception_value, traceback):
		# Close GeoIP2 database reader
		self.reader.close()
		logging.info('GeoIP2 database closed')

