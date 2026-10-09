# Umsetzungsplan: lokaler Rechercheagent als Web-POC

Stand: 9. Oktober 2026. Status: erster Web-POC implementiert;
Validierung und verbleibende Grenzen siehe [docs/VALIDATION.md](docs/VALIDATION.md).

Die folgenden Arbeitspakete dokumentieren die vorgesehene Vorgehensweise und
Abnahmekriterien. Sie sind keine pauschale Bestätigung aller Qualitätsziele.
Aktueller Start: [README.md](README.md); Umgebung: [docs/SETUP.md](docs/SETUP.md).


## 1. Auftrag und verbindliche Abgrenzung

Implementiere den in [POC-SCOPE.md](POC-SCOPE.md) beschriebenen Web-POC.
Dieses Dokument ist der aktuelle Arbeitsplan; README.md und PLAN.md sind
historische Referenzen und erweitern den Auftrag nicht.

Liefere eine lokal laufende deutschsprachige Webanwendung mit einem lesenden
Rechercheagenten, zwei öffentlichen Beispielquellen, belegten Antworten,
Gesprächsverlauf innerhalb einer Sitzung und verständlichen Fortschrittsmeldungen.

Der POC läuft auf einem MacBook Air M1 mit 8 GB RAM. Er nutzt ein lokales Modell
über eine OpenAI-kompatible Schnittstelle. Das ChatGPT-Pro-Abo dient der Entwicklung
und ist keine notwendige Laufzeitabhängigkeit der Anwendung.

Nicht implementieren: DBOS, Hintergrundjobs, Nachtplanung, Datenbank, Broker,
Vektorsuche, Dokumentenupload, OCR, Rollenverwaltung, SSO, schreibende Aktionen,
Confluence/Jira/SOLR-Integrationen, Containerdeployment oder Produktionshärtung.
Keine zusätzlichen Agenten pro Quelle aufbauen.

## Verbindliches Prinzip für alle Arbeitspakete

Der POC demonstriert Machbarkeit und dient zugleich dazu, anderen Architektur
und Vorgehensweise zu erklären. Deshalb jeden Schritt so klar und minimal wie
möglich umsetzen:

- Pro Schritt einen kleinen, sichtbaren Fortschritt liefern und dessen Ablauf
  demonstrieren können. Innerhalb der Arbeitspakete zuerst den einfachsten
  durchgängigen Erfolgsfall bauen, danach notwendige Fehlerfälle ergänzen.
- Kontroll- und Datenfluss direkt nachvollziehbar halten; sprechende Namen und
  wenige Komponenten mit klaren Aufgaben verwenden. Keine generischen Frameworks,
  zusätzlichen Agenten oder Schichten ohne konkreten Bedarf einführen.
- Die beschriebenen Datenverträge und Erweiterungsgrenzen schlank umsetzen.
  Das Architekturdiagramm beschreibt Verantwortlichkeiten und erzwingt nicht für
  jeden Kasten eine eigene Klasse, einen Dienst oder ein Modul.
- DBOS, Berechtigungen und weitere Quellen nur an den vereinbarten Grenzen
  berücksichtigen; dafür keine ungenutzten Platzhalterimplementierungen bauen.
- Nach jedem Arbeitspaket kurz dokumentieren: Was funktioniert jetzt, wie fließen
  Anfrage, Quellen und Ergebnis durch den Code, und warum war dieser Schritt nötig?
  Eine passende Demonstration oder Prüfung nennen; keine parallele umfangreiche
  Dokumentationsstruktur aufbauen.
- Kommentare erklären nicht offensichtliche Entscheidungen. Wiederholungen des
  Codes und unnötige Konfigurationsoptionen vermeiden.
- Quellenvalidierung, begrenzte Ausführung, verständliche Fehler und erforderliche
  Tests bleiben Bestandteil der minimalen Lösung.

Die Architektur muss den vereinbarten Ausbau ermöglichen. Minimalität bedeutet,
die folgenden Erweiterungsgrenzen klar und schlank anzulegen:

