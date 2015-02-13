# Built-in modules
import hashlib

# Extern modules
import bencodepy

## Providing methods for analysis of torrent files
class torrent:
	## Reads and decodes a torrent file from the file system
	#  @param path File path
	def __init__(self, path):
		try:
			torrent_file_object = open(path, mode='rb')
			torrent_file_bencoded = torrent_file_object.read()
			torrent_file_object.close()
		except OSError as err:
			raise BadFile('Could not read file: ' + str(err))
		self.torrent_file = bencodepy.decode(torrent_file_bencoded)

	## Extract announce URL
	#  @return The tracker announce URL
	def get_announce_url(self):
		announce_url_bytes = self.torrent_file[b'announce']
		return announce_url_bytes.decode()

	## Extract info hash
	#  @return The info hash
	def get_info_hash(self):
		info_dict = self.torrent_file[b'info']
		info_dict_bencoded = bencodepy.encode(info_dict)
		sha1_hasher = hashlib.sha1(info_dict_bencoded)
		return sha1_hasher.digest()

## Exception for a unreachable or bad torrent file
class BadFile(Exception):
	pass

