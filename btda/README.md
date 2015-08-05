[TOC]

* Measure timeout on connection establishment
* Reduce peer_revisit_delay to 3 min, review thread workload
* Remove ip and peerid from db
* ducument missing tracker requests

# BitTorrent Download Analyzer
This tool is aimed at counting confirmed downloads performed via BitTorrent by analyzing its peers. It is part of a Bachelor thesis at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

This is work in progress.

### Questions
* Evaluate database by merging peers via IP, ISP, Client, maybe bitfields?
* Compare results with tracker scrape requests? - optional

### Next steps
* ! Statistik mit Grafik in LaTeX mit R
* ! Write thesis text
    * Hardwaredaten der VM notieren
    * Counting transition from leecher to seeder (~98%)
    * Justify config values
* ! **FIXME:** database is locked error ([see](output/2015-05-13_16-03-21_faui1-246_crit.log)), bad peer objects in queue
* ! Note used torrents with time frame and send to RRZE
* Tidy readme: Requirements, installation, usage, thanks
* (Tool organization in analyis modules)

### Code quality
* Review logging messages
* Review doxygen comments
* Review documentation references
* Implement unit tests? How about no.

### Optional steps
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

### Restrictions
* No support for IPv6 on HTTP, UDP or DHT requests
* No support for the Micro Transport Protocol (µTP)
* No support for Peer exchange (PeX)
* No support for the Tracker exchange extension (BEP 28)
* No support for the BitTorrent Local Tracker Discovery Protocol (BEP 22)
* No analysis of peer upload behaviour

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

#### Statistical evaluation
* r-base

### Steps
These are the standard installation steps on a Debian based system.

1. `sudo apt-get install python3 python3-pip`
2. `sudo pip3 install virtualenv`
3. `virtualenv --python=python3 env-main`
4. `source env-main/bin/activate`
5. `pip install bencodepy sqlalchemy geoip2`
6. `deactivate`
7. Download the [GeoLite2 City Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `input/GeoLite2-City.mmdb`

R

1. `sudo R`
2. install.packages("DBI")
3. install.packages("RSQLite")

## Usage
### Start pymdh DHT node
1. `tmux new-session -s pymdht`
2. `./run_pymdht_node.py --port=17000 --telnet-port=17001`
3. Tmux detach with `Ctrl+B` followed by `d`

Logs are saved in `~/.pymdht/`. If this step is skipped, make sure pymdht still works as expected!

### Start bittorrent-analyzer peer evaluation
1. `tmux new-session -s btda`
2. `source env-main/bin/activate`
3. `./main.py`
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