| Erweiterung | Bereits im POC vorzusehen | Später zu implementieren |
|---|---|---|
| Weitere Quellen | Einheitlicher Such-/Lesevertrag und explizites Quellenregister | Neue Adapter und Dokumentenverarbeitung |
| Quellenberechtigungen | Zentraler Zugriffspfad für alle Such-/Leseoperationen; keine direkten Adapteraufrufe am Zugriffspfad vorbei | Identität, Rollen und Prüfungen vor Zugriff auf Inhalte |
| Hintergrundjobs / DBOS | HTTP-unabhängige Bearbeitungslogik, zuordenbare Run-IDs und getrennte Ereignisausgabe | Dauerhafte Workflows, Queue, Speicherung, Replay und Nachtfenster |
| Interne Modelle | Konfigurierbare Modellanbindung außerhalb der Fachlogik | Interner Inferenzserver und angepasste Modelle |
| Menschliche Freigaben | Werkzeugausführung an einer klaren Grenze; lesende Quellwerkzeuge separat halten | Schreibende Werkzeuge, Freigabezustände, Berechtigungsprüfung und Schutz gegen doppelte Ausführung |

Diese Grenzen sollen Erweiterungen ohne grundlegenden Neubau der Recherchelogik
ermöglichen. Dafür sind jetzt weder ein generisches Plugin-System noch leere
Queue-, Rollen- oder Freigabeimplementierungen erforderlich. Die spätere
Integration benötigt weiterhin konkrete Implementierung und Tests.

Bei mehreren Lösungen, die diese Ausbauziele gleichermaßen erfüllen, diejenige
wählen, die sich anhand eines konkreten Anfrageablaufs am einfachsten erklären lässt.

## 2. Ausgangslage und technische Entscheidungen

Zum Beginn der Umsetzung enthielt das Repository ein Hello-World-Paket und die
uv-Projektumgebung. Inzwischen sind Backend, Oberfläche und Offline-Tests ergänzt.

Docling und Weaviate wurden aus den Projektabhängigkeiten entfernt. Vorhandene
Weaviate-Skills und sonstige Nutzerdateien bleiben erhalten.

| Bereich | Entscheidung |
|---|---|
| Sprache | Python 3.11 als Entwicklungs- und Prüfversion |
| Projekt | uv; uv.lock für reproduzierbare Installation commitfähig erzeugen |
| Agent | PydanticAI; OpenAI-kompatibler Chat-Completions-Zugriff |
| Modellruntime | Ollama, zunächst quantisiertes Granite 4.2 3B (`granite4.2:3b`) |
| Web | FastAPI async, Uvicorn, ein Worker |
| UI | Jinja2, lokal ausgeliefertes JavaScript und CSS, keine CDN-Abhängigkeiten |
| Protokoll | PydanticAI AG-UI-Adapter, SSE als Transport |
| Quellen | httpx.AsyncClient; Wikipedia und Open Library |
| Konfiguration | pydantic-settings und dokumentierte Umgebungsvariablen |
| Tests | pytest, pytest-asyncio, httpx.MockTransport für Quellen-Fixtures |
| Qualität | Ruff für Format/Lint, Pyrefly für Typechecks |
| Zustand | Im Speicher, begrenzt und sitzungsbezogen; Verlust beim Neustart akzeptiert |
| Spätere Ausführung | DBOS als vorgesehene Ergänzung, jetzt keine DBOS-Abhängigkeit |

Vor Implementierung die mit Python 3.11 kompatiblen Paketversionen und benötigten
Extras prüfen und locken. Insbesondere die AG-UI-, Modell- und Test-APIs anhand der
gewählten Version verifizieren. Keine Beispiel-APIs aus anderer Version ungeprüft
übernehmen. Keine Python-Versionsänderung ohne dokumentierten Grund.

## 3. Architektur und Schnittstellen

```text
Browser: Jinja2 + JavaScript
        | Nachricht / AG-UI-Ereignisse über SSE
FastAPI-Endpunkt + serverseitiger Sitzungszustand
        |
Recherche-Service: Lebenszyklus, Limits, Quellenregister, Status
        |
PydanticAI-Agent ---- OpenAI-kompatibler Client ---- lokales Ollama
        |
Such- und Lesewerkzeuge
        |
Quellenadapter: Wikipedia / Open Library
```

Der Recherche-Service enthält keine HTTP-Request- oder Template-Abhängigkeiten.
Agentenereignisse werden an der Webgrenze in AG-UI übersetzt. Ein eigener
Fortschrittstyp bildet Statusmeldungen wie „Suche in Wikipedia“ ab; den genauen
Custom-Event-Hook anhand der gelockten PydanticAI-Version wählen.

