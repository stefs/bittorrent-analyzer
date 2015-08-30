# Database Evaluation with R
## Installation
    sudo apt-get install r-base r-cran-dbi r-cran-rsqlite r-cran-ggplot2 r-cran-reshape

Since the `r-cran-rsqlite` is broken in Debian Jessie, an alternative version can be installed as follows:

    sudo R
    install.packages("RSQLite")

## Usage
`./download_per_set.r "<torrent_set>" <file.sqlite>`
:   Compile number or confirmed downloads and scrape download numbers from tracker. Threshold is independend from data collection phase. *torrent\_set* refers to the torrent id in the database and must be of the form `(1,2,3,4)`.

`./source.r <mode> <file.sqlite>`
:   Plot received peers from DHT network and tracker server, distinguishing unique and duplicate peers. Includes successful evaluated incoming peers. If *mode* is "sum", a summary for all torrents will be plotted. If *mode* is "torrent", the source is plottet for every single torrent.

`cat combine.sql | sqlite3 | sqlite3 <combined.sqlite>`
:   Combine databases from two analysis passes. Used, because analysis was performed on different VMs for performance reasons. Input database filenames are in-code parameters.

## Why not to use R
* Errors without line numbers
* Very incomplete documentation
* Implicit dimension reduction on data types
* `function(variable) <- assignment`
* In `function(dataframe, column)`, `column` may refer to `dataframe$column` implicitly
* Data types not distinguishable when using `print()`, one has to use `typeof()` and `class()`

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License v3
