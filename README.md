# bittorrent-analyzer
Bachelor thesis about the analysis of BitTorrent trackers and peers

## TODO
### Next steps
- ! Revisit in progress peers (save time, extract download speed)
- ! Wurde der Download während der Beobachtungszeit abgeschlossen? (Anzahl pieces bei erstem Kontakt in die DB)
- ! Speichere maximale Download Geschwindigkeit zwischen Snapshots
- Make database usage thread safe
- Magnet link support
- Peer exchange message support
- Support incoming connections to include people without an open port
- Add a licence

### Code quality
- Refactor main
- Review logging messages
- Review exception flow
- Review imports
- Review doxygen comments
- Review documentation references
- Compact some statements
- Implement unit tests

## Installation
### Requirements
* Unix-like operating system
* Python 3.4+
* [pip](https://pip.pypa.io/) 1.5+
* [virtualenv](https://virtualenv.pypa.io/) 1.11+
* [BencodePy](https://github.com/eweast/BencodePy) 0.9+
* [SQLAlchemy](http://www.sqlalchemy.org/) 0.9+
* Database <!-- TODO -->
* [GeoIP2 API](https://pypi.python.org/pypi/geoip2) 2.1+

### Steps
These are the standard installation steps on a Debian based system.

1. `sudo apt-get install python3 python3-pip`
2. `sudo pip3 install virtualenv`
3. `virtualenv -p /usr/bin/python3 py3env`
4. `source py3env/bin/activate`
5. `pip install bencodepy sqlalchemy geoip2`
6. `deactivate`
7. Download the [GeoLite2 Country Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `input/GeoLite2-Country.mmdb`

## Usage
1. `source py3env/bin/activate`
2. `./main.py [-h] -f <filename> [-t <seconds>] [-l <level>] [-j <number>]`
3. `deactivate`
4. Statistics are saved in `output/` directory as a SQLite database.

### Command Line Arguments:
* `-h, --help`  
  Show this help message and exit
* `-f <filename>, --file <filename>`  
  Torrent file to be examined
* `-t <seconds>, --timeout <seconds>`  
  Timeout in seconds for network connections
* `-l <level>, --loglevel <level>`  
  Level of detail for log messages
* `-j <number>, --jobs <number>`  
  Number of threads used for peer connections
* `-d <minutes>, --delay <minutes>`  
  Time delay for revisiting unfinished peers in minutes

## Licence
© Copyright 2015 Stefan Schindler  
Licensed under GNU General Public License Version 3
