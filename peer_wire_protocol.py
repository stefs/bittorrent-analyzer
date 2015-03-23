# Built-in modules
import logging
import struct
import math
import collections
import time

## Named tuple representing a cached peer
Peer = collections.namedtuple('Peer', 'revisit ip_address port id bitfield pieces active torrent key')

## Communicates to a peer according to https://wiki.theory.org/BitTorrentSpecification#Peer_wire_protocol_.28TCP.29
class PeerSession:
	## Construct a peer session
	#  @param socket An active connection socket
	#  @param info_hash Info hash from original torrent regarding this session
	#  @param peer_id Own peer ID
	def __init__(self, socket, info_hash, peer_id):
		# Store peer socket
		self.sock = socket

		# Store common parameters
		self.info_hash = info_hash
		self.peer_id = peer_id

		# Create buffer for consecutive receive_bytes calls
		self.received_bytes_buffer = b''

	## Sends bytes according to https://docs.python.org/3/howto/sockets.html#using-a-socket
	#  @param data Bytes data to be sent
	#  @exception PeerError
	def send_bytes(self, data):
		total_sent_count = 0
		while total_sent_count < len(data):
			try:
				sent_count = self.sock.send(data[total_sent_count:])
			except OSError as err:
				raise PeerError('Sending data failed: ' + str(err))
			if sent_count == 0:
			        raise PeerError('Socket connection broken')
			total_sent_count += sent_count

	## Receives bytes blocking according to https://stackoverflow.com/a/17508900
	#  @param required_bytes Nuber of bytes to be returned
	#  @return Byte object of exact requested size
	#  @exception PeerError
	def receive_bytes(self, required_bytes):
		# Receive more data if local buffer cannot serve the request
		bytes_to_receive = required_bytes - len(self.received_bytes_buffer)
		if bytes_to_receive > 0:
			data_parts = [self.received_bytes_buffer]
			received_bytes = 0
			while received_bytes < bytes_to_receive:
				try:
					buffer = self.sock.recv(1024)
				except OSError as err:
					raise PeerError('Receiving data failed: ' + str(err))
				if buffer == b'':
			                raise PeerError('Socket connection broken')
				data_parts.append(buffer)
				received_bytes += len(buffer)
			self.received_bytes_buffer = b''.join(data_parts)

		# Extract requested bytes and adjust local buffer
		data = self.received_bytes_buffer[:required_bytes]
		self.received_bytes_buffer = self.received_bytes_buffer[required_bytes:]
		return data

	## Receive a peer wire protocol handshake
	#  @return Tuple of ID choosen by other peer and reserved bytes as unsigned integer
	#  @exception PeerError
	def receive_handshake(self):
		# Receive handshake pstrlen
		pstrlen_bytes = self.receive_bytes(1) # PeerError
		pstrlen_tuple = struct.unpack('>B', pstrlen_bytes)
		pstrlen = pstrlen_tuple[0]

		# Receive rest of the handshake
		handshake_bytes = self.receive_bytes(pstrlen + 8 + 20 + 20) # PeerError
		format_string = '>' + str(pstrlen) + 'sQ20s20s'
		handshake_tuple = struct.unpack(format_string, handshake_bytes)

		# Parse protocol string
		pstr = handshake_tuple[0]
		if pstr != b'BitTorrent protocol':
			raise PeerError('Peer speaks unknown protocol: ' + str(pstr))

		# Parse reserved bytes for protocol extensions according to https://wiki.theory.org/BitTorrentSpecification#Reserved_Bytes
		reserved = handshake_tuple[1]
		if reserved != 0:
			reserved_bitmap = number_to_64_bitmap(reserved)
			logging.info('Reserved bytes of received handshake set: ' + reserved_bitmap)

		# Parse info hash
		received_info_hash = handshake_tuple[2]
		if received_info_hash != self.info_hash:
			raise PeerError('Mismatch on received info hash: ' + str(received_info_hash))

		# Parse peer id
		received_peer_id = handshake_tuple[3]
		logging.info('ID of connected peer is ' + str(received_peer_id))

		return (received_peer_id, reserved)

	## Receives and sends handshake to initiate BitTorrent Protocol
	#  @return Tuple of ID choosen by other peer and reserved bytes as unsigned integer
	#  @exception PeerError
	def exchange_handshakes(self):
		# Pack handshake string
		pstr = b'BitTorrent protocol'
		peer_id_bytes = self.peer_id.encode()
		format_string = '>B' + str(len(pstr)) + 'sQ20s20s'
		handshake = struct.pack(format_string, len(pstr), pstr, 0, self.info_hash, peer_id_bytes)
		assert len(handshake) == 49 + len(pstr), 'handshake has the wrong length'
		logging.debug('Prepared handshake is ' + str(handshake))

		# Send and receive handshake
		self.send_bytes(handshake) # PeerError
		return self.receive_handshake() # PeerError

	## Receive a peer message
	#  @return Tuple of message id and payload, keepalive has id -1
	#  @exception PeerError
	def receive_message(self):
		# Receive message length prefix
		length_prefix_bytes = self.receive_bytes(4) # PeerError
		length_prefix_tuple = struct.unpack('>I', length_prefix_bytes)
		length_prefix = length_prefix_tuple[0]
		if length_prefix == 0:
			return (-1, b'')

		# Receive message id and payload
		message_id_bytes = self.receive_bytes(1) # PeerError
		message_id_tuple = struct.unpack('>B', message_id_bytes)
		message_id = message_id_tuple[0]

		# Receive payload
		payload_length = length_prefix - 1
		payload_bytes = self.receive_bytes(payload_length) # PeerError
		format_string = '>' + str(payload_length) + 's'
		payload_tuple = struct.unpack(format_string, payload_bytes)
		payload = payload_tuple[0]

		# Return message id and payload tuple
		message_str = message_to_string(message_id, payload, 80)
		logging.debug('Received message: ' + message_str)
		return (message_id, payload)

	## Collect all messages from the peer until timeout or error
	#  @param max_messages Maximal number of messages received in one connection
	#  @return List of tuples of message id and payload
	def receive_all_messages(self, max_messages):
		messages = list()
		while len(messages) < max_messages:
			try:
				message = self.receive_message()
			except PeerError as err:
				logging.info('No more messages: ' + str(err))
				break
			else:
				messages.append(message)
		if len(messages) == max_messages:
			logging.error('Reached message limit of ' + str(max_messages))
		return messages

