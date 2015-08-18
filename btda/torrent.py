# Built-in modules
import hashlib
import logging
import urllib.parse
import tempfile
import time

# Project modules
import config
from util import *

# Extern modules
import bencodepy

## Providing methods for analysis of torrent files
class TorrentFile:
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
		logging.info('Read torrent file ' + path)

	## Extract announce URL
	#  @return A list of tracker announce URLs
	#  @exception FileError
	def get_announce_url(self):
		announce = set()
		if b'announce' in self.torrent_file:
			announce.add(self.torrent_file[b'announce'].decode())
		if b'announce-list' in self.torrent_file:
			for url in self.torrent_file[b'announce']
				announce.add(url[0].deode())
		if not announce:
			raise FileError('File did not contain a announce URL: ' + str(err))
		return list(announce)

	## Extract info dict
	#  @return Bencoded info dict
	#  @exception FileError
	def get_info_dict(self):
		try:
			info_dict = self.torrent_file[b'info']
		except KeyError as err:
			raise FileError('File did not contain the info dictionary: ' + str(err))
		try:
			return bencodepy.encode(info_dict)
		except bencodepy.exceptions.EncodingError as err:
			raise FileError('Bencoding failed: ' + str(err))

## Providing methods for analysis of a bencoded info dict
class InfoDict:
	## Decode a info dict
	#  @param info_dict Bencoded info dict
	#  @exception FileError
	def __init__(self, info_dict):
		self.info_dict_bencoded = info_dict
		try:
			self.info_dict = bencodepy.decode(info_dict)
		except bencodepy.exceptions.EncodingError as err:
			raise FileError('Bencoding failed: {}'.format(err))

	## Calculate the info hash
	#  @return The info hash
	def get_info_hash(self):
		return hashlib.sha1(self.info_dict_bencoded).digest()

	## Extract the size of the pieces
	#  @return Size in Bytes
	#  @exception FileError
	def get_piece_length(self):
		try:
			size = self.info_dict[b'piece length']
		except KeyError as err:
			raise FileError('File did not contain the length of pieces: {}'.format(err))
		if size == 0:
			raise FileError('Piece size is zero')
		return size

	## Extract the number of pieces
	#  @return Pieces number
	#  @exception FileError
	def get_pieces_count(self):
		try:
			pieces = self.info_dict[b'pieces']
		except KeyError as err:
			raise FileError('File did not contain the pieces list: {}'.format(err))
		number = int(len(pieces) / 20)
		if number == 0:
			raise FileError('Torrent containes no pieces')
		return number

	## Extract the name
	#  @return The name or None
	def get_name(self):
		try:
			return self.info_dict[b'name'].decode()
		except KeyError as err:
			logging.warning('File did not contain a name tag: {}'.format(err))

## Extract the info hash according to BEP 9
#  @return Info hash as hex string
#  @exception FileError
def hash_from_magnet(magnet):
	url = urllib.parse.urlparse(magnet)
	if url.scheme != 'magnet':
		raise FileError('Wrong scheme: {}'.format(url.scheme))
	params = urllib.parse.parse_qs(url.query)
	if len(params['xt']) > 1:
		logging.error('Magnet links with multiple info hashes are not supported')
	splitted = params['xt'][0].split(':')
	if len(splitted) != 3 or splitted[0] != 'urn' or splitted[1] != 'btih':
		raise FileError('Bad xt parameter')
	if len(splitted[2]) == 40:
		return hex_to_bytes(splitted[2])
	elif len(splitted[2]) == 32:
		raise FileError('Base32 hashes not supported')
	raise FileError('Bad info hash length')

## Extract the tracker announce URL according to BEP 9
#  @return The announce URL
#  @exception FileError
def tracker_from_magnet(magnet)
	url = urllib.parse.urlparse(magnet)
	if url.scheme != 'magnet':
		return list()
	params = urllib.parse.parse_qs(url.query)
	if 'tr' not in params:
		return list()
	return params['tr']
