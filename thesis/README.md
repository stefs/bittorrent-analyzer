# Analysis of BitTorrent Trackers and Peers
## Abstract
BitTorrent is the most used technology for file sharing to date and discussed to damage the creative industry. However, due to its distributed structure the extent of downloaded copies can only be estimated. The common method is to collect all IP addresses of a torrent swarm by issuing scrape and announce requests to tracker servers. After testing their reachability, this number is used as an estimation of downloads, but falsely includes peers who did not finish the download. This thesis will extend this method by contacting each peer continuously and learning the download progress through the BitTorrent protocol. A tool was written to do this after collecting addresses from trackers and the DHT network, and accepting incoming connections. A confirmed download was registered when a peer crossed the threshold of 98 %. For small and large torrents respectively, between 9 % and 55 % of the downloads reported by the main trackers in scrape responses could be confirmed over 34 hours and 19 torrents. For less than 2 % of unique peer addresses a download was confirmed. Often subsequent progress evaluations of peers failed, which lowers this numbers significantly. Further adjustments to the used implementation are necessary to obtain better results.

## Todo
0. Finalize
    0. Erklären: Leecher, Seeder, Peer
    0. Check bibliography file for errors, add or remove links
0. Final Reading
    0. Roter faden, einfaches lesen
    0. Explainen all abbreviations?
    0. No wherby
    0. New fact: [Mainline DHT](https://en.wikipedia.org/wiki/Mainline_DHT)
    0. New fact: Discard incoming peers, when they were actively contacted before, to prevent double counting
0. Production
    0. Print 2 times
    0. Tidy Readmes
    0. Burn 2 CDs
0. Other
    0. Send Torrents to RRZE

## Progress
★ first pass / ★★ good / ★★★ ready

Chapter | Progress
--- | ---
Abstract | ★★
1 Introduction | ★★★
– 1.1 Motivation | ★★★
– 1.2 Task | ★★★
– 1.3 Related Work | ★★★
– 1.4 Results | ★★
– 1.5 Outline | ★★
– 1.6 Acknowledgments | ★★★
2 Background | ★★★
3 Implementation | ★★★
4 Evaluation | ★★★
5 Conclusion and Future Work | ★★
