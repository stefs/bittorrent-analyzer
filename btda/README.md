# BitTorrent Download Analyzer
This tool is aimed at counting confirmed downloads performed via BitTorrent by analyzing its peers. It is part of a Bachelor thesis at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

## Features
* Import torrents from `.torrent` files (BEP 3)
* Import torrents form magnet links by fetching metadata via the *ut_metadata* extension (BEP 9) using the Extension Protocol (BEP 10)
* Continuously get IPv4 peers and scrape information from the multiple trackers per torrent using HTTP (BEP 3) and UDP announce requests (BEP 15)
* Communicate with peers using a subset of the Peer Wire Protocol (BEP 3)
* Continuously get IPv4 peers by integrating a running DHT node (BEP 5) from the *pymdht* project using local telnet
* Actively contact collected peers and calculate minimum number of downloaded pieces by receiving all *have* and *bitfield* messages until a timeout
* Reconnect to peers until they have downloaded a defined threshold
* Passively listen for incoming peer connections and calculate minimum number of downloaded pieces analog
* Save number of downloaded pieces from first and last visit and maximum download speed per peer in a SQLite database
* Save city, country and latitude/longitude via IP address geolocation
* Analyze multiple torrents at once
* Synchronized analysis shutdown process
* Produce extensive log output
* Save duplicate and timing statistics about peers received via DHT and tracker
* Save statistics about failed and succeeded peer and tracker connections
* Save system statistics and queue lengths for monitoring
* Timeout calibration mode for recording peer message receive duration

### Restrictions
* No support for IPv6 on HTTP, UDP or DHT requests
* No support for the Micro Transport Protocol (µTP)
* No support for Peer exchange (PeX)
* No support for the Tracker exchange extension (BEP 28)
* No support for the BitTorrent Local Tracker Discovery Protocol (BEP 22)
* No support for encrypted peer connections.

## Known Issues
* Despite using the supposedly *scoped\_session* of SQLAlchemy, "database is locked" errors are reported for an unknown reason. This occurs when storing requests or statistics, not when storing peers. The current workaroud is to apply faild SQL statements, which are all recorded in the logfile, to the database afterwards with the `evaluation/sql_from_log.py` script.
* The coude base could use a major refactoring pass. For instane, the starter functions of the analyzer module should be converted in some kind of analysis units as classes with a common interface. 

## Installation
These are the installation steps used in this project, on a Ubuntu 14.04 LTS operating system. Usually matplotlib can also be installed using pip.

    sudo apt-get install python3 python3-pip python3-matplotlib
    sudo pip3 install virtualenv
    virtualenv --python=python3 --system-site-packages ve
    source ve/bin/activate
    pip install bencodepy sqlalchemy geoip2
    deactivate

Download the [GeoLite2 City Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `btda/input/GeoLite2-City.mmdb`.

To handle many incoming connections, the open file descriptor limit may be increased. In `/etc/sysctl.conf` set

    fs.file-max = 1000000

to increase the system wide limit and in `/etc/security/limits.conf` append

    *   hard   nofile   1000000
    *   soft   nofile   1000000

to increase per-user limits. After rebooting, check success with

    cat /proc/sys/fs/file-max
    ulimit -Hn
    ulimit -Sn

## Usage
### pymdh DHT node
First, checkout the [pymdht repository](https://github.com/rauljim/pymdht). To have *pymdht* running in the background, *tmux* can be used.

    ./run_pymdht_node.py --port=17000 --telnet-port=17001

Logs are saved in `~/.pymdht/`. If *pymdht* was already running, make sure it is not crashed meanwhile.

### BitTorrent Download Analyzer
Beware, that peers from earlier evaluations with other torrents may cause unnecessary load on the server. To prevent this, change the used BitTorrent port in the configuration file. The limit of the virtual machine used in this project was about 2,800 simultaneous server threads.

    source ve/bin/activate
    ./main.py -apd

Usage hints can be viewed with flag `-h`. The analysis can be stopped with Ctrl+C. Results are saved in `output/<time_host>.sqlite`. Check if all torrents were imported as expected in the `torrent` table of the database. Check log file with `grep "ERROR\|CRITICAL" <time_host>.log`. Look for unusual errors in the `<time_host>_peer_error.txt` and `<time_host>_tracker_error.txt` outfile. Also, check columns `thread_workload`, `load_average` and `memory_mb` of the `statistic` table in the database with the script `/evaluation/workload.r`.

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License v3
