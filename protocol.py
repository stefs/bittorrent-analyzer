# Built-in modules
import logging
import struct
import math
import time
import socket
import hashlib
import string
import random

# Project modules
import config
from util import *

# Extern modules
import bencodepy

## Communicates to a peer according to https://wiki.theory.org/BitTorrentSpecification#Peer_wire_protocol_.28TCP.29
class PeerSession:
	## Construct a peer session
	#  @param socket An active connection socket
	#  @param peer_id Own peer ID
	def __init__(self, socket, peer_id):
		# Store attributes
		self.sock = socket
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
				raise PeerError('Sending data failed: {}'.format(err))
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
					raise PeerError('Receiving data failed: {}'.format(err))
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
	#  @param expected_hash An error will be raised if received info hash does not match
	#  @return Tuple of ID choosen by other peer and reserved bytes as unsigned integer
	#  @exception PeerError
	def receive_handshake(self, expected_hash=None):
		# Receive handshake pstrlen
		pstrlen_bytes = self.receive_bytes(1) # PeerError
		pstrlen_tuple = struct.unpack('>B', pstrlen_bytes)
		pstrlen = pstrlen_tuple[0]

		# Receive rest of the handshake
		handshake_bytes = self.receive_bytes(pstrlen + 8 + 20 + 20) # PeerError
		format_string = '>{}s8s20s20s'.format(pstrlen)
		handshake_tuple = struct.unpack(format_string, handshake_bytes)

		# Parse protocol string
		pstr = handshake_tuple[0]
		if pstr != b'BitTorrent protocol':
			raise PeerError('Peer speaks unknown protocol: {}'.format(pstr))

		# Parse reserved bytes for protocol extensions according to https://wiki.theory.org/BitTorrentSpecification#Reserved_Bytes
		reserved = handshake_tuple[1]
		reserved_bitmap = bytes_to_bitmap(reserved)
		logging.info('Reserved bytes in received handshake: {}'.format(reserved_bitmap))

		# Parse info hash
		received_info_hash = handshake_tuple[2]
		if not expected_hash is None and received_info_hash != expected_hash:
			raise PeerError('Mismatch on received info hash: {}'.format(received_info_hash))

		# Parse peer id
		received_peer_id = handshake_tuple[3]
		logging.info('ID of connected peer is ' + str(received_peer_id))

		return received_peer_id, reserved, received_info_hash

	## Sends handshake to initiate BitTorrent Protocol
	#  @param info_hash The info hash to be sent
	#  @param dht_enabled Set BEP 5 DHT bit in reserved bytes
	#  @param extension_enabled Set BEP 10 Extension Protocol bit in reserved bytes
	#  @return Tuple of ID choosen by other peer and reserved bytes as unsigned integer
	#  @exception PeerError
	def send_handshake(self, info_hash, dht_enabled=False, extension_enabled=False):
		# Pack handshake string
		pstr = b'BitTorrent protocol'
		reserved = bytearray(8)
		if dht_enabled:
			reserved[7] |= 0x01
		if extension_enabled:
			reserved[5] |= 0x10
		reserved_bitmap = bytes_to_bitmap(reserved)
		logging.info('Reserved bytes in sent handshake: {}'.format(reserved_bitmap))
		format_string = '>B{}s8s20s20s'.format(len(pstr))
		handshake = struct.pack(format_string, len(pstr), pstr, reserved, info_hash, self.peer_id.encode())
		assert len(handshake) == 49 + len(pstr), 'handshake has the wrong length'

		# Send and receive handshake
		self.send_bytes(handshake) # PeerError

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
		message = Message(message_id, payload)
		message_str = message_to_string(message)
		logging.debug('Received message: {}'.format(message_str))
		return message

	## Collect all messages from the peer until timeout or error
	#  @return List of tuples of message id and payload and duration without last timeout
	def receive_all_messages(self):
		messages = list()
		start = end = time.perf_counter()
		while len(messages) < config.receive_message_max:
			try:
				message = self.receive_message()
			except PeerError as err:
				logging.info('No more messages: {}'.format(err))
				break
			else:
				end = time.perf_counter()
				messages.append(message)
		else:
			logging.warning('Reached message limit')
		return messages, end - start

	## Sends a BitTorrent Protocol message
	#  @param message The message
	#  @exception PeerError
	def send_message(self, message):
		# 4 byte length prefix
		# 1 byte message id
		# payload
		format_string = '!IB{}s'.format(len(message.payload))
		data = struct.pack(format_string, 1+len(message.payload), message.type, message.payload)
		self.send_bytes(data) # PeerError
		message_str = message_to_string(message)
		logging.debug('Sent message: {}'.format(message_str))

	## Sends a port message, according to BEP 5
	#  @param dht_port UDP port of DHT node
	#  @exception PeerError
	def send_port(self, dht_port):
		data = struct.pack('!H', dht_port)
		self.send_message(Message(9, data)) # PeerError
		logging.info('Sent DHT port {} to remote peer'.format(dht_port))

	## Sends a extended message using the BEP 10 Extension Protocol
	#  @param message The Message
	#  @exception PeerError
	def send_extended_message(self, extended_message_id, payload):
		format_string = '!B{}s'.format(len(payload))
		data = struct.pack(format_string, extended_message_id, payload)
		self.send_message(Message(20, data)) # PeerError
		logging.debug('Sent Extension Protocol message of type {}'.format(extended_message_id))

	## Sends extended handshake of the BEP 10 Extension Protocol
	#  @param supported_extensions Dict of supported extensions
	#  @param items Other items to include in the handshake
	def send_extended_handshake(self, supported_extensions, items):
		handshake = dict()
		handshake[b'm'] = supported_extensions
		handshake.update(items)
		handshake_bencoded = bencodepy.encode(handshake)
		self.send_extended_message(0, handshake_bencoded)

