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

	def __exit__(self, exc_type, exc_value, tb):
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

## Sets a bit at a given index in a given bitfield on true
#  @param bitfield The bitfield to be altered as a bytearray
#  @param index The position to be changed, 0 refers to highest bit of first byte
#  @warn The bitfield parameter must be a bytearray, not of the bytes type, not of type string
def set_bit_at_index(bitfield, index):
	# Devide index in byte index (0123...) and bit index (76543210)
	byte_index = int(index / 8)
	bit_index = 8 - index % 8

	# Alter affected byte
	byte_before = bitfield[byte_index]
	byte_after = byte_before | bit_index

	# Write back
	bitfield[byte_index] = byte_after
	return bitfield

## Returns the numbers of bits set in an bitfield
#  @param bitfield An arbitrary bitfield
#  @return Number of one bits
def count_bits(bitfield):
	count = 0
	for byte in bitfield:
		mask = 1
		for i in range(0,8):
			masked_byte = byte & mask
			if masked_byte > 0:
				count += 1
			mask *= 2
	return count

