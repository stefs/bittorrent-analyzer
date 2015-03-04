# Built-in modules
import logging
import threading
import traceback
import queue
import time

# Project modules
import torrent_file
import tracker_request
import peer_wire_protocol
import peer_storage

class SwarmAnalyzer:
	## Initializes analyser for peers of one torrent
	#  @param database PeerDatabase object
	#  @param torrent_path File system path to a torrent file
	#  @param delay Minimal timedelta between contacting the same peer in minutes
	#  @param timeout Timeout for network operations in seconds
	#  @exception AnalyzerError
	def __init__(self, database, torrent_path, delay, timeout):
		# Smart queue for peer management
		self.peers = PeerQueue()

		# PeerDatabase object
		self.database = database

		# Torrent and tracker data
		try:
			self.torrent = torrent_file.import_torrent(torrent_path)
		except torrent_file.FileError as err:
			raise AnalyzerError('Could not import torrent file: ' + str(err))
		self.own_peer_id = tracker_request.generate_peer_id()
		self.tracker = tracker_request.TrackerCommunicator(self.own_peer_id, self.torrent.announce_url)

		# Network parameters
		self.delay = delay * 60
		self.timeout = timeout

		# Statistical counters
		self.first_evaluation_error = SharedCounter()
		self.late_evaluation_error = SharedCounter()
		self.critical_evaluation_error = SharedCounter()
		self.critical_database_error = SharedCounter()
		self.database_peer_update = SharedCounter()
		self.database_new_peer = SharedCounter()
		self.duplicate = self.peers.duplicate
		self.total_received_peers = 0
		self.total_duplicate = 0

	## Issues GET request to tracker and puts received peers in queue
	#  @exception AnalyzerError
	def get_new_peers(self):
		# Ask tracker
		try:
			self.tracker.issue_request(self.torrent.info_hash)
			peer_ips = self.tracker.get_peers()
		except tracker_request.TrackerError as err:
			raise AnalyzerError('Could not get new peers: ' + str(err))

		# Put peers in queue if not already contained
		#import random # debug
		#peer_ips = random.sample(peer_ips, 8) # debug
		self.duplicate.reset()
		for peer_ip in peer_ips:
			new_peer = peer_wire_protocol.Peer(revisit=0, ip_address=peer_ip[0], port=peer_ip[1], id=None, bitfield=None, pieces=None, key=None)
			self.peers.put(new_peer)
		duplicate_counter = self.duplicate.get()
		self.total_duplicate += duplicate_counter
		self.total_received_peers += len(peer_ips)

		# Calculate number of new peers, inaccurate due to consumer threads
		percentage = int(duplicate_counter * 100 / len(peer_ips))
		logging.info(str(len(peer_ips)) + ' peers received, ' + str(duplicate_counter) + ' duplicates, equals ' + str(percentage) + '%')

	## Get the right interval considering tracker's response
	#  @param requested_interval Requested interval in minutes or None for tracker recommendation
	#  @return Tracker recommendation or requested_interval considering tracker min interval
	#  @exception AnalyzerError
	def get_interval(self, requested_interval=None):
		# Use interval recommendation from tracker
		if requested_interval is None:
			try:
				interval = self.tracker.get_interval()
			except tracker_request.TrackerError as err:
				raise AnalyzerError('No request interval specified and tracker did not send a recommended interval: ' + str(err))

		# Use min interval as minimum
		else:
			min_interval = self.tracker.get_min_interval()
			if min_interval is None:
				interval = requested_interval * 60
			else:
				interval = max(min_interval, requested_interval * 60)

		# Return result
		logging.info('Using a request interval of ' + str(interval/60) + ' minutes')
		return interval

	## Evaluate peers from main queue
	#  @param SQLAlchemy database scoped session object
	#  @note This is a worker method to be started as a thread, it does not return
	def evaluator(self, database_session):
		# Log thread id
		logging.info('The identifier for this worker thread is ' + str(threading.get_ident()))

		# Ends when daemon thread dies
		while True:
			# Get new peer
			peer = self.peers.get()
			first_evaluation = peer.key is None

			# Delay evaluation and write back if delay too long
			delay = peer.revisit - time.perf_counter()
			if delay > 0:
				logging.info('Delaying peer evaluation for ' + str(delay) + ' seconds ...')
				time.sleep(delay)

			# Contact peer and update attributes
			if first_evaluation:
				logging.info('################ Evaluating a new peer ################')
			else:
				logging.info('################ Revisiting peer with database id ' + str(peer.key) + ' ################')
			try:
				peer = peer_wire_protocol.evaluate_peer(
						peer, self.torrent.info_hash, self.own_peer_id, self.torrent.pieces_count, self.delay, self.timeout)

			# Handle bad peers
			except peer_wire_protocol.PeerError as err:
				if first_evaluation:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Peer evaluation failed: ' + str(err))
				continue

			# Catch all exceptions to enable ongoing analysis, should never happen
			except Exception as err:
				self.critical_evaluation_error.increment()
				logging.critical('Unexpected error during peer evaluation: ' + str(err))
				traceback.print_tb(err.__traceback__)
				continue

			# Store evaluated peer and fill peer.key
			try:
				peer = self.database.store(peer, 0, database_session) # TODO give torrent id

			# Catch all exceptions to enable ongoing analysis, should never happen
			except Exception as err:
				database_session.rollback()
				self.critical_database_error.increment()
				logging.critical('Unexpected error during database update: ' + str(err))
				traceback.print_tb(err.__traceback__)
				continue

			# Update statistical counters
			if first_evaluation:
				self.database_new_peer.increment()
			else:
				self.database_peer_update.increment()

			# Write back in progress peers, discard finished ones
			if peer.pieces < self.torrent.pieces_count:
				self.peers.put(peer)

	## Evaluates all peers in the queue
	#  @param jobs Number of parallel thread to use
	def start_threads(self, jobs):
		# Create thread pool
		for i in range(jobs):
			# Get thread safe session object
			database_session = self.database.get_session()
			# Create a thread with worker callable and pass it it's own session
			thread = threading.Thread(target=self.evaluator, args=(database_session,))
			# Thread dies when main thread exits, requires Queue.join()
			thread.daemon = True
			# Start thread
			thread.start()

	## Print log
	def log_statistics(self):
		# Peer queue, inaccurate due to consumer threads
		logging.info('Currently are about ' + str(self.peers.qsize()) + ' peers in queue')

		# Received peers
		percentage = int(self.total_duplicate * 100 / self.total_received_peers)
		logging.info('In total ' + str(self.total_received_peers) + ' peers received, ' + str(self.total_duplicate) + ' duplicates, equals ' + str(percentage) + '%')

		# Evaluation errors
		logging.info('Failed evaluations: ' + str(self.first_evaluation_error.get()) + ' on first contact, ' +
				str(self.late_evaluation_error.get()) + ' on later contact')

		# Database access
		logging.info('Peer database access: ' + str(self.database_new_peer.get()) + ' stored, ' +
				str(self.database_peer_update.get()) + ' updated')

		# Critical errors
		critical_evaluation_error_counter = self.critical_evaluation_error.get()
		if critical_evaluation_error_counter > 0:
			logging.critical('Encountered ' + str(critical_evaluation_error_counter) + ' critical evaluation errors')
		critical_database_error_counter = self.critical_database_error.get()
		if critical_database_error_counter > 0:
			logging.critical('Encountered ' + str(critical_database_error_counter) + ' critical database errors')

