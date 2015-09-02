# Analysis of BitTorrent Trackers and Peers
## Abstract
...

## Todo
* Quantify incoming peers in table `unique-peers` and request history plots
* http scrape in chapter 2?
* Alle Abkürzungne einführen, evtl. Abkverzeichnis
* Min 24 h laufzeit
* Send Torrents to RRZE
* ggplot2 plots 9 inch width
* Mention every logarithmic axis
* Explain in the beginning, why a threshold is used: 1. Exclude leechers, 2. Count in short range.

### New Data
* Check figures
* Check tables
* Check in text data
* Check discussion

### Final Reading
* Roter faden/ einfaches lesen.
* Begriffserklärung or in place: Dictionary, Cryptographic hash, Leecher / Seeder / Peer, NAT, ISP
* Explain all abbreviations
* No wherby
* New fact: [Mainline DHT](https://en.wikipedia.org/wiki/Mainline_DHT)
* New fact: Discard incoming peers, when they were actively contacted before, to prevent double counting
* Check bibliography file for errors, add or remove links
* Check spelling with automatic tool

### Time Table
Today | Date | Task | Done
--- | --- | --- | ---
  | 27.8. | | test evaluation, Architecture, Functionallity, Config
  | 28.8. | evaluation | Architecture, Functionallity, Config, Restrictions
  | 29.8. | Evaluation ++ | (strange tracker scrape, noticable unique tracker peers)
  | 30.8. | Evaluation +++, Results++, Conclusion++
  | 31.8. | Results+++, Conclusion++ Abstract ++, Outline ++
  |  1.9. | Abstract +++, Outline +++, Todos
→ |  2.9. | Tidy readme, Print thesis, burn CD
  |  3.9. | (unklar)

### Progress
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
3 Implementation | ★★★
4 Evaluation | ★★★
– 4.1 Choosing Torrents | ★★★
– 4.2 Getting Addresses of Peers | ★★★
– 4.3 Counting Confirmed Downloads | ★★★
– 4.4 Problems | ★★★
– 4.5 Further Analysis of Peers |
– 4.5.1 Download Speed | ★★
– 4.5.3 Peer's Host Names | ★★
5 Conclusion and Future Work |
