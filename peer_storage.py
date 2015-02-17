# Built-in modules
import logging
import time
import os

# Extern modules
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm

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

# Declarative class for the torrent file table
#class Torrent(Base):
#	__tablename__ = 'torrent'
#	
#	id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
#	announce_url = sqlalchemy.Column(sqlalchemy.String)
#	info_hash = sqlalchemy.Column(sqlalchemy.String) # Bytes
	
## Handling database access with SQLAlchemy
class PeerDatabase:
	## Prepare SQLAlchemy backend
	def __init__(self):
		# Expecting version 0.9
		if not sqlalchemy.__version__.startswith('0.9'):
			logging.warning('Expected SQLAlchemy version is at least 0.9')

		# Create engine, usable with SQLAlchemy Expression Language, used via SQLAlchemy Object Relational Mapper
		directory = 'output/'
		if not os.path.exists(directory):
			os.makedirs(directory)
		time_string = time.strftime('%Y-%m-%d_%H-%M-%S')
		database_path = 'sqlite:///' + directory + time_string + '.sqlite'
		self.engine = sqlalchemy.create_engine(database_path, echo=False) # echo enables debug output

		# Create empty tables
		Base.metadata.create_all(self.engine)

		# Create session factory class
		self.Session = sqlalchemy.orm.sessionmaker(bind=self.engine)
		
		# Create session object for database access
		self.session = self.Session()

	## Store new peer statistic
	#  @param partial_ip Anonymized IP address ready to be stored
	#  @param id The ID the peer has given itself
	#  @param bitfield Torrent parts this peer is known to hold
	#  @param pieces Number of pieces as apparent from the bitfield
	#  @param hostname Hostname associated to the IP address
	#  @param country Two letter country code as specified in ISO 3166-1 alpha-2
	#  @param torrent Database ID of the related torrent
	def store_peer(self, partial_ip, id, bitfield, pieces, hostname, country, torrent):
		# Check types before export in database
		assert type(partial_ip) is str, 'partial ip is of type ' + str(type(partial_ip))
		assert type(id) is bytes, 'peer id is of type ' + str(type(id))
		assert type(bitfield) is bytearray, 'bitfield is of type ' + str(type(bitfield))
		assert type(pieces) is int, 'pieces is of type ' + str(type(pieces))
		assert type(hostname) is str, 'hostname is of type ' + str(type(hostname))
		assert type(country) is str, 'country is of type ' + str(type(country))
		assert type(torrent) is int, 'torrent is of type ' + str(type(torrent))
		
		# Write to database
		new_peer = Peer(partial_ip=partial_ip, peer_id=id, progress=pieces, isp=hostname, country=country, torrent=torrent)
		self.session.add(new_peer)
		self.session.commit()
		logging.info('Stored peer: ' + str(new_peer))