## Exception for not expected behavior of other peers and network failures
class PeerError(Exception):
	pass

## Pack a peer message according to http://www.bittorrent.org/beps/bep_0003.html#peer-messages
#  @param message_id Message id to specify their type, -1 for a keep-alive
#  @param payload Bytes string representing the payload
#  @return Packed message ready for sending
def pack_message(message_id, payload=b''):
	if message_id == -1:
		data = struct.pack('>I', 0)
	else:
		format_string = '>IB' + str(len(payload)) + 's'
		data = struct.pack(format_string, 1 + len(payload), message_id, payload)
	return data

## Converts a number to a seperated bitmap string of length 64, for logging purposes
#  @param number Integer to be converted, maximum value is 2**64-1
def number_to_64_bitmap(number):
	reserved_bitmap = '{:064b}'.format(int(number))
	assert len(reserved_bitmap) <= 64, 'format string result too long: ' + str(len(reserved_bitmap))
	bitmap_parts = list()
	for byte in range(0, 8):
		start = byte * 8
		bitmap_parts.append(reserved_bitmap[start:start+8])
	return '|'.join(bitmap_parts)

## Gives string representation of a message for user output, for logging purposes
#  @param message_id Type of the message as integer ID
#  @param payload Message content as a bytestring
#  @param length Maximum length of the message payload part
#  @return Printable string with type string
def message_to_string(message_id, payload, length):
	# Known message types according to http://www.bittorrent.org/beps/bep_0003.html#peer-messages
	peer_message_type = {0: 'choke', 1: 'unchoke', 2: 'interested', 3: 'not interested', 4: 'have', 5: 'bitfield', 6: 'request', 7: 'piece', 8: 'cancel'}

	# Custom id for a keepalive signal
	peer_message_type[-1] = 'keepalive'

	# Get type id and string
	result = list()
	result.append(str(message_id))
	type_string = peer_message_type.get(message_id, 'unknown')
	result.append(type_string)

	# Shorten message and append ellipsis
	message_string = str(payload)
	result.append(message_string[:length])
	if len(message_string) > length:
		result.append('...')

	# Join strings with seperator
	return ' '.join(result)

