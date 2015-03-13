# Built-in modules
import logging
import threading
import traceback
import queue
import time
import socketserver
import socket
import os
import base64

# Project modules
import tracker_request
import peer_wire_protocol
import database_storage
import torrent_file

## Requests peers from tracker and initiates peer connections
class SwarmAnalyzer:
	## Initializes analyzer for peers of one torrent
	#  @param delay Minimal timedelta between contacting the same peer in minutes
	#  @param timeout Timeout for network operations in seconds
	#  @param output Path for database output without file extension
	#  @exception AnalyzerError
	def __init__(self, delay, timeout, output):
		# Smart queue for peer management
		self.peers = PeerQueue()
		self.database_queue = queue.Queue()

		# Generate peer id
		self.own_peer_id = tracker_request.generate_peer_id()

		# Network parameters
		self.delay = delay * 60
		logging.info('Time delay for revisiting unfinished peers is ' + str(delay) + ' minutes')
		self.timeout = timeout
		logging.info('Timeout for network operations is ' + str(timeout) + ' seconds')

		# Statistical counters
		self.first_evaluation_error = SharedCounter()
		self.late_evaluation_error = SharedCounter()
		self.critical_evaluation_error = SharedCounter()
		self.critical_database_error = SharedCounter()
		self.database_peer_update = SharedCounter()
		self.database_new_peer = SharedCounter()
		self.total_received_peers = 0
		self.total_duplicate = 0
		self.active_success = SharedCounter()
		self.passive_success = SharedCounter()
		self.passive_error = SharedCounter()
		
		# Analysis parts, activated via starter methods
		self.shutdown_request = threading.Event()
		self.active_evaluation = False
		self.tracker_requests = False
		self.passive_evaluation = False
		self.database_archive = False
		
		# Create database
		try:
			self.database = database_storage.Database(output)
		except database_storage.DatabaseError as err:
			raise AnalyzerError('Could not create database: ' + str(err))

	## Resouces are allocated in starter methods
	def __enter__(self):
		return self
	
	## Reads all torrent files from input directory
	def import_torrents(self):
		# Create torrent dictionary
		self.torrents = dict()

		# Import all files
		database_session = self.database.get_session()
		try:
			walk = os.walk('input/')
		except OSError as err:
			raise AnalyzerError('Could not read from input directory: ' + str(err))
		for dirname, dirnames, filenames in walk:
			for filename in filenames:
				# Sort out non torrents
				if not filename.endswith('.torrent'):
					continue
					
				# Read torrent file
				path = os.path.join(dirname, filename)
				try:
					parser = torrent_file.TorrentParser(path)
					announce_url = parser.get_announce_url()
					info_hash = parser.get_info_hash()
					pieces_number = parser.get_pieces_number()
					piece_size = parser.get_piece_size()
				except torrent_file.FileError as err:
					logging.error('Could not import torrent ' + filename + ': ' + str(err))
					continue

				# Store in database and dictionary
				torrent = torrent_file.Torrent(announce_url, info_hash, pieces_number, piece_size)
				key = self.database.store_torrent(torrent, path, database_session)
				self.torrents[key] = torrent
		
		# Close database sesssion						
		database_session.close()
		if len(self.torrents) > 0:
			logging.info('Imported ' + str(len(self.torrents)) + ' torrent files')
		else:
			raise AnalyzerError('No valid torrent files found')
	
	## Evaluates all peers in the queue
	#  @param jobs Number of parallel thread to use
	def start_active_evaluation(self, jobs):
		# Thread termination barrier
		self.active_shutdown_done = threading.Barrier(jobs + 1)
		logging.info('Connecting to peers in ' + str(jobs) + ' threads')

		# Create thread pool
		for i in range(jobs):
			# Create a thread with worker callable
			thread = threading.Thread(target=self._evaluator)
			# Thread dies when main thread exits
			thread.daemon = True
			# Start thread
			thread.start()
		
		# Remember activation to enable shutdown
		self.active_evaluation = True

	## Evaluate peers from main queue
	#  @note This is a worker method to be started as a thread
	def _evaluator(self):
		while not self.shutdown_request.is_set():
			# Get new peer with timeout to react to shutdown request
			try:
				peer = self.peers.get(timeout=10)
			except queue.Empty:
				continue

			# Delay evaluation
			delay = peer.revisit - time.perf_counter()
			better_peer_reaction = 60
			if delay > 0:
				logging.info('Delaying peer evaluation for ' + str(better_peer_reaction) + ' seconds, target is ' + str(delay/60) + ' minutes ...')
				self.shutdown_request.wait(better_peer_reaction)
				self.peers.put(peer)
				continue

			# Establish connection
			if peer.key is None:
				logging.info('################ Evaluating a new peer ################')
			else:
				logging.info('################ Revisiting peer with database id ' + str(peer.key) + ' ################')
			logging.info('Connecting to peer ...')
			try:
				sock = socket.create_connection((peer.ip_address, peer.port), self.timeout)
			except OSError as err:
				if peer.key is None:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Connection establishment failed: ' + str(err))
				continue
			logging.info('Connection established')

			# Contact peer and update attributes
			torrent = self.torrents[peer.torrent]
			try:
				peer = peer_wire_protocol.evaluate_peer(peer, sock,
						torrent.info_hash, self.own_peer_id, torrent.pieces_count, self.delay)

			# Handle bad peers
			except peer_wire_protocol.PeerError as err:
				if peer.key is None:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Peer evaluation failed: ' + str(err))
				continue

			# Catch all exceptions to enable ongoing analysis, should never happen
			except Exception as err:
				self.critical_evaluation_error.increment()
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('Unexpected error during peer evaluation: ' + str(err) + '\n' + ''.join(tb))
				continue

			# Close connection
			try:
				sock.close()
			except OSError as err:
				logging.warning('Closing of connectioin failed: ' + str(err))
			else:
				logging.info('Connection closed')
			
			# Put in archiver queue
			self.active_success.increment()
			self.database_queue.put(peer)
		
		# Propagate shutdown finish
		self.active_shutdown_done.wait()

	## Continuously asks the tracker server for new peers	
	#  @param interval Timer interval between tracker requests are issued in minutes
	def start_tracker_requests(self, interval):
		# Thread termination indicator
		self.tracker_shutdown_done = threading.Barrier(len(self.torrents) + 1)
		logging.info('Desired interval between asking the tracker for new peers is ' + str(interval) + ' minutes')
		
		# Create tracker request threads
		interval_seconds = interval * 60
		for torrent in self.torrents:
			thread = threading.Thread(target=self._tracker_requestor, args=(torrent, interval_seconds))
			thread.daemon = True
			thread.start()

		# Remember activation to enable shutdown
		self.tracker_requests = True

	## Issues GET request to tracker, puts received peers in queue, wait an interval considering tracker minimum
	#  @param torrent_key Torrent key specifying the target torrent and tracker
	#  @param desired_interval Requested interval in seconds
	#  @note This is a worker method to be started as a thread
	def _tracker_requestor(self, torrent_key, desired_interval):
		tracker = tracker_request.TrackerCommunicator(self.own_peer_id, self.torrents[torrent_key].announce_url)

		while not self.shutdown_request.is_set():
			# Ask tracker
			logging.info('Contacting tracker for torrent with id ' + str(torrent_key))
			try:
				tracker.issue_request(self.torrents[torrent_key].info_hash)
				peer_ips = tracker.get_peers()
			except tracker_request.TrackerError as err:
				logging.warning('Could not receive peers from tracker: ' + str(err))
				interval = desired_interval
			else:
				# Put peers in queue
				#import random # debug
				#peer_ips = random.sample(peer_ips, 8) # debug
				self.peers.duplicate.reset()
				for peer_ip in peer_ips:
					new_peer = peer_wire_protocol.Peer(revisit=0, ip_address=peer_ip[0], port=peer_ip[1],
							id=None, bitfield=None, pieces=None, active=True, torrent=torrent_key, key=None)
					self.peers.put(new_peer)
				duplicate_counter = self.peers.duplicate.get() # TODO inaccurate due to passive evaluation?
				self.total_duplicate += duplicate_counter
				self.total_received_peers += len(peer_ips)

				# Calculate number of new peers
				try:
					percentage = int(duplicate_counter * 100 / len(peer_ips))
				except ZeroDivisionError:
					percentage = 0
				logging.info(str(len(peer_ips)) + ' peers received, ' + str(duplicate_counter) + ' duplicates, equals ' + str(percentage) + '%')
			
				# Receive interval recommendation from tracker for logging purposes # debug
				try:
					tracker.get_interval()
				except tracker_request.TrackerError:
					pass

				# Check requested_interval against min interval
				# TODO test
				min_interval = tracker.get_min_interval()
				if min_interval is None:
					interval = desired_interval
				else:
					interval = max(min_interval, desired_interval)

			# Wait accordingly
			logging.info('Waiting ' + str(interval/60) + ' minutes until next tracker request ...')
			self.shutdown_request.wait(interval)
		
		# Propagate thread termination
		self.tracker_shutdown_done.wait()

	## Starts a multithreaded TCP server to analyze incoming peers
	#  @param port Extern listen port number
	#  @exception AnalyzerError
	# TODO test with real data
	def start_passive_evaluation(self, port):
		# Create the server, binding to outside address on custom port
		if not 0 <= port <= 65535:
			raise AnalyzerError('Invalid port number: ' + str(port))
		address = (socket.gethostname(), port)
		logging.info('Starting passive evaluation server on host ' + address[0] + ', port ' + str(address[1]))
		try:
			self.server = PeerEvaluationServer(address, PeerHandler, 
					info_hash=self.torrent.info_hash, 
					own_peer_id=self.own_peer_id,
					pieces_number=self.torrent.pieces_count,
					database_queue=self.database_queue,
					delay=self.delay,
					sock_timeout=self.timeout,
					success=self.passive_success,
					error=self.passive_error)
		except PermissionError as err:
			raise AnalyzerError('Could not start server on port ' + str(port) + ': ' + str(err))

		# Activate the server in it's own thread
		server_thread = threading.Thread(target=self.server.serve_forever)
		server_thread.daemon = True
		server_thread.start()
		
		# Remember activation to enable shutdown
		self.passive_evaluation = True
		logging.info('Listening on port ' + str(port) + ' for incomming peer connections')

	## Comsumes peers from database queue and put back in main queue
	def start_database_archiver(self):
		# Get database session
		self.database_session = self.database.get_session()

		# Start database thread
		thread = threading.Thread(target=self._database_archivator, args=(self.database_session,))
		thread.daemon = True
		thread.start()

		# Remember activation to enable shutdown
		self.database_archive = True
	
	## Consumes peers and stores them in the database
	#  @param database_session Database session instance
	#  @note This is a worker method to be started as a thread
	def _database_archivator(self, database_session):
		# Log thread id
		logging.info('The identifier for this database archiver thread is ' + str(threading.get_ident()))

		while True:
			# Get new peer to store
			peer = self.database_queue.get()
			first_evaluation = peer.key is None

			# Store evaluated peer and fill peer.key
			try:
				peer = self.database.store_peer(peer, 0, database_session)

			# Catch all exceptions to enable ongoing thread, should never happen
			except Exception as err:
				database_session.rollback()
				self.critical_database_error.increment()
				self.database_queue.task_done()
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('Unexpected error during database update: ' + str(err) + '\n' + ''.join(tb))
				continue

			# Update statistical counters
			if first_evaluation:
				self.database_new_peer.increment()
			else:
				self.database_peer_update.increment()

			# Write back in progress peers, discard finished ones
			if peer.pieces < self.torrents[peer.torrent].pieces_count:
				self.peers.put(peer)
		
			# Allow waiting for all peers to be stored at shutdown
			self.database_queue.task_done()

	## Print evaluation statistics
	def log_statistics(self):
		# Peer queue, inaccurate due to consumer threads
		logging.info('Currently are about ' + str(self.peers.qsize()) + ' peers in queue left')

		# Received peers
		try:
			percentage = int(self.total_duplicate * 100 / self.total_received_peers)
		except ZeroDivisionError:
			percentage = 0
		logging.info('In total ' + str(self.total_received_peers) + ' peers received, ' + str(self.total_duplicate) + ' duplicates, equals ' + str(percentage) + '%')

		# Evaluation errors
		logging.info('Active evaluations: ' + str(self.active_success.get()) + ' successful, ' +
				str(self.first_evaluation_error.get()) + ' failed on first contact, ' +
				str(self.late_evaluation_error.get()) + ' failed on later contact')
		logging.info('Passive evaluations: ' + str(self.passive_success.get()) + ' successful, ' + 
				str(self.passive_error.get()) + ' failed')

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

	## Shutdown all worker threads if started
	def __exit__(self, exception_type, exception_value, traceback):
		# Propagate shutdown request
		self.shutdown_request.set()
		
		if self.active_evaluation:
			logging.info('Waiting for current evaluations to finish ...')
			self.active_shutdown_done.wait()

		if self.tracker_requests:
			logging.info('Waiting for current tracker requests to finish ...')
			self.tracker_shutdown_done.wait()

		if self.passive_evaluation:
			logging.info('Shutdown peer evaluation server ...')
			self.server.shutdown()

		if self.database_archive:
			logging.info('Waiting for peers to be written to database ...')
			self.database_queue.join()
			self.database_session.close()
			logging.info('Database session closed')
		
		self.database.close()

