"""Per-request user context.

Every tool call runs on behalf of the end user who asked the question. The
``auth_token`` is forwarded to the source API so the API's own permission
checks decide what the user may see -- never the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UserContext:
    auth_token: str | None = None
    """Value forwarded as the ``Authorization`` header (e.g. ``"Bearer abc"``)."""

    user_id: str | None = None
    roles: tuple[str, ...] = ()
    locale: str = "vi"
    extra: dict[str, Any] = field(default_factory=dict)

    def auth_headers(self) -> dict[str, str]:
        if not self.auth_token:
            return {}
        token = self.auth_token
        if " " not in token:
            token = f"Bearer {token}"
        return {"Authorization": token}
