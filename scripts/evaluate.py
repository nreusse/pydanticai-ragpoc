"""Opt-in actual Ollama evaluation against explicitly labelled offline sources.

This measures agent behavior, not live source availability. Semantic correctness
and the rubric's manual items still need a human review of the recorded answers.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from pydantic_ai.messages import ToolCallEvent, ToolResultEvent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from pydanticai_poc.contracts import AnswerReady
from pydanticai_poc.research import ResearchService, build_agent
from pydanticai_poc.settings import Settings
from pydanticai_poc.sources import fixture_sources


async def evaluate(cases: list[dict]) -> list[dict]:
    settings = Settings(source_mode="fixture")
    agent = build_agent(
        OpenAIChatModel(
            settings.model_name,
            provider=OpenAIProvider(
                base_url=settings.model_base_url,
                api_key=settings.model_api_key,
            ),
        )
    )
    service = ResearchService(agent, fixture_sources(), settings)
    conversations = {}
    results = []
    async with agent:
        for case in cases:
            conversation = conversations.get(case.get("followup_to")) or service.new_conversation()
            conversations[case["id"]] = conversation
            run_id = service.reserve(conversation)
            start = time.monotonic()
            answer: AnswerReady | None = None
            trace = []
            error = None
            try:
                async for event in service.stream(conversation, run_id, case["question"]):
                    if isinstance(event, AnswerReady):
                        answer = event
                    if isinstance(event, (ToolCallEvent, ToolResultEvent)):
                        trace.append(str(event)[:2500])
            except Exception as exc:
                error = str(exc)
            ok = False
            if answer:
                text = str(answer.answer["text"]).casefold()
                sources = {row["source_id"] for row in answer.sources}
                ok = (
                    all(word.casefold() in text for word in case.get("contains", []))
                    and all(word.casefold() not in text for word in case.get("forbidden", []))
                    and set(case["sources"]) <= sources
                    and (not case.get("insufficient") or answer.answer["insufficient"])
                )
            row = {
                "id": case["id"],
                "automated_ok": ok,
                "seconds": round(time.monotonic() - start, 2),
                "result": {"answer": answer.answer, "sources": answer.sources} if answer else None,
                "trace": trace,
                "error": error,
            }
            results.append(row)
            print(
                json.dumps(
                    {key: row[key] for key in ("id", "automated_ok", "seconds", "error")},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            await asyncio.to_thread(
                Path("docs/evaluation-results.json").write_text,
                json.dumps(results, ensure_ascii=False, indent=2) + "\n",
            )
    return results


if __name__ == "__main__":
    cases = json.loads(Path("tests/fixtures/evaluation.json").read_text())
    if len(sys.argv) > 1:
        cases = [case for case in cases if case["id"] in sys.argv[1:]]
    asyncio.run(evaluate(cases))
