"""Read public NRW.BANK pages and products from its German SOLR index."""

import re
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts import Evidence, SearchHit
from .sources import SourceError, clean, fetch


class IndexDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    type: str
    link: str
    public_access: bool = False
    search_exclude: str | bool = True
    title: str = Field(default="", validation_alias="title_de_s")
    page_title: str = Field(default="", validation_alias="Title_prop_s")
    description: str = Field(default="", validation_alias="description_de_s")
    content: str | list[str] = Field(default="", validation_alias="content_de")

    def public_url(self) -> str:
        if not self.public_access or self.search_exclude not in (False, "false"):
            raise ValueError("Not a public searchable document")
        if self.type == "localProduct":
            match = re.fullmatch(r"/\.content/localProduct/(\d+)\.xml", self.link)
            if match:
                return f"https://www.nrwbank.de/de/foerderung/foerderprodukte/{match[1]}/index.html"
        if self.type == "containerpage" and re.fullmatch(
            r"/de/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.html", self.link
        ):
            return "https://www.nrwbank.de" + self.link
        raise ValueError("No supported public page URL")

    def title_text(self) -> str:
        return clean(self.title or self.page_title) or "NRW.BANK-Fundstelle"


class NRWBank:
    name = "NRW.BANK (öffentliche Seiten und Förderprodukte, deutscher SOLR-Indextext)"
    endpoint = "https://www.nrwbank.de/handleSolrSelect"
    public_filter = (
        "public_access:true AND search_exclude:false AND "
        "(type:localProduct OR type:containerpage) AND con_locales:de"
    )
    fields = (
        "id,type,link,title_de_s,Title_prop_s,description_de_s,"
        "content_de,public_access,search_exclude"
    )

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def documents(self, query: str, limit: int, *, content: bool) -> list[IndexDocument]:
        data = await fetch(
            self.client,
            self.endpoint,
            {
                "q": query,
                "fq": self.public_filter,
                "fl": self.fields if content else self.fields.replace("content_de,", ""),
                "rows": limit,
                "sort": "score desc",
                "wt": "json",
            },
        )
        try:
            if data["responseHeader"]["status"] != 0:
                raise SourceError("NRW.BANK meldet einen Suchfehler.")
            rows = data["response"]["docs"]
            if not isinstance(rows, list):
                raise TypeError("Expected document list")
        except (KeyError, TypeError) as exc:
            raise SourceError("NRW.BANK liefert ein unerwartetes SOLR-Format.") from exc
        documents = []
        for row in rows[:limit]:
            try:
                document = IndexDocument.model_validate(row)
                # Enforce locally too: a server filter alone is not an access check.
                document.public_url()
                documents.append(document)
            except (ValidationError, ValueError):
                continue
        return documents

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        # Treat agent input as text, not as a free SOLR query or filter expression.
        escaped = re.sub(r'([+\-!(){}\[\]^"~*?:\\/|&])', r"\\\1", query)
        terms = " ".join(f'"{term}"' for term in escaped.split())
        rows = await self.documents(terms, limit, content=False)
        return [
            SearchHit(
                source_id="nrwbank",
                document_id=str(row.id),
                title=row.title_text(),
                url=row.public_url(),
                snippet=clean(row.description)[:250],
            )
            for row in rows
        ]

    async def read(self, document_id: str, max_chars: int) -> Evidence:
        try:
            canonical_id = str(UUID(document_id))
        except ValueError as exc:
            raise SourceError("Ungültige NRW.BANK-Dokument-ID.") from exc
        rows = await self.documents(f'id:"{canonical_id}"', 1, content=True)
        if not rows or str(rows[0].id) != canonical_id:
            raise SourceError("NRW.BANK-Fundstelle ist nicht mehr verfügbar.")
        row = rows[0]
        content = row.content if isinstance(row.content, str) else "\n".join(row.content)
        text = clean("\n".join(part for part in (row.description, content) if part))
        if not text:
            raise SourceError("NRW.BANK liefert keinen lesbaren Indextext.")
        return Evidence(
            source_id="nrwbank",
            document_id=canonical_id,
            title=row.title_text(),
            url=row.public_url(),
            locator="Deutscher SOLR-Indextext; keine Live-Seitenfassung",
            text=text[:max_chars],
            truncated=len(text) > max_chars,
        )
