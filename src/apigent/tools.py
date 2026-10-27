"""Tool definitions and the registry the agent picks from."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

from pydantic import create_model

from apigent.context import UserContext

ToolHandler = Callable[..., Awaitable[Any]]


class ToolError(Exception):
    """An error the LLM is allowed to see (e.g. "department not found")."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    wants_ctx: bool = False
    tags: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    async def run(self, args: dict[str, Any], ctx: UserContext) -> Any:
        if self.wants_ctx:
            return await self.handler(**args, ctx=ctx)
        return await self.handler(**args)

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _schema_from_signature(fn: Callable[..., Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)
    fields: dict[str, Any] = {}
    for pname, param in sig.parameters.items():
        if pname == "ctx":
            continue
        annotation = hints.get(pname, Any)
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[pname] = (annotation, default)
    model = create_model(f"{fn.__name__}_args", **fields)
    schema: dict[str, Any] = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    return schema


def tool(
    fn: ToolHandler | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: Iterable[str] = (),
) -> Any:
    """Turn an async function into a :class:`Tool`.

    The docstring becomes the description the LLM reads, so write it for the
    model: what the tool returns, when to use it, and the format of each
    argument. Add a ``ctx: UserContext`` parameter to receive the caller.

    >>> @tool
    ... async def get_headcount(department_id: str | None = None, ctx: UserContext = None):
    ...     '''Number of active employees, optionally filtered by department.'''
    """

    def wrap(f: ToolHandler) -> Tool:
        if not inspect.iscoroutinefunction(f):
            raise TypeError(f"@tool requires an async function, got {f.__name__}")
        doc = description or inspect.getdoc(f) or ""
        if not doc:
            raise ValueError(f"Tool {f.__name__} needs a description (docstring) for the LLM")
        return Tool(
            name=name or f.__name__,
            description=doc,
            parameters=_schema_from_signature(f),
            handler=f,
            wants_ctx="ctx" in inspect.signature(f).parameters,
            tags=tuple(tags),
        )

    if fn is not None:
        return wrap(fn)
    return wrap


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for t in tools:
            self.add(t)

    def add(self, t: Tool) -> None:
        if t.name in self._tools:
            raise ValueError(f"Duplicate tool name: {t.name}")
        self._tools[t.name] = t

    def extend(self, tools: Iterable[Tool]) -> None:
        for t in tools:
            self.add(t)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def names(self) -> list[str]:
        return list(self._tools)
