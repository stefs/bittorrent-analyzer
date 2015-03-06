# Built-in modules
import logging
import threading
import traceback
import queue
import time
import socketserver
import socket

# Project modules
import tracker_request
import peer_wire_protocol

## Requests peers from tracker and initiates peer connections
class SwarmAnalyzer:
	## Initializes analyzer for peers of one torrent
	#  @param database PeerDatabase object
	#  @param torrent Torrent named tuple
	#  @param delay Minimal timedelta between contacting the same peer in minutes
	#  @param timeout Timeout for network operations in seconds
	def __init__(self, database, torrent, delay, timeout):
		# Smart queue for peer management
		self.peers = PeerQueue()
		self.database_queue = queue.Queue()

		# PeerDatabase object
		self.database = database

		# Torrent and tracker data
		self.torrent = torrent
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
		self.total_received_peers = 0
		self.total_duplicate = 0
		
		# Analysis parts, activated via starter methods
		self.active_evaluation = False
		self.passive_evaluation = False
	
	## Resouces are allocated in starter methods
	def __enter__(self):
		return self
	
	## Evaluates all peers in the queue
	#  @param jobs Number of parallel thread to use
	#  @param interval Timer interval between tracker requests are issued in seconds
	def start_active_evaluation(self, jobs, interval):
		# Create thread pool
		for i in range(jobs):
			# Get thread safe session object
			database_session = self.database.get_session()
			# Create a thread with worker callable and pass it it's own session
			thread = threading.Thread(target=self._evaluator, args=(database_session,))
			# Thread dies when main thread exits, requires Queue.join()
			thread.daemon = True
			# Start thread
			thread.start()
		
		# Create tracker request thread
		thread = threading.Thread(target=self._tracker_requestor, args=(interval,))
		thread.daemon = True
		thread.start()

		# Remember activation to enable shutdown
		self.active_evaluation = True

	## Evaluate peers from main queue
	#  @param SQLAlchemy database scoped session object
	#  @note This is a worker method to be started as a thread, it does not return
	def _evaluator(self, database_session):
		# Log thread id
		logging.info('The identifier for this active evaluator thread is ' + str(threading.get_ident()))

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

			# Establish connection
			if first_evaluation:
				logging.info('################ Evaluating a new peer ################')
			else:
				logging.info('################ Revisiting peer with database id ' + str(peer.key) + ' ################')
			logging.info('Connecting to peer ...')
			try:
				sock = socket.create_connection((peer.ip_address, peer.port), self.timeout)
			except OSError as err:
				if first_evaluation:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Connection establishment failed: ' + str(err))
				continue
			logging.info('Connection established')

			# Contact peer and update attributes
			try:
				peer = peer_wire_protocol.evaluate_peer(peer, sock,
						self.torrent.info_hash, self.own_peer_id, self.torrent.pieces_count, self.delay)

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

			# Close connection
			try:
				sock.close()
			except OSError as err:
				logging.warning('Closing of connectioin failed: ' + str(err))
			else:
				logging.info('Connection closed')

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
	
	## Issues GET request to tracker, puts received peers in queue, wait an interval considering tracker minimum
	#  @param desired_interval Requested interval in minutes
	#  @exception AnalyzerError
	def _tracker_requestor(self, desired_interval):
		# Log thread id
		logging.info('The identifier for this tracker requestor thread is ' + str(threading.get_ident()))

		# Ends when daemon thread dies
		while True:
			# Ask tracker
			try:
				self.tracker.issue_request(self.torrent.info_hash)
				peer_ips = self.tracker.get_peers()
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
							id=None, bitfield=None, pieces=None, active=True, key=None)
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
			
				# Receive interval recommendation from tracker for logging purposes
				try:
					self.tracker.get_interval()
				except tracker_request.TrackerError:
					pass

				# Check requested_interval against min interval
				min_interval = self.tracker.get_min_interval()
				if min_interval is None:
					interval = desired_interval * 60
				else:
					interval = max(min_interval, desired_interval * 60)

			# Wait accordingly
			logging.info('Waiting ' + str(interval/60) + ' minutes until next tracker request ...')
			time.sleep(interval)

	## Starts TCP server analyzer for incoming peers of one torrent
	#  @param port Extern listen port number
	# TODO test with real data
	def start_passive_evaluation(self, port):
		# Create the server, binding to outside address on custom port
		if not 0 <= port <= 65535:
			raise AnalyzerError('Invalid port number: ' + str(port))
		address = (socket.gethostname(), port)
		logging.info('Starting passive evaluation server on host ' + address[0] + ', port ' + str(address[1]))
		# TODO use self.timeout
		self.server = PeerEvaluationServer(address, PeerHandler,
				self.torrent.info_hash, self.own_peer_id, self.torrent.pieces_count, self.database_queue, self.delay)

		# Activate the server in it's own thread
		server_thread = threading.Thread(target=self.server.serve_forever)
		server_thread.daemon = True
		server_thread.start()
		
		# Remember activation to enable shutdown
		self.passive_evaluation = True
	
	## Thread shutdown and logs
	def __exit__(self, exception_type, exception_value, traceback):
		# Active evaluation shutdown
		if self.active_evaluation:
			# TODO evaluator threads shutdown
			# TODO tracker thread shutdown
			pass

		# Passive evaluation shutdown
		if self.passive_evaluation:
			logging.info('Shutdown passive peer evaluation server')
			self.server.shutdown()

		# TODO database thread shutdown

		# Peer queue, inaccurate due to consumer threads
		logging.info('Currently are about ' + str(self.peers.qsize()) + ' peers in queue')

		# Received peers
		try:
			percentage = int(self.total_duplicate * 100 / self.total_received_peers)
		except ZeroDivisionError:
			percentage = 0
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

## Subclass of library class to change parameters, add attributes and add multithreading mix-in class
class PeerEvaluationServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
	# Parent class parameter
	allow_reuse_address = True

	## Extended init
	#  @param server_address Pass through to parent
	#  @param RequestHandlerClass Pass through to parent
	#  @param info_hash Torrent info hash
	#  @param own_peer_id Own peer id
	#  @param pieces_number Number of pieces of the torrent
	#  @param database_queue queue.Queue instance for database access
	#  @param delay Delay between peer visits
	def __init__(self, server_address, RequestHandlerClass, info_hash, own_peer_id, pieces_number, database_queue, delay):
		# Call base constructor
		socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass)
		
		# Add attributes that are later available in handler method
		self.info_hash = info_hash
		self.own_peer_id = own_peer_id
		self.pieces_number = pieces_number
		self.database_queue = database_queue
		self.delay = delay

## Connection handler, an instance is created for each request
class PeerHandler(socketserver.BaseRequestHandler):
	## Evaluate one peer
	#  @note Overrides parent method
	def handle(self):
		# self.client_address is tuple of incoming client address and port
		# self.request is incoming connection socket
		# self.server is own server instance
		logging.info('################ Evaluating an incoming peer ################')
		old_peer = peer_wire_protocol.Peer(None, self.client_address[0], self.client_address[1], None, None, None, False, None)
		try:
			peer = peer_wire_protocol.evaluate_peer(old_peer, self.request,
					self.server.info_hash, self.server.own_peer_id, self.server.pieces_number, self.server.delay)
		except peer_wire_protocol.PeerError as err:
			logging.warning('Could not evaluate incoming peer: ' + str(err))
		else:
			key_peer = self.server.database_queue.put(peer)
	
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

