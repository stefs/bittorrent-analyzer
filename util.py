# Built-in modules
import collections
import enum
import threading
import logging
import socket
import binascii
import struct

### CONSTANTS ###

UT_METADATA_BLOCK_SIZE = 16384

### NAMED TUPLES ###

Address = collections.namedtuple('Address', 'ip port')

Message = collections.namedtuple('Message', 'type payload')

Peer = collections.namedtuple('Peer', 'revisit ip_address port id bitfield pieces source torrent key')

Torrent = collections.namedtuple('Torrent', 'announce_url info_hash info_hash_hex pieces_count piece_size complete_threshold')

### CLASSES ###

class AnalyzerError(Exception):
	pass

class FileError(AnalyzerError):
	pass

class DHTError(AnalyzerError):
	pass

class TrackerError(AnalyzerError):
	pass

class DatabaseError(AnalyzerError):
	pass

class PeerError(AnalyzerError):
	pass

class Source(enum.Enum):
	tracker = 0
	incoming = 1
	dht = 2

## Simple thread-safe counter
class SharedCounter:
	## Set value and create a lock
	def __init__(self):
		self.value = 0
		self.lock = threading.Lock()

	## Increase value by one
	def increment(self):
		with self.lock:
			self.value += 1

	## Read value
	#  @return The value
	def get(self):
		with self.lock:
			return self.value

	## Resets the value to zero
	def reset(self):
		with self.lock:
			self.value = 0

## Establishes and closes a TCP connection
class TCPConnection:
	def __init__(self, ip, port, timeout):
		logging.info('Connecting to peer ...')
		try:
			self.sock = socket.create_connection((ip, port), timeout)
		except OSError as err:
			raise PeerError('Connection establishment failed: {}'.format(err))
		logging.info('Connection established')

	def __enter__(self):
		return self.sock

	def __exit__(self, exception_type, exception_value, traceback):
		try:
			self.sock.close()
		except OSError as err:
			logging.warning('Closing of connectioin failed: {}'.format(err))
		else:
			logging.info('Connection closed')

### METHODS ###

## Convert bytes to hex string
#  @param data Input bytes
#  @return Hex string
def bytes_to_hex(data):
	return binascii.hexlify(data).decode()

## Convert hex string to bytes
#  @param data Input hex string
#  @return Bytes
def hex_to_bytes(data):
	return bytes.fromhex(data)

## Converts bytes to a separated bitmap string
#  @param data Bytes to be converted
#  @return Bitmap string containing only '0' and '1' and '|' as separator
def bytes_to_bitmap(data):
	bitmap_parts = list()
	for byte in data:
		bitmap_parts.append(format(byte, '008b'))
	return '|'.join(bitmap_parts)

