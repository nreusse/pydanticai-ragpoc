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
getrennt. Tests liegen unter `tests/`; die Standardsuite ist offline. Die Webanwendung
startet mit `uv run pydanticai-poc` oder mit
`uv run uvicorn pydanticai_poc.app:app --host 127.0.0.1 --port 8000 --workers 1`.
Ollama muss separat laufen und `granite4.2:3b` bereitstellen. `.env.example`
dokumentiert die Einstellungen. `/api/health` prüft die Anwendung, nicht die
Erreichbarkeit des Modells.

Runtime-Abhängigkeiten: FastAPI, httpx, Jinja2, pydantic-ai-slim mit `openai`- und
`ag-ui`-Extras, pydantic-settings, Uvicorn. Entwicklungswerkzeuge: library-skills,
Pyrefly, pytest, pytest-asyncio und Ruff. Docling, Weaviate und DBOS werden für den
vereinbarten POC nicht installiert.
