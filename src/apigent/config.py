"""Build an :class:`Agent` from ``apigent.yaml``."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from apigent.agent import Agent
from apigent.openapi import OpenAPISource
from apigent.policy import Policy
from apigent.transform import Transform

_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


class SourceConfig(BaseModel):
    openapi: str
    base_url: str | None = None
    include: list[str] = ["*"]
    exclude: list[str] = []
    methods: list[str] = ["get"]
    overrides: dict[str, dict[str, Any]] = {}


class PolicyConfig(BaseModel):
    allow: list[str] = ["*"]
    deny: list[str] = []
    by_role: dict[str, list[str]] = {}


class TransformConfig(BaseModel):
    max_items: int = 50
    max_chars: int = 12_000
    mask_fields: list[str] = []
    drop_fields: list[str] = []


class AgentConfig(BaseModel):
    llm: str
    system_prompt: str | None = None
    max_turns: int = 6
    max_tool_calls: int = 12
    sources: list[SourceConfig] = []
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    transform: TransformConfig = Field(default_factory=TransformConfig)


def _expand_env(text: str) -> str:
    return _ENV_RE.sub(lambda m: os.getenv(m.group(1), m.group(2) or ""), text)


def load_config(path: str | Path) -> AgentConfig:
    raw = yaml.safe_load(_expand_env(Path(path).read_text(encoding="utf-8"))) or {}
    return AgentConfig.model_validate(raw)


def build_agent(cfg: AgentConfig, **overrides: Any) -> Agent:
    sources = [
        OpenAPISource(
            s.openapi,
            base_url=s.base_url,
            include=s.include,
            exclude=s.exclude,
            methods=s.methods,
            overrides=s.overrides,
        )
        for s in cfg.sources
    ]
    kwargs: dict[str, Any] = {
        "sources": sources,
        "policy": Policy(**cfg.policy.model_dump()),
        "transform": Transform(**cfg.transform.model_dump()),
        "system_prompt": cfg.system_prompt,
        "max_turns": cfg.max_turns,
        "max_tool_calls": cfg.max_tool_calls,
    }
    kwargs.update(overrides)
    llm = kwargs.pop("llm", cfg.llm)
    return Agent(llm, **kwargs)


def load_agent(path: str | Path, **overrides: Any) -> Agent:
    return build_agent(load_config(path), **overrides)
