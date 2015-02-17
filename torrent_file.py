# Built-in modules
import hashlib
import logging
import base64

# Extern modules
import bencodepy

## Providing methods for analysis of torrent files
class TorrentParser:
	## Reads and decodes a torrent file from the file system
	#  @param path File path
	def __init__(self, path):
		# Open file
		try:
			torrent_file_object = open(path, mode='rb')
		except OSError as err:
			raise FileError('Could not open file: ' + str(err))

		# Read and close file
		try:
			torrent_file_bencoded = torrent_file_object.read()
		except OSError:
			raise FileError('Could not read file: ' + str(err))
		finally:
			torrent_file_object.close()
		self.torrent_file = bencodepy.decode(torrent_file_bencoded)

	## Extract announce URL
	#  @return The tracker announce URL
	def get_announce_url(self):
		announce_url_bytes = self.torrent_file[b'announce']
		announce_url = announce_url_bytes.decode()
		logging.info('Announce URL is ' + announce_url)
		return announce_url

	## Extract info hash
	#  @return The info hash
	def get_info_hash(self):
		info_dict = self.torrent_file[b'info']
		info_dict_bencoded = bencodepy.encode(info_dict)
		sha1_hasher = hashlib.sha1(info_dict_bencoded)
		info_hash = sha1_hasher.digest()
		
		# Convert to hex for logging
		info_hash_hex_bytes = base64.b16encode(info_hash)
		info_hash_hex = info_hash_hex_bytes.decode()
		logging.info('Info hash is ' + info_hash_hex)
		
		return info_hash
		
	## Extract the number of pieces
	#  @return Pieces number
	def get_pieces_number(self):
		info_dict = self.torrent_file[b'info']
		pieces = info_dict[b'pieces']
		pieces_number = int(len(pieces) / 20)
		logging.info('Number of pieces is ' + str(pieces_number))
		return pieces_number

## Exception for a unreachable or bad torrent file
class FileError(Exception):
	pass

