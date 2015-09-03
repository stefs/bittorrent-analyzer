# Analysis of BitTorrent Trackers and Peers
## Counting Confirmed Downloads in BitTorrent
**Abstract**

BitTorrent is the most used technology for file sharing to date and discussed to damage the creative industry. However, due to its distributed structure the extent of downloaded copies can only be estimated. The common method is to collect all IP addresses of a torrent swarm by issuing scrape and announce requests to tracker servers. After testing their reachability, this number is used as an estimation of downloads, but falsely includes peers who did not finish the download. This thesis will extend this method by contacting each peer continuously and learning the download progress through the BitTorrent protocol. A tool was written to do this after collecting addresses from trackers and the DHT network, and accepting incoming connections. A confirmed download was registered when a peer crossed the threshold of 98 %. For small and large torrents respectively, between 9 % and 55 % of the downloads reported by the main trackers in scrape responses could be confirmed over 34 hours and 19 torrents. For less than 2 % of unique peer addresses a download was confirmed. Often subsequent progress evaluations of peers failed, which lowers this numbers significantly. Further adjustments to the used implementation are necessary to obtain better results.

## Copyright
Copyright © 2015 Stefan Schindler  
Licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/)
