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
	#  @param delay Minimal timedelta between contacting the same peer
	#  @param timeout Timeout for network operations in seconds
	#  @exception AnalyzerError
	def __init__(self, database, torrent_path, delay, timeout):
		# Queues for peer management
		self.peers = queue.PriorityQueue()
		self.finished_peers = queue.Queue()
		self.error_peers = queue.Queue()
		
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
		self.delay = delay
		self.timeout = timeout
		
		# Statistical counters
		self.first_evaluation_error = SharedCounter()
		self.late_evaluation_error = SharedCounter()
		self.critical_evaluation_error = SharedCounter()
		self.critical_database_error = SharedCounter()
		self.database_peer_update = SharedCounter()
		self.database_new_peer = SharedCounter()
	
	## Issues GET request to tracker and puts received peers in queue
	#  @exception AnalyzerError
	def get_new_peers(self):
		try:
			peer_ips = self.tracker.get_peers(self.torrent.info_hash)
		except tracker_request.TrackerError as err:
			raise AnalyzerError('Could not get new peers: ' + str(err))
		import random # debug
		peer_ips = random.sample(peer_ips, 8) # debug
		for peer_ip in peer_ips:
			new_peer = peer_wire_protocol.Peer(revisit=0, ip_address=peer_ip[0], port=peer_ip[1], id=None, bitfield=None, pieces=None, key=None)
			self.peers.put(new_peer)
	
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
			if first_evaluation:
				logging.info('################ Evaluating a new peer ################')
			else:
				logging.info('################ Revisiting peer with database id ' + str(peer.key) + ' ################')
	
			# Delay evaluation
			delay = peer.revisit - time.perf_counter()
			if delay > 0:
				logging.info('Delaying peer evaluation for ' + str(delay) + ' seconds ...')
				time.sleep(delay)

			# Contact peer and update attributes
			try:
				peer = peer_wire_protocol.evaluate_peer(
						peer, self.torrent.info_hash, self.own_peer_id, self.torrent.pieces_count, self.delay, self.timeout)
			
			# Handle bad peers
			except peer_wire_protocol.PeerError as err:
				self.error_peers.put(peer)
				if first_evaluation:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Peer evaluation failed: ' + str(err))
				self.peers.task_done()
				continue

			# Catch all exceptions to enable ongoing analysis
			except Exception as err:
				self.error_peers.put(peer)
				self.critical_evaluation_error.increment()
				logging.critical('Unexpected error during peer evaluation: ' + str(err))
				traceback.print_tb(err.__traceback__)
				self.peers.task_done()
				continue
				
			# Store evaluated peer and fill peer.key
			try:
				peer = self.database.store(peer, 0, database_session) # TODO give torrent id

			# Catch all exceptions to enable ongoing analysis
			except Exception as err:
				database_session.rollback()
				self.error_peers.put(peer)
				self.critical_database_error.increment()
				logging.critical('Unexpected error during database update: ' + str(err))
				traceback.print_tb(err.__traceback__)
				self.peers.task_done()
				continue
			
			# Update statistical counters
			if first_evaluation:
				self.database_new_peer.increment()
			else:
				self.database_peer_update.increment()

			# Write back in progress peers, discard finished ones
			if peer.pieces < self.torrent.pieces_count:
				self.peers.put(peer)
			else:
				self.finished_peers.put(peer)
			
			# Queue.task_done() to allow Queue.join()
			self.peers.task_done()

	## Evaluates all peers in the queue
	#  @param jobs Number of parallel thread to use
	def run(self, jobs):
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

		# Wait for all peers to be evaluated
		self.peers.join()

	## Print log 
	def log_statistics(self):
		# Peer queues
		logging.info('Peer queues: ' + str(self.peers.qsize()) + ' remaining, ' +
				str(self.finished_peers.qsize()) + ' finished, ' +
				str(self.error_peers.qsize()) + ' failed to evaluate')

		# Evaluation errors
		logging.info('Failed evaluations: ' + str(self.first_evaluation_error.get()) + ' on first contact, ' +
				str(self.late_evaluation_error.get()) + ' on later contact')

		# Database access
		logging.info('Peer database access: ' + str(self.database_peer_update.get()) + ' stored, ' +
				str(self.database_new_peer.get()) + ' updated')

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