Von Beginn an conversation_id und run_id zur Zuordnung verwenden. Zustände:
`running`, `completed`, `failed`, `cancelled`. `queued` und `waiting_for_window`
bleiben spätere Erweiterungen. Ein Browserabbruch beendet im POC den direkten
Lauf kontrolliert und gibt Ressourcen frei; Fortsetzung nach Disconnect ist noch
kein POC-Versprechen.

### Datenverträge

- `SearchHit`: source_id, document_id, Titel, URL und kurzer Suchauszug.
- `Evidence`: eindeutige evidence_id, source_id, document_id, Titel, vom Adapter
  erzeugte URL, Locator soweit vorhanden, gelesener Text, Abrufzeitpunkt.
- `ResearchAnswer`: deutscher Antworttext mit Belegmarkern, verwendete evidence_ids,
  Hinweise auf fehlende Informationen oder widersprüchliche Quellen.
- `Progress`: run_id, Schrittart und verständlicher deutscher Text; keine internen
  Gedankenketten oder rohen Modellargumente als Nutzerstatus ausgeben.

Die endgültige Quellenliste wird serverseitig aus dem Evidence-Register aufgebaut.
Das Modell darf Belege referenzieren, aber keine eigenen Quellen-URLs erfinden.
Unbekannte Beleg-IDs werden zurückgewiesen. Prüfen, dass Marker und Quellenliste
zusammenpassen. Diese Prüfung garantiert gültige Referenzen, nicht automatisch
inhaltliche Belegtreue; diese wird zusätzlich anhand der Testfragen bewertet.

### Quellenvertrag

Ein schlankes async-Protokoll stellt `search(query, limit)` und
`read(document_id)` bereit. Adapter kapseln Parameter, Antwortformate, Kürzung und
Fehlerbehandlung. Quellen werden explizit registriert; keine beliebigen URLs vom
Modell abrufen. In der zentralen Zugriffsschicht bleibt ein klarer Ansatzpunkt
für spätere Berechtigungsprüfung, ohne jetzt ein Rollensystem zu implementieren.

## 4. Umsetzung in aufeinanderfolgenden Arbeitspaketen

### A. Projektbasis und reproduzierbare Umgebung

1. pyproject.toml auf den vereinbarten Stack ausrichten; benötigte schlanke
   PydanticAI-Extras für OpenAI und AG-UI prüfen. Docling/Weaviate und unbenötigte
   Laufzeitpakete entfernen.
2. Python 3.11 für uv festlegen; Entwicklungsgruppe für pytest, pytest-asyncio,
   Ruff und Pyrefly einrichten; uv.lock erzeugen.
3. Ruff-, Pyrefly- und pytest-Konfiguration ergänzen. Relevanten Anwendungscode
   vollständig prüfen; externe Bibliotheken nicht durch pauschale Any-Typen ersetzen.
4. Settings und .env.example mit Modellname/-adresse, Timeouts, Recherchelimits und
   Quellenmodus anlegen. Lokale Secrets und .env über .gitignore ausschließen.
5. FastAPI-Lifespan verwaltet gemeinsame HTTP- und Modellclients. Einen lokalen
   Startbefehl und einen Health-Endpunkt bereitstellen.

Ergebnis: Die Anwendung startet mit `uv run uvicorn pydanticai_poc.app:app
--host 127.0.0.1 --port 8000` (als einzeiliger Befehl dokumentieren).
Modell-/Quellenausfälle werden verständlich angezeigt und verhindern nicht die
Anzeige der Oberfläche. Keine automatischen Modell-Downloads beim App-Start.

### B. Früher Modelltest als Entscheidungspunkt

1. Ollama separat installieren/starten und Modell einmalig bereitstellen;
   Anleitung schreiben, nicht stillschweigend globale Software installieren.
2. Mit PydanticAI und exakt der vorgesehenen Schnittstelle testen: deutscher Text,
   ein Suchwerkzeugaufruf, Verarbeitung des Werkzeugergebnisses und strukturierte
   Ausgabe beziehungsweise validierbare Quellenmarker.
3. Zehn kleine Werkzeugtests ausführen; Aufrufgültigkeit, Laufzeit und beobachteten
   Speicherbedarf in docs/model-check.md festhalten. Keine Qualität von größeren
   Modellen auf das kleine Modell übertragen.
4. Startziel: mindestens 8/10 korrekte Werkzeugabläufe ohne manuelle Eingriffe und
   ohne Prozessabbruch durch Speichermangel. Kontext zunächst klein halten und
   tatsächlich wirksame Ollama-Einstellungen dokumentieren.