## Smart queue which excludes peers that are already in queue or processed earlier while keeping revisits
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
		# Create copy peer data for equality check
		peer_equalality = (peer.ip_address, peer.port, peer.torrent)

		# Check if this is a revisit or if it is a new peer
		if peer.key is not None or peer_equalality not in self.all_peers:
			# Call parent method
			queue.PriorityQueue._put(self, peer)

			# Remember equality information, set discards revisit duplicates
			self.all_peers.add(peer_equalality)
		else:
			self.duplicate.increment()

## Subclass of library class to change parameters, add attributes and add multithreading mix-in class
class PeerEvaluationServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
	# Parent class parameter
	allow_reuse_address = True

	## Extended init
	#  @param server_address Pass through to parent
	#  @param RequestHandlerClass Pass through to parent
	#  @param **server_args Server attributes available in handle method
	def __init__(self, server_address, RequestHandlerClass, **server_args):
		# Call base constructor
		socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass)
		
		# Add attributes that are later available in handler method
		self.__dict__.update(server_args)

## Connection handler, an instance is created for each request
class PeerHandler(socketserver.BaseRequestHandler):
	## Evaluate one peer
	#  @note Overrides parent method
	def handle(self):
		# self.client_address is tuple of incoming client address and port
		# self.request is incoming connection socket
		# self.server is own server instance
		try:
			self.request.settimeout(self.server.sock_timeout)
		except OSError as err:
			logging.warning('Could not set timeout on incoming connection')
			return
		logging.info('################ Evaluating an incoming peer ################')
		old_peer = peer_wire_protocol.Peer(None, self.client_address[0], self.client_address[1], None, None, None, False, None)
		try:
			peer = peer_wire_protocol.evaluate_peer(old_peer, self.request,
					self.server.info_hash, self.server.own_peer_id, self.server.pieces_number, self.server.delay)
		except peer_wire_protocol.PeerError as err:
			logging.warning('Could not evaluate incoming peer: ' + str(err))
			self.server.error.increment()
		else:
			key_peer = self.server.database_queue.put(peer)
			self.server.success.increment()
	
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

## Indicates an error for this module
class AnalyzerError(Exception):
	pass

