[TOC]

# BitTorrent Download Analyzer
This tool is aimed at counting confirmed downloads performed via BitTorrent by analyzing its peers. It is part of a Bachelor thesis at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

This is work in progress.

## Todo
### Questions
* Count uploads?
* Minimal libtorrent usage for magent link metadata fetching OK?
* Evaluate database by merging peers via IP, ISP, Client, maybe bitfields?

### Next steps
* ! Accept magnet links (BEP 9, BEP 10)
* ! Statistik mit Grafik in LaTeX mit R (Count downloads within evaluation period)
* ! Gliederung Arbeit, Stichpunkte und Vorüberlegungen aufschreiben
* Save statistics about double received peers and communication failures per peer source
* Tool organization in analyis modules
* Note used torrents with time frame and send to RRZE
* Check name collisions of torrent files and magnet links

### Code quality
* Review logging messages
* Review doxygen comments
* Review documentation references
* Compact some statements
* Implement unit tests?

### Optional steps
* Ergebinsse auf Plausibilität prüfen, Warum keine vollständigen Downloads beobachtet? --> (Reaktion auf Port 0, Statistiken downloaded, uploaded, left) --> Dokumentieren
* Revisit incoming peers?
* Scrape request zum Vergleich
* Peer exchange message support ([AZMP, LTEP](https://wiki.theory.org/BitTorrentPeerExchangeConventions))
* Tracker exchange message support (BEP 28)
* ? Support encrypted peer connections
* ? Pause evaluation on network outage
* (Record active thread sleeping statistics)

## Features
* Import torrent from file (BEP 3) or fetch metadata (BEP 9, BEP 10) via magnet link (BEP 9) using libtorrent
* Continuously get IPv4 peers from the tracker using HTTP (BEP 3) and UDP announce requests (BEP 15)
* Communicate with peers using a subset of the Peer Wire Protocol (BEP 3)
* Continuously get IPv4 peers by integrating a running DHT node (BEP 5) from the *pymdht* project using local telnet
* Actively contact collected peers and calculate minimum number of downloaded pieces by receiving alle *have* and *bitfield* messages until a timeout
* Passively listen for incoming peer connections and calculate minimum number of downloaded pieces analog
* Save number of downloaded pieces from first and last visit and maximum download speed per peer in a SQLite database
* Save city, country and continent via IP address geolocation
* Save ISP by hostname and anonymized IP address
* Analyze multiple torrents at once
* Synchronized analysis shutdown process
* Produce extensive log output

### Restrictions
* No support for IPv6 on HTTP, UDP or DHT requests
* No support for the Micro Transport Protocol (µTP)
* No support for Peer exchange (PeX)
* No support for the Tracker exchange extension (BEP 28)
* No support for the BitTorrent Local Tracker Discovery Protocol (BEP 22)

## Installation
### Requirements
#### BitTorrent Download Analyzer
* Unix-like operating system
* Python 3.4+
* [pip](https://pip.pypa.io/) 1.5+
* [virtualenv](https://virtualenv.pypa.io/) 1.11+
* [BencodePy](https://github.com/eweast/BencodePy) 0.9+
* [SQLAlchemy](http://www.sqlalchemy.org/) 0.9+
* Database
* [GeoIP2 API](https://pypi.python.org/pypi/geoip2) 2.1+
* libtorrent

#### Mainline DHT node
* [pymdht](https://github.com/rauljim/pymdht) with patches

#### Statistical evaluation
* r-base

### Steps
These are the standard installation steps on a Debian based system.

1. `sudo apt-get install python3 python3-pip python3-libtorrent`
2. `sudo pip3 install virtualenv`
3. `virtualenv --python=/usr/bin/python3 --system-site-packages env-main`
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
2. `./run_pymdht_node.py -p 17000 --telnet-port=17001`
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
