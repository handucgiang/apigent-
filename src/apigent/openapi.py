"""Generate tools from an OpenAPI 3.x spec.

Only read operations (GET) are exposed by default. Each call is made with the
end user's token, so the API's own permission rules apply.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import yaml

from apigent.context import UserContext
from apigent.tools import Tool, ToolError

_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _resolve(spec: dict[str, Any], node: Any, depth: int = 0) -> Any:
    """Inline local ``$ref``s (``#/components/...``)."""
    if depth > 20:
        return node
    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/"):
            target: Any = spec
            for part in node["$ref"][2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            return _resolve(spec, target, depth + 1)
        return {k: _resolve(spec, v, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve(spec, v, depth + 1) for v in node]
    return node


def _tool_name(op: dict[str, Any], method: str, path: str) -> str:
    raw = op.get("operationId") or f"{method}_{path}"
    name = _NAME_RE.sub("_", raw).strip("_")
    return name[:64]


class OpenAPISource:
    """Expose an API's operations as tools.

    :param spec: URL, file path, or already-loaded dict.
    :param base_url: API root; defaults to the first ``servers`` entry.
    :param include: glob patterns on the path (``"/reports/*"``). Default: all.
    :param exclude: glob patterns on the path to skip.
    :param methods: HTTP methods to expose. Keep it to GET unless you add confirmation.
    :param overrides: ``{tool_name: {"description": ...}}`` to fix weak spec docs.
    """

    def __init__(
        self,
        spec: str | Path | dict[str, Any],
        *,
        base_url: str | None = None,
        include: Iterable[str] = ("*",),
        exclude: Iterable[str] = (),
        methods: Iterable[str] = ("get",),
        overrides: dict[str, dict[str, Any]] | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.spec_ref = spec
        self.base_url = base_url
        self.include = list(include)
        self.exclude = list(exclude)
        self.methods = [m.lower() for m in methods]
        self.overrides = overrides or {}
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._spec: dict[str, Any] | None = None

    async def load_spec(self) -> dict[str, Any]:
        if self._spec is not None:
            return self._spec
        ref = self.spec_ref
        if isinstance(ref, dict):
            spec = ref
        elif isinstance(ref, str) and ref.startswith(("http://", "https://")):
            resp = await self._client.get(ref)
            resp.raise_for_status()
            spec = yaml.safe_load(resp.text)
        else:
            text = await asyncio.to_thread(Path(ref).read_text, encoding="utf-8")
            spec = yaml.safe_load(text)
        if not str(spec.get("openapi", "")).startswith("3"):
            raise ValueError("Only OpenAPI 3.x specs are supported")
        self._spec = spec
        if self.base_url is None:
            servers = spec.get("servers") or []
            if servers:
                self.base_url = servers[0]["url"]
            elif isinstance(ref, str) and ref.startswith(("http://", "https://")):
                self.base_url = str(httpx.URL(ref).copy_with(path="/", query=None))
        return spec

    def _selected(self, path: str) -> bool:
        if any(fnmatch(path, p) for p in self.exclude):
            return False
        return any(fnmatch(path, p) for p in self.include)

    async def tools(self) -> list[Tool]:
        spec = await self.load_spec()
        out: list[Tool] = []
        for path, item in (spec.get("paths") or {}).items():
            if not self._selected(path):
                continue
            item = _resolve(spec, item)
            shared_params = item.get("parameters", [])
            for method in self.methods:
                op = item.get(method)
                if not op or op.get("deprecated"):
                    continue
                out.append(self._make_tool(path, method, op, shared_params))
        return out

    def _make_tool(
        self, path: str, method: str, op: dict[str, Any], shared: list[dict[str, Any]]
    ) -> Tool:
        name = _tool_name(op, method, path)
        params = {(p["name"], p["in"]): p for p in shared}
        params.update({(p["name"], p["in"]): p for p in op.get("parameters", [])})
        props: dict[str, Any] = {}
        required: list[str] = []
        locations: dict[str, str] = {}
        for (pname, loc), p in params.items():
            if loc not in ("path", "query"):
                continue  # headers/cookies are set by apigent, not the LLM
            schema = dict(p.get("schema") or {"type": "string"})
            schema.pop("title", None)
            if p.get("description"):
                schema["description"] = p["description"]
            props[pname] = schema
            locations[pname] = loc
            if p.get("required") or loc == "path":
                required.append(pname)

        description = (
            " ".join(s for s in (op.get("summary"), op.get("description")) if s)
            or f"{method.upper()} {path}"
        )
        override = self.overrides.get(name, {})
        description = override.get("description", description)

        parameters: dict[str, Any] = {"type": "object", "properties": props}
        if required:
            parameters["required"] = sorted(set(required))

        async def handler(ctx: UserContext, **kwargs: Any) -> Any:
            return await self._call(method, path, locations, kwargs, ctx)

        return Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            wants_ctx=True,
            tags=tuple(op.get("tags", [])),
            meta={"method": method.upper(), "path": path},
        )

    async def _call(
        self,
        method: str,
        path: str,
        locations: dict[str, str],
        args: dict[str, Any],
        ctx: UserContext,
    ) -> Any:
        unknown = set(args) - set(locations)
        if unknown:
            raise ToolError(f"Unknown parameter(s): {', '.join(sorted(unknown))}")
        url_path = path
        query: dict[str, Any] = {}
        for k, v in args.items():
            if v is None:
                continue
            if locations[k] == "path":
                url_path = url_path.replace("{" + k + "}", quote(str(v), safe=""))
            else:
                query[k] = v
        if not self.base_url:
            raise ToolError("API base_url is not configured")
        url = self.base_url.rstrip("/") + url_path
        resp = await self._client.request(
            method.upper(), url, params=query, headers=ctx.auth_headers()
        )
        if resp.status_code in (401, 403):
            raise ToolError("The current user is not allowed to access this data.")
        if resp.status_code == 404:
            raise ToolError("Not found.")
        if resp.status_code >= 400:
            raise ToolError(f"API error {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except json.JSONDecodeError:
            return resp.text
