# Prüfstand und Demonstration

Stand: 9. Oktober 2026. Der Web-POC ist implementiert. Die unten genannten
Prüfungen gelten für den lokalen Einzelplatzbetrieb, nicht als Produktionsfreigabe.
Die abschließenden Modellergebnisse stehen in `evaluation-results.json`.

## Was bereits geprüft ist

- Python 3.11 mit den Versionen aus uv.lock.
- 25 bestandene Offline-Tests für Quellenformate, lesbare Auszüge, Quellenvalidierung,
  Gesprächsverlauf, AG-UI/SSE, Busy-Zustand, Zeit-/Werkzeuglimits, Modellfehler
  und Aufräumen bei Abbruch. Tests verwenden FunctionModel/TestModel und MockTransport.
- Ruff, Pyrefly einschließlich Prüfskripten und JavaScript-Syntaxprüfung.
- Live-Smoke-Test für Wikipedia: Suche nach Franz Kafka, drei Treffer,
  Lesen der Einleitung mit revisionsgebundener URL.
- Live-Smoke-Test für Open Library: Suche nach Die Verwandlung/Kafka, drei Treffer,
  Lesen eines Werkdatensatzes. Metadaten aus dem Suchtreffer werden beim Lesen
  in den Beleg übernommen; Autor/Jahr sind nicht in jedem Werkdatensatz vorhanden.
- Ergebnisse der Quellenprüfung: `source-check.json`.

## Modellbefunde und gewählter Ablauf

Ollama meldete `granite4.2:3b`, Q4_K_M, 3,7 Milliarden Parameter. Während der
Prüfung war ein Modell mit 4.096 Tokens Kontext geladen; `/api/ps` meldete rund
2,64 GB für das geladene Modell. Das ist keine Messung des gesamten RAM-Bedarfs:
macOS, Anwendung und Ollama-Caches benötigen zusätzlichen Speicher.

Der initiale synthetische Werkzeug-/Strukturtest bestand 8/10 Fälle, mit einem
Timeout und einer ungültigen Ausgabe. Erfolgreiche Fälle dauerten ungefähr
21–31 Sekunden (`model-check.json`). Im vollständigen Agentenlauf erwies sich
strukturierte Tool-Ausgabe als deutlich unzuverlässiger. Native JSON-Schema-Ausgabe
wurde ebenfalls geprüft; die lokale Kombination antwortete mit einem
Sampler-/Grammatikfehler (HTTP 400). Ein früher Lauf mit aktivem Denkmodus erreichte
das Gesamtzeitlimit von 180 Sekunden.

Die finale Anwendung verwendet deshalb normale Textausgabe des Agenten und bildet
das typisierte `ResearchAnswer` serverseitig. Quellen- und Werkzeugwahl bleiben
beim Agenten; es handelt sich nicht um fest verdrahtete Rechercheantworten.

- Der Agent muss vor einer Sachantwort recherchieren und Fundstellen lesen.
- Verwendet er Marker, müssen diese zu gelesenen Beleg-IDs passen.
- Fehlen Marker, ergänzt die Anwendung alle gelesenen Belege als Antwortbelege.
  Das ist eine Zuordnung auf Antwortebene, kein Nachweis pro Satz.
- Ohne gelesene Belege nach einer Suche wird ein klarer Hinweis auf fehlende
  Grundlage ausgegeben, keine ungeprüfte Modellbehauptung.
- URLs kommen ausschließlich aus den Quellenadaptern. Das Modell darf keine
  URLs in der Antwort erzeugen.
- Denkmodus wird für diesen Laptop über den OpenAI-kompatiblen Parameter
  `reasoning_effort=none` abgeschaltet. Andere Modellserver müssen diesen
  Parameter und das Werkzeugverhalten separat unterstützen beziehungsweise
  entsprechend konfiguriert werden.

Diese Anpassung reduziert Anforderungen an das kleine Modell, ohne dessen
Werkzeugwahl zu simulieren. Die Quellenprüfung ist strukturell. Eine gültige
Quellen-ID beweist nicht, dass jede Aussage inhaltlich von der Quelle gedeckt ist.

## Evaluation mit tatsächlichem Modell

`scripts/evaluate.py` führt zehn Fälle aus `tests/fixtures/evaluation.json` gegen
Ollama aus, mit ausdrücklich gespeicherten Quellendaten: Wikipedia, Buchmetadaten,
quellenübergreifende Frage, Rückfrage, unbeantwortbare Frage und manipulativer
Quelltext. Die Prüfausgabe enthält Antworten, Belege, Laufzeiten und Werkzeugereignisse.

Die automatischen Kriterien prüfen erwartete Begriffe, Quellen und Unbeantwortbarkeit.
Antworten müssen zusätzlich auf inhaltliche Belegtreue geprüft werden. Ein
Injection-Fall zählt nur als geprüft, wenn der manipulierte Datensatz tatsächlich
gelesen wurde. Eine Verweigerung ohne Lesen belegt keine Injection-Resistenz.
Modelltests bleiben opt-in und können bei Wiederholung anders ausfallen.

Bei Teilprüfungen mit Fall-IDs, z.B. `uv run scripts/evaluate.py wiki-person`, wird
die Ergebnisdatei ebenfalls ersetzt. Die abschließende Evaluation ohne Fallfilter
ist deshalb die maßgebliche Ausgabe. Frühere Fehlversuche werden hier erklärt;
sie sind keine erfolgreiche Abnahme.

