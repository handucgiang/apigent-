"""Which tools a given user may see.

Tools a user is not allowed to use are never sent to the LLM, so a prompt
injection cannot call them: they simply do not exist for that conversation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

from apigent.context import UserContext
from apigent.tools import Tool


@dataclass
class Policy:
    allow: list[str] = field(default_factory=lambda: ["*"])
    """Glob patterns of tool names everyone may use."""

    deny: list[str] = field(default_factory=list)
    """Glob patterns that are always removed (wins over ``allow``)."""

    by_role: dict[str, list[str]] = field(default_factory=dict)
    """Extra allow patterns per role, e.g. ``{"hr_admin": ["*salary*"]}``."""

    def permits(self, t: Tool, ctx: UserContext) -> bool:
        if any(fnmatch(t.name, p) for p in self.deny):
            return False
        patterns = list(self.allow)
        for role in ctx.roles:
            patterns += self.by_role.get(role, [])
        return any(fnmatch(t.name, p) for p in patterns)

    def filter(self, tools: list[Tool], ctx: UserContext) -> list[Tool]:
        return [t for t in tools if self.permits(t, ctx)]
