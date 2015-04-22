[TOC]

# BitTorrent Download Analyzer
This tool is aimed at counting confirmed downloads performed via BitTorrent by analyzing its peers. It is part of a Bachelor thesis at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

## Todo
### Next steps
* ! Accept magnet links (BEP 9, BEP 10)
* ! Statistik mit Grafik in LaTeX mit R (Count downloads within evaluation period)
* ! Gliederung Arbeit, Stichpunkte und Vorüberlegungen aufschreiben

* Ergebinsse auf Plausibilität prüfen, Warum keine vollständigen Downloads beobachtet?  
    --> (Reaktion auf Port 0, Statistiken downloaded, uploaded, left) --> Dokumentieren
* Revisit incoming peers?

### Later steps
* Scrape request zum Vergleich
* Peer exchange message support ([AZMP, LTEP](https://wiki.theory.org/BitTorrentPeerExchangeConventions))
* Tracker exchange message support (BEP 28)
* Evaluate database by merging peers via IP, ISP, Client, maybe bitfields (programming language R)
* Import Torrent file(s) in database and start evaluating from there (incl. file name, name collissions!)
* ? Support encrypted peer connections
* ? Pause evaluation on network outage
* (Multiple torrent support for passive evaluation)
* (Record active thread sleeping statistics)
* (Document database needed)
* (Use start-stop-daemon?)

### Code quality
* Review logging messages
* Review doxygen comments
* Review documentation references
* Compact some statements
* Implement unit tests?

## Features
* Analyze multiple torrent files at once
* Log city, country and continent via IP address
* Request new IPv4 peers using the HTTP and UDP tracker protocols (BEP 15)
* Integrate a running pymdht DHT node via telnet by sending PORT messages and performing peer lookups - NEW
* Perform IPv4 DHT (BEP 5) requests to a pymdht DHT node through telnet
* (list incomplete)

### Restrictions
* No IPv6 only peers
* No uTP only peers
* No PEX
* No IPv6 DHT (BEP 32)
* No Local Peer Discovery

## Requirements
### BitTorrent Download Analyzer
* Unix-like operating system
* Python 3.4+
* [pip](https://pip.pypa.io/) 1.5+
* [virtualenv](https://virtualenv.pypa.io/) 1.11+
* [BencodePy](https://github.com/eweast/BencodePy) 0.9+
* [SQLAlchemy](http://www.sqlalchemy.org/) 0.9+
* Database
* [GeoIP2 API](https://pypi.python.org/pypi/geoip2) 2.1+
* libtorrent

### Mainline DHT node
* [pymdht](https://github.com/rauljim/pymdht) with patches

### Statistical evaluation
* r-base

## Installation
### Steps
These are the standard installation steps on a Debian based system.

1. `sudo apt-get install python3 python3-pip`
2. `sudo pip3 install virtualenv`
3. `virtualenv -p /usr/bin/python3 env-main`
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
1. `tmux new-session -s bta`
2. `source env-main/bin/activate`
3. `./main.py`
4. Tmux detach with `Ctrl+B` followed by `d`

Logs are saved in `output/`.

### End bittorrent-analyzer
1. `tmux attach-session -t bta`
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
