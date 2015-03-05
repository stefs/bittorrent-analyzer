# bittorrent-analyzer
Bachelor thesis about the analysis of BitTorrent trackers and peers

## Todo
### Next steps
- ! Support incoming connections to include people without an open port
- ! Magnet link support
- Record thread sleeping statistics
- Peer exchange message support
- Evaluate database by merging peers via IP, ISP, Client, maybe bitfields
- Allow socket and SQLAlchemy sessions to close at evaluation termination
- Import Torrent fille(s) in database and start evaluating from there
- Document database needed

### Code quality
- Review logging messages
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
7. Download the [GeoLite2 Country Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `input/GeoLite2-Country.mmdb`

## Usage
1. `source py3env/bin/activate`
2. `./main.py [-h] [-j <number>] [-t <seconds>] [-d <minutes>] [-i <minutes>] [-l <level>] <torrent>`
3. `deactivate`
4. Statistics are saved in `output/` directory as a SQLite database.

### Command Line Arguments:
* `<torrent>`  
  File system path to the torrent file to be examined
* `-h, --help`  
  Show this help message and exit
* `-j <number>, --jobs <number>`  
  Number of threads used for peer connections (default: 1)
* `-t <seconds>, --timeout <seconds>`  
  Timeout in seconds for network connections (default: 10)
* `-d <minutes>, --delay <minutes>`  
  Time delay for revisiting unfinished peers in minutes (default: 10)
* `-i <minutes>, --interval <minutes>`  
  Time delay between asking the tracker server for new peers in minutes, defaults to a value recommended by the tracker server (default: None)
* `-l <level>, --loglevel <level>`  
  Level of detail for log messages (default: INFO)

## License
© Copyright 2015 Stefan Schindler  
Licensed under the GNU General Public License Version 3
