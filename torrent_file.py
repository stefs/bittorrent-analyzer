# Built-in modules
import hashlib
import logging
import urllib.parse
import libtorrent
import tempfile
import time

# Extern modules
import bencodepy

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
		logging.info('Read torrent file ' + path)

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

## Uses libtorrent to get pieces count and pieces size of an info hash
#  @param magnet Magnet URI, will not be validated, in case of bad magnet returns after timeout
#  @param peers List of known peers of torrent, used when tracker is missing
#  @param timeout Throw error if not returned after this time
#  @return Extracted metadata
#  @exception FileError
#  @note Inspired by https://github.com/erindru/m2t/blob/58c34f97a5ae613e98cf63e562a4de63e936a071/m2t/api.py
def fetch_magnet(magnet, peers, timeout):
	# Creating temporary directory
	with tempfile.TemporaryDirectory() as tempdir:
		# Create libtorrent session
		lt_ses = libtorrent.session()
		params = {"save_path": tempdir, "paused": False, "auto_managed": False, "url": magnet}
		handle = lt_ses.add_torrent(params)

		try:
			# Waiting for metadata
			i = 0
			while not handle.has_metadata():
				# Connect known peers successive to minimize uptime
				if i < len(peers):
					handle.connect_peer(peers[i]) # TODO test

				# Respect timeout and wait
				if i >= timeout:
					raise FileError('Could not get pieces info from magnet link in time')
				time.sleep(1)

			# Extract metadata
			info_hash = handle.info_hash()
			torrent_info = handle.get_torrent_info()
			trackers = torrent_info.trackers()
			piece_length = torrent_info.piece_length()
			num_pieces = torrent_info.num_pieces()
		except:
			raise
		finally:
			# End libtorrent session in any case
			lt_ses.remove_torrent(handle)
			del lt_ses

	# Sanitize trackers
	if len(trackers) > 1:
		logging.warning('Only using first tracker: {}'.format(trackers))
	tracker = trackers[0] if len(tracker)>0 else None

	# Return result
	return info_hash, tracker, piece_length, num_pieces

