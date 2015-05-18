# Consider peers to have completely downloaded the torrent at this pieces amount
torrent_complete_threshold = 0.98

# Timeout for network connections in seconds
network_timeout = 10

# Integrate an already running DHT node with this UDP port
dht_node_port = 17000

# Uses an already running DHT node over the given localhost telnet port
dht_control_port = 17001

# Time delay between asking DHT for new peers in seconds
dht_request_interval = 15 * 60

# Time delay between asking the tracker for new peers in seconds
tracker_request_interval = 15 * 60

# Time delay for revisiting unfinished peers in seconds
peer_revisit_delay = 15 * 60

# When collecting all messages from a peer, cancel after this amount
receive_message_max = 100

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

