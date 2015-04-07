# Built-in modules
import logging
import threading
import traceback
import queue
import time
import socketserver
import socket
import os
import collections
import telnetlib
import base64

# Project modules
import tracker_request
import peer_wire_protocol
import database_storage
import torrent_file
import pymdht_connector

## Named tuples representing cached peer and a torrent file
Peer = collections.namedtuple('Peer', 'revisit ip_address port id bitfield pieces source torrent key')
Torrent = collections.namedtuple('Torrent', 'announce_url info_hash info_hash_hex pieces_count piece_size')

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
		self.visited_peers = queue.Queue()

		# Generate peer id
		self.own_peer_id = tracker_request.generate_peer_id()

		# Network parameters
		self.delay = delay * 60
		logging.info('Time delay for revisiting unfinished peers is {} minutes'.format(delay))
		self.timeout = timeout
		logging.info('Timeout for network operations is {} seconds'.format(timeout))
		self.listen_port = None
		self.dht_port = None

		# Statistical counters
		self.first_evaluation_error = SharedCounter()
		self.late_evaluation_error = SharedCounter()
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
		self.peer_handler = False
		self.dht_started = False

		# Create database
		try:
			self.database = database_storage.Database(output)
		except database_storage.DatabaseError as err:
			raise AnalyzerError('Could not create database: {}'.format(err))

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
			raise AnalyzerError('Could not read from input directory: {}'.format(err))
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
					logging.error('Could not import torrent {}: {}'.format(filename, err))
					continue

				# Store in database and dictionary
				hex_hash = base64.b16encode(info_hash).decode()
				torrent = Torrent(announce_url, info_hash, hex_hash, pieces_number, piece_size)
				key = self.database.store_torrent(torrent, path, database_session)
				self.torrents[key] = torrent

		# Close database sesssion
		database_session.close()
		if len(self.torrents) > 0:
			logging.info('Imported {} torrent files'.format(len(self.torrents)))
		else:
			raise AnalyzerError('No valid torrent files found')

	## Evaluates all peers in the queue
	#  @param jobs Number of parallel thread to use
	def start_active_evaluation(self, jobs):
		# Thread termination barrier
		self.active_shutdown_done = threading.Barrier(jobs + 1)
		logging.info('Connecting to peers in {} threads'.format(jobs))

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
				logging.info('Delaying peer evaluation for {} seconds, target is {} minutes ...'.format(better_peer_reaction, delay/60))
				self.shutdown_request.wait(better_peer_reaction)
				self.peers.put(peer)
				continue

			# Establish connection
			if peer.key is None:
				logging.info('################ Connecting to new peer ... ################')
			else:
				logging.info('################ Reconnecting to peer {} ... ################'.format(peer.key))
			try:
				sock = socket.create_connection((peer.ip_address, peer.port), self.timeout)
			except OSError as err:
				if peer.key is None:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Connection establishment failed: {}'.format(err))
				continue
			logging.info('Connection established')

			# Contact peer
			try:
				result = peer_wire_protocol.evaluate_peer(sock, self.own_peer_id, self.dht_port, self.torrents[peer.torrent].info_hash)

			# Handle bad peers
			except peer_wire_protocol.PeerError as err:
				if peer.key is None:
					self.first_evaluation_error.increment()
				else:
					self.late_evaluation_error.increment()
				logging.warning('Peer evaluation failed: {}'.format(err))
				continue

			# Catch all exceptions to enable ongoing analysis, should never happen
			except Exception as err:
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('Unexpected error during peer evaluation: {}\n{}'.format(err, ''.join(tb)))
				continue

			# Close connection
			try:
				sock.close()
			except OSError as err:
				logging.warning('Closing of connectioin failed: {}'.format(err))
			else:
				logging.info('Connection closed')

			# Put in visited queue
			revisit_time = time.perf_counter() + delay
			self.visited_peers.put((peer, result, revisit_time))
			self.active_success.increment()

		# Propagate shutdown finish
		self.active_shutdown_done.wait()

	## Continuously asks the tracker server for new peers
	#  @param interval Timer interval between tracker requests are issued in minutes
	#  @note Start passive evaluation first to ensure port propagation
	def start_tracker_requests(self, interval):
		# Thread termination indicator
		self.tracker_shutdown_done = threading.Barrier(len(self.torrents) + 1)

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
	#  @param interval Time delay between contacting the tracker in seconds
	#  @note This is a worker method to be started as a thread
	def _tracker_requestor(self, torrent_key, interval):
		tracker = tracker_request.TrackerCommunicator(self.own_peer_id, self.torrents[torrent_key].announce_url,
				self.timeout, self.listen_port, self.torrents[torrent_key].pieces_count)

		while not self.shutdown_request.is_set():
			# Ask tracker
			logging.info('Contacting tracker for torrent with id {}'.format(torrent_key))
			try:
				tracker_interval, peer_ips = tracker.announce_request(self.torrents[torrent_key].info_hash)
			except tracker_request.TrackerError as err:
				logging.error('Could not receive peers from tracker: {}'.format(err))
			else:
				# Log recommended interval
				if interval > tracker_interval:
					logging.warning('Tracker wished interval of {} but we are using {} minutes'.format(tracker_interval/60, interval/60))
				else:
					logging.info('Tracker recommended interval of {} minutes'.format(tracker_interval/60))

				# Put peers in queue
				self.peers.duplicate.reset()
				for peer_ip in peer_ips:
					new_peer = Peer(revisit=0, ip_address=peer_ip[0], port=peer_ip[1],
							id=None, bitfield=None, pieces=None, source=0, torrent=torrent_key, key=None)
					self.peers.put(new_peer)
				duplicate_counter = self.peers.duplicate.get() # TODO inaccurate due to passive evaluation?
				self.total_duplicate += duplicate_counter
				self.total_received_peers += len(peer_ips)

				# Calculate number of new peers
				try:
					percentage = int(duplicate_counter * 100 / len(peer_ips))
				except ZeroDivisionError:
					percentage = 0
				logging.info('{} peers received, {} duplicates, equals {}%'.format(len(peer_ips), duplicate_counter, percentage))

			# Log queue stats
			self.log_statistics()

			# Wait interval
			logging.info('Waiting {} minutes until next tracker request ...'.format(interval/60))
			self.shutdown_request.wait(interval)

		# Propagate thread termination
		self.tracker_shutdown_done.wait()

	## Starts a multithreaded TCP server to analyze incoming peers
	#  @param port Extern listen port number
	#  @exception AnalyzerError
	def start_passive_evaluation(self, port):
		# Create the server, binding to outside address on custom port
		if not 0 <= port <= 65535:
			raise AnalyzerError('Invalid port number: {}'.format(port))
		address = ('0.0.0.0', port)
		try:
			self.server = PeerEvaluationServer(address, PeerHandler,
					own_peer_id=self.own_peer_id,
					torrents=self.torrents,
					visited_peers=self.visited_peers,
					delay=self.delay,
					sock_timeout=self.timeout,
					success=self.passive_success,
					error=self.passive_error,
					dht_port=self.dht_port)
		except PermissionError as err:
			raise AnalyzerError('Could not start server on port {}: {}'.format(port, err))
		self.listen_port = port
		logging.info('Started passive evaluation server on host {}, port {}'.format(address[0], address[1]))

		# Activate the server in it's own thread
		server_thread = threading.Thread(target=self.server.serve_forever)
		server_thread.daemon = True
		server_thread.start()

		# Remember activation to enable shutdown
		self.passive_evaluation = True
		logging.info('Listening on port {} for incomming peer connections'.format(port))

	## Comsumes peers from database queue and put back in main queue
	def start_peer_handler(self):
		# Get database session
		self.database_session = self.database.get_session()

		# Start handler thread
		thread = threading.Thread(target=self._peer_handler)
		thread.daemon = True
		thread.start()

		# Remember activation to enable shutdown
		self.peer_handler = True

	## Consumes peers and stores them in the database
	#  @note This is a worker method to be started as a thread
	def _peer_handler(self):
		# Log thread id
		logging.info('The identifier for this peer handler thread is {}'.format(threading.get_ident()))

		while True:
			# Get new peer to store
			peer, result, revisit = self.visited_peers.get()
			rec_peer_id, rec_info_hash, messages = result

			# Evaluate messages
			bitfield = peer_wire_protocol.bitfield_from_messages(messages, self.torrents[peer.torrent].pieces_count)

			# Evaluate bitfield
			downloaded_pieces = peer_wire_protocol.count_bits(bitfield)
			percentage = int(downloaded_pieces * 100 / self.torrents[peer.torrent].pieces_count)
			remaining = self.torrents[peer.torrent].pieces_count - downloaded_pieces
			logging.info('Peer reports to have {} pieces, {} remaining, equals {}%'.format(downloaded_pieces, remaining, percentage))

			# Update peer with results
			peer = Peer(revisit, peer.ip_address, peer.port,
					rec_peer_id, bitfield, downloaded_pieces,
					peer.source, peer.torrent, peer.key)

			# Store evaluated peer and receive database key
			try:
				peer_key = self.database.store_peer(peer, self.database_session)

			# Catch all exceptions to enable ongoing thread, should never happen
			except Exception as err:
				self.database_session.rollback()
				self.visited_peers.task_done()
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('Unexpected error during database update: {}\n{}'.format(err, ''.join(tb)))
				continue

			# Remember database key and update statistical counters
			if peer.key is None:
				*old_peer, key = peer
				peer = Peer(*old_peer, key=peer_key)
				self.database_new_peer.increment()
			else:
				self.database_peer_update.increment()

			# Write back in progress peers, discard finished ones
			if peer.pieces < self.torrents[peer.torrent].pieces_count:
				# Exclude incoming peers
				if peer.source != 1:
					self.peers.put(peer)

			# Allow waiting for all peers to be stored at shutdown
			self.visited_peers.task_done()

	## Use an already running DHT node to extracts new peers
	#  @param node_port UDP port where the node is running
	#  @param control_port TCP port for sending telnet commands
	#  @param interval Time delay between contacting the dht in minutes
	#  @exception AnalyzerError
	def start_dht(self, node_port, control_port, interval):
		# Start communication
		try:
			self.dht = pymdht_connector.DHT(control_port)
		except pymdht_connector.DHTError as err:
			raise AnalyzerError(str(err))
		self.dht_port = node_port

		# Start handler thread
		thread = threading.Thread(target=self._dht_requestor, args=(interval*60,))
		thread.daemon = True
		thread.start()

		# Remember activation to enable shutdown
		self.dht_started = True

	## Requests new peers from the node for all torrents repeatingly
	#  @param interval Time delay between contacting the dht in seconds
	def _dht_requestor(self, interval):
		while not self.shutdown_request.is_set():
			for key in self.torrents:
				logging.info('Performing DHT peer lookup for torrent {} ...'.format(key))
				try:
					dht_peers = self.dht.get_peers(self.torrents[key].info_hash_hex, self.listen_port)
				except pymdht_connector.DHTError as err:
					logging.error('Could not receive DHT peers: {}'.format(err))

				# TODO put in self.peers
				logging.debug('Received DHT peers: {}'.format(dht_peers))

			# Wait interval
			logging.info('Waiting {} minutes until next dht request ...'.format(interval/60))
			self.shutdown_request.wait(interval)

	## Print evaluation statistics
	def log_statistics(self):
		# Peer queue, inaccurate due to consumer threads
		logging.info('Currently are about {} peers in queue left'.format(self.peers.qsize()))

		# Received peers
		try:
			percentage = int(self.total_duplicate * 100 / self.total_received_peers)
		except ZeroDivisionError:
			percentage = 0
		logging.info('In total {} peers received, {} duplicates, equals {}%'.format(self.total_received_peers, self.total_duplicate, percentage))

		# Evaluation errors
		logging.info('Active evaluations: {} successful, {} failed on first contact, {} failed on later contact'.format(
				self.active_success.get(), self.first_evaluation_error.get(), self.late_evaluation_error.get()))
		logging.info('Passive evaluations: {} successful, {} failed'.format(self.passive_success.get(), self.passive_error.get()))

		# Database access
		logging.info('Peer database access: {} stored, {} updated'.format(self.database_new_peer.get(), self.database_peer_update.get()))

	## Shutdown all worker threads if started
	def __exit__(self, exception_type, exception_value, traceback):
		# Propagate shutdown request
		self.shutdown_request.set()

		# Wait for termination
		if self.dht_started:
			self.dht.shutdown()
			logging.info('Exited DHT node')
		if self.active_evaluation:
			logging.info('Waiting for current evaluations to finish ...')
			self.active_shutdown_done.wait()
		if self.tracker_requests:
			logging.info('Waiting for current tracker requests to finish ...')
			self.tracker_shutdown_done.wait()
		if self.passive_evaluation:
			logging.info('Shutdown peer evaluation server ...')
			self.server.shutdown()
		if self.peer_handler:
			logging.info('Waiting for peers to be written to database ...')
			self.visited_peers.join()
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
		try:
			result = peer_wire_protocol.evaluate_peer(self.request, self.server.own_peer_id, self.server.dht_port)
		except peer_wire_protocol.PeerError as err:
			logging.warning('Could not evaluate incoming peer: {}'.format(err))
			self.server.error.increment()
		else:
			# Search received info hash in torrents dict
			torrent = None
			for key in self.server.torrents:
				if result[1] == self.server.torrents[key].info_hash:
					torrent = key
			if torrent is None:
				logging.warning('Ignoring incoming peer with unknown info hash')
				return
			else:
				logging.info('Storing incoming peer for torrent {}'.format(torrent))

			# Queue for peer handler
			new_peer = Peer(None, self.client_address[0], self.client_address[1], None, None, None, 1, torrent, None)
			revisit_time = time.perf_counter() + self.server.delay
			self.server.visited_peers.put((new_peer, result, revisit_time))
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