Wenn der Test scheitert: einmal Konfiguration/Prompt gezielt verbessern und
erneut messen. Danach einen expliziten Fallback dokumentieren: Anwendung steuert
Suche/Lesen, PydanticAI übernimmt die Antwortgenerierung. Die Oberfläche benennt
den Modus. Dies demonstriert Quellenantworten, erfüllt aber nicht automatisch
die Abnahme für autonome Werkzeugwahl. Keine Cloud-API stillschweigend ergänzen.
Andere unabhängige Arbeitspakete dürfen trotz Modellproblemen weitergehen.

### C. Quellenadapter und deterministische Fixtures

1. Wikipedia: MediaWiki-Such-API, vorzugsweise deutschsprachig; Fundstellen per
   Seiten-ID lesen. Für jeden gelesenen Auszug Titel und URL erhalten; Locator
   und Revision erfassen, soweit der gewählte Lese-Endpunkt sie liefert.
2. Open Library: Such-API für Bücher und Lesen ausgewählter Werkdatensätze.
   Nur vorhandene Metadaten wie Titel, Autor, Erstveröffentlichungsjahr und
   Beschreibung verwenden. Keine Buchvolltexte oder vollständige Inhaltskenntnis
   behaupten. Nicht vorhandene Felder explizit behandeln.
3. Je Quelle einen kleinen Live-Smoke-Test ausführen. API-Verhalten, User-Agent,
   Nutzungs-/Ratenregeln und Feldnamen dokumentieren. Die Dokumentationsprüfung
   ersetzt diesen Erreichbarkeitstest nicht.
4. Bereinigte kleine Fixtures für beide Quellen anlegen. Dieselben Adapter
   über MockTransport ohne Internet testen; für eine Offline-Demo optional einen
   explizit gekennzeichneten Fixture-Modus bereitstellen.
5. Timeouts, HTTP 429/5xx, leere Treffer und ungültige Antworten behandeln.
   Nur begrenzte Wiederholungen; keine unendlichen Retries.

Ergebnis: Beide Quellen liefern normalisierte Treffer und lesbare Evidence.
Adaptertests benötigen weder Internet noch lokales Modell.

### D. Recherche-Service und Gesprächsverlauf

1. Ein Agent erhält zwei generische Werkzeuge: Suche in registrierter Quelle und
   Lesen eines gefundenen Dokuments. Quellenkatalog mit kurzer Beschreibung im
   Kontext bereitstellen; Quellenwahl darf je Frage variieren.
2. Pro Lauf ein Evidence-Register führen. Anweisungen aus Quellen als Daten
   behandeln; Systemauftrag bleibt ausschließlich Recherche mit lesenden Werkzeugen.
3. Antwortschema und serverseitige Quellenvalidierung implementieren. Ohne
   ausreichende Evidence keine sachliche Antwort aus Modellwissen als belegt ausgeben.
4. Server hält Nachrichtenverlauf und IDs je Sitzung. Browser sendet neue Nutzertexte;
   clientseitig mitgelieferte Tool-/Systemnachrichten sind keine vertrauenswürdige
   Historie. AG-UI-Request entsprechend auf serverseitigen Zustand abbilden.
5. Neue Sitzung und Zurücksetzen ermöglichen. Verlauf begrenzen; abgeschnittene
   Evidence nicht als weiterhin verfügbar voraussetzen.
6. Einen aktiven Modelllauf zulassen. Weitere Anfragen erhalten einen verständlichen
   Busy-Status statt einer versteckten Jobqueue. Auch Tests für Parallelzugriff vorsehen.
7. Bei Timeout, Fehler oder Disconnect Zustand abschließen, Clients/Iteratoren
   schließen und Beleg- beziehungsweise Gesprächszustand konsistent halten.

Konfigurierbare Startgrenzen: drei Treffer je Suche, höchstens vier gelesene
Dokumente, 1.500 Zeichen je Auszug, acht Werkzeugaufrufe und sechs Modellanfragen
pro Lauf, 180 Sekunden Gesamtlaufzeit. Modellkontext und Gesprächshistorie zusätzlich
begrenzen. Grenzwerte sind Startwerte und werden nach B angepasst; Kürzung sichtbar
machen und keine Vollständigkeit behaupten.

### E. Weboberfläche und AG-UI

