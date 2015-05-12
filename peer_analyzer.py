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
import enum

# Project modules
import tracker_request
import peer_wire_protocol
import database_storage
import torrent_file
import pymdht_connector
from error import *

## Named tuples representing cached peer and a torrent file
Peer = collections.namedtuple('Peer', 'revisit ip_address port id bitfield pieces source torrent key') # no None allowed
Torrent = collections.namedtuple('Torrent', 'announce_url info_hash info_hash_hex pieces_count piece_size complete_threshold') # only announce_url may be None
class Source(enum.Enum):
	tracker = 0
	incoming = 1
	dht = 2

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
		self.all_incoming_peers = dict() # equality check

		# Create torrent dictionary
		self.torrents = dict()

		# Generate peer id
		self.own_peer_id = tracker_request.generate_peer_id()

		# Network parameters
		self.delay = delay * 60
		self.timeout = timeout
		self.listen_port = None
		self.dht_port = None

		# Statistical counters
		self.first_evaluation_error = SharedCounter()
		self.late_evaluation_error = SharedCounter()
		self.database_peer_update = SharedCounter()
		self.database_new_peer = SharedCounter()
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
		self.database = database_storage.Database(output)

	## Resouces are allocated in starter methods
	def __enter__(self):
		return self

	## Reads all torrent files from input directory
	def import_torrents(self):
		# Import all files
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
					name = parser.get_name()
				except FileError as err:
					logging.error('Could not import torrent {}: {}'.format(filename, err))
					continue

				# Store in database and dictionary
				bytes_hash = bytes.fromhex(info_hash)
				complete_threshold = peer_wire_protocol.get_complete_threshold(pieces_number)
				torrent = Torrent(announce_url, bytes_hash, info_hash, pieces_number, piece_size, complete_threshold)
				key = self.database.store_torrent(torrent, path, name)
				self.torrents[key] = torrent

		# Check result
		if len(self.torrents) > 0:
			logging.info('Imported {} torrent files'.format(len(self.torrents)))
		else:
			raise AnalyzerError('No valid torrent files found')

	## Read magnet links from file
	#  @filename File system path to text file with one magnet link per line
	#  @note Call start_dht_connection first
	def import_magnets(self, filename):
		success = 0
		linenumber = 0
		with open(filename) as file:
			for magnet in file:
				# Skip empty lines
				linenumber += 1
				logging.info('Parsing magnet link form {}, line {} ...'.format(filename, linenumber))
				magnet = magnet.rstrip('\n')
				if magnet == '':
					continue

				# Get peers for metadata aquisition
				info_hash = torrent_file.hash_from_magnet(magnet)
				metadata_peers = self.dht.get_peers(info_hash, self.listen_port)

				# Parse magnet link
				timeout = 60 # TODO in code config
				name, info_hash_fetch, announce_url, piece_size, pieces_number = torrent_file.fetch_magnet(magnet, metadata_peers, timeout) # FileError
				if info_hash_fetch.lower() != info_hash.lower():
					raise AnalyzerError('Hash mismatch after metadata fetch: {} to {}'.format(info_hash, info_hash_fetch))
				success += 1

				# Store in database and dictionary
				bytes_hash = bytes.fromhex(info_hash)
				complete_threshold = peer_wire_protocol.get_complete_threshold(pieces_number)
				torrent = Torrent(announce_url, bytes_hash, info_hash, pieces_number, piece_size, complete_threshold)
				key = self.database.store_torrent(torrent, filename, name)
				self.torrents[key] = torrent

		# Check result
		if success > 0:
			logging.info('Imported {} magnet links'.format(success))
		else:
			raise AnalyzerError('No magnet links found')

	## Evaluates all peers in the queue
	#  @param jobs Number of parallel thread to use
	def start_active_evaluation(self, jobs):
		# Concurrency management
		self.active_shutdown_done = threading.Barrier(jobs + 1)

		# Create thread pool
		logging.info('Connecting to peers in {} threads'.format(jobs))
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
				self.peers.put((peer, None))
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
				logging.critical('{} during peer evaluation: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))
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
		# Extract torrents with tracker
		torrents_with_tracker = list()
		for torrent in self.torrents:
			if self.torrents[torrent].announce_url is not None:
				torrents_with_tracker.append(torrent)

		# Concurrency management
		self.tracker_shutdown_done = threading.Barrier(len(torrents_with_tracker) + 1)

		# Create tracker request threads
		interval_seconds = interval * 60
		for torrent in torrents_with_tracker:
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
				start = time.perf_counter()
				tracker_interval, peer_ips = tracker.announce_request(self.torrents[torrent_key].info_hash)
				end = time.perf_counter()
			except tracker_request.TrackerError as err:
				logging.error('Could not receive peers from tracker: {}'.format(err))
			else:
				# Log recommended interval
				if interval > tracker_interval:
					logging.warning('Tracker wished interval of {} but we are using {} minutes'.format(tracker_interval/60, interval/60))
				else:
					logging.info('Tracker recommended interval of {} minutes'.format(tracker_interval/60))

				# Put peers in queue
				duplicate_counter = 0
				for peer_ip in peer_ips:
					new_peer = Peer(revisit=0, ip_address=peer_ip[0], port=peer_ip[1],
							id=None, bitfield=None, pieces=None, source=Source.tracker, torrent=torrent_key, key=None)
					is_duplicate = [False]
					self.peers.put((new_peer, is_duplicate))
					if is_duplicate[0]:
						duplicate_counter += 1
				try:
					self.database.store_request(Source.tracker, len(peer_ips), duplicate_counter, end-start)
				except Exception as err:
					tb = traceback.format_tb(err.__traceback__)
					logging.critical('{} during request storing: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))

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

			# Retrieve key for reoccurred incoming peers
			key = peer.key
			assert (peer.source is Source.incoming) == (peer.source == Source.incoming), 'problem with enum comparison' # debug
			if peer.source is Source.incoming:
				equality = (peer.ip_address, peer.torrent) # Port differs every time
				try:
					key = self.all_incoming_peers[equality]
				except KeyError:
					pass

			# Update peer with results
			peer = Peer(revisit, peer.ip_address, peer.port,
					rec_peer_id, bitfield, downloaded_pieces,
					peer.source, peer.torrent, key)

			# Store evaluated peer and receive database key
			try:
				peer_key = self.database.store_peer(peer)
				#raise Exception('halt stop') # TODO debug test this

			# Catch all exceptions to enable ongoing thread, should never happen
			except Exception as err:
				self.visited_peers.task_done()
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('{} during database update: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))
				continue

			# Update statistical counters
			if peer_key is None:
				self.database_peer_update.increment()
			else:
				self.database_new_peer.increment()

			# Remember equality information of new incoming peers and discard all incoming
			if peer.source is Source.incoming:
				if peer_key is not None:
					self.all_incoming_peers[equality] = peer_key
				self.visited_peers.task_done()
				continue

			# Write back peer when not finished and add key if necessary
			if peer.pieces < self.torrents[peer.torrent].complete_threshold:
				if peer.key is None:
					*old_peer, key = peer
					peer = Peer(*old_peer, key=peer_key)
				self.peers.put((peer, None))

			# Allow waiting for all peers to be stored at shutdown
			self.visited_peers.task_done()

	## Contact an already running DHT node
	#  @param node_port UDP port where the node is running
	#  @param control_port TCP port for sending telnet commands
	#  @exception AnalyzerError
	def start_dht_connection(self, node_port, control_port):
		self.dht = pymdht_connector.DHT(control_port, self.timeout)
		self.dht_port = node_port

	## Extract new peers from DHT
	#  @param interval Time delay between contacting the dht in minutes
	#  @exception AnalyzerError
	#  @note Call start_dht_connection first
	def start_dht_requests(self, interval):
		# Concurrency management
		self.dht_shutdown_done = threading.Event()

		# Start requestor thread
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
				# Request peers
				start = time.perf_counter()
				dht_peers = list()
				try:
					dht_peers = self.dht.get_peers(self.torrents[key].info_hash_hex, self.listen_port)
				except pymdht_connector.DHTError as err:
					logging.error('Could not receive DHT peers: {}'.format(err))
				except Exception as err:
					tb = traceback.format_tb(err.__traceback__)
					logging.critical('{} during DHT request: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))
				end = time.perf_counter()

				# Put in queue
				duplicate_counter = 0
				for peer in dht_peers:
					new_peer = Peer(revisit=0, ip_address=peer[0], port=peer[1],
							id=None, bitfield=None, pieces=None, source=Source.dht, torrent=key, key=None)
					is_duplicate = [False]
					self.peers.put((new_peer, is_duplicate))
					if is_duplicate[0]:
						duplicate_counter += 1
				try:
					self.database.store_request(Source.dht, len(dht_peers), duplicate_counter, end-start)
				except Exception as err:
					tb = traceback.format_tb(err.__traceback__)
					logging.critical('{} during request storing: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))

			# Print stats at DHT node # TODO receive instead of print
			try:
				self.dht.print_stats()
			except Exception as err:
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('{} during DHT stats printing: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))

			# Wait interval
			logging.info('Waiting {} minutes until next DHT request ...'.format(interval/60))
			self.shutdown_request.wait(interval)

		# Propagate thread termination
		self.dht_shutdown_done.set()

	## Print evaluation statistics
	def log_statistics(self):
		# Peer queue, inaccurate due to consumer threads
		logging.info('Currently are about {} peers in queue left'.format(self.peers.qsize()))

		# Unique incoming peers
		logging.info('Seen {} unique incoming peers'.format(len(self.all_incoming_peers)))

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
			logging.info('Waiting for DHT requests to finish ...')
			self.dht_shutdown_done.wait()
			self.dht.close()
		if self.active_evaluation:
			logging.info('Waiting for current evaluations to finish ...')
			self.active_shutdown_done.wait()
		if self.tracker_requests:
			logging.info('Waiting for current tracker requests to finish ...')
			self.tracker_shutdown_done.wait()
		if self.passive_evaluation:
			logging.info('Shutdown peer evaluation server ...')
			self.server.shutdown() # TODO use semaphore, because it does not wait for current handlers to finish
			time.sleep(self.timeout+3) # debug
		if self.peer_handler:
			logging.info('Waiting for peers to be written to database ...')
			self.visited_peers.join() # TODO does not wait long enough, see 2015-04-07_16h03m36s.log
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

	## Put new peer in queue if not already processed, does not exclude peers with database id
	#  @param peer Peer named tuple and duplicate indicator
	#  @return True if this is a new peer, False if it has already been put
	#  @note Overrides intern method
	#  @warning Disables join option according to http://stackoverflow.com/a/24183479 and https://hg.python.org/cpython/file/3.4/Lib/queue.py#l147
	def _put(self, peer):
		# Unpack duplicate indicator
		peer, is_duplicate = peer

		# Create copy peer data for equality check
		peer_equality = (peer.ip_address, peer.port, peer.torrent)

		# Check if this is a revisit or if it is a new peer
		if peer.key is not None or peer_equality not in self.all_peers:
			# Call parent method
			queue.PriorityQueue._put(self, peer)

			# Remember equality information, set discards revisit duplicates
			self.all_peers.add(peer_equality)
		else:
			is_duplicate[0] = True

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
			new_peer = Peer(None, self.client_address[0], self.client_address[1], None, None, None, Source.incoming, torrent, None)
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

