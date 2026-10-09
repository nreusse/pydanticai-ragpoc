# Quellenwerk – lokaler Recherche-POC

Eine kleine Webanwendung mit einem lesenden PydanticAI-Agenten. Sie durchsucht
Wikipedia und Open Library, liest Fundstellen und beantwortet Fragen auf Deutsch
mit geprüften Quellenreferenzen. Bearbeitungsschritte erscheinen live über AG-UI/SSE.

## Start

Voraussetzungen: Python 3.11, uv und ein laufendes Ollama mit `granite4.2:3b`.
Der POC benötigt keinen externen Modellanbieter.

```sh
uv sync --locked
cp .env.example .env
uv run pydanticai-poc
```

Öffne [die Anwendung](http://127.0.0.1:8000). Es läuft ein Backend-Prozess mit
höchstens einer aktiven Recherche. Ohne `.env` gelten dieselben Standardwerte.
Bestehende `.env`-Dateien beim Einrichten nicht überschreiben.

Beispiel: „Wer war Franz Kafka?“ Danach: „In welcher Stadt wurde er geboren?“
Für Buchmetadaten: „Finde Die Verwandlung von Kafka in Open Library.“ Open Library
liefert keine Buchvolltexte. Wikipedia verwendet den Einleitungstext eines Artikels.

Für die ausdrücklich gekennzeichnete Offline-Quellendemo:

```sh
POC_SOURCE_MODE=fixture uv run pydanticai-poc
```

Auch diese Demo benötigt das lokale Modell. Sie enthält nur kleine kuratierte
Beispieldaten über Kafka und Die Verwandlung sowie einen manipulativen Testdatensatz;
sie ersetzt keine Live-Quellensuche. Gespräche gehen bei Neustart verloren.

## Architektur erklären

1. `app.py` nimmt eine neue Nachricht und eine serverseitig erzeugte Gesprächs-ID an.
2. `research.py` startet den Agenten mit begrenztem Kontext und Ausführungslimits.
3. Die Werkzeuge `search_source` und `read_source` greifen zentral auf registrierte
   Adapter in `sources.py` zu. Nur IDs aus vorherigen Suchtreffern dürfen gelesen werden.
4. Gelesene Auszüge erhalten Beleg-IDs. Der Antwortvalidator prüft, ob Quellenliste
   und Textmarker zu diesen Belegen passen. URLs stammen ausschließlich aus Adaptern.
5. PydanticAI-Ereignisse werden durch den offiziellen AG-UI-Encoder in SSE übersetzt.
   Die Oberfläche zeigt Statusmeldungen und die validierte Antwort samt Auszügen.

Die Prüfung erkennt erfundene Beleg-IDs, garantiert aber nicht die inhaltliche
Richtigkeit jeder Modellbehauptung. Quellen prüfen bleibt notwendig.

Weitere Quellen ergänzen den Adaptervertrag. Berechtigungen gehören vor jeden
Such-/Lesezugriff in `RunData`. Die HTTP-unabhängige Bearbeitung kann später in
DBOS laufen; Ereignispersistenz, Wiederverbindung und Nachtfenster kommen dann
hinzu. Schreibende Werkzeuge benötigen einen separaten Freigabeprozess.

## Prüfungen

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
```

Die Standardsuite verwendet kontrollierte Modelle und Mock-HTTP; sie benötigt
weder Ollama noch Internet. Opt-in-Tests mit dem tatsächlichen Modell:

```sh
uv run scripts/check_model.py
uv run scripts/evaluate.py
uv run scripts/check_sources.py
```

Diese Tests verwenden lokale Fixture-Quellen beziehungsweise ein synthetisches
Werkzeug. Ihre Ergebnisse unter `docs/` überschreiben frühere Testausgaben.
`check_sources.py` prüft die öffentlichen APIs; die beiden Modelltests sind keine
Live-Quellenprüfung. Evaluationsrubrik: `tests/fixtures/evaluation.json`.

## Dokumentation

- [Aktueller Scope](POC-SCOPE.md)
- [Umsetzungsplan](IMPLEMENTATION-PLAN.md)
- [Umgebung und Skills](docs/SETUP.md)
- [Validierung und bekannte Grenzen](docs/VALIDATION.md)
- [Historische Anforderungen](docs/legacy/README.md) und [historischer Plan](PLAN.md)

Die Anwendung bindet an Loopback und ist ein Einzelplatz-POC, kein Mehrbenutzersystem.
Die Live-Quellen benötigen Internet; Modell und Oberfläche laufen lokal.
