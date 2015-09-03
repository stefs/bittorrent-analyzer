# Database Evaluation with R
## Installation
    sudo apt-get install r-base r-cran-dbi r-cran-rsqlite r-cran-ggplot2 r-cran-reshape

Since the `r-cran-rsqlite` is broken in Debian Jessie, an alternative version can be installed as follows:

    sudo R
    install.packages("RSQLite")

## Usage
Scripts can be invoked using

    ./<script.r> <database.sqlite>

except `source.r`, which can render plots for the "sum" of all torrents or for "each" torrent:

    ./source.r <which_torrents> <database.sqlite>

Other special scripts are:

    ./tracker_error.r <file_tracker_error.txt>
    ./threshold.r <file_threshold.csv> # file created manually

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the GNU General Public License v3
