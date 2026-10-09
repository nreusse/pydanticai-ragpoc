import json

import httpx
import pytest

from pydanticai_poc.nrwbank import NRWBank
from pydanticai_poc.sources import SourceError

DOC_ID = "d4a47249-3ad4-11f0-848c-1d7b371dccb1"
DOCUMENT = {
    "id": DOC_ID,
    "type": "localProduct",
    "link": "/.content/localProduct/15913.xml",
    "title_de_s": "Innovation und Digitalisierung",
    "description_de_s": "Fördert Unternehmen.",
    "content_de": ["Ein lesbarer Text.", "Weitere Angaben."],
    "public_access": True,
    "search_exclude": "false",
}


def response(rows):
    return httpx.Response(200, json={"responseHeader": {"status": 0}, "response": {"docs": rows}})


async def test_search_read_and_fixed_request_parameters():
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url).startswith(NRWBank.endpoint)
        assert request.url.params["fq"] == NRWBank.public_filter
        assert "contentblob" not in request.url.params["fl"]
        return response([DOCUMENT])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = NRWBank(client)
        hits = await source.search("Digitalisierung OR id:*", 3)
        assert requests[0].url.params["q"] == r'"Digitalisierung" "OR" "id\:\*"'
        assert "content_de" not in requests[0].url.params["fl"]
        assert hits[0].url.endswith("/foerderprodukte/15913/index.html")
        evidence = await source.read(hits[0].document_id, 30)
        assert requests[1].url.params["q"] == f'id:"{DOC_ID}"'
        assert "content_de" in requests[1].url.params["fl"]
        assert evidence.text.startswith("Fördert Unternehmen.\nEin")
        assert evidence.truncated
        assert "SOLR" in evidence.locator
        assert "contentblob" not in json.dumps(evidence.model_dump(mode="json"))


@pytest.mark.parametrize(
    "changes",
    [
        {"public_access": False},
        {"search_exclude": "true"},
        {"type": "text"},
        {"link": "https://evil.example/page.html"},
        {"type": "containerpage", "link": "/de/../partner/secret.html"},
        {"type": "containerpage", "link": "//evil.example/page.html"},
    ],
)
async def test_unusable_or_nonpublic_rows_are_never_exposed(changes):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: response([{**DOCUMENT, **changes}]))
    ) as client:
        source = NRWBank(client)
        assert await source.search("Digitalisierung", 3) == []
        with pytest.raises(SourceError, match="nicht mehr verfügbar"):
            await source.read(DOC_ID, 1500)


async def test_container_page_and_title_fallback():
    row = {**DOCUMENT, "type": "containerpage", "link": "/de/themen/index.html"}
    del row["title_de_s"]
    row["Title_prop_s"] = "Themen"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _, row=row: response([row]))
    ) as client:
        hit = (await NRWBank(client).search("Themen", 1))[0]
        assert hit.title == "Themen"
        assert hit.url == "https://www.nrwbank.de/de/themen/index.html"


async def test_invalid_id_does_not_issue_request():
    def handler(_):
        raise AssertionError("No request expected")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError, match="Dokument-ID"):
            await NRWBank(client).read("* OR id:*", 1500)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"responseHeader": {"status": 1}},
        {"responseHeader": {"status": 0}, "response": {"docs": "invalid"}},
    ],
)
async def test_bad_solr_format(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(SourceError):
            await NRWBank(client).search("test", 1)


async def test_wrong_id_and_empty_text_are_not_evidence():
    for row in (
        {**DOCUMENT, "id": "c7d10dd2-cdc5-11eb-b88e-7516f6b84173"},
        {**DOCUMENT, "description_de_s": "", "content_de": []},
    ):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _, row=row: response([row]))
        ) as client:
            with pytest.raises(SourceError):
                await NRWBank(client).read(DOC_ID, 1500)