1. Eingabefeld, Verlauf, Quellenliste, Statusbereich und „Neue Unterhaltung“ bauen.
2. AG-UI-Adapter der gelockten Version verwenden. Bei POST-Streaming einen geeigneten
   fetch-SSE-Client oder lokal gebündelten AG-UI-Client nutzen; natives EventSource
   kann keinen POST-Body senden. SSE-Frames korrekt über Chunkgrenzen hinweg parsen.
3. Text, Tool-Lebenszyklus, eigene Fortschrittsereignisse, Abschluss und Fehler
   verarbeiten. Quellenliste aus serverseitig validierter Antwort anzeigen.
4. Such-/Lesestatus vor dem jeweiligen I/O veröffentlichen. Statusmeldungen sollen
   nicht erst gesammelt nach der Antwort erscheinen.
5. Fremden Inhalt als Text rendern beziehungsweise sicher escapen; keine ungeprüften
   HTML-Fragmente aus Wikipedia oder Modellantworten übernehmen.
6. JavaScript und CSS lokal ausliefern. Anwendung an Loopback binden; keine
   Anmeldung erforderlich. Kein Hosting oder öffentlicher Zugriff im POC.

Ergebnis: Ein vollständiger Browserdurchlauf zeigt mindestens Suche, Lesen und
Antworterstellung; Quellenlinks sind anklickbar. Fehler und Busy-Status bleiben
verständlich und lassen eine neue Anfrage zu.

### F. Integration, Bewertung und Übergabe

1. Service- und FastAPI-Tests mit kontrollierten Modellantworten beziehungsweise
   dem passenden PydanticAI-Testmodell der gewählten Version erstellen.
2. AG-UI-Ereignisreihenfolge, gültigen Abschluss, Fehler und Quellenübertragung
   integrieren und testen. Einen manuellen Browser-Smoke-Test dokumentieren.
3. Zehn versionierte Evaluationsfälle mit Fixture-Belegen und Erwartungsrubrik
   erstellen: drei Wikipedia-, drei Open-Library-Fragen, eine quellenübergreifende
   Frage, eine Rückfrage, eine unbeantwortbare Frage, eine Quelle mit eingebetteter
   manipulativer Anweisung. Beispielsweise Autorinformationen aus Wikipedia mit
   Buchmetadaten aus Open Library kombinieren.
4. Zusätzlich deterministische Fehlerfälle testen: Quelltimeout, leere Treffer,
   ungültige Beleg-ID, fehlendes Modell, Limitüberschreitung und parallele Anfrage.
5. Live-Modelltests als opt-in markieren; Standardsuite bleibt offline und
   reproduzierbar. Laufzeit-/Modellmessungen nicht als deterministische Unit-Tests
   behandeln.
6. Aktuelle Startanleitung erstellen und README auf den neuen POC umstellen;
   bisherigen Inhalt vorher als historische Datei unter docs/legacy/ erhalten.
   Bekannte Grenzen und Modelltestbefunde dokumentieren.

## 5. Abnahmekriterien

- Installation und Start sind mit Python 3.11 und uv anhand der Anleitung möglich.
- Wikipedia und Open Library bestehen je einen dokumentierten Live-Smoke-Test.
- Der Browser zeigt während der Bearbeitung verständliche Statusmeldungen.
- Deutsche Antworten enthalten Quellenmarker und die tatsächlich gelesenen Belege.
- Kein erzeugter Quellenlink stammt ungeprüft aus dem Modell; unbekannte IDs
  werden in allen deterministischen Tests abgewiesen.
- Eine Rückfrage nutzt den Verlauf und kann eine neue Recherche auslösen.
- Fehlende Belege, Fehler und Grenzen werden verständlich angezeigt.
- Mindestens 8/10 Evaluationsfälle erfüllen die hinterlegte Rubrik mit dem lokalen
  Modell. Für belegbare Fakten müssen passende gelesene Belege vorhanden sein.
  Unbeantwortbarkeit und manipulative Quellenanweisungen müssen korrekt behandelt
  werden; Fehlversuche werden ausgewiesen, nicht durch Fixture-Antworten verdeckt.
