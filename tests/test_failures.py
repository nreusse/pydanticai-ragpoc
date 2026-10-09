import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.function import AgentInfo, FunctionModel

from pydanticai_poc.contracts import AnswerReady
from pydanticai_poc.research import ResearchService


async def test_unavailable_model_has_clear_failure_and_releases(service: ResearchService):
    async def unavailable(messages, info: AgentInfo):
        raise ModelHTTPError(status_code=503, model_name="missing")
        yield "unreachable"

    with service.agent.override(model=FunctionModel(stream_function=unavailable)):
        conversation = service.new_conversation()
        run_id = service.reserve(conversation)
        with pytest.raises(RuntimeError, match="Prüfe Ollama"):
            _ = [event async for event in service.stream(conversation, run_id, "Kafka")]
    assert service.active_run is None
    assert conversation.status == "failed"
    assert not conversation.turns


async def test_tool_limit_releases(service: ResearchService):
    service.settings.max_tool_calls = 1
    conversation = service.new_conversation()
    run_id = service.reserve(conversation)
    with pytest.raises(RuntimeError, match="nicht abschließen"):
        _ = [event async for event in service.stream(conversation, run_id, "Kafka")]
    assert service.active_run is None
    assert conversation.status == "failed"


async def test_disconnect_while_agent_running(service: ResearchService):
    from pydantic_ai.messages import FunctionToolCallEvent

    conversation = service.new_conversation()
    run_id = service.reserve(conversation)
    stream = service.stream(conversation, run_id, "Kafka")
    async for event in stream:
        if isinstance(event, FunctionToolCallEvent):
            break
    await stream.aclose()
    assert service.active_run is None
    assert conversation.status == "cancelled"


async def test_bad_citation_is_never_published(service: ResearchService):
    from pydantic_ai.models.test import TestModel

    with service.agent.override(
        model=TestModel(
            call_tools=[],
            custom_output_text="Erfundener Beleg [E99]",
        )
    ):
        conversation = service.new_conversation()
        run_id = service.reserve(conversation)
        published = []
        with pytest.raises(RuntimeError, match="nicht abschließen"):
            async for event in service.stream(conversation, run_id, "Kafka"):
                if isinstance(event, AnswerReady):
                    published.append(event)
        assert not published
