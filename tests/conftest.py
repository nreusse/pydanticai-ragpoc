"""All ordinary tests run with local functions and saved source data."""

import json
from collections.abc import AsyncIterator

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from pydanticai_poc.research import ResearchService, build_agent
from pydanticai_poc.settings import Settings
from pydanticai_poc.sources import fixture_sources


async def model_stream(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
    returns = [
        part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    if not returns:
        name, args = "search_source", {"source_id": "wikipedia", "query": "Franz Kafka"}
    elif returns[-1].tool_name == "search_source":
        name, args = "read_source", {"source_id": "wikipedia", "document_id": "1"}
    else:
        yield "Franz Kafka wurde 1883 in Prag geboren. [E1]"
        return
    yield {0: DeltaToolCall(name=name, json_args=json.dumps(args))}


@pytest.fixture
def service() -> ResearchService:
    settings = Settings(source_mode="fixture", _env_file=None)
    return ResearchService(
        build_agent(FunctionModel(stream_function=model_stream)), fixture_sources(), settings
    )