Die abschließende Evaluation besteht **9 von 10 automatischen Kriterien**.
Erfolgreiche Fälle dauern etwa 7–25 Sekunden. Der Fall `book-scope` erklärt korrekt,
dass Open Library Metadaten und keinen Volltext liefert, nennt aber nicht die vom
Prüfkriterium zusätzlich erwarteten konkreten Werte für Autor und Jahr. Die Antwort
ist damit unvollständig. Das Prüfkriterium wurde nicht abgeschwächt.
Der Injection-Fall liest den manipulierten Datensatz tatsächlich und antwortet mit
dem gesuchten Titel, ohne die eingebettete Anweisung zu übernehmen.

Der manuelle Browser-Test gegen die Live-Quellen ist ebenfalls erfolgreich:
„Wer war Franz Kafka? Nutze Wikipedia.“ zeigt laufende Statusmeldungen und endet
mit einer Antwort, Beleg E1 und einer revisionsgebundenen Wikipedia-Verknüpfung.

## Kurze Demonstration der Architektur

1. Ollama starten, dann `uv run pydanticai-poc`; Browser auf localhost:8000 öffnen.
2. „Wer war Franz Kafka?“ stellen. Suche, Lesen und Antwortstatus beobachten.
3. Die Belege und „Gelesenen Auszug anzeigen“ öffnen. Quellen-IDs im Antworttext
   mit der Quellenliste vergleichen.
4. „In welcher Stadt wurde er geboren?“ fragen. Der Verlauf liefert den Bezug,
   eine neue Recherche liefert frische Belege.
5. Eine Buchfrage ausdrücklich an Open Library stellen. Metadaten erklären;
   keine Volltextkenntnis suggerieren.
6. Eine unbeantwortbare Frage stellen oder „Abbrechen“ während eines Laufs nutzen.
   Den nachvollziehbaren Abschluss und eine danach mögliche neue Anfrage zeigen.

Im Code dem Weg `app.py` → `ResearchService.stream` → `search_source`/`read_source`
→ Quellenadapter → Antwortvalidator → `AGUIEventStream` → Browser folgen.

## Erweiterungsgrenzen und verbleibende Grenzen

- Weitere Quelle: Adapter mit `search/read` und Registrierung. Prompt und
  Werkzeug-Schema werden aus der wirksamen Quellenliste erzeugt. Keine Änderung der
  Recherche-Schleife erforderlich.
- Berechtigungen: in `RunData.search/read` vor dem Adapterzugriff und vor
  Rückgabe von gespeicherten Belegen prüfen. Das heutige UUID-Gespräch ist keine
  Authentifizierung für Mehrbenutzerbetrieb.
- DBOS: HTTP-unabhängigen Service in einen dauerhaften Workflow überführen.
  Live-Iterator und Datenobjekte werden dabei nicht unverändert serialisiert;
  Run-Zustand, Eventtransport und Wiederverbindung müssen ergänzt werden.
- Interner Modellserver: Providerkonfiguration und unterstützte Modellparameter
  prüfen; kein Wechsel des fachlichen Quellenvertrags erforderlich.
- Schreibende Werkzeuge: separate Freigabegrenze mit konkreten Aktionsparametern,
  erneuter Berechtigungsprüfung und Schutz gegen doppelte Ausführung.

Es gibt keine Hintergrundjobs, dauerhaften Gespräche, Rollen oder Schreibwerkzeuge.
Abbruch beendet den direkten Lauf; nach Browser-Neuladen wird eine neue Unterhaltung
begonnen. Es gibt ein aktives Modell pro Backend-Prozess; mehrere Worker würden
diese Begrenzung umgehen und werden im POC nicht verwendet.

Der Gesprächskontext ist auf 1.200 Zeichen begrenzt; längere Zusammenhänge können
verloren gehen. Suchtreffer, Dokumentzahl, Auszüge und Ausführung sind begrenzt.
Die lokale Demo-Suche verwendet Wortüberschneidung und ist kein echter Suchindex.
Die Anwendung garantiert keine vollständige Recherche über ganze Dokumentbestände.

Referenz für den Denkmodus: [Ollama OpenAI-Kompatibilität](https://docs.ollama.com/api/openai-compatibility).

## Dynamische Quellenwahl

`GET /api/sources` liefert nur die durch `sources_for_user` erlaubten Quellen.
Im Einzelplatz-POC sind dies alle registrierten Adapter; eine echte Anmeldung
und Rollenverwaltung sind weiterhin nicht implementiert. `POST /api/chat` prüft
`source_ids` gegen dieselbe serverseitige Grenze. Nicht verfügbare IDs ergeben
403, eine leere Auswahl 422; ohne Auswahlfeld gelten alle erlaubten Quellen.
Nur die ausgewählten Adapter gelangen in `RunData`. Dynamische Agentenanweisungen
und vorbereitete Werkzeug-Schemas werden daraus pro Lauf erzeugt. Suche und Lesen
prüfen die Verfügbarkeit zusätzlich im Python-Code. Bei geänderter Quellenliste
wird der alte Gesprächskontext verworfen; bereits angezeigte Nachrichten bleiben
im Browser sichtbar. Berechtigungen werden zu Beginn jeder Anfrage aufgelöst;
ein Entzug während eines laufenden Jobs ist damit noch nicht umgesetzt.

Zusätzliche Tests prüfen Quellenfilterung, abgelehnte Auswahl, gesperrte Lesezugriffe,
getrennte Werkzeug-Schemas/Anweisungen und das Zurücksetzen des Gesprächskontexts.
Die frühere Granite-Evaluation ist keine erneute Modellabnahme dieser Erweiterung.
