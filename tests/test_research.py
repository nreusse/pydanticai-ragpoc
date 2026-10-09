import asyncio

import pytest
from pydantic_ai import ModelRetry

from pydanticai_poc.contracts import AnswerReady, ResearchAnswer
from pydanticai_poc.research import ResearchService, RunData, validate_answer
from pydanticai_poc.settings import Settings
from pydanticai_poc.sources import fixture_sources


async def test_search_read_answer_and_followup(service: ResearchService):
    conversation = service.new_conversation()
    for question in ("Wer war Kafka?", "Wo wurde er geboren?"):
        run_id = service.reserve(conversation)
        events = [event async for event in service.stream(conversation, run_id, question)]
        answer = next(event for event in events if isinstance(event, AnswerReady))
        assert answer.answer["evidence_ids"] == ["E1"]
        assert answer.sources[0]["document_id"] == "1"
        assert conversation.status == "completed"
        assert service.active_run is None
    assert len(conversation.turns) == 2
    assert "[E1]" not in conversation.turns[0][1]


async def test_only_discovered_documents_and_document_limit():
    data = RunData(Settings(max_documents=1, _env_file=None), fixture_sources())
    with pytest.raises(ModelRetry, match="Zuerst suchen"):
        await data.read("wikipedia", "1")
    await data.search("wikipedia", "Kafka Verwandlung")
    first = await data.read("wikipedia", "1")
    assert await data.read("wikipedia", "1") is first
    with pytest.raises(ModelRetry, match="Dokumentlimit"):
        await data.read("wikipedia", "2")
    with pytest.raises(ModelRetry, match="Quelle für diesen Lauf nicht verfügbar"):
        await data.search("http://localhost", "test")


@pytest.mark.parametrize(
    "answer",
    [
        ResearchAnswer(text="Erfunden [E9]", evidence_ids=["E9"]),
        ResearchAnswer(text="Ohne Beleg"),
        ResearchAnswer(text="Link https://example.com", insufficient=True),
    ],
)
def test_invalid_references_rejected(answer):
    with pytest.raises(ModelRetry):
        validate_answer(answer, {})


def test_insufficient_answer_is_not_unverified_model_prose():
    answer = validate_answer(ResearchAnswer(text="Erfundene Behauptung", insufficient=True), {})
    assert answer.insufficient
    assert "Erfundene" not in answer.text


async def test_busy_and_disconnect_release(service: ResearchService):
    conversation = service.new_conversation()
    run_id = service.reserve(conversation)
    with pytest.raises(RuntimeError, match="bereits"):
        service.reserve(service.new_conversation())
    stream = service.stream(conversation, run_id, "Kafka")
    await anext(stream)
    await stream.aclose()
    assert service.active_run is None
    assert conversation.status == "cancelled"


async def test_timeout_releases_model(service: ResearchService):
    class SlowSource:
        name = "slow"

        async def search(self, query, limit):
            await asyncio.sleep(10)
            return []

        async def read(self, document_id, max_chars):
            raise AssertionError("not reached")

    service.sources["wikipedia"] = SlowSource()
    service.settings.run_timeout = 0.02
    conversation = service.new_conversation()
    run_id = service.reserve(conversation)
    with pytest.raises(RuntimeError, match="Zeitlimit"):
        _ = [event async for event in service.stream(conversation, run_id, "Kafka")]
    assert conversation.status == "failed"
    assert service.active_run is None


def test_sessions_are_bounded(service: ResearchService):
    service.settings.max_sessions = 2
    first = service.new_conversation()
    service.reserve(first)
    second = service.new_conversation()
    third = service.new_conversation()
    assert first.id in service.conversations
    assert second.id not in service.conversations
    assert third.id in service.conversations


async def test_valid_ids_get_canonical_markers():
    data = RunData(Settings(_env_file=None), fixture_sources())
    await data.search("wikipedia", "Kafka")
    row = await data.read("wikipedia", "1")
    answer = validate_answer(
        ResearchAnswer(text="Kafka war Schriftsteller.", evidence_ids=["E1"]), {"E1": row}
    )
    assert answer.text.endswith("[E1]")
    with pytest.raises(ModelRetry):
        validate_answer(ResearchAnswer(text="Kafka [E2]", evidence_ids=["E1"]), {"E1": row})


async def test_disconnect_after_answer_preserves_completed_turn(service: ResearchService):
    conversation = service.new_conversation()
    run_id = service.reserve(conversation)
    stream = service.stream(conversation, run_id, "Kafka")
    async for event in stream:
        if isinstance(event, AnswerReady):
            break
    await stream.aclose()
    assert conversation.status == "completed"
    assert len(conversation.turns) == 1
    assert service.active_run is None


async def test_unavailable_source_cannot_be_searched_or_read():
    sources = fixture_sources()
    data = RunData(Settings(_env_file=None), {"wikipedia": sources["wikipedia"]})
    with pytest.raises(ModelRetry, match="nicht verfügbar"):
        await data.search("openlibrary", "Kafka")
    # Even an old/discovered ID must not bypass the current source scope.
    from pydanticai_poc.contracts import SearchHit

    data.found[("openlibrary", "OL1W")] = SearchHit(
        source_id="openlibrary",
        document_id="OL1W",
        title="Old",
        url="https://example.com",
        snippet="",
    )
    with pytest.raises(ModelRetry, match="nicht verfügbar"):
        await data.read("openlibrary", "OL1W")


async def test_instructions_and_schema_are_isolated_per_run(service: ResearchService):
    from pydantic_ai.models.function import FunctionModel

    seen = []

    async def inspect(messages, info):
        seen.append(info)
        yield "Keine Belege verfügbar."

    conversation = service.new_conversation()
    with service.agent.override(model=FunctionModel(stream_function=inspect)):
        for key in ("wikipedia", "openlibrary"):
            conversation.turns = [("alte Frage", "vertrauliche alte Antwort")]
            run_id = service.reserve(conversation)
            stream = service.stream(conversation, run_id, "Kafka", {key: service.sources[key]})
            # The output validator retries because this model never searches.
            with pytest.raises(RuntimeError):
                _ = [event async for event in stream]
            assert not conversation.turns
            for info in seen:
                assert f"- {key}:" in info.instructions
                other = "openlibrary" if key == "wikipedia" else "wikipedia"
                assert f"- {other}:" not in info.instructions
                for tool in info.function_tools:
                    assert tool.parameters_json_schema["properties"]["source_id"]["enum"] == [key]
            seen.clear()
