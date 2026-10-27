from __future__ import annotations

import pytest

from apigent import Policy, Transform, UserContext, tool
from apigent.builtins import safe_eval
from apigent.tools import ToolError


@tool
async def get_headcount(department_id: str | None = None, ctx: UserContext | None = None) -> int:
    """Number of active employees."""
    return 3


def test_tool_schema_skips_ctx() -> None:
    schema = get_headcount.parameters
    assert set(schema["properties"]) == {"department_id"}
    assert "required" not in schema
    assert get_headcount.wants_ctx
    assert get_headcount.to_openai()["function"]["name"] == "get_headcount"


def test_tool_requires_docstring() -> None:
    with pytest.raises(ValueError):

        @tool
        async def nodoc() -> None:
            pass


@pytest.mark.parametrize(
    ("expr", "value"),
    [("1 + 2 * 3", 7), ("round(3 / 14 * 100, 1)", 21.4), ("sum([1, 2, 3])", 6), ("-2 ** 2", -4)],
)
def test_safe_eval(expr: str, value: float) -> None:
    assert safe_eval(expr) == value


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "1/0", "9 ** 9999", "[1, 2]"])
def test_safe_eval_rejects(expr: str) -> None:
    with pytest.raises(ToolError):
        safe_eval(expr)


def test_policy_deny_wins_and_roles() -> None:
    p = Policy(allow=["get*"], deny=["*Salary*"], by_role={"hr": ["list*"]})
    names = ["getHeadcount", "getSalaryCost", "listEmployees"]

    class T:
        def __init__(self, name: str) -> None:
            self.name = name

    staff = [n for n in names if p.permits(T(n), UserContext())]  # type: ignore[arg-type]
    hr = [n for n in names if p.permits(T(n), UserContext(roles=("hr",)))]  # type: ignore[arg-type]
    assert staff == ["getHeadcount"]
    assert hr == ["getHeadcount", "listEmployees"]


def test_transform_masks_and_truncates() -> None:
    t = Transform(max_items=2, mask_fields=["*phone*"], drop_fields=["password"])
    out = t.apply({"rows": [{"phone_number": "0901", "password": "x", "n": i} for i in range(5)]})
    assert out["rows"][0] == {"phone_number": "***", "n": 0}
    assert len(out["rows"]) == 3 and "_truncated" in out["rows"][-1]


def test_auth_headers() -> None:
    assert UserContext(auth_token="abc").auth_headers() == {"Authorization": "Bearer abc"}
    assert UserContext(auth_token="Token x").auth_headers() == {"Authorization": "Token x"}
    assert UserContext().auth_headers() == {}
