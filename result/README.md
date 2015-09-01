# Result
This are the file produced by the BitTorrent Download Analyzer, which were used for the thesis.

## Timeout parameter
* Files: 2015-08-14_17-46-44_faui1-246*

## Hostname collection
* Files: 2015-08-26_11-24-21_faui1-246*

## Test evaluation
* Files: 2015-08-27_21-03-31_faui1-246*

## Main evaluation
* Files VM1: 2015-08-30_20-34-06_faui1-246*  
  The tracker requestor thread of torrent 6 crashed after four hours due to an invalid tracker response. The exception is printed below. Despite this, the analysis was successfull and can be used excluding torrent 6. At the end, the analysis had to be shutdown with multiple Ctrl+C, since the program tries to wait for all tracker threads. The resulting SQLite journal file was removed using `sqlite3 2015-08-30_20-34-06_faui1-246.sqlite vacuum`.

        Exception in thread Thread-6:
        Traceback (most recent call last):
          File "/usr/lib/python3.4/threading.py", line 920, in _bootstrap_inner
            self.run()
          File "/usr/lib/python3.4/threading.py", line 868, in run
            self._target(*self._args, **self._kwargs)
          File "/home/stefan/bittorrent-analyzer/btda/analyzer.py", line 326, in _tracker_requestor
            tracker_interval, peer_ips = tracker_conn.announce_request(self.torrents[torrent_key].info_hash)
          File "/home/stefan/bittorrent-analyzer/btda/tracker.py", line 43, in announce_request
            interval, ip_bytes = self._http_request(info_hash)
          File "/home/stefan/bittorrent-analyzer/btda/tracker.py", line 93, in _http_request
            interval = response[b'interval']
        TypeError: tuple indices must be integers, not bytes

* Files VM2: 2015-08-30_20-41-36_faui1-246*

As mentioned in the BitTorrent Download Analyzer's [README.md](../btda/README.md), SQLAlchemy did refuse to store some entries in the request and statistic table, not the peer table. These entries were logged instead and were extracted with the `sql_from_log.py` script and applied to the database afterwards.

Further approach for creating the final database:

    scp torrent-vm1:bittorrent-analyzer/btda/output/2015-08-30_20-34-06_faui1-246* .
    scp torrent-vm2:bittorrent-analyzer/btda/output/2015-08-30_20-41-36_faui1-246* .
    sqlite3 2015-08-30_20-34-06_faui1-246.sqlite vacuum
    sqlite3 2015-08-30_20-41-36_faui1-246.sqlite vacuum
    ./sql_from_log.py 2015-08-30_20-34-06_faui1-246.log
    ./sql_from_log.py 2015-08-30_20-41-36_faui1-246.log
    cat 2015-08-30_20-34-06_faui1-246.log.sql | sqlite3 2015-08-30_20-34-06_faui1-246.sqlite
    cat 2015-08-30_20-41-36_faui1-246.log.sql | sqlite3 2015-08-30_20-41-36_faui1-246.sqlite
    cat combine.sql | sqlite3 | sqlite3 2015-08-30_20-combined.sqlite