## Calculates the bitfield from a list of messages
#  @param messages List of messages to be evaluated
#  @param pieces_number Number of pieces contained the corresponding
#  @return Received bitfield as a bytearray
def bitfield_from_messages(messages, pieces_number):
	bitfield = bytearray(pieces_number)
	bitfield_count = have_count = other_count = 0
	for message in messages:
		# Store bitfields
		if message[0] == 5:
			# Check for correct length of bytes
			needed_bytes = math.ceil(pieces_number / 8)
			if len(message[1]) != needed_bytes:
				logging.warning('Peer sent invalid bitfield of length ' + str(len(message[1])) + ', expected was ' + str(needed_bytes))
				continue

			# Check for correct sparse zero bits in last byte
			zeros_count = needed_bytes * 8 - pieces_number
			zeros_mask = 2 ** zeros_count - 1
			masked_padding = message[1][-1] & zeros_mask
			if masked_padding != 0:
				logging.warning('Peer sent invalid bitfield with padding bits ' + str(masked_padding) + ' instead of zeros')
				continue

			# Assign new bitfield
			bitfield = bytearray(message[1])
			bitfield_count += 1

		# Note have messages in local bitfield
		elif message[0] == 4:
			piece_index_tuple = struct.unpack('>I', message[1])
			piece_index = piece_index_tuple[0]
			if piece_index <= pieces_number:
				set_bit_at_index(bitfield, piece_index)
				have_count += 1
			else:
				logging.warning('Peer sent a have message with out of bounds piece index')

		# Unknown or other message
		else:
			other_count += 1

	# Return peer_id and bitfield
	logging.info('Received ' + str(bitfield_count) + ' bitfield, ' + str(have_count) + ' have and ' + str(other_count) + ' other messages')
	return bitfield

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

## Evaluate a peer by receiving all messages and updating attributes accordingly
#  @param peer Peer named tuple
#  @param socket Active peer connection socket
#  @param info_hash Info hash of the current torrent
#  @param own_peer_id Own peer id
#  @param pieces_number Number of pieces of the current torrent
#  @param delay Evaluation delay in seconds
#  @return Evaluated Peer named tuple
#  @exception PeerError
# TODO take out Peer creation to reduce argument list
def evaluate_peer(peer, socket, info_hash, own_peer_id, pieces_number, delay):
	# Initiate session, exchange handshakes, receive messages
	session = PeerSession(socket, info_hash, own_peer_id)
	peer_id = session.exchange_handshakes()[0] # PeerError
	messages = session.receive_all_messages(100)

	# Evaluate bitfield
	bitfield = bitfield_from_messages(messages, pieces_number)

	# Count finished pieces
	pieces_count = count_bits(bitfield)
	percentage = int(pieces_count * 100 / pieces_number)
	remaining = pieces_number - pieces_count
	logging.info('Peer reports to have ' + str(pieces_count) + ' pieces, ' + str(remaining) + ' remaining, equals ' + str(percentage) + '%')

	# Save results
	revisit_time = time.perf_counter() + delay
	return Peer(revisit_time, peer.ip_address, peer.port, peer_id, bitfield, pieces_count, peer.active, peer.torrent, peer.key)

