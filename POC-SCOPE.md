# Rechercheagent: Vision und POC-Scope

Stand: 9. Oktober 2026

Dieses Dokument hält den aktuellen Abstimmungsstand fest. Es beschreibt den
vereinbarten Scope sowie Architekturvorschläge und offene Entscheidungen. Der Implementierungs- und Prüfstand ist separat in docs/VALIDATION.md dokumentiert.

README.md und PLAN.md enthalten einen früheren, umfangreicheren Plan. Für die
Abgrenzung des jetzt besprochenen POC ist dieses Dokument maßgeblich. Der ausführbare Arbeitsplan steht in IMPLEMENTATION-PLAN.md. Die älteren
Dokumente bleiben als historische Referenz erhalten und sind entsprechend markiert.

## Vision

Eine Webanwendung stellt einen Agenten bereit, der Nutzeranfragen anhand
verschiedener Datenquellen beantwortet. Perspektivisch gehören dazu:

- Hochgeladene Dokumente und bestehende Dokumentensammlungen.
- Confluence-Seiten und Jira.
- Webseiten beziehungsweise Suchdienste mit SOLR-Schnittstelle.
- Weitere Quellen über ergänzbare Integrationen.

Antworten sollen durch nachvollziehbare Quellenverweise belegt sein. Verständliche
Statusmeldungen zeigen, welchen Bearbeitungsschritt die Anwendung gerade ausführt.

Langfristig soll eine Workflow-Queue die Ausführung steuern. Rechenintensive
Aufgaben können beispielsweise auf ein Nachtfenster warten. Später sollen auch
schreibende Aktionen möglich sein, abgesichert durch menschliche Freigaben
(Human-in-the-Loop).

## Zweck und Umsetzungsprinzip

Der POC hat zwei gleichwertige Ziele: die technische Machbarkeit demonstrieren
und anderen die Architektur sowie die Vorgehensweise verständlich erklären.

Jeder Umsetzungsschritt soll so klar und minimal wie möglich sein. Bevorzugt
werden kleine, durchgängig demonstrierbare Schritte, sprechende Namen und ein
leicht nachvollziehbarer Kontroll- und Datenfluss. Abstraktionen werden nur dort
eingeführt, wo sie eine aktuelle Aufgabe vereinfachen oder eine konkret vereinbarte
Erweiterungsgrenze schaffen. Zukünftige Funktionen rechtfertigen keine vorgezogene
Infrastruktur oder unnötige Framework-Schichten.

Die Architektur muss zugleich für den besprochenen Ausbau geeignet sein.
Quellenzugriff, Modellanbindung, Bearbeitungslogik und Webdarstellung erhalten
klare Schnittstellen. Weitere Quellen, Berechtigungsprüfungen, DBOS-Ausführung
und menschliche Freigaben sollen daran ergänzt werden können, ohne die zentrale
Recherchelogik grundlegend neu zu bauen. Diese Erweiterungsgrenzen gehören bereits
zum POC; die späteren Funktionen und ihre Infrastruktur bleiben außerhalb seines
Umfangs. Einfachheit wird innerhalb dieser Architektur angestrebt.

Minimalität darf Quellenbelege, Fehlerbehandlung und notwendige Prüfungen nicht
aufheben. Kurze Erklärungen sollen Zweck und Entscheidungen vermitteln; Code und
Dokumentation sollen gemeinsam als verständliches Architekturbeispiel dienen.

## Vereinbarter POC

| Bereich | Festgelegter Umfang |
|---|---|
| Oberfläche | Webanwendung mit Eingabe, Antwort, Quellen und Statusmeldungen |
| Nutzung | Zunächst ein einzelner Nutzer |
| Agent | Recherche und Beantwortung anhand angebundener Quellen |
| Quellzugriff | Ausschließlich lesend |
| Datenquellen | Öffentliche Beispielquellen: Wikipedia und eine zweite öffentlich durchsuchbare Quelle |
| Ausführung | Direkte Bearbeitung; keine Hintergrundjobs und keine Workflow-Queue im POC |
| Fortschritt | Verständliche Meldungen zu tatsächlichen Bearbeitungsschritten |
| Betrieb | Lokal auf einem MacBook Air M1 mit 8 GB RAM |
| Modell | Lokales Sprachmodell; konkrete Eignung wird auf dem Gerät geprüft |
| Entwicklung | ChatGPT-Pro-Abo für die Entwicklungsunterstützung; lokale Modellinferenz für die Anwendung |

Dokumentenupload, interne Dokumentensammlungen, Confluence, Jira und SOLR gehören
zur Zielvision und sind keine Pflichtintegrationen dieses POC. Rollenverwaltung,
schreibende Aktionen und menschliche Freigabeprozesse werden ebenfalls noch nicht
implementiert.

## Vorgeschlagener erster Ablauf

1. Der Nutzer stellt eine Frage.
2. Der Agent durchsucht eine passende Beispielquelle.
3. Er liest ausgewählte Fundstellen.
4. Er erstellt eine Antwort mit Quellenverweisen.
5. Die Oberfläche zeigt währenddessen verständliche Statusmeldungen.

Beispiele: „Suche in Wikipedia“, „Lese drei Fundstellen“ und „Erstelle Antwort mit
Quellen“. Die Meldungen beschreiben beobachtbare Arbeitsschritte; ein technisches
Ausführungsprotokoll ist für den POC nicht erforderlich.

Bei unzureichenden Belegen soll die Anwendung die fehlende Grundlage kenntlich
machen, statt eine vermeintlich belegte Antwort zu erzeugen.

## Architekturleitlinien

Diese Leitlinien sollen spätere Erweiterungen ermöglichen, ohne deren gesamte
Infrastruktur bereits im POC aufzubauen.

### Quellenadapter

