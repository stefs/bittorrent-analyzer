# Built-in modules
import logging
import socket
import struct
import select

## Handles connection and communication to a peer according to https://wiki.theory.org/BitTorrentSpecification#Peer_wire_protocol_.28TCP.29
class peer_session:
	## Construct a peer session
	#  @param peer_ip Tuple of ip address as string and port number
	#  @warning Must be used with the with statement to guarantee a close
	def __init__(self, peer_ip):
		# Store peer ip data
		self.peer_ip = peer_ip
		
		# Create buffer for consecutive receive_bytes calls
		self.received_bytes_buffer = b''
		
	## Create a socket and open the TCP connection
	#  @note The enter method is called by the with statement
	def __enter__(self):
		# Create connection to peer
		logging.info('Connecting to peer at ' + self.peer_ip[0] + ' at port ' + str(self.peer_ip[1]))
		try:
			self.sock = socket.create_connection(self.peer_ip, timeout=3)
		except OSError as err:
			raise PeerFailure('Connection establishment failed: ' + str(err))
		logging.info('Connection established')
		
		# Enter method returns self to with-target
		return self
		
	## Sends bytes according to https://docs.python.org/3/howto/sockets.html#using-a-socket
	#  @param data Bytes data to be sent
	def send_bytes(self, data):
		total_sent_count = 0
		while total_sent_count < len(data):
			try:
				sent_count = self.sock.send(data[total_sent_count:])
			except OSError as err:
				raise PeerFailure('Could not send data: ' + str(err))
			if sent_count == 0:
			        raise PeerFailure('Socket connection broken')
			total_sent_count += sent_count

	## Receives bytes blocking and without timeout according to https://stackoverflow.com/a/17508900
	#  @param required_bytes Nuber of bytes to be returned
	#  @return Byte object of exact requested size
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
					raise PeerFailure('Could not read from socket: ' + str(err))
				if buffer == b'':
			                raise PeerFailure('Socket connection broken')
				data_parts.append(buffer)
				received_bytes += len(buffer)
			self.received_bytes_buffer = b''.join(data_parts)
		
		# Extract requested bytes and adjust local buffer
		data = self.received_bytes_buffer[:required_bytes]
		self.received_bytes_buffer = self.received_bytes_buffer[required_bytes:]
		logging.debug('Returned bytes: ' + str(data))
		logging.debug('Stored bytes: ' + str(self.received_bytes_buffer))
		return data
	
	## Receive a peer wire protocol handshake
	#  @param info_hash Expected info hash from original torrent
	#  @return ID choosen by other peer
	def receive_handshake(self, info_hash):
		# Receive handshake pstrlen
		pstrlen_bytes = self.receive_bytes(1)
		pstrlen_tuple = struct.unpack('>B', pstrlen_bytes)
		pstrlen = pstrlen_tuple[0]
		
		# Receive rest of the handshake
		handshake_bytes = self.receive_bytes(pstrlen + 8 + 20 + 20)
		format_string = '>' + str(pstrlen) + 'sQ20s20s'
		handshake_tuple = struct.unpack(format_string, handshake_bytes)
		
		# Parse protocol string
		pstr = handshake_tuple[0]
		if pstr != b'BitTorrent protocol':
			raise PeerFailure('Peer speaks unknown protocol: ' + str(pstr))

		# Parse reserved bytes for protocol extensions according to https://wiki.theory.org/BitTorrentSpecification#Reserved_Bytes
		reserved = handshake_tuple[1]
		if reserved != 0:
			reserved_bitmap = number_to_64_bitmap(reserved)
			logging.info('Reserved bytes in handshake contained non zero value: ' + reserved_bitmap)
		
		# Parse info hash
		received_info_hash = handshake_tuple[2]
		if received_info_hash != info_hash:
			raise PeerFailure('Mismatch on received info hash: ' + str(received_info_hash))

		# Parse peer id
		return handshake_tuple[3]
	
	## Receive a peer message
	#  @return Tuple of message id and payload, keepalive has id -1
	def receive_message(self):
		# Receive message length prefix
		length_prefix_bytes = self.receive_bytes(4)
		length_prefix_tuple = struct.unpack('>I', length_prefix_bytes)
		length_prefix = length_prefix_tuple[0]
		if length_prefix == 0:
			return (-1, b'')

		# Receive message id and payload
		message_id_bytes = self.receive_bytes(1)
		message_id_tuple = struct.unpack('>B', message_id_bytes)
		message_id = message_id_tuple[0]
		
		# Receive payload
		payload_length = length_prefix - 1
		payload_bytes = self.receive_bytes(payload_length)
		format_string = '>' + str(payload_length) + 's'
		payload_tuple = struct.unpack(format_string, payload_bytes)
		payload = payload_tuple[0]
		
		# Return message id and payload tuple
		return (message_id, payload)
	
	## Checks weather the peer has sent a message which could be received
	#  @return True if there is a peer message, False otherwise
	def has_message(self):
		# Check if partial message is in buffer
		if len(self.received_bytes_buffer) > 0:
			return True
		
		# Check if ther is new data according to https://docs.python.org/3/library/select.html#select.select
		potential_readers = [self.sock]
		timeout = 10
		try:
			ready_to_read, ready_to_write, in_error = select.select(potential_readers, [], [], timeout)
		except OSError:
			return False
		return len(ready_to_read) > 0
	
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

## Exception for not expected behavior of other peers and network failures
class PeerFailure(Exception):
	pass

## Assamble a handshake to the other peer
#  @param peer_id 20 byte string choosen by the client to identify itself
#  @param info_hash 20 byte sha-1 hash representing the current torrent
#  @return Packed handshake ready for sending
def pack_handshake(peer_id, info_hash):
	# Pack handshake string
	pstr = b'BitTorrent protocol'
	peer_id_bytes = peer_id.encode()
	format_string = '>B' + str(len(pstr)) + 'sQ20s20s'
	handshake = struct.pack(format_string, len(pstr), pstr, 0, info_hash, peer_id_bytes)

	# Send handshake of correct length
	assert len(handshake) == 49 + len(pstr), 'handshake has the wrong length'
	return handshake

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

## Converts a number to a seperated bitmap string of length 64
#  @param input Integer to be converted, maximum value is 2**64-1
def number_to_64_bitmap(input):
	reserved_bitmap = '{:064b}'.format(int(input))
	assert len(reserved_bitmap) <= 64, 'format string result too long: ' + str(len(reserved_bitmap))
	bitmap_parts = list()
	for byte in range(0, 8):
		start = byte * 8
		bitmap_parts.append(reserved_bitmap[start:start+8])
	return '|'.join(bitmap_parts)

## Gives string representation of a message for user output
#  @param message The message to be evaluated as a tupel (type id, payload)
#  @param length Maximum length of the message payload part
#  @return Printable string with type string
def message_to_string(message, length):
	# Known message types according to http://www.bittorrent.org/beps/bep_0003.html#peer-messages
	peer_message_type = {0: 'choke', 1: 'unchoke', 2: 'interested', 3: 'not interested', 4: 'have', 5: 'bitfield', 6: 'request', 7: 'piece', 8: 'cancel'}
	
	# Custom id for a keepalive signal
	peer_message_type[-1] = 'keepalive'
	
	# Get type id and string
	result = list()
	result.append(str(message[0]))
	type_string = peer_message_type.get(message[0], 'unknown')
	result.append(type_string)
	
	# Shorten message and append ellipsis
	message_string = str(message[1])
	result.append(message_string[:length])
	if len(message_string) > length:
		result.append('...')
	
	# Join strings with seperator
	return ' '.join(result)

