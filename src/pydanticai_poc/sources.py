"""Two read-only adapters behind the same search/read contract.

All network traffic goes through fixed API endpoints. Document identifiers come
from searches; the agent cannot supply arbitrary URLs.
"""

import asyncio
import json
import re
from collections.abc import Mapping
from html import unescape
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import quote

import httpx

from .contracts import Evidence, SearchHit

SourceId = Literal["wikipedia", "openlibrary"]


class SourceError(Exception):
    """A source could not supply usable evidence."""


class Source(Protocol):
    name: str

    async def search(self, query: str, limit: int) -> list[SearchHit]: ...

    async def read(self, document_id: str, max_chars: int) -> Evidence: ...


def clean(text: str) -> str:
    return unescape(re.sub("<[^>]*>", "", text)).strip()


async def fetch(client: httpx.AsyncClient, url: str, params: Mapping[str, str | int] | None = None):
    """Retry a transient failure once, under the outer source/run deadlines."""
    for attempt in range(2):
        try:
            response = await client.get(url, params=params)
            if attempt == 0 and (response.status_code == 429 or response.status_code >= 500):
                await asyncio.sleep(0.5)
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceError(
                "Die Quelle ist nicht erreichbar oder liefert ungültige Daten."
            ) from exc
    raise SourceError("Die Quelle ist vorübergehend nicht verfügbar.")


class Wikipedia:
    name = "Wikipedia (deutschsprachige Artikel)"
    endpoint = "https://de.wikipedia.org/w/api.php"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        data = await fetch(
            self.client,
            self.endpoint,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
                "formatversion": 2,
            },
        )
        try:
            return [
                SearchHit(
                    source_id="wikipedia",
                    document_id=str(row["pageid"]),
                    title=row["title"],
                    url=f"https://de.wikipedia.org/?curid={row['pageid']}",
                    snippet=clean(row.get("snippet", ""))[:250],
                )
                for row in data["query"]["search"][:limit]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError("Wikipedia liefert ein unerwartetes Suchformat.") from exc

    async def read(self, document_id: str, max_chars: int) -> Evidence:
        if not document_id.isdigit():
            raise SourceError("Ungültige Wikipedia-Seiten-ID.")
        data = await fetch(
            self.client,
            self.endpoint,
            {
                "action": "query",
                "pageids": document_id,
                "prop": "extracts|info|revisions",
                "explaintext": 1,
                "exintro": 1,
                "inprop": "url",
                "rvprop": "ids",
                "format": "json",
                "formatversion": 2,
            },
        )
        try:
            row = data["query"]["pages"][0]
            text = row["extract"].strip()
            if not text:
                raise SourceError("Der Artikel enthält keinen lesbaren Einleitungstext.")
            revision = row["revisions"][0]["revid"]
            return Evidence(
                source_id="wikipedia",
                document_id=document_id,
                title=row["title"],
                url=f"https://de.wikipedia.org/w/index.php?oldid={revision}",
                locator=f"Einleitung, Revision {revision}",
                text=text[:max_chars],
                truncated=len(text) > max_chars,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise SourceError("Wikipedia liefert keinen verwendbaren Artikel.") from exc


class OpenLibrary:
    name = "Open Library (Buchmetadaten, keine Volltexte)"
    endpoint = "https://openlibrary.org"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        data = await fetch(
            self.client,
            self.endpoint + "/search.json",
            {
                "q": query,
                "limit": limit,
                "fields": "key,title,author_name,first_publish_year",
            },
        )
        try:
            return [
                SearchHit(
                    source_id="openlibrary",
                    document_id=row["key"].split("/")[-1],
                    title=row["title"],
                    url=self.endpoint + row["key"],
                    snippet=f"Autoren: {', '.join(row.get('author_name', []))}; "
                    f"Erstveröffentlichung: {row.get('first_publish_year', 'nicht angegeben')}",
                )
                for row in data["docs"][:limit]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError("Open Library liefert ein unerwartetes Suchformat.") from exc

    async def read(self, document_id: str, max_chars: int) -> Evidence:
        if not re.fullmatch(r"OL\d+W", document_id):
            raise SourceError("Ungültige Open-Library-Werk-ID.")
        row = await fetch(self.client, self.endpoint + f"/works/{quote(document_id)}.json")
        try:
            description = row.get("description", "Keine Beschreibung angegeben.")
            if isinstance(description, dict):
                description = description.get("value", "Keine Beschreibung angegeben.")
            text = f"Titel: {row['title']}\nBeschreibung: {description}"
            return Evidence(
                source_id="openlibrary",
                document_id=document_id,
                title=row["title"],
                url=self.endpoint + f"/works/{document_id}",
                locator="Werkdatensatz",
                text=text[:max_chars],
                truncated=len(text) > max_chars,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceError("Open Library liefert keinen verwendbaren Werkdatensatz.") from exc


class FixtureSource:
    """Offline demonstration of the same source contract; never claims live data."""

    def __init__(self, source_id: str, records: list[Evidence]):
        self.source_id = source_id
        self.name = source_id + " (gespeicherte Demo-Daten)"
        self.records = records

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        words = set(re.findall(r"\w+", query.casefold()))
        records = [
            row
            for row in self.records
            if words & set(re.findall(r"\w+", (row.title + " " + row.text).casefold()))
        ]
        return [
            SearchHit(
                source_id=row.source_id,
                document_id=row.document_id,
                title=row.title,
                url=row.url,
                snippet=row.text[:200],
            )
            for row in records[:limit]
        ]

    async def read(self, document_id: str, max_chars: int) -> Evidence:
        for row in self.records:
            if row.document_id == document_id:
                return row.model_copy(
                    update={
                        "text": row.text[:max_chars],
                        "truncated": len(row.text) > max_chars,
                    }
                )
        raise SourceError("Kein Demo-Datensatz mit dieser ID.")


def fixture_sources() -> dict[str, Source]:
    path = Path(__file__).parent / "fixtures.json"
    records = [Evidence.model_validate(row) for row in json.loads(path.read_text())]
    return {
        key: FixtureSource(key, [r for r in records if r.source_id == key])
        for key in ("wikipedia", "openlibrary")
    }
