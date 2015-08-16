[TOC]

# BitTorrent Download Analyzer
This tool is aimed at counting confirmed downloads performed via BitTorrent by analyzing its peers. It is part of a Bachelor thesis at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

This is work in progress.

## Todo
* ! **FIXME:** database is locked error ([see](output/2015-05-13_16-03-21_faui1-246_crit.log)), bad peer objects in queue
* ! Note used torrents with time frame and send to RRZE
* Reduce peer_revisit_delay to 3 min, review thread workload
* ducument missing tracker requests
* Probably interesting: 2015-07-18_21-57-15_faui1-246.sqlite

### Code quality
* Review logging messages
* Review doxygen comments
* Review documentation references
* Unit tests
* Tool organization in analyis modules

### Optional
* Ergebinsse auf Plausibilität prüfen
    * Warum keine vollständigen Downloads beobachtet?
    * --> (Reaktion auf Port 0, Statistiken downloaded, uploaded, left)
    * --> Dokumentieren
* Revisit incoming peers? No.
* Peer exchange message support ([AZMP, LTEP](https://wiki.theory.org/BitTorrentPeerExchangeConventions)) No.
* Tracker exchange message support (BEP 28) No.
* Support encrypted peer connections. No.
* Pause evaluation on network outage. No.

## Features
* Import torrents from `.torrent` files (BEP 3)
* Import torrents form magnet links by fetching metadata via the *ut_metadata* extension (BEP 9) using the Extension Protocol (BEP 10)
* Continuously get IPv4 peers and scrape information from the tracker using HTTP (BEP 3) and UDP announce requests (BEP 15)
* Communicate with peers using a subset of the Peer Wire Protocol (BEP 3)
* Continuously get IPv4 peers by integrating a running DHT node (BEP 5) from the *pymdht* project using local telnet
* Actively contact collected peers and calculate minimum number of downloaded pieces by receiving all *have* and *bitfield* messages until a timeout
* Reconnect to peers until they have downloaded a defined threshold
* Passively listen for incoming peer connections and calculate minimum number of downloaded pieces analog
* Save number of downloaded pieces from first and last visit and maximum download speed per peer in a SQLite database
* Save city, country and continent via IP address geolocation
* Save ISP by hostname and anonymized IP address
* Analyze multiple torrents at once
* Synchronized analysis shutdown process
* Produce extensive log output
* Save duplicate and timing statistics about peers received via DHT and tracker
* Save statistics about failed and succeeded peer connections
* Save workload statistics of active peer evaluation threads
* Timeout calibration mode for recording peer message receive duration

### Restrictions
* No support for IPv6 on HTTP, UDP or DHT requests
* No support for the Micro Transport Protocol (µTP)
* No support for Peer exchange (PeX)
* No support for the Tracker exchange extension (BEP 28)
* No support for the BitTorrent Local Tracker Discovery Protocol (BEP 22)
* No analysis of peer upload behaviour
* Only one tracker server per torrent is supported

## Installation
### Requirements
#### BitTorrent Download Analyzer
* Unix-like operating system
* Python 3.4+
* [pip](https://pip.pypa.io/) 1.5+
* [virtualenv](https://virtualenv.pypa.io/) 1.11+
* [BencodePy](https://github.com/eweast/BencodePy) 0.9+
* [SQLAlchemy](http://www.sqlalchemy.org/) 1.0+
* Database SQLite
* [GeoIP2 API](https://pypi.python.org/pypi/geoip2) 2.1+

#### Mainline DHT node
* [pymdht](https://github.com/rauljim/pymdht) with patches

### Steps
These are the installation steps used in this project, on a Ubuntu 14.04 LTS operating system. Usually matplotlib can also be installed using pip.

    sudo apt-get install python3 python3-pip python3-matplotlib
    sudo pip3 install virtualenv
    virtualenv --python=python3 --system-site-packages env-main
    source env-main/bin/activate
    pip install bencodepy sqlalchemy geoip2
    deactivate

Finally, download the [GeoLite2 City Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `btda/input/GeoLite2-City.mmdb`

## Usage
### Start pymdh DHT node
1. `tmux new-session -s pymdht`
2. `./run_pymdht_node.py --port=17000 --telnet-port=17001`
3. Tmux detach with `Ctrl+B` followed by `d`

Logs are saved in `~/.pymdht/`. If this step is skipped, make sure pymdht still works as expected!

### Start bittorrent-analyzer peer evaluation
1. `tmux new-session -s btda`
2. `source env-main/bin/activate`
3. `btda/main.py`
4. Tmux detach with `Ctrl+B` followed by `d`

Logs are saved in `output/`.

### End bittorrent-analyzer
1. `tmux attach-session -t btda`
2. Stop program with Ctrl+C
3. `deactivate`

Results are saved in `output/`.

### End pymdht
1. `telnet localhost 17001`
2. Type `KILL\n`

## About
### Thanks to
* ..., advisor
* Erin Drummond, for *[m2t](https://github.com/erindru/m2t/tree/75b457e65d71b0c42afdc924750448c4aaeefa0b)* under GPLv3
* pymdht

### Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License Version 3