- Werkzeugtest aus B erfüllt sein Ziel oder die eingeschränkte Fallback-Abnahme
  wird ausdrücklich als solche dokumentiert. Ein fehlschlagendes Modellziel ist
  kein vollständig erfolgreicher Agenten-POC.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` und
  `uv run pyrefly check` bestehen. Die Standardsuite benötigt keinen Netzwerkzugriff.
- Laufzeiten für Modellstart, erste Statusmeldung und vollständige Antwort sowie
  Speicherbeobachtung werden auf dem M1 dokumentiert. Kein erfundenes Latenzziel;
  der Gesamttimeout beendet Ausreißer kontrolliert.
- Keine externe Modell-API, Telemetrie oder CDN ist für den Betrieb erforderlich.
  Die beiden Live-Quellen benötigen im POC weiterhin Internet. Ein Fixture-Modus
  ist als Demo gekennzeichnet und prüft keine Live-Erreichbarkeit.

### Nachvollziehbarkeit als Abnahmekriterium

Die Übergabe enthält eine kurze Anleitung für eine Demonstration: Start, Frage,
Statusmeldungen, Quellen und Antwort sowie ein Fehlerfall. Eine Person, die den
Code noch nicht kennt, soll mit der Dokumentation den Weg vom Web-Endpunkt über
Recherche und Quellenadapter bis zur Antwort nachvollziehen können. Nicht genutzte
Abstraktionen und vorgezogene Erweiterungsinfrastruktur gehören nicht zur Abnahme.
Die vereinbarten Erweiterungsgrenzen dagegen sind verbindlich: Bei der Übergabe
anhand des Codes zeigen, wo ein weiterer Quellenadapter, eine Berechtigungsprüfung,
ein DBOS-Worker, ein anderer Modellserver und eine Freigabe für ein neues
schreibendes Werkzeug anschließen würden. Dafür keine dieser Erweiterungen
vorzeitig implementieren.

## 6. Spätere DBOS-Erweiterung

DBOS wird nach Abschluss dieses POC separat implementiert:

1. Recherche durch eine DBOS-Workflow-Funktion starten; passende aktuelle
   PydanticAI-Integration prüfen. Die derzeitige Dokumentation empfiehlt
   DBOSDurability statt des veralteten DBOSAgent-Wrappers.
2. Modell-, Quellen- und Statusoperationen auf korrekte Workflow-/Step-Grenzen
   prüfen. Eigene Tools werden nicht automatisch allein durch Aktivieren der
   Capability dauerhaft; Serialisierung und Wiederholung ausdrücklich gestalten.
3. Queue, dauerhafte Run-Zustände, Ergebnis- und Ereignisspeicherung ergänzen.
   Für Produktion PostgreSQL vorsehen; bisheriges MySQL nicht als DBOS-Systemdatenbank
   voraussetzen. Self-hosted-Konfiguration ohne Cloud-/Internetabhängigkeit prüfen.
4. Jobstart vom Beobachten trennen: Job-ID zurückgeben, Status/Ergebnis abrufen und
   SSE erneut abonnieren können. Wiederverbindung braucht Ereignispositionen und
   gespeicherte Daten; AG-UI allein stellt kein Replay bereit.
5. Nachtfenster als Ausführungsregel umsetzen. Cron-Start allein verhindert nicht,
   dass Wiederholungen außerhalb des Fensters starten. Verhalten beim Ende des
   Fensters und die Zeitzone Europe/Berlin einschließlich Sommerzeit festlegen.
6. Vor schreibenden Werkzeugen menschliche Freigabe, erneute Berechtigungsprüfung
   und Schutz gegen doppelte Ausführung ergänzen. Eine Freigabe bezieht sich auf
   eine konkrete Aktion mit konkreten Parametern.

Aktuelle Einschränkung: PydanticAI puffert innerhalb von DBOS Modell-Streamereignisse
bis zum Schrittabschluss. Statusmeldungen und Ereignisweitergabe deshalb gezielt
entwerfen; tokenweises Echtzeitstreaming nicht als automatische Eigenschaft zusagen.

## 7. Referenzen und Prüfung bei Umsetzung

Die folgenden Dokumentationen wurden für die Planung herangezogen; gewählte
Paketversionen können andere APIs haben. Bei der Umsetzung diese Versionen und
Integrationstests als Maßstab verwenden.

- [PydanticAI UI Event Streams und getrennte Ausführung](https://pydantic.dev/docs/ai/integrations/ui/overview/)
- [PydanticAI DBOS-Integration und Streaminggrenzen](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)
- [DBOS: Grundlagen und Systemdatenbank](https://docs.dbos.dev/python/programming-guide)
- [DBOS: Workflow-Zeitplanung](https://docs.dbos.dev/python/tutorials/scheduled-workflows)
- [MediaWiki: Such-API](https://www.mediawiki.org/wiki/API:Search)
- [Open Library: Such-API](https://openlibrary.org/dev/docs/api/search)
