# Result
This are the file produced by the BitTorrent Download Analyzer, which were used for the thesis. The filenames are using the timezone CEST, which is UTC+02:00.

## Timeout parameter
Only used in chapter 3.4 *Justification of Configuration values*.

* Files: `2015-08-14_17-46-44_faui1-246*`

## Hostname collection
Only used in chapter 4.4.3 *Peer's Hostnames*.

* Files: `2015-08-26_11-24-21_faui1-246*`

## Main evaluation
This are the files used for chapter 4 *Evaluation*.

* Files VM1: `2015-08-30_20-34-06_faui1-246*`  
  The tracker requestor thread of torrent 6 crashed after four hours due to an invalid tracker response. The exception is printed below. Despite this, the analysis was successfull and can be used when excluding torrent 6. At the end, the analysis had to be shutdown with multiple Ctrl+C, since the program tries to wait for all tracker threads. The resulting SQLite journal file was resolved using `sqlite3 2015-08-30_20-34-06_faui1-246.sqlite vacuum`.

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

* Files VM2: `2015-08-30_20-41-36_faui1-246*`

* Files, combined: `2015-08-30_20-combined*`  
The file `2015-08-30_20-combined.sqlite.csv` was manually created and assigns each torrent file to a set, which is used in the evaluation of the thesis.
