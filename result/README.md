# Result
This are the file produced by the BitTorrent Download Analyzer, which were used for the thesis.

## Timeout parameter
Only used in chapter 3.4 *Justification of Configuration values*.

* Files: `2015-08-14_17-46-44_faui1-246*`

## Hostname collection
Only used in chapter 4.4.3 *Peer's Hostnames*.

* Files: `2015-08-26_11-24-21_faui1-246*`

## Main evaluation
This are the files used for chapter 4 *Evaluation*.

* Files VM1: `2015-08-30_20-34-06_faui1-246*`  
  The tracker requestor thread of torrent 6 crashed after four hours due to an invalid tracker response. The exception is printed below. Despite this, the analysis was successfull and can be used excluding torrent 6. At the end, the analysis had to be shutdown with multiple Ctrl+C, since the program tries to wait for all tracker threads. The resulting SQLite journal file was removed using the SQLite vacuum command.

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

As explained in the BitTorrent Download Analyzer's [README.md](../btda/README.md#known-issues), SQLAlchemy did refuse to store some entries in the request and statistic table. These entries were logged instead and were extracted with the `sql_from_log.py` script and applied to the database afterwards.

Finally, the databases of the two VMs were combined, using the `combine.sql` script. This script does exclude torrent 6 from VM1.

Following commands were used to create the final database:

    scp torrent-vm1:bittorrent-analyzer/btda/output/2015-08-30_20-34-06_faui1-246* .
    scp torrent-vm2:bittorrent-analyzer/btda/output/2015-08-30_20-41-36_faui1-246* .
    sqlite3 2015-08-30_20-34-06_faui1-246.sqlite vacuum
    sqlite3 2015-08-30_20-41-36_faui1-246.sqlite vacuum
    ./sql_from_log.py 2015-08-30_20-34-06_faui1-246.log
    ./sql_from_log.py 2015-08-30_20-41-36_faui1-246.log
    cat 2015-08-30_20-34-06_faui1-246.log.sql | sqlite3 2015-08-30_20-34-06_faui1-246.sqlite
    cat 2015-08-30_20-41-36_faui1-246.log.sql | sqlite3 2015-08-30_20-41-36_faui1-246.sqlite
    cat combine.sql | sqlite3 | sqlite3 2015-08-30_20-combined.sqlite