## Pack a peer message according to http://www.bittorrent.org/beps/bep_0003.html#peer-messages
#  @param message_id Message id to specify their type, -1 for a keep-alive
#  @param payload Bytes string representing the payload
#  @return Packed message ready for sending
def pack_message(message_id, payload=b''):
	if message_id == -1:
		data = struct.pack('>I', 0)
	else:
		format_string = '>IB{}s'.format(len(payload))
		data = struct.pack(format_string, 1 + len(payload), message_id, payload)
	return data

## Get payload of an message with one byte prefix
#  @param data Input
#  @return Tuple of prefix and payload
def unpack_message(data):
	format_string = '!B{}s'.format(len(data)-1)
	return struct.unpack(format_string, data)

## Generate a random peer id without client software information
#  @return A random peer id as a string
def generate_peer_id():
	possible_chars = string.ascii_letters + string.digits
	peer_id_list = random.sample(possible_chars, 20)
	peer_id = ''.join(peer_id_list)
	logging.info('Generated peer id is {}'.format(peer_id))
	return peer_id

## Gives string representation of a BitTorrent Protocol message for logging purposes
#  @param message The message
#  @return Printable string with type string
def message_to_string(message):
	# Known message types according to http://www.bittorrent.org/beps/bep_0003.html#peer-messages
	peer_message_type = {0: 'choke', 1: 'unchoke', 2: 'interested', 3: 'not interested', 4: 'have', 5: 'bitfield', 6: 'request', 7: 'piece', 8: 'cancel', 9: 'port', 20: 'extended'}

	# Custom id for a keepalive signal
	peer_message_type[-1] = 'keepalive'

	# Get type id and string
	result = list()
	result.append(str(message.type))
	type_string = peer_message_type.get(message.type, 'unknown')
	result.append(type_string)

	# Shorten message and append ellipsis
	message_string = str(message.payload)
	result.append(message_string[:config.bittorrent_message_log_length])
	if len(message_string) > config.bittorrent_message_log_length:
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
		if message.type == 5:
			# Check for correct length of bytes
			needed_bytes = math.ceil(pieces_number / 8)
			if len(message.payload) != needed_bytes:
				logging.warning('Peer sent invalid bitfield of length {} expected was {}'.format(len(message.payload), str(needed_bytes)))
				continue

			# Check for correct sparse zero bits in last byte
			zeros_count = needed_bytes * 8 - pieces_number
			zeros_mask = 2 ** zeros_count - 1
			masked_padding = message.payload[-1] & zeros_mask
			if masked_padding != 0:
				logging.warning('Peer sent invalid bitfield with padding bits {} instead of zeros'.format(masked_padding))
				continue

			# Assign new bitfield
			bitfield = bytearray(message.payload)
			bitfield_count += 1

		# Note have messages in local bitfield
		elif message.type == 4:
			piece_index_tuple = struct.unpack('>I', message.payload)
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
	logging.info('Received {} bitfield, {} have and {} other messages'.format(bitfield_count, have_count, other_count))
	return bitfield

## Determine the threshold in pieces where a download is considered complete
#  @param total_pieces Number of total pieces
#  @return True false answer
def get_complete_threshold(total_pieces):
	return math.ceil(total_pieces * config.torrent_complete_threshold)

## Evaluate a peer by receiving and parsing all messages; send a dht PORT message
#  @param sock Connection socket
#  @param own_peer_id Own peer id
#  @param dht_enabled Should DHT node port be announced
#  @param info_hash Info hash for outgoing evaluations, None for incoming connections
#  @return Evaluation results
#  @exception PeerError
def evaluate_peer(sock, own_peer_id, dht_enabled, info_hash=None):
	# Establish session
	session = PeerSession(sock, own_peer_id)

	# Incoming connection
	if info_hash is None:
		rec_peer_id, reserved, rec_info_hash = session.receive_handshake() # PeerError
		session.send_handshake(rec_info_hash, dht_enabled) # PeerError

	# Outgoning connection
	else:
		session.send_handshake(info_hash, dht_enabled) # PeerError
		rec_peer_id, reserved, rec_info_hash = session.receive_handshake(info_hash) # PeerError

	# Receive messages
	messages, duration = session.receive_all_messages()

	# Send own DHT node UDP port to peer if supported
	if dht_enabled and reserved[7] & 0x01 != 0:
		try:
			session.send_port(config.dht_node_port) # PeerError
		except PeerError as err:
			logging.warning('Could not send PORT message: {}'.format(err))

	# Return results
	return rec_peer_id, rec_info_hash, messages, duration

