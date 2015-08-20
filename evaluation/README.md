# Database Evaluation with R
## Installation
    sudo apt-get install r-base r-cran-dbi r-cran-rsqlite

## Usage
`download.r <file.sqlite>`
:   Compile number or confirmed downloads and scrape download numbers from tracker. Threshold is independend from data collection phase.

`source.r <file.sqlite>`
:   Plot received peers from DHT network and tracker server, distinguishing unique and duplicate peers. Includes successful evaluated incoming peers.

## Resources
* [ggplot2: Changing the Default Order of Legend Labels and Stacking of Data | Learning R](https://learnr.wordpress.com/2010/03/23/ggplot2-changing-the-default-order-of-legend-labels-and-stacking-of-data/)

## Why not to use R
* Errors without line numbers
* Bad documentation
* Implicit dimension reduction

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License v3
