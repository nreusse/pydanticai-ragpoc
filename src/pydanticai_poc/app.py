"""Thin web boundary: server-owned sessions and AG-UI encoded SSE."""

import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast
from uuid import UUID

import httpx
from ag_ui.core import BaseEvent
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.ui.ag_ui import AGUIEventStream
from starlette.background import BackgroundTask

from .access import User, can_access_source, current_user
from .nrwbank import NRWBank
from .research import ResearchService, RunData, build_agent
from .settings import Settings
from .sources import OpenLibrary, Source, Wikipedia, fixture_sources

ROOT = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=ROOT / "templates")


class ChatInput(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=1200)
    source_ids: list[str] | None = Field(default=None, max_length=100)


class SessionOutput(BaseModel):
    conversation_id: str


class HealthOutput(BaseModel):
    status: str = "ok"
    model: str
    source_mode: str
    busy: bool


def service_from(request: Request) -> ResearchService:
    return request.app.state.service


Service = Annotated[ResearchService, Depends(service_from)]


CurrentUser = Annotated[User, Depends(current_user)]


def sources_for_user(research: Service, user: CurrentUser) -> dict[str, Source]:
    """Apply server-owned roles before source selection and agent execution."""
    return {key: source for key, source in research.sources.items() if can_access_source(user, key)}


AllowedSources = Annotated[dict[str, Source], Depends(sources_for_user)]


def create_app(settings: Settings | None = None, service: ResearchService | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if service is not None:
            app.state.service = service
            yield
            return
        # Own network clients once per application, not once per request.
        async with httpx.AsyncClient(
            timeout=config.source_timeout,
            follow_redirects=False,
            headers={"User-Agent": "ResearchPOC/0.1 (local read-only demonstration)"},
        ) as source_client:
            provider = OpenAIProvider(
                base_url=config.model_base_url,
                api_key=config.model_api_key,
            )
            agent: Agent[RunData, str] = build_agent(
                OpenAIChatModel(config.model_name, provider=provider)
            )
            sources: dict[str, Source] = (
                fixture_sources()
                if config.source_mode == "fixture"
                else {
                    "wikipedia": Wikipedia(source_client),
                    "openlibrary": OpenLibrary(source_client),
                    "nrwbank": NRWBank(source_client),
                }
            )
            async with agent:
                app.state.service = ResearchService(agent, sources, config)
                yield

    app = FastAPI(title="Quellenwerk – Recherche-POC", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "model": config.model_name,
                "source_mode": config.source_mode,
            },
        )

    @app.get("/api/health")
    async def health(research: Service) -> HealthOutput:
        # Liveness only: a model outage must not prevent the UI from loading.
        return HealthOutput(
            model=research.settings.model_name,
            source_mode=research.settings.source_mode,
            busy=research.active_run is not None,
        )

    @app.get("/api/me")
    async def me(user: CurrentUser) -> dict[str, object]:
        return {
            "id": user.id,
            "display_name": user.display_name,
            "roles": sorted(role.value for role in user.roles),
        }

    @app.get("/api/sources")
    async def available_sources(allowed: AllowedSources) -> list[dict[str, str]]:
        return [{"id": key, "name": source.name} for key, source in allowed.items()]

    @app.post("/api/conversations")
    async def new_conversation(research: Service) -> SessionOutput:
        try:
            return SessionOutput(conversation_id=research.new_conversation().id)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/chat", response_class=StreamingResponse)
    async def chat(
        payload: ChatInput, research: Service, allowed: AllowedSources
    ) -> StreamingResponse:
        question = payload.message.strip()
        if not question:
            raise HTTPException(422, "Bitte gib eine Frage ein.")
        conversation = research.conversations.get(str(payload.conversation_id))
        if conversation is None:
            raise HTTPException(404, "Unterhaltung abgelaufen. Bitte starte eine neue.")
        selected = list(allowed) if payload.source_ids is None else payload.source_ids
        if not selected:
            raise HTTPException(422, "Bitte wähle mindestens eine verfügbare Quelle.")
        if any(key not in allowed for key in selected):
            raise HTTPException(403, "Mindestens eine gewählte Quelle ist nicht verfügbar.")
        effective = {key: allowed[key] for key in selected}
        try:
            run_id = research.reserve(conversation)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        encoder = AGUIEventStream(thread_id=conversation.id, run_id=run_id)

        async def body() -> AsyncIterator[str]:
            native = research.stream(conversation, run_id, question, effective)
            transformed = cast(AsyncGenerator[BaseEvent, None], encoder.transform_stream(native))
            try:
                async for event in encoder.encode_stream(transformed):
                    yield event
            finally:
                # Explicitly close nested iterators on disconnect under Python 3.11.
                await transformed.aclose()
                await native.aclose()
                research.release(conversation, run_id)

        # The official encoder already produces SSE framing. StreamingResponse
        # forwards it verbatim rather than encoding the frames a second time.
        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            background=BackgroundTask(research.release, conversation, run_id),
        )

    return app


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