## Get pieces count and pieces size of an info hash form peer using BEP 9 and BEP 10
#  @param info_hash Info hash of desired torrent
#  @param peer Peer to ask, should be known to have the torrent
#  @param own_peer_id Own peer id to use
#  @return Bencoded info dict
#  @exception PeerError
def get_ut_metadata(info_hash, peer, own_peer_id):
	# Contact peer
	with TCPConnection(*peer, timeout=config.network_timeout) as sock:
		# Establish session
		logging.info('Exchanging handshakes ...')
		session = PeerSession(sock, own_peer_id)
		session.send_handshake(info_hash, dht_enabled=True, extension_enabled=True)
		rec_peer_id, reserved, rec_info_hash = session.receive_handshake(info_hash)
		if rec_info_hash != info_hash:
			raise PeerError('Info hash mismatch')
		if reserved[5] & 0x10 == 0:
			raise PeerError('Extension Protocol not supported')

		# Sending Extension Protocol handshake
		logging.info('Exchanging extended handshake ...')
		supported_extensions = {'ut_metadata': config.extension_ut_metadata_id}
		session.send_extended_handshake(supported_extensions, dict())

		# Receive Extension Protocol handshake
		msg_count = 0
		while msg_count < config.receive_message_max:
			try:
				rec_message = session.receive_message()
			except PeerError as err:
				raise PeerError('No Extension Protocol support: {}'.format(err))
			if rec_message.type == 20:
				break
			msg_count += 1
		else:
			raise PeerError('No extension handshake until message limit')

		# Check for ut_metadata support
		logging.info('Check handshake for ut_metadata support ...')
		extended_message_id, extended_payload = unpack_message(rec_message.payload)
		if extended_message_id != 0:
			raise PeerError('Unknown extended message of type {}'.format(extended_message_id))
		try:
			extended_dict = bencodepy.decode(extended_payload)
		except bencodepy.exceptions.DecodingError as err:
			raise PeerError('Decode error: {}'.format(err))
		try:
			supported_extensions = extended_dict[b'm']
		except KeyError:
			raise PeerError('Bad handshake')
		try:
			rec_ut_metadata_id = supported_extensions[b'ut_metadata']
		except KeyError:
			raise PeerError('No ut_metadata support')
		try:
			metadata_size = extended_dict[b'metadata_size']
		except KeyError:
			raise PeerError('Not received metadata_size')

		# Request blocks
		number_blocks = math.ceil(metadata_size / UT_METADATA_BLOCK_SIZE)
		logging.info('Request {} bytes of metadata in {} blocks ...'.format(metadata_size, number_blocks))
		for block in range(0, number_blocks):
			request = {'msg_type': 0, 'piece': block}
			request = bencodepy.encode(request)
			session.send_extended_message(rec_ut_metadata_id, request)

		# Receive data
		logging.info('Receiving all messages ...')
		messages = session.receive_all_messages()[0]

	# Parse response
	metadata_pieces = dict()
	for message in messages:
		# Check for extended messages
		if message.type != 20:
			continue
		extended_message_id, extended_payload = unpack_message(message.payload)
		if extended_message_id != config.extension_ut_metadata_id:
			logging.warning('Peer sent extended message of unknown type {}'.format(extended_message_id))
			continue

		# Decode extended payload
		try:
			extended_dict = bencodepy.decode(extended_payload)
		except bencodepy.exceptions.DecodingError as err:
			logging.warning('Peer sent bad extended message: {}'.format(err))
			continue
		try:
			msg_type = extended_dict[b'msg_type']
		except KeyError as err:
			logging.warning('Peer sent bad metadata response: {}'.format(err))
			continue
		if msg_type != 1:
			logging.warning('Peer sent wrong metadata response')
			continue
		try:
			piece = extended_dict[b'piece']
		except KeyError as err:
			logging.warning('Peer sent bad metadata response: {}'.format(err))
			continue

		# Save metadata pieces
		expected_appendix = UT_METADATA_BLOCK_SIZE if piece < number_blocks-1 else metadata_size % UT_METADATA_BLOCK_SIZE
		appendix_start = len(extended_payload) - expected_appendix
		assert appendix_start > 0
		metadata_pieces[piece] = extended_payload[appendix_start:]
		logging.info('Received metadata block {} of length {}'.format(piece, len(metadata_pieces[piece])))

	# Merge received pieces of metadata
	metadata = list()
	for block in range(0, number_blocks):
		try:
			metadata.append(metadata_pieces[block])
		except KeyError:
			raise PeerError('Peer did not send block {}'.format(block))
	metadata = b''.join(metadata)

	# Check hash value
	rec_info_hash = hashlib.sha1(metadata).digest()
	if rec_info_hash != info_hash:
		raise PeerError('Mismatch of info hash on received parts')

	# Return info dict
	logging.info('Successfully fetched metadata from peer')
	return metadata
