# Built-in modules
import logging
import queue
import collections
import socket

## Create named tuple
CachedPeer = collections.namedtuple('CachedPeer', 'delay ip_address port id bitfield pieces')

## Cache of peers in different conection and progress states
#  @warn Not threadsafe, calls must be guarded with locks
class PeerCache:
	## Initialization of a cache for peers
	def __init__(self):
		# Containes CachedPeer tuples
		self.in_progress = queue.PriorityQueue()
	
	## Add a new peer with unknown connectivity status
	#  @param peer Tuple of IP address and port number
	def add_new(self, peer):
		new_peer = CachedPeer(delay=0, ip_address=peer[0], port=peer[1], id=b'', bitfield=b'', pieces=0)
		self.in_progress.put(new_peer)
	
	## Puts a peer back in the in progress list
	#  @param peer CachedPeer named tuple 
	#  @param delay Delay in seconds before should be evaluated again
	def add_in_progress(self, peer):
		self.in_progress.put(peer)

## Returns the numbers of bits set in an integer
#  @param byte An arbitrary integer between 0 and 255
#  @return Count of 1 bits in the binary representation of byte
def count_bits(byte):
	assert 0 <= byte <= 255, 'Only values between 0 and 255 allowed'
	mask = 1
	count = 0
	for i in range(0,8):
		masked_byte = byte & mask
		if masked_byte > 0:
			count += 1
		mask *= 2
	return count

