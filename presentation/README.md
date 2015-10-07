# Presentation
> **Note:** The presentation is available in German only.

* In deutscher Sprache
* 30 Minuten
* Keine Vorkenntnisse über BitTorrent oder die Arbeit

## Todo
### Zeitplan
* **5.10.:** Bis Folie 1
* **6.10.:** —
* **→ 7.10.:** Bis Folie 2
* **8.10.:** Folien
* **9.10.:** Folien
* **10.10.:** Vortrag üben
* **11.10.:** Vortrag üben
* **12.10.:** Vortrag üben
* **13.10.:** Vortrag um 15:00 Uhr

## Vortragsnotizen
0. 
0. Agenda --> Kapitel Outline
0. 
0. 
0. 
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
0. **Peer-ID:** Wiedererkennung von Tracker/ geänderter IP, unwichtig  
   **Antwort:** Bencodete Liste von Dicts mit IPs und Ports  
   **UDP:** 50% Einsparung, wenige Datagramme
0. **choke/interested:** Bereitschaft Anfragen zu beantworten/ Interesse an
   `unchoke`
