"""Optional HTTP server (``pip install apigent[server]``).

POST /chat   {"question": "...", "history": [...]}   + Authorization header of the end user
GET  /tools  list of tools visible to the caller
GET  /health
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, Header
    from pydantic import BaseModel
except ImportError as e:  # pragma: no cover
    raise ImportError("Install the server extra: pip install 'apigent[server]'") from e

from apigent.agent import Agent
from apigent.context import UserContext


class ChatRequest(BaseModel):
    question: str
    history: list[dict[str, Any]] = []
    locale: str = "vi"


class StepOut(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    duration_ms: int


class ChatResponse(BaseModel):
    answer: str
    turns: int
    stopped: str
    steps: list[StepOut]


def create_app(agent: Agent, *, expose_steps: bool = True) -> FastAPI:
    app = FastAPI(title="apigent", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/tools")
    async def list_tools(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        ctx = UserContext(auth_token=authorization)
        reg = await agent.registry()
        return [
            {"name": t.name, "description": t.description}
            for t in agent.policy.filter(list(reg), ctx)
        ]

    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        req: ChatRequest, authorization: str | None = Header(default=None)
    ) -> ChatResponse:
        ctx = UserContext(auth_token=authorization, locale=req.locale)
        res = await agent.ask(req.question, ctx=ctx, history=req.history)
        steps = (
            [
                StepOut(name=s.name, arguments=s.arguments, ok=s.ok, duration_ms=s.duration_ms)
                for s in res.steps
            ]
            if expose_steps
            else []
        )
        return ChatResponse(answer=res.answer, turns=res.turns, stopped=res.stopped, steps=steps)

    return app
