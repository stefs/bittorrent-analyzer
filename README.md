# Analysis of BitTorrent Trackers and Peers
Work in progress.

This is a Bachelor thesis written at the Friedrich-Alexander-Universität Erlangen-Nürnberg.

[BitTorrent Download Analyzer](btda/)
:   Software tool written in Python 3 which is able to count confirmed downloads in a BitTorrent swarm.

[Evaluation scripts](evaluation/)
:   Create diagrams from the SQLite database using the R programming language.

[Bachelor thesis](thesis/)
:   Extensive text containing an intruductino into the subject, background information about the BitTorrent technology, implementation details about the software tool, evaluation of research results and a conclusion on the topic.

## Current Task
* Get torrent plots on one page
    * How many torrents are analyzed?
    * FIXED - Shorten timestamp in R with strftime()
    * WONTFIX - Legend is shown n times per page
    * WONTFIX - Make script for getting plot on one page
    * Implement torrent description generator in Python