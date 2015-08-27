# Analysis of BitTorrent Trackers and Peers
## Progress
★ first pass / ★★ good / ★★★ ready

Chapter | Progress
--- | ---
[Abstract](https://www.ece.cmu.edu/~koopman/essays/abstract.html) |
1 Introduction | ★★★
– 1.1 Motivation | ★★★
– 1.2 Task | ★★★
– 1.3 Related Work | ★★★
– 1.4 Results |
– 1.5 Outline |
– 1.6 Acknowledgments | ★★★
2 Background | ★★★
– 2.1 BitTorrent Protocol | ★★★
– 2.1.1 Bencoding | ★★★
– 2.1.2 Metainfo File | ★★★
– 2.1.3 Tracker Server | ★★★
– 2.1.4 UDP Tracker Protocol | ★★★
– 2.1.5 Peer Wire Protocol | ★★★
– 2.2 DHT Protocol | ★★★
– 2.3 Magnet Link | ★★★
– 2.3.1 Extension Protocol | ★★★
– 2.3.2 Extension for Peers to Send Metadata Files | ★★★
– 2.4 BitTorrent and German Law | ★★★
– 2.4.1 Illegal Content | ★★★
– 2.4.2 Collecting IP addresses | ★★★
3 Implementation | ★★★
– 3.1 Dependencies | ★★★
– 3.2 Architecture | ★★ (read)
– 3.3 Functionality | ★★
– 3.3.1 Import Torrents | ★★
– 3.3.2 Requesting Peers | ★★
– 3.3.3 Contact Peers | ★★
– 3.3.4 Extracting the Download Progress | ★★
– 3.3.5 Peer Database| ★
– 3.3.6 Secondary Statistics | ★
– 3.4 Justification of Configuration Values |
– 3.5 Restrictions |
4 Evaluation | ★
– 4.1 Choosing Torrents | ★★
– 4.2 Getting Addresses of Peers | ★
– 4.3 Counting Confirmed Downloads |
– 4.3.1 Problems of this Method |
– 4.4 Further Analysis of Peers |
– 4.4.1 Download Speed |
– 4.4.2 BitTorrent Clients |
– 4.4.3 Peer's Host Names |
5 Conclusion and Future Work |

# Todo
* Compare length with [other](https://www1.cs.fau.de/staff/gruhn)
* table scheme
* Quantify incoming peers in table `unique-peers` and request history plots
- change the title to subtitle?
- github history ok?
- cite bep 20, bep 29
- add or remove links from bibliography
- http scrape in chapter 2?
- Roter faden/ einfaches lesen.
* Alle Abkürzungne einführen, evtl. Abkverzeichnis
* wherby komisch
* Min 24 h laufzeit

# Begriffserklärung or in place erklärung
* Dictionary
* Cryptographic hash
* Leecher / Seeder / Peer

# Time Table
* **27.8.:** Test Auswergung, Sec Architecture +++, sec Config ++
* **28.8.:** Config +++, Restrictions ++, Auswertung
* **29.8.:** Restrictions +++, Evaluation ++
* **30.8.:** Evaluation +++, Results++, Conclusion++
* **31.8.:** Results+++, Conclusion++ Abstract ++, Outline ++
* **1.9.:** Abstract +++, Outline +++, Todos
* **2.9.:** Tidy readme, Print thesis, burn CD
* **3.9.:** (unklar)

## Resourcces BitTorrent
* http://www.bittorrent.org/beps/bep_0000.html
* https://en.wikipedia.org/wiki/Date_and_time_notation_in_the_United_States
* https://en.wikipedia.org/wiki/Date_and_time_notation_in_the_United_Kingdom
* https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Dates_and_numbers#Dates.2C_months_and_years
* https://wiki.theory.org/BitTorrentSpecification
* http://people.kth.se/~rauljc/p2p11/
