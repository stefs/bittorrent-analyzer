# BitTorrent Download Analyzer
This tool is aimed at counting confirmed downloads performed via BitTorrent by analyzing its peers. It is part of a Bachelor thesis at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

## Todo
### Next steps
* ! Accept magnet links (partial BEP 9)
* ! Ergebinsse auf Plausibilität prüfen, Warum keine vollständigen Downloads beobachtet?  
    --> (Reaktion auf Port 0, Statistiken downloaded, uploaded, left) --> Dokumentieren
* ! More tests on VM
* ! Search peers via IPv4 DHT (BEP 5) and IPv6 DHT (BEP 32)

### Later steps
* Scrape request zum Vergleich
* Peer exchange message support ([AZMP, LTEP](https://wiki.theory.org/BitTorrentPeerExchangeConventions))
* Tracker exchange message support (BEP 28)
* Evaluate database by merging peers via IP, ISP, Client, maybe bitfields
* Import Torrent file(s) in database and start evaluating from there (incl. file name, name collissions!)
* ? Support encrypted peer connections
* ? Pause evaluation on network outage
* (Record active thread sleeping statistics)
* (Document database needed)

### Code quality
* Review logging messages
* Review doxygen comments
* Review documentation references
* Compact some statements
* Implement unit tests?

## Features
* Import multiple torrent files at once
* Log city, countra and continent via IP address - NEW
* Request new peers using the HTTP and UDP (BEP 15) tracker protocols, IPv4 only - NEW
* (list incomplete)

## Installation
### Requirements
* Unix-like operating system
* Python 3.4+
* [pip](https://pip.pypa.io/) 1.5+
* [virtualenv](https://virtualenv.pypa.io/) 1.11+
* [BencodePy](https://github.com/eweast/BencodePy) 0.9+
* [SQLAlchemy](http://www.sqlalchemy.org/) 0.9+
* Database
* [GeoIP2 API](https://pypi.python.org/pypi/geoip2) 2.1+

### Steps
These are the standard installation steps on a Debian based system.

1. `sudo apt-get install python3 python3-pip`
2. `sudo pip3 install virtualenv`
3. `virtualenv -p /usr/bin/python3 py3env`
4. `source py3env/bin/activate`
5. `pip install bencodepy sqlalchemy geoip2`
6. `deactivate`
7. Download the [GeoLite2 City Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `input/GeoLite2-City.mmdb`

## Usage
1. Place torrent files in the `input/` directory.
2. `source py3env/bin/activate`
3. `./main.py [-h] [-j <number>] [-p <port>] [-t <seconds>] [-d <minutes>] [-i <minutes>] [-l <level>] <torrent>`
4. `deactivate`
5. Logs and results are saved in the `output/` directory.

The following commandline options are available:

* `<torrent>`  
  File system path to the torrent file to be examined
* `-h, --help`  
  Show this help message and exit
* `-j <number>, --jobs <number>`  
  Active peer evaluation using the specified number of threads (default: None)
* `-p <port>, --port <port>`  
  Passive peer evaluation of incoming peers at the specified port number (default: None)
* `-t <seconds>, --timeout <seconds>`  
  Timeout in seconds for network connections (default: 10)
* `-d <minutes>, --delay <minutes>`  
  Time delay for revisiting unfinished peers in minutes (default: 10)
* `-i <minutes>, --interval <minutes>`  
  Time delay between asking the tracker server for new peers in minutes, defaults to a value recommended by the tracker server (default: None)
* `-l <level>, --loglevel <level>`  
  Level of detail for log messages (default: INFO)

## About
### Thanks to
* ..., advisor
* Erin Drummond, for *[m2t](https://github.com/erindru/m2t/tree/75b457e65d71b0c42afdc924750448c4aaeefa0b)* under GPLv3

### Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License Version 3

