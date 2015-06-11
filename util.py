# Built-in modules
import collections
import enum
import threading
import logging
import socket
import binascii
import struct
import time

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

class UtilError(AnalyzerError):
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
			raise UtilError('Connection establishment failed: {}'.format(err))
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

## Activity timer
class ActivityTimer:
	## Initialize an activity timer
	def __init__(self):
		self.read_timestamp = time.perf_counter()
		self.timer = dict()
		self.lock = threading.RLock()

	## Register a thread to be timed
	#  @param thread Identifier
	#  @param active Register thread as active or inactive
	def register(self, thread, active=True):
		with self.lock:
			self.timer[thread] = (
					active, # is active
					0, # timer seconds
					time.perf_counter()) # unpaused timestamp

	## Mark a thread as inactive and add active seconds
	#  @param thread Identifier
	def inactive(self, thread):
		with self.lock:
			if self.timer[thread][0]:
				self.timer[thread] = (
						False,
						self.timer[thread][1] + time.perf_counter() - self.timer[thread][2],
						None)
			else:
				raise UtilError('Timer for thread {} is already inactive'.format(thread))

	## Mark a thread as active and log timestamp
	#  @param thread Identifier
	def active(self, thread):
		with self.lock:
			if not self.timer[thread][0]:
				self.timer[thread] = (
						True,
						self.timer[thread][1],
						time.perf_counter())
			else:
				raise UtilError('Timer for thread {} is already inactive'.format(thread))

	## Extract active seconds exactly and reset active threads
	#  @return Average thread workload between 0 and 1
	def read(self):
		# Calculate total time delta
		perf_counter = time.perf_counter()
		total_delta = perf_counter - self.read_timestamp
		self.read_timestamp = perf_counter

		# Calculate workload
		workload = list()
		with self.lock:
			for thread in self.timer:
				active = self.timer[thread][0]
				if active:
					self.inactive(thread)
				workload.append(self.timer[thread][1] / total_delta)
				logging.info('Workload of thread {} is {}s/{}s = {}'.format(thread, round(self.timer[thread][1]), round(total_delta), workload[-1]))
				self.register(thread, active)
		try:
			workload = sum(workload) / len(workload)
		except ZeroDivisionError:
			workload = None
		logging.info('Overall thread workload is {}'.format(workload))
		return workload

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
