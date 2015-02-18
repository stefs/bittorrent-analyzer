# Built-in modules
import logging
import socket
import struct
import select
import math

## Handles connection and communication to a peer according to https://wiki.theory.org/BitTorrentSpecification#Peer_wire_protocol_.28TCP.29
class PeerSession:
	## Construct a peer session
	#  @param peer_ip Tuple of ip address as string and port number
	#  @param timeout Timeout in seconds used for all network operations
	#  @param info_hash Info hash from original torrent regarding this session
	#  @param peer_id Own peer ID
	#  @warning Must be used with the with statement to guarantee a close
	def __init__(self, peer_ip, timeout, info_hash, peer_id):
		# Store peer and torrent data and timeout parameter
		self.peer_ip = peer_ip
		self.timeout = timeout
		self.info_hash = info_hash
		self.peer_id = peer_id
		
		# Create buffer for consecutive receive_bytes calls
		self.received_bytes_buffer = b''
		
	## Create a socket and open the TCP connection
	#  @exception OSError
	def __enter__(self):
		# Create connection to peer
		logging.info('Connecting to peer at ' + self.peer_ip[0] + ' port ' + str(self.peer_ip[1]) + ' ...')
		self.sock = socket.create_connection(self.peer_ip, self.timeout) # OSError
		logging.info('Connection established')
		
		# Enter method returns self to with-target
		return self
		
	## Sends bytes according to https://docs.python.org/3/howto/sockets.html#using-a-socket
	#  @param data Bytes data to be sent
	#  @exception OSError
	def send_bytes(self, data):
		total_sent_count = 0
		while total_sent_count < len(data):
			sent_count = self.sock.send(data[total_sent_count:]) # OSError
			if sent_count == 0:
			        raise OSError('Socket connection broken')
			total_sent_count += sent_count

	## Receives bytes blocking according to https://stackoverflow.com/a/17508900
	#  @param required_bytes Nuber of bytes to be returned
	#  @return Byte object of exact requested size
	#  @exception OSError
	def receive_bytes(self, required_bytes):
		# Receive more data if local buffer cannot serve the request
		bytes_to_receive = required_bytes - len(self.received_bytes_buffer)
		if bytes_to_receive > 0:
			data_parts = [self.received_bytes_buffer]
			received_bytes = 0
			while received_bytes < bytes_to_receive:
				buffer = self.sock.recv(1024) # OSError
				if buffer == b'':
			                raise OSError('Socket connection broken')
				data_parts.append(buffer)
				received_bytes += len(buffer)
			self.received_bytes_buffer = b''.join(data_parts)
		
		# Extract requested bytes and adjust local buffer
		data = self.received_bytes_buffer[:required_bytes]
		self.received_bytes_buffer = self.received_bytes_buffer[required_bytes:]
		return data
	
	## Receive a peer wire protocol handshake
	#  @return Tuple of ID choosen by other peer and reserved bytes as unsigned integer
	#  @exception OSError,PeerError
	def receive_handshake(self):
		# Receive handshake pstrlen
		pstrlen_bytes = self.receive_bytes(1) # OSError
		pstrlen_tuple = struct.unpack('>B', pstrlen_bytes)
		pstrlen = pstrlen_tuple[0]
		
		# Receive rest of the handshake
		handshake_bytes = self.receive_bytes(pstrlen + 8 + 20 + 20) # OSError
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
	#  @exception OSError,PeerError
	def exchange_handshakes(self):
		# Pack handshake string
		pstr = b'BitTorrent protocol'
		peer_id_bytes = self.peer_id.encode()
		format_string = '>B' + str(len(pstr)) + 'sQ20s20s'
		handshake = struct.pack(format_string, len(pstr), pstr, 0, self.info_hash, peer_id_bytes)
		assert len(handshake) == 49 + len(pstr), 'handshake has the wrong length'
		logging.debug('Prepared handshake is ' + str(handshake))
		
		# Send and receive handshake
		self.send_bytes(handshake) # OSError
		return self.receive_handshake() # OSError, PeerError
	
	## Receive a peer message
	#  @return Tuple of message id and payload, keepalive has id -1
	#  @exception OSError
	def receive_message(self):
		# Receive message length prefix
		length_prefix_bytes = self.receive_bytes(4) # OSError
		length_prefix_tuple = struct.unpack('>I', length_prefix_bytes)
		length_prefix = length_prefix_tuple[0]
		if length_prefix == 0:
			return (-1, b'')

		# Receive message id and payload
		message_id_bytes = self.receive_bytes(1) # OSError
		message_id_tuple = struct.unpack('>B', message_id_bytes)
		message_id = message_id_tuple[0]
		
		# Receive payload
		payload_length = length_prefix - 1
		payload_bytes = self.receive_bytes(payload_length) # OSError
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
				message = self.receive_message() # OSError
			except OSError as err:
				logging.info('No more message: ' + str(err))
				break
			else:
				messages.append(message)
		if len(messages) == max_messages:
			logging.error('Reached message limit of ' + str(max_messages))
		return messages

	## Closing connection on socket
	#  @note Exit method is guaranteed called in conjunction with the with statement
	def __exit__(self, exception_type, exception_value, traceback):
		try:
			self.sock.close()
		except OSError as err:
			# No exception as the results can still be used as this is the session end
			logging.warning('Closing of connectioin failed: ' + str(err))
		else:
			logging.info('Connection closed')

# Exception for not expected behavior of other peers and network failures
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
	logging.debug('Bit ' + str(index) + ' equals bit ' + str(bit_index) + ' in byte ' + str(byte_index) + ', converted ' + str(byte_before) + ' to ' + str(byte_after))

	# Write back
	bitfield[byte_index] = byte_after
	return bitfield

