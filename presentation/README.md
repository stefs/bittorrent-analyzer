# Präsentation
> **Note:** The presentation is only available in German.

* In deutscher Sprache
* 30 Minuten
* Keine Vorkenntnisse über BitTorrent oder die Arbeit

## Todo
### Zeitplan
* **5.10.:** 1 Folie
* **6.10.:** —
* **7.10.:** 7 Folien
* **8.10.:** —
* **9.10.:** —
* **10.10.:** 4 Folien, Überarbeitungen
* **→ 11.10.:** Vortrag üben
* **12.10.:** Vortrag üben
* **13.10.:** Vortrag um 15:00 Uhr

## Miscellaneous
* Swap Page Up / Page Down:  
  `xmodmap -e "keysym Prior = Next" -e "keysym Next = Prior"`
* Test keyboard events:  
  `xev`

## Vortragsnotizen
0. **Titel:** "In meiner Bachelor-Arbeit geht es um das Zählen von bestätigten
   Downloads in BitTorrent."  
   **Bisher:** Nur Sammlung von IP-Adressen, evtl. Ping ob erreichbar, Peers
   mit kurzem Beitritt ohne Abschließen mitgezählt  
   **Erweiterung:** Verbindung mit BitTorrent-Protokoll herstellen,
   Download-Fortschritt feststellen, leider nicht so gut funktioniert

0. **BitTorrent:** Grundlagen, Torrent-Datei, Peers finden mit Tracker-Server,
   Peer-Kommunikation, DHT wofür/wie  
   **BTDA:** Funktion, welche Daten, Einschränkungen  
   **Ergebnis:** Gezählte Downloads, Statistiken zu Herkunftsländern anhand IP

0. ----- FUNKTIONSWEISE VON BITTORRENT -----

0. **Segmente:** Beliebige Reihenfolge und Absender, verlässlich bei schlechter
   Verbindung  
   **P2P:** dezentral, keine Hostingkosten  
   **SHA-1:** robust gegen Übertragungsfehler, Angriffe bösartiger Peers mit
   falschen Daten

0. **Begrenzung:** Kleinbuchstaben  
   **String:** Zahlen in ASCII, auch Bytestring  
   **Dicts:** Strings als Dict-Keys  
   **Einfache/zusammengesetzte Typen:** eindeutige Länge durch Präfix/
   Buchstaben  
   **Beispiel:** Gültige Torrent-Datei im Einzeldatei-Modus, Keys
   hervorgehoben, Geschachtelte Dicts  
   **Metainfo:** `length` = Dateigröße, `pieces` = 20 Byte SHA-1, Infohash =
   Hash des info-Dicts

0. **Peer-ID:** Wiedererkennung von Tracker/geänderter IP, unwichtig  
   **Antwort:** Bencodete Liste von Dicts mit IPs und Ports  
   **UDP:** 50% Einsparung, wenige Datagramme

0. **choke/interested:** Bereitschaft Anfragen zu beantworten bzw. Interesse an
   `unchoke`

0. **DHT:** Um sich Tracker-Server zu sparen (Ausfallsicherheit, Kosten)  
   **ID:** Im gleichen Adressraum wie Infohash, Interpretation als *unsigned
   integer*  
   (Magnet-Links nicht erwähnen)

0. ----- BITTORRENT DOWNLOAD ANALYZER -----

0. **Adressen:** Abfrage alle 5 Minuten, 200 Peers pro UDP-Abfrage, DHT 100-
   1300  
   **Fortschritt:** Client sendet nach BitTorrent-Protokoll *bitfield*/*have*
   nach Verbindungsaufbau  
   **Schema Peer-Tabelle:** Segmente erster/letzter Besuch, Zeitstempel,
   IP-Adressen-basierte Ortsangabe  
   **Threshold:** Relativ egal

0. **IPv6:** 2011 unter 4%  
   **PEX/TEX:** Eher bei kleinen Torrents von Bedeutung  
   **Azureus:** Wesentlich kleinere Nutzerbasis

0. ----- AUSWERTUNG -----

0. **Duplikate:** Quelle ausgeschöpft  
   **Eingehend:** Nur erfolgreich ausgewertete  
   **Spitze:** Alle Peers zu diesem Zeitpunkt, Start 18:40 UTC  
   **Konstant:** Neue Peers während der Analyse

0. **Scrape:** Nur von Haupt-Tracker, daher evtl. zu niedrig  
   **Peers:** Entält Seeder und falsche Adressen, daher evtl. zu hoch  

0. **Besätigt:** Zeitstempel bei erstem Kontakt  
   **Scrape:** Hoch bei jeweils 19 Uhr UTC

0. **Zweitversuch:** 15% Erfolg, 85% Misserfolg  
   **Ursache:** Keine Wiederholung nach (temporärem) Fehler, Peer Blacklist
   weil keine Daten, Peer ausgelastet  
   **Verbesserung:** Erneuter Versuch nach Verzögerung, Verhalten von Clients
   untersuchen

0. **Methode:** Differenz im Download-Fortschritt zwischen zwei Versuchen,
   Maximum aus allen Differenzen  
   **Logarithmische** Skala  
   **Verteilung:** BitTorrent überall genutzt, beachte Einwohnerzahlen  
   **Maximum:** USA, Russland, Philippinen, Vereinigtes Königreich, Südkorea

0. **Weiß:** Nur Länder ab 50 Peers  
   **Median:** Meistens um die 100 kB/s  
   **10 MB/s:** China, Trinidad und Tobago

0. **Zusammenfassung:** Fazit, Ausblick
