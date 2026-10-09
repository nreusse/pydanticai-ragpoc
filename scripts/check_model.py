"""Opt-in local model check: tools, German output and structured evidence references."""

import asyncio
import json
import time
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


class Answer(BaseModel):
    text: str
    evidence_ids: list[str]


async def main() -> None:
    agent = Agent(
        OpenAIChatModel(
            "granite4.2:3b",
            provider=OpenAIProvider(base_url="http://127.0.0.1:11434/v1", api_key="ollama"),
        ),
        output_type=Answer,
        name="model_check",
        instructions=(
            "Antworte auf Deutsch. Rufe IMMER lookup auf, bevor du antwortest. "
            "Nutze nur dessen Ergebnis und die evidence_id E1. Keine URLs erfinden."
        ),
        model_settings={
            "temperature": 0,
            "max_tokens": 400,
            "timeout": 90,
            "extra_body": {"reasoning_effort": "none"},
        },
    )
    calls = 0

    @agent.tool_plain
    async def lookup(keyword: str) -> dict[str, str]:
        """Read the authoritative test record for a keyword."""
        nonlocal calls
        calls += 1
        return {"evidence_id": "E1", "text": "Das Testprojekt heißt Lesefuchs."}

    results = []
    async with agent:
        for index in range(10):
            before = calls
            start = time.monotonic()
            try:
                async with asyncio.timeout(120):
                    result = await agent.run(
                        f"Wie heißt das Testprojekt? Prüflauf {index + 1}.",
                        usage_limits=UsageLimits(request_limit=4, tool_calls_limit=3),
                    )
                ok = (
                    calls > before
                    and "Lesefuchs" in result.output.text
                    and result.output.evidence_ids == ["E1"]
                )
                error = None
            except Exception as exc:
                ok, error = False, f"{type(exc).__name__}: {exc}"
            row: dict[str, object] = {
                "case": index + 1,
                "ok": ok,
                "seconds": round(time.monotonic() - start, 2),
            }
            if error:
                row["error"] = error
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    await asyncio.to_thread(
        Path("docs/model-check.json").write_text,
        json.dumps({"model": "granite4.2:3b", "results": results}, indent=2) + "\n",
    )


if __name__ == "__main__":
    asyncio.run(main())