## Indicates an error for this module
class AnalyzerError(Exception):
	pass

## Simple thread safe counter
class SharedCounter:
	## Set value and create a lock
	def __init__(self):
		self.value = 0
		self.lock = threading.Lock()

	## Increase value by one
	def increment(self):
		with self.lock:
			self.value += 1

	## Read value
	#  @return The value
	def get(self):
		with self.lock:
			return self.value

	## Resets the value to zero
	def reset(self):
		with self.lock:
			self.value = 0

## Smart queue which excludes items that are already in queue or processed earlier while keeping revisits
#  according to http://stackoverflow.com/a/1581937 and https://hg.python.org/cpython/file/3.4/Lib/queue.py#l197
class PeerQueue(queue.PriorityQueue):
	## Add a set to remember processed peers
	#  @param maxsize Passed in original method, passing through
	#  @note Overrides intern method
	def _init(self, maxsize):
		# Call parent method
		queue.PriorityQueue._init(self, maxsize)

		# Add new attribute
		self.all_peers = set()

		# Add a duplicate counter
		self.duplicate = SharedCounter()

	## Put new peer in queue if not already processed, does not exclude peers with database id
	#  @param peer Peer named tuple
	#  @return True if this is a new peer, False if it has already been put
	#  @note Overrides intern method
	#  @warning Disables join option according to http://stackoverflow.com/a/24183479 and https://hg.python.org/cpython/file/3.4/Lib/queue.py#l147
	def _put(self, peer):
		# Create copy of ip_address and port for equality check
		peer_ip = (peer.ip_address, peer.port)

		# Check if this is a revisit or if it is a new peer
		if peer.key is not None or peer_ip not in self.all_peers:
			# Call parent method
			queue.PriorityQueue._put(self, peer)

			# Remember equality information, set discards revisit duplicates
			self.all_peers.add(peer_ip)
		else:
			self.duplicate.increment()

