# bittorrent-analyzer
Bachelor thesis about the analysis of BitTorrent trackers and peers

## Requirements
* Unix-like operating system
* Python 3.4+
* [pip](https://pip.pypa.io/) 1.5+
* [virtualenv](https://virtualenv.pypa.io/) 1.11+
* [BencodePy](https://github.com/eweast/BencodePy) 0.9+
* [SQLAlchemy](http://www.sqlalchemy.org/) 0.9+
* [GeoIP2 API](https://pypi.python.org/pypi/geoip2) 2.1+
* [GeoLite2 Country Database](http://dev.maxmind.com/geoip/geoip2/geolite2/)

## Installation
These steps describe standard installation steps on a Debian based system.

1. `sudo apt-get install python3 python3-pip`
2. `sudo pip3 install virtualenv`
3. `virtualenv -p /usr/bin/python3 py3env`
4. `source py3env/bin/activate`
5. `pip install bencodepy sqlalchemy geoip2`
6. `deactivate`
7. Download the [GeoLite2 Country Database](http://dev.maxmind.com/geoip/geoip2/geolite2/#Downloads) and place it at `./input/GeoLite2-Country.mmdb`

## Usage
1. `source py3env/bin/activate`
2. `./main.py [-h] -f <filename> [-t <seconds>] [-l <level>] [-j <number>]`
3. `deactivate`
4. Statistics are saved in `./output/` directory as a SQLite database.

### Command Line Arguments:
* `-h, --help`  
show this help message and exit
* `-f <filename>, --file <filename>`  
Torrent file to be examined
* `-t <seconds>, --timeout <seconds>`  
Timeout in seconds for network connections
* `-l <level>, --loglevel <level>`  
Level of detail for log messages
* `-j <number>, --jobs <number>`  
Number of threads used for peer connections

## Licence
All rights reserved. This is subject to change.
