import httpx
import pytest

from pydanticai_poc.sources import OpenLibrary, SourceError, Wikipedia, fetch


async def test_wikipedia_api_normalization():
    def handle(request: httpx.Request):
        if request.url.params.get("list") == "search":
            return httpx.Response(
                200,
                json={
                    "query": {
                        "search": [
                            {
                                "pageid": 123,
                                "title": "Kafka",
                                "snippet": "<b>Kafka</b> &amp; Literatur",
                            }
                        ]
                    }
                },
            )
        assert request.url.params["pageids"] == "123"
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "title": "Kafka",
                            "extract": "A" * 500,
                            "revisions": [{"revid": 456}],
                        }
                    ]
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = Wikipedia(client)
        hits = await adapter.search("Kafka", 3)
        assert hits[0].snippet == "Kafka & Literatur"
        evidence = await adapter.read(hits[0].document_id, 200)
        assert len(evidence.text) == 200
        assert evidence.truncated
        assert evidence.url.endswith("oldid=456")
        with pytest.raises(SourceError):
            await adapter.read("https://example.com", 200)


async def test_openlibrary_metadata_and_missing_description():
    def handle(request: httpx.Request):
        if request.url.path == "/search.json":
            return httpx.Response(
                200,
                json={
                    "docs": [
                        {
                            "key": "/works/OL123W",
                            "title": "A book",
                            "author_name": ["An author"],
                            "first_publish_year": 1915,
                        }
                    ]
                },
            )
        assert request.url.path == "/works/OL123W.json"
        return httpx.Response(200, json={"title": "A book"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        adapter = OpenLibrary(client)
        hits = await adapter.search("A book", 3)
        assert "1915" in hits[0].snippet
        evidence = await adapter.read(hits[0].document_id, 500)
        assert "Keine Beschreibung" in evidence.text
        with pytest.raises(SourceError):
            await adapter.read("../admin", 500)


@pytest.mark.parametrize("status", [429, 500])
async def test_transient_failure_retried_once(status):
    calls = 0

    def handle(request):
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(SourceError):
            await fetch(client, "https://example.com")
    assert calls == 2


async def test_source_timeout_and_invalid_json():
    def timeout(request):
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(SourceError):
            await fetch(client, "https://example.com")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="not json"),
        )
    ) as client:
        with pytest.raises(SourceError):
            await fetch(client, "https://example.com")
