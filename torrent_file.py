# Built-in modules
import hashlib
import logging
import base64
import collections

# Extern modules
import bencodepy

## Named tuple representing a torrent
Torrent = collections.namedtuple('Torrent', 'announce_url info_hash pieces_count piece_size')

## Providing methods for analysis of torrent files
class TorrentParser:
	## Reads and decodes a torrent file from the file system
	#  @param path File path
	#  @exception FileError
	def __init__(self, path):
		# Open file
		try:
			torrent_file_object = open(path, mode='rb')
		except OSError as err:
			raise FileError('Could not open file: ' + str(err))

		# Read and close file
		try:
			torrent_file_bencoded = torrent_file_object.read()
		except OSError as err:
			raise FileError('Could not read file: ' + str(err))
		finally:
			torrent_file_object.close()

		# Decode content
		try:
			self.torrent_file = bencodepy.decode(torrent_file_bencoded)
		except bencodepy.exceptions.DecodingError as err:
			raise FileError('Could not decode file: ' + str(err))
		logging.info('Read torrent file from ' + path)

	## Extract announce URL
	#  @return The tracker announce URL
	#  @exception FileError
	def get_announce_url(self):
		try:
			announce_url_bytes = self.torrent_file[b'announce']
		except KeyError as err:
			raise FileError('File did not contain a announce URL: ' + str(err))
		return announce_url_bytes.decode()

	## Extract info hash
	#  @return The info hash
	#  @exception FileError
	def get_info_hash(self):
		try:
			info_dict = self.torrent_file[b'info']
		except KeyError as err:
			raise FileError('File did not contain the info dictionary: ' + str(err))
		try:
			info_dict_bencoded = bencodepy.encode(info_dict)
		except bencodepy.exceptions.EncodingError as err:
			raise FileError('Bencoding failed: ' + str(err))
		sha1_hasher = hashlib.sha1(info_dict_bencoded)
		return sha1_hasher.digest()

	## Extract the number of pieces
	#  @return Pieces number
	#  @exception FileError
	def get_pieces_number(self):
		try:
			info_dict = self.torrent_file[b'info']
			pieces = info_dict[b'pieces']
		except KeyError as err:
			raise FileError('File did not contain the info dictionary or pieces list: ' + str(err))
		number = int(len(pieces) / 20)
		if number == 0:
			raise FileError('Torrent containes no pieces')
		return number

	## Extract the size of the pieces
	#  @return Size in Bytes
	#  @exception FileError
	def get_piece_size(self):
		try:
			info_dict = self.torrent_file[b'info']
			size = info_dict[b'piece length']
		except KeyError as err:
			raise FileError('File did not contain the length of pieces: ' + str(err))
		if size == 0:
			raise FileError('Piece size is zero')
		return size

## Exception for a unreachable or bad torrent file
class FileError(Exception):
	pass

## Return Torrent named tuple using the TorrentParser
#  @param path File system path to a valid torrent file
#  @return Torrent named tuple
#  @exception FileError
def import_torrent(path):
	parser = TorrentParser(path)
	announce_url = parser.get_announce_url()
	logging.info('Announce URL is ' + announce_url)
	info_hash = parser.get_info_hash()
	info_hash_hex = base64.b16encode(info_hash).decode()
	logging.info('Info hash is ' + info_hash_hex)
	pieces_number = parser.get_pieces_number()
	logging.info('Number of pieces is ' + str(pieces_number))
	piece_size = parser.get_piece_size()
	logging.info('Size of one piece is ' + str(piece_size) + ' bytes')
	return Torrent(announce_url, info_hash, pieces_number, piece_size)

