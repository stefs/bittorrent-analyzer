-- docs: https://www.sqlite.org/cli.html
-- stop after hitting an error
.bail on
.print '.bail on'

-- usage: cat combine.sql | sqlite3 | sqlite3 combined.sqlite
ATTACH DATABASE 'x/2015-08-29_17-09-13_faui1-246.sqlite' AS vm1;
ATTACH DATABASE 'x/2015-08-29_17-10-23_faui1-246.sqlite' AS vm2;

-- use single transaction for performance reasons
.print 'BEGIN TRANSACTION;'

-- recreate tables
SELECT sql || ';'
	FROM vm1.sqlite_master
	WHERE type='table';

-- table torrent
.mode insert torrent
SELECT id, announce_url, info_hash, info_hash_hex, pieces_count, piece_size, complete_threshold, filepath, display_name, gigabyte
	FROM vm1.torrent;
SELECT id+50, announce_url, info_hash, info_hash_hex, pieces_count, piece_size, complete_threshold, filepath, display_name, gigabyte
	FROM vm2.torrent;

-- table peer
.mode insert peer
SELECT NULL, client, continent, country, latitude, longitude, first_pieces, last_pieces, first_seen, last_seen, max_speed, visits, source, torrent
	FROM vm1.peer;
SELECT NULL, client, continent, country, latitude, longitude, first_pieces, last_pieces, first_seen, last_seen, max_speed, visits, source, torrent+50
	FROM vm2.peer;

-- table request
.mode insert request
SELECT NULL, timestamp, source, received_peers, duplicate_peers, seeders, completed, leechers, duration_sec, torrent
	FROM vm1.request;
SELECT NULL, timestamp, source, received_peers, duplicate_peers, seeders, completed, leechers, duration_sec, torrent+50
	FROM vm2.request;

-- table statistic
.mode insert statistic
.print 'ALTER TABLE statistic ADD COLUMN vm INTEGER;'
SELECT NULL, timestamp, peer_queue, visited_queue, unique_incoming, success_active, thread_workload, load_average, memory_mb, server_threads, evaluator_threads, 1
	FROM vm1.statistic;
SELECT NULL, timestamp, peer_queue, visited_queue, unique_incoming, success_active, thread_workload, load_average, memory_mb, server_threads, evaluator_threads, 2
	FROM vm2.statistic;

-- end transaction
.print 'COMMIT;'