Der Agent erhält klar definierte Such- und Lesewerkzeuge. Quellenspezifische APIs
und Datenformate bleiben in den jeweiligen Adaptern. Neue Quellen sollen dadurch
ergänzt werden können, ohne die zentrale Bearbeitungslogik grundlegend zu ändern.

Spätere Berechtigungsprüfungen müssen vor dem Zugriff auf geschützte Inhalte
greifen. Unberechtigte Inhalte dürfen weder in Modellkontext noch Antwort gelangen.
Das konkrete Rollenmodell ist noch offen.

### Bearbeitung und Statusereignisse

Die Bearbeitungslogik wird von HTTP-Anfragen und der Darstellung in der Oberfläche
getrennt. Sie erzeugt Statusereignisse, die die Oberfläche anzeigen kann.

Im POC führt das Backend die Bearbeitung direkt aus. Später soll ein Worker dieselbe
fachliche Bearbeitung übernehmen können. Dauerhafte Jobzustände, Wiederholungen,
Zeitplanung und die konkrete Queue-Technik müssen dann ergänzt werden; die
Trennung allein liefert diese Funktionen noch nicht.

### Austauschbarer Modellzugriff

Das Modell wird über eine austauschbare Anbindung aufgerufen. Der POC verwendet
lokale Inferenz auf dem Laptop. Später kann ein interner Inferenzserver ein größeres
Modell bereitstellen.

Die Zielumgebung läuft on-premise ohne Internetzugriff. Modellinferenz und
notwendige Laufzeitdienste dürfen dort keine externen Dienste voraussetzen. Die
öffentlichen POC-Quellen werden in dieser Umgebung durch interne Quellen ersetzt.

## Modell und Ressourcen

Der Nutzer hat Ollama und Granite 4.2 3B (`granite4.2:3b`) bereitgestellt. Dieses
Modell ist der aktuelle POC-Standard; daraus folgt keine Leistungszusage. Geschwindigkeit, Speicherbedarf, Antwortqualität und zuverlässige
Werkzeugaufrufe müssen früh auf dem MacBook geprüft werden.

Für die begrenzten Ressourcen sind zunächst vorgesehen:

- Eine Anfrage gleichzeitig.
- Wenige Suchtreffer und kurze Quellenauszüge.
- Begrenzte Recherche- und Werkzeugaufrufe.
- Direkte Quellensuche ohne zusätzliche lokale Vektordatenbank.

Ein kleines Modell kann den technischen Ablauf demonstrieren. Die Qualität
komplexer Recherche muss gesondert bewertet werden und kann mit einem späteren,
größeren Modell anders ausfallen.

Ergänzend wurden gespeicherte Beispieldaten vorgeschlagen, damit der Ablauf auch
ohne Internetverbindung geprüft werden kann. Das ist eine Empfehlung, noch kein
ausdrücklich vereinbarter Bestandteil.

## Spätere Erweiterungen

- Weitere Quellen und Dokumentenverarbeitung.
- Mehrbenutzerbetrieb und Quellenberechtigungen anhand von Rollen.
- Workflow-Queue mit Hintergrundjobs und Nachtfenstern.
- Fortschrittsanzeige für wartende und laufende Hintergrundjobs.
- Schreibende Aktionen mit menschlicher Freigabe.
- On-premise-Betrieb mit internem Modell und ohne Internetzugriff.

## Vereinbarter Tech-Stack

- Python 3.11, uv für Projekt- und Abhängigkeitsverwaltung.
- PydanticAI mit OpenAI-kompatibler Modellschnittstelle.
- FastAPI mit asynchroner Verarbeitung und Uvicorn als ASGI-Server.
- Jinja2 und JavaScript für die Oberfläche.
- AG-UI über SSE für Agentenereignisse und verständliche Statusmeldungen.
- httpx für asynchrone Quellenzugriffe; pydantic-settings für Konfiguration.
- pytest und pytest-asyncio für Tests, Ruff für Linting und Formatierung,
  Pyrefly für Typechecks.
- Ollama als lokale Modellruntime; Modellstartpunkt Granite 4.2 3B (`granite4.2:3b`), quantisiert.
- Gesprächsverlauf im Arbeitsspeicher; Verlust bei Neustart ist im POC akzeptiert.
- Keine Datenbank, kein Broker und keine Vektordatenbank im POC.

DBOS ist die vorgesehene spätere Erweiterung für dauerhafte Workflows und Queues,
bleibt aber außerhalb der POC-Implementierung. Das AG-UI-Protokoll kann auch mit
separater Agentenausführung genutzt werden. Wiederverbindung, Ereignisspeicherung
und Nachtfenster benötigen später eigene Implementierung.

Die aktuelle PydanticAI-DBOS-Integration puffert Modell-Streamingereignisse bis zum
Abschluss des betreffenden Schritts. Ein späterer Wechsel auf DBOS garantiert
somit kein tokenweises Live-Streaming. Fortschrittsmeldungen bleiben erforderlich.

Referenzen: [PydanticAI UI Event Streams](https://pydantic.dev/docs/ai/integrations/ui/overview/),
[PydanticAI DBOS](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/).

## Noch offen

- Open Library ist durch den Live-Smoke-Test als zweite Quelle bestätigt;
  der POC verwendet Buchmetadaten, keine Buchvolltexte.
- Weitere Modellqualität über die dokumentierten Praxistests hinaus.
- Abhängigkeiten und konkrete APIs sind über uv.lock und die dokumentierten
  Prüfungen festgehalten.

Architekturabgleich, Testfälle, Umsetzungsschritte und Abnahmekriterien sind im
IMPLEMENTATION-PLAN.md beschrieben. Es bestehen keine blockierenden fachlichen
Rückfragen; technische Befunde werden bei der Umsetzung dokumentiert.
