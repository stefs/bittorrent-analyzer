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
2 Background | ★★
– 2.1 BitTorrent Protocol | ★★
– 2.1.1 Bencoding | ★
– 2.1.2 Metainfo File | ★
– 2.1.3 Tracker Server | ★
– 2.1.4 UDP Tracker Protocol | ★
– 2.1.5 Peer Wire Protocol | ★
– 2.2 DHT Protocol | ★
– 2.3 Magnet Link +2 | ★
– 2.4 BitTorrent and German Law +2 | ★★
3 Implementation | ★★
– 3.1 Dependencies | ★★
– 3.2 Functionality | ★★
– 3.3 Architecture |
– 3.4 Justification of Configuration Values |
– 3.5 Restrictions |
– 3.6 Usage |
4 Evaluation | ★
– 4.1 Choosing Torrents | ★★
– 4.2 Getting Addresses of Peers +1 | ★
– 4.3 Counting Confirmed Downloads +1 |
– 4.4 Peer Analysis |
5 Conclusion and Future Work |

# Todo
* Compare length with [other](https://www1.cs.fau.de/staff/gruhn)
* table scheme
* Quantify incoming peers in table `unique-peers` and request history plots
- change the title to subtitle?
- github history ok?
- cite bep 20, bep 29
- add or remove links from bibliography

# Begriffserklärung or in place erklärung
* Dictionary
* Cryptographic hash
* Leecher / Seeder / Peer

## Hinweise 2015-07-17
→ Siehe gedruckte PDF-Notizen!

Mündliche Hinweise:

> revisit delay verkleinern --> veränderung
> gb in diagramm --> verhältnis scrape vs confirmed
>
> michael mit drauf
> keine ein-Zeien Absätze--> Roter Fadden
>
> Bencode bsp
> grafik /bsp torent file
> Alle Abkürzungne einführen, evtl. Abkverzeichnis
> self weglassen
> wherby komisch
> Absatz zwischen tracker Antwort geht unter
> Aprupter übergang UDP connect, vllt Diagramm oder Ankündigung
>
> dht protocol graphiken
>
> torrent ominimal size nicht uri
>
> Ausführlicher, mehr Text für einfachem Folgen, BitTorrent Kapitel besonders wirr
>
> Warum Verwendung von Schwellwert? Erklären begründen oder verweisen auf Auswertung (negative Differenz)
>
> Plots: Karten
>
> Mehr Torrents
>
> Min 24 h laufzeit
>
> scrape values am Ende
> Abstract

## Resourcces BitTorrent
* http://www.bittorrent.org/beps/bep_0000.html
* https://en.wikipedia.org/wiki/Date_and_time_notation_in_the_United_States
* https://en.wikipedia.org/wiki/Date_and_time_notation_in_the_United_Kingdom
* https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Dates_and_numbers#Dates.2C_months_and_years
* https://wiki.theory.org/BitTorrentSpecification
* http://people.kth.se/~rauljc/p2p11/
