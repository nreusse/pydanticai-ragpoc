# Entwicklungsumgebung

Python 3.11 und uv werden benötigt. Das Projekt bildet einen eigenen uv-Workspace,
auch wenn das übergeordnete Verzeichnis einen anderen Workspace enthält.

```sh
uv sync --locked
uv run library-skills --skill fastapi --skill building-pydantic-ai-agents --no-tool-skill --yes
```

Die Python-Version steht in `.python-version`, die aufgelösten Paketversionen in
`uv.lock`. `library-skills` ist eine Entwicklungsabhängigkeit. Die ausgewählten
Skills werden relativ unter `.agents/skills` mit den in `.venv` installierten
Bibliotheken verlinkt. Die Links können mit Git versioniert werden und lösen sich
nach `uv sync --locked` auf. Bestehende Weaviate-Skills bleiben erhalten.

Ausgewählt sind `fastapi` und `building-pydantic-ai-agents`. Migrationsskills sind
für diesen Neubau nicht erforderlich. Nach Paketupdates die Skill-Verknüpfungen
mit demselben Installationsbefehl abgleichen.

```sh
uv run library-skills scan --json
uv run library-skills --skill fastapi --skill building-pydantic-ai-agents --no-tool-skill --check
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv run pytest
```

Ruff und Pyrefly prüfen Anwendungscode; mitgelieferte Skill-Skripte sind davon
getrennt. Tests werden unter `tests/` angelegt. Aktuell gibt es noch keine Tests;
pytest meldet daher „keine Tests gesammelt“ (Exitcode 5). Importprüfungen für
FastAPI, PydanticAI und AG-UI sowie Ruff und Pyrefly wurden bei der Einrichtung
mit Python 3.11 erfolgreich ausgeführt. Die Webanwendung und das lokale Modell
sind noch nicht eingerichtet.

Runtime-Abhängigkeiten: FastAPI, httpx, Jinja2, pydantic-ai-slim mit `openai`- und
`ag-ui`-Extras, pydantic-settings, Uvicorn. Entwicklungswerkzeuge: library-skills,
Pyrefly, pytest, pytest-asyncio und Ruff. Docling, Weaviate und DBOS werden für den
vereinbarten POC nicht installiert.
