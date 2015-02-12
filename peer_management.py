# Built-in modules
import logging

# Extern modules
import sqlalchemy
import sqlalchemy.ext.declarative
import sqlalchemy.orm

# Create declarative base class, from which table classes are inherited
Base = sqlalchemy.ext.declarative.declarative_base()

# Declarative class for peer session table
class Peer(Base):
	__tablename__ = 'peer'
	
	id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
	partial_ip_address = sqlalchemy.Column(sqlalchemy.String)
	client_name = sqlalchemy.Column(sqlalchemy.String)
	pieces_bitmap = sqlalchemy.Column(sqlalchemy.String) # Bytes
	progress = sqlalchemy.Column(sqlalchemy.Integer) # Float
	autonomous_system = sqlalchemy.Column(sqlalchemy.String)
	country_code = sqlalchemy.Column(sqlalchemy.String)
	session_count = sqlalchemy.Column(sqlalchemy.Integer)
	first_occurrence = sqlalchemy.Column(sqlalchemy.Integer) # Date
	last_seen = sqlalchemy.Column(sqlalchemy.Integer) # Date
	torrent = sqlalchemy.Column(sqlalchemy.Integer) # foreign key of torrent

	def __repr__(self):
		return 'implement __repr__!'

# Declarative class for the torrent file table
class Torrent(Base):
	__tablename__ = 'torrent'
	
	id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
	announce_url = sqlalchemy.Column(sqlalchemy.String)
	info_hash = sqlalchemy.Column(sqlalchemy.String) # Bytes
	
# TESTING
Base.metadata.create_all(engine)
mytor = Torrent(announce_url = 'http:/x/a', info_hash='hash')
session = Session()
session.add(mytor)
session.commit()

# Create session_storage class for extern usage
class session_database:
	## Prepare SQLAlchemy backend
	def __init__(self):
		# Expecting version 0.9
		if not sqlalchemy.__version__.startswith('0.9'):
			logging.warning('Expected SQLAlchemy version is at least 0.9')

		# Create engine, usable with SQLAlchemy Expression Language, used via SQLAlchemy Object Relational Mapper
		self.engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=True) # TODO use file with dated name

		# Create session factory class
		self.Session = sqlalchemy.orm.sessionmaker(bind=self.engine)
		
		# Create session object for database access
		self.session = self.Session()

	## Store new peer statistic or update if peer already present
	#  @param peer_ip Tuple of ip address and port number
	#  @param peer_id The ID the peer has given itself
	#  @param bitmap Torrent parts this peer is known to hold
	#  @param torrent_id Database ID of the related torrent
	def store_in_database(self, peer_ip, peer_id, bitmap, torrent_id):
		anonym_ip = ip_anonymizer(peer_ip)
		client_name = peer_id # TODO can store bytes?
		country = country_of_ip(peer_ip[0])
		isp = isp_of_ip(peer_ip[0])
		
		# TODO implement
		if peer_already_sotred:
			update
		else:
			new_peer
		
		new_peer = Peer(partial_ip_address=anonym_ip, pieces_bitmap=bitmap, torrent=torrent_id, country_code)

class session_storage
		
## Shortens IPv4 and IPv6 address to 20 Bit
#  @param ip_port Tuple of ip address as string and port
#  @return Shortened IP address as a string
def ip_anonymizer(ip_port):
	# TODO implement
	return ip_port[0]

## Perform a country look up for the given IP address
#  @param ip_address The addres to be analyzed
#  @return Two letter country code according to TODO
def country_of_ip(ip_address):
	# TODO implement
	return '?'

## Perform a ISP look up for the given IP address
#  @param ip_address The addres to be analyzed
#  @return ISP as a string # TODO specify
def isp_of_ip(ip_address):
	# TODO implement
	return '?'

