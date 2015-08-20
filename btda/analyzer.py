# Built-in modules
import logging
import threading
import traceback
import queue
import time
import socketserver
import socket
import os
import telnetlib

# Project modules
import tracker
import protocol
import storage
import torrent
import dht
import config
from util import *

## Requests peers from tracker and initiates peer connections
class SwarmAnalyzer:
	## Initializes analyzer for peers of one torrent
	#  @param debug Log to stdout and include debug messages
	#  @exception AnalyzerError
	def __init__(self, debug):
		# Set output path
		if not os.path.exists(config.output_path):
			os.makedirs(config.output_path)
		self.outfile = '{}{}_{}'.format(config.output_path, time.strftime('%Y-%m-%d_%H-%M-%S'), os.uname().nodename)

		# Configure logging
		logging_config = {'format': '[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s', 'datefmt': '%dd%Hh%Mm%Ss'}
		if debug:
			logging_config['level'] = logging.DEBUG
		else:
			logging_config['level'] = logging.WARNING
			logfile = '{}.log'.format(self.outfile)
			print('Log is written to {}'.format(logfile))
			logging_config['filename'] = logfile
		logging.basicConfig(**logging_config)

		# Smart queue for peer management
		self.peers = PrioritySetQueue()
		self.visited_peers = queue.Queue()
		self.all_incoming_peers = dict() # equality check

		# Create torrent dictionary
		self.torrents = dict()

		# Generate peer id
		self.own_peer_id = protocol.generate_peer_id()

		# Statistical counters
		self.active_success = SharedCounter()
		self.incoming_total = DictCounter()
		self.incoming_duplicate = DictCounter()
		self.error = DictCounter()
		if config.rec_dur_analysis:
			self.eval_timer = list()

		# Analysis parts, activated via starter methods
		self.shutdown_request = threading.Event()
		self.active_evaluation = False
		self.tracker_requests = False
		self.passive_evaluation = False
		self.peer_handler = False
		self.dht_started = False
		self.statistic_started = False

		# Create database
		self.database = storage.Database(self.outfile)

		# Create thread activity timer
		self.timer = ActivityTimer()

	## Resouces are allocated in starter methods
	def __enter__(self):
		return self

	## Reads all torrent files from input directory
	def import_torrents(self):
		# Import all files
		try:
			walk = os.walk(config.input_path)
		except OSError as err:
			raise AnalyzerError('Could not read from input directory: {}'.format(err))
		for dirname, dirnames, filenames in walk:
			for filename in filenames:
				# Sort out non torrents
				if not filename.endswith('.torrent'):
					continue

				# Read torrent file
				path = os.path.join(dirname, filename)
				torrent_file = torrent.TorrentFile(path)
				announce_url = torrent_file.get_announce_url()
				info_dict_bencoded = torrent_file.get_info_dict()
				info_dict = torrent.InfoDict(info_dict_bencoded)
				info_hash = info_dict.get_info_hash()
				piece_size = info_dict.get_piece_length()
				pieces_count = info_dict.get_pieces_count()
				name = info_dict.get_name()

				# Store in database and dictionary
				info_hash_hex = bytes_to_hex(info_hash)
				complete_threshold = protocol.get_complete_threshold(pieces_count)
				new_torrent = Torrent(announce_url, info_hash, info_hash_hex, pieces_count, piece_size, complete_threshold)
				key = self.database.store_torrent(new_torrent, path, name)
				self.torrents[key] = new_torrent

	## Read magnet links from file
	#  @note Call start_dht_connection first
	def import_magnets(self):
		filename = os.path.join(config.input_path, config.magnet_file)
		if not os.path.exists(filename):
			logging.info('Magnet file {} does not exist, nothing to import'.format(filename))
			return
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
				info_hash = torrent.hash_from_magnet(magnet)
				dht_conn = dht.DHT()
				metadata_peers = dht_conn.get_peers(info_hash)
				dht_conn.close()

				# Fetch metadata from a peer
				own_peer_id = protocol.generate_peer_id()
				for peer in metadata_peers:
					logging.info('Trying to fetch metadata from peer ...')
					try:
						info_dict_bencoded = protocol.get_ut_metadata(info_hash, peer, own_peer_id)
					except (PeerError, UtilError) as err:
						logging.warning('Failed to fetch metadata: {}'.format(err))
					else:
						break
				else:
					raise AnalyzerError('Could not fetch metadata from any peer')

				# Decode info dict
				tracker = torrent.tracker_from_magnet(magnet)
				info_dict = torrent.InfoDict(info_dict_bencoded)
				info_hash_hex = bytes_to_hex(info_hash)
				pieces_count = info_dict.get_pieces_count()
				piece_size = info_dict.get_piece_length()
				complete_threshold = protocol.get_complete_threshold(pieces_count)
				name = info_dict.get_name()

				# Store in database and dictionary
				new_torrent = Torrent(tracker, info_hash, info_hash_hex, pieces_count, piece_size, complete_threshold)
				key = self.database.store_torrent(new_torrent, filename, name)
				self.torrents[key] = new_torrent

	## Raise exception when duplicate torrents found
	def torrent_duplicates(self):
		info_hashes = set()
		for id, torrent in self.torrents.items():
			if torrent.info_hash in info_hashes:
				raise AnalyzerError('Duplicate torrent: id {}, hash {}'.format(id, torrent.info_hash_hex))
			info_hashes.add(torrent.info_hash)

	## Evaluates all peers in the queue
	def start_active_evaluation(self):
		# Concurrency management
		self.active_shutdown_done = threading.Barrier(config.peer_evaluation_threads + 1)

		# Create thread pool
		logging.info('Connecting to peers in {} threads'.format(config.peer_evaluation_threads))
		for i in range(config.peer_evaluation_threads):
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
		# Register timer
		thread = threading.current_thread().name
		self.timer.register(thread)

		# Start main loop
		while not self.shutdown_request.is_set():
			# Get new peer, wait on empty queue
			try:
				peer = self.peers.get()
			except PrioritySetQueueEmpty:
				self.timer.inactive(thread)
				self.shutdown_request.wait(config.evaluator_reaction)
				self.timer.active(thread)
				continue

			# Delay evaluation
			delay = peer.revisit - time.perf_counter()
			if delay > 0:
				logging.info('Delaying peer evaluation for {} seconds, target is {} minutes ...'.format(config.evaluator_reaction, delay/60))
				self.timer.inactive(thread)
				self.shutdown_request.wait(config.evaluator_reaction)
				self.timer.active(thread)
				self.peers.force_put(peer)
				continue

			# Establish connection
			# TODO use util.TCPConnection
			if peer.key is None:
				logging.info('Connecting to new peer ...')
			else:
				logging.info('Reconnecting to peer {} ...'.format(peer.key))
			try:
				sock = socket.create_connection((peer.ip_address, peer.port), config.network_timeout)
			except OSError as err:
				if peer.key is None:
					self.error.count('First contact,{}'.format(err))
				else:
					self.error.count('Later contact,{}'.format(err))
				logging.warning('Connection establishment failed: {}'.format(err))
				continue
			logging.debug('Connection established')

			# Contact peer
			dht_port = config.dht_node_port if self.dht_started else None
			try:
				result = protocol.evaluate_peer(sock, self.own_peer_id, self.dht_started, self.torrents[peer.torrent].info_hash)

			# Handle bad peers
			except PeerError as err:
				if peer.key is None:
					self.error.count('First contact,{}'.format(err))
				else:
					self.error.count('Later contact,{}'.format(err))
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
				logging.debug('Connection closed')

			# Put in visited queue
			revisit_time = time.perf_counter() + delay
			self.visited_peers.put((peer, result, revisit_time))
			self.active_success.increment()

		# Propagate shutdown finish
		self.active_shutdown_done.wait()

	## Continuously asks the tracker server for new peers
	#  @note Start passive evaluation first to ensure port propagation
	def start_tracker_requests(self):
		# Extract torrents with tracker
		torrents_with_tracker = list()
		for torrent_id in self.torrents:
			if self.torrents[torrent_id].announce_url is not None:
				torrents_with_tracker.append(torrent_id)

		# Concurrency management
		self.tracker_shutdown_done = threading.Barrier(len(torrents_with_tracker) + 1)

		# Create tracker request threads
		for torrent_id in torrents_with_tracker:
			thread = threading.Thread(target=self._tracker_requestor, args=(torrent_id,))
			thread.daemon = True
			thread.start()

		# Remember activation to enable shutdown
		self.tracker_requests = True

	## Issues GET request to tracker, puts received peers in queue, wait an interval
	#  @param torrent_key Torrent key specifying the target torrent and tracker
	#  @note This is a worker method to be started as a thread
	def _tracker_requestor(self, torrent_key):
		while not self.shutdown_request.is_set():
			is_first_announce_url = True
			for announce_url in self.torrents[torrent_key].announce_url:
				# Create tracker connection
				tracker_conn = tracker.TrackerCommunicator(self.own_peer_id, announce_url, self.torrents[torrent_key].pieces_count)

				# Try scrape request
				if is_first_announce_url:
					is_first_announce_url = False
					try:
						seeders, completed, leechers = tracker_conn.scrape_request(self.torrents[torrent_key].info_hash)
					except TrackerError as err:
						logging.warning('Scrape request failed on torrent {}: {}'.format(torrent_key, err))
						seeders = completed = leechers = None
				else:
					seeders = completed = leechers = None

				# Ask tracker
				logging.info('Contacting tracker for torrent with id {}'.format(torrent_key))
				try:
					start = time.perf_counter()
					tracker_interval, peer_ips = tracker_conn.announce_request(self.torrents[torrent_key].info_hash)
					end = time.perf_counter()
				except TrackerError as err:
					logging.warning('Could not receive peers from tracker on torrent {}: {}'.format(torrent_key, err))
				else:
					# Log recommended interval
					if config.tracker_request_interval > tracker_interval:
						logging.warning('Tracker wished interval of {} but we are using {} minutes'.format(tracker_interval/60,
								config.tracker_request_interval/60))
					else:
						logging.info('Tracker recommended interval of {} minutes'.format(tracker_interval/60))

					# Put peers in queue
					duplicate_counter = 0
					for peer_ip in peer_ips:
						new_peer = Peer()
						new_peer.revisit = 0
						new_peer.ip_address = peer_ip[0]
						new_peer.port = peer_ip[1]
						new_peer.source = Source.tracker
						new_peer.torrent = torrent_key
						if not self.peers.put(new_peer):
							duplicate_counter += 1
					try:
						self.database.store_request(Source.tracker, len(peer_ips), duplicate_counter,
								seeders, completed, leechers, end-start, torrent_key)
					except Exception as err:
						logging.critical(err)

			# Wait interval
			logging.info('Waiting {} minutes until next tracker request ...'.format(config.tracker_request_interval/60))
			self.shutdown_request.wait(config.tracker_request_interval)

		# Propagate thread termination
		self.tracker_shutdown_done.wait()

	## Starts a multithreaded TCP server to analyze incoming peers
	#  @exception AnalyzerError
	def start_passive_evaluation(self):
		# Create the server, binding to outside address on custom port
		assert 0 <= config.bittorrent_listen_port <= 65535
		address = ('0.0.0.0', config.bittorrent_listen_port)
		self.server = PeerEvaluationServer(address, PeerHandler,
				own_peer_id=self.own_peer_id,
				torrents=self.torrents,
				visited_peers=self.visited_peers,
				error=self.error,
				dht_enabled=self.dht_started)
		logging.info('Listening on {}:{} for incomming peer connections'.format(*address))

		# Activate the server in it's own thread
		server_thread = threading.Thread(target=self.server.serve_forever)
		server_thread.daemon = True
		server_thread.start()

		# Remember activation to enable shutdown
		self.passive_evaluation = True

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
			rec_peer_id, rec_info_hash, messages, duration = result

			# Store duration
			if config.rec_dur_analysis and duration:
				self.eval_timer.append(duration)

			# Evaluate messages
			bitfield = protocol.bitfield_from_messages(messages, self.torrents[peer.torrent].pieces_count)

			# Evaluate bitfield
			downloaded_pieces = protocol.count_bits(bitfield)
			percentage = int(downloaded_pieces * 100 / self.torrents[peer.torrent].pieces_count)
			remaining = self.torrents[peer.torrent].pieces_count - downloaded_pieces
			logging.debug('Peer reports to have {} pieces, {} remaining, equals {}%'.format(downloaded_pieces, remaining, percentage))

			# Retrieve key for reoccurred incoming peers
			if peer.source is Source.incoming:
				equality = (peer.ip_address, peer.torrent) # Port differs every time
				try:
					peer.key = self.all_incoming_peers[equality]
				except KeyError:
					pass

			# Update peer with results
			peer.id = rec_peer_id
			peer.pieces = downloaded_pieces

			# Store evaluated peer and receive database key
			try:
				new_peer_key = self.database.store_peer(peer)
			except Exception as err:
				self.visited_peers.task_done()
				logging.critical(err)
				continue

			# Remember equality information of new incoming peers and discard all incoming
			if peer.source is Source.incoming:
				self.incoming_total.count(peer.torrent)
				if peer.key is None:
					self.all_incoming_peers[equality] = new_peer_key
				else:
					self.incoming_duplicate.count(peer.torrent)
				self.visited_peers.task_done()
				continue

			# Write back peer when not finished and add key if necessary
			if peer.pieces < self.torrents[peer.torrent].complete_threshold:
				if peer.key is None:
					peer.key = new_peer_key
				self.peers.force_put(peer)

			# Allow waiting for all peers to be stored at shutdown
			self.visited_peers.task_done()

	## Extract new peers from DHT
	#  @exception AnalyzerError
	#  @note Call start_dht_connection first
	def start_dht_requests(self):
		# Contact an already running DHT node
		self.dht_conn = dht.DHT()

		# Concurrency management
		self.dht_shutdown_done = threading.Event()

		# Start requestor thread
		thread = threading.Thread(target=self._dht_requestor)
		thread.daemon = True
		thread.start()

		# Remember activation to enable shutdown
		self.dht_started = True

	## Requests new peers from the node for all torrents repeatingly
	def _dht_requestor(self):
		while not self.shutdown_request.is_set():
			for key in self.torrents:
				# Request peers
				start = time.perf_counter()
				dht_peers = list()
				try:
					dht_peers = self.dht_conn.get_peers(self.torrents[key].info_hash)
				except DHTError as err:
					logging.error('Could not receive DHT peers: {}'.format(err))
				except Exception as err:
					tb = traceback.format_tb(err.__traceback__)
					logging.critical('{} during DHT request: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))
				end = time.perf_counter()

				# Put in queue
				duplicate_counter = 0
				for peer in dht_peers:
					new_peer = Peer()
					new_peer.revisit = 0
					new_peer.ip_address = peer[0]
					new_peer.port = peer[1]
					new_peer.source = Source.dht
					new_peer.torrent = key
					if not self.peers.put(new_peer):
						duplicate_counter += 1
				try:
					self.database.store_request(Source.dht, len(dht_peers), duplicate_counter,
							None, None, None, end-start, key)
				except Exception as err:
					logging.critical(err)

			# Print stats at DHT node # TODO receive instead of print
			try:
				self.dht_conn.print_stats()
			except Exception as err:
				tb = traceback.format_tb(err.__traceback__)
				logging.critical('{} during DHT stats printing: {}\n{}'.format(type(err).__name__, err, ''.join(tb)))

			# Wait interval
			logging.info('Waiting {} minutes until next DHT request ...'.format(config.dht_request_interval/60))
			self.shutdown_request.wait(config.dht_request_interval)

		# Propagate thread termination
		self.dht_shutdown_done.set()

	## Write connection statistics to database
	def log_connection_stats(self):
		# Concurrency management
		self.statistic_shutdown = threading.Event()

		# Start requestor thread
		thread = threading.Thread(target=self._statistic_logger)
		thread.daemon = True
		thread.start()

		# Remember activation to enable shutdown
		self.statistic_started = True

	## Store connection statistics to database
	def _statistic_logger(self):
		while not self.shutdown_request.is_set():
			self.shutdown_request.wait(config.statistic_interval)
			logging.info('Logging analysis statistics to database ...')
			try:
				self.database.store_statistic(
						peer_queue=len(self.peers),
						unique_incoming=len(self.all_incoming_peers),
						success_active=self.active_success.get(),
						thread_workload=self.timer.read())
			except Exception as err:
				logging.critical(err)

			# Store peer connection errors
			self.error.write_csv(self.outfile)

			# Store incoming peer statistics
			for id in self.torrents:
				try:
					self.database.store_request(
						source = Source.incoming,
						received_peers = self.incoming_total.reset(id),
						duplicate_peers = self.incoming_duplicate.reset(id),
						seeders=None, completed=None, leechers=None, duration=None,
						torrent = id)
				except Exception as err:
					logging.critical(err)

		# Propagate thread termination
		self.statistic_shutdown.set()

	## Wait for termination, return after SIGINT is received
	def wait_for_sigint(self):
		try:
			logging.info('End with "kill -SIGINT {}"'.format(os.getpid()))
			while True:
				time.sleep(1024)
		except KeyboardInterrupt:
			logging.info('Received interrupt signal')

	## Shutdown all worker threads if started
	def __exit__(self, exc_type, exc_value, tb):
		# Log exception when exiting after error
		if exc_type is not None:
			if issubclass(exc_type, AnalyzerError):
				logging.error('{}: {}'.format(exc_type.__name__, exc_value))
			else:
				tb_lines = traceback.format_tb(tb)
				logging.critical('{}: {}\n{}'.format(exc_type.__name__, exc_value, ''.join(tb_lines)))

		# Propagate shutdown request
		self.shutdown_request.set()

		# Plot message receive durations for timeout calibration
		if config.rec_dur_analysis:
			plot_receive_duration(self.eval_timer, self.outfile)

		# Wait for termination
		if self.dht_started:
			logging.info('Waiting for DHT requests to finish ...')
			self.dht_shutdown_done.wait()
			self.dht_conn.close()
			print('DHT requests terminated')
		if self.active_evaluation:
			logging.info('Waiting for current evaluations to finish ...')
			self.active_shutdown_done.wait()
			print('Active evaluation terminated')
		if self.tracker_requests:
			logging.info('Waiting for current tracker requests to finish ...')
			self.tracker_shutdown_done.wait()
			print('Tracker requests terminated')
		if self.passive_evaluation:
			logging.info('Shutdown peer evaluation server ...')
			self.server.shutdown() # TODO use semaphore, because it does not wait for current handlers to finish. Only in case of previous crash?
			print('Passive evaluation server terminated')
		if self.peer_handler:
			logging.info('Waiting for peers to be written to database ...')
			# TODO does not wait long enough,
			# see 2015-04-07_16h03m36s.log,
			# reason is passive eval threads add peers after shutdown, see above
			self.visited_peers.join()
			print('Database thread terminated')
		if self.statistic_started:
			logging.info('Waiting for analysis statistics to be written to database ...')
			self.statistic_shutdown.wait()
			print('Statistics thread terminated')
		self.database.close()

		# Do not reraise incoming exceptions, as it is already logged above
		logging.info('Finished')
		return True

class Peer(RichComparisonMixin):
	def __init__(self):
		self.revisit = None
		self.ip_address = None
		self.port = None
		self.id = None
		self.pieces = None
		self.source = None
		self.torrent = None
		self.key = None

	def __lt__(self, other):
		return self.revisit < other.revisit

	def __eq__(self, other):
		return self.revisit == other.revisit

	def __hash__(self):
		return hash((self.ip_address, self.port, self.torrent))

	def __str__(self):
		return 'Peer {}'.format(self.key)

## Subclass of library class to change parameters, add attributes and add multithreading mix-in class
class PeerEvaluationServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
	## Extended init
	#  @param server_address Pass through to parent
	#  @param RequestHandlerClass Pass through to parent
	#  @param **server_args Server attributes available in handle method
	def __init__(self, server_address, RequestHandlerClass, **server_args):
		# Parent class parameter
		self.allow_reuse_address = True
		self.all_incoming_ips = set()
		self.all_incoming_ips_lock = threading.Lock()

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
			self.request.settimeout(config.network_timeout)
		except OSError as err:
			logging.warning('Could not set timeout on incoming connection')
			return
		logging.info('Evaluating an incoming peer ...')
		try:
			result = protocol.evaluate_peer(self.request, self.server.own_peer_id, self.server.dht_enabled)
		except PeerError as err:
			logging.warning('Could not evaluate incoming peer: {}'.format(err))
			self.server.error.count('Incoming peer,{}'.format(err))
		else:
			# Search received info hash in torrents dict
			torrent_id = None
			for key in self.server.torrents:
				if result[1] == self.server.torrents[key].info_hash:
					torrent_id = key
			if torrent_id is None:
				logging.warning('Ignoring incoming peer with unknown info hash')
				self.server.error.count('Incoming peer,Unknown info hash')
				return

			# Queue for peer handler
			new_peer = Peer()
			new_peer.ip_address = self.client_address[0]
			new_peer.port = self.client_address[1]
			new_peer.source = Source.incoming
			new_peer.torrent = torrent_id
			revisit_time = time.perf_counter() + config.peer_revisit_delay
			self.server.visited_peers.put((new_peer, result, revisit_time))
