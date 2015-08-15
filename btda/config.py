# Number of threads used to contact peers in queue
peer_evaluation_threads = 64
# Amount of downloaded pieces reported to the tracker
fake_downloaded_stat = 1.0
# Amount of left pieces reported to the tracker
fake_left_stat = 0.0
# Amount of uploaded pieces reported to the tracker
fake_uploaded_stat = 0.42
# Consider peers to have completely downloaded the torrent at this pieces amount
torrent_complete_threshold = 0.98
# Timeout for network connections in seconds
network_timeout = 6
# Integrate an already running DHT node with this UDP port
dht_node_port = 17000
# Uses an already running DHT node over the given localhost telnet port
dht_control_port = 17001
# Time delay between asking DHT for new peers in seconds
dht_request_interval = 5 * 60
# Time delay between asking the tracker for new peers in seconds
tracker_request_interval = 13 * 60
# Time delay for revisiting unfinished peers in seconds
peer_revisit_delay = 5 * 60
# When collecting all messages from a peer, cancel after this amount
receive_message_max = 128
# Truncate raw BitTorrent Protocol messages in logs to length
bittorrent_message_log_length = 80
# ut_metadata Extension Protocol message id
extension_ut_metadata_id = 4
# Evaluate incoming peers at the specified port number
bittorrent_listen_port = 6881
# Output path for log and database, with trailing slash
output_path = 'output/'
# Input path for torrent files and magnet file, with trailing slash
input_path = 'input/'
# Filename for magnet files, relative to input_path, one magnet link per line
magnet_file = 'magnet.txt'
# Time delay between logging peer statistics to database
statistic_interval = 5 * 60
# Evaluator reaction time on empty queue and delayed peers
evaluator_reaction = 40
# Write durations of message receival to file for timeout calibration
rec_dur_analysis = False
