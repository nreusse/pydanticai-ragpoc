"""Opt-in live API smoke checks, independent of the model."""

import asyncio
import json
from pathlib import Path

import httpx

from pydanticai_poc.nrwbank import NRWBank
from pydanticai_poc.sources import OpenLibrary, Source, Wikipedia


async def check() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    async with httpx.AsyncClient(
        timeout=20,
        headers={"User-Agent": "ResearchPOC/0.1 (local read-only demonstration)"},
    ) as client:
        sources: list[tuple[str, Source, str]] = [
            ("wikipedia", Wikipedia(client), "Franz Kafka"),
            ("openlibrary", OpenLibrary(client), "Die Verwandlung Kafka"),
            ("nrwbank", NRWBank(client), "Digitalisierung"),
        ]
        for source_id, source, query in sources:
            try:
                hits = await source.search(query, 3)
                evidence = await source.read(hits[0].document_id, 1500)
                row: dict[str, object] = {
                    "source": source_id,
                    "ok": True,
                    "hits": len(hits),
                    "title": evidence.title,
                    "url": evidence.url,
                }
            except Exception as exc:
                row = {"source": source_id, "ok": False, "error": str(exc)}
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    return results


if __name__ == "__main__":
    Path("docs/source-check.json").write_text(json.dumps(asyncio.run(check()), indent=2) + "\n")
