"""End-to-end with the demo HRM API and a scripted LLM (no network, no API key)."""

from __future__ import annotations

from typing import Any

import httpx

from apigent import Agent, LLMResponse, OpenAPISource, ScriptedLLM, ToolCall, UserContext


def source(client: httpx.AsyncClient, spec: dict[str, Any]) -> OpenAPISource:
    return OpenAPISource(spec, include=["/reports/*", "/departments/*"], client=client)


async def test_tools_generated_from_openapi(hrm_app: Any, hrm_client: httpx.AsyncClient) -> None:
    tools = {t.name: t for t in await source(hrm_client, hrm_app.openapi()).tools()}
    assert set(tools) == {
        "searchDepartments",
        "getHeadcount",
        "getTurnover",
        "getLeaveSummary",
        "getSalaryCost",
    }
    turnover = tools["getTurnover"].parameters
    assert turnover["required"] == ["month"]
    assert "department_id" in turnover["properties"]
    assert "authorization" not in {k.lower() for k in turnover["properties"]}


async def test_agent_answers_with_user_token(hrm_app: Any, hrm_client: httpx.AsyncClient) -> None:
    llm = ScriptedLLM(
        [
            LLMResponse(None, [ToolCall("c1", "searchDepartments", {"keyword": "kinh doanh"})]),
            LLMResponse(
                None,
                [
                    ToolCall("c2", "getTurnover", {"month": "2026-09", "department_id": "d3"}),
                    ToolCall("c3", "getHeadcount", {"department_id": "d3"}),
                ],
            ),
            LLMResponse(
                None, [ToolCall("c4", "calculate", {"expression": "round(3 / 14 * 100, 1)"})]
            ),
            LLMResponse("Tháng 9/2026 phòng Kinh doanh có 3 người nghỉ, tương đương 21.4%.", []),
        ]
    )
    agent = Agent(llm, sources=[source(hrm_client, hrm_app.openapi())])
    res = await agent.ask("...", ctx=UserContext(auth_token="manager-token"))

    assert res.stopped == "answered"
    assert [s.name for s in res.steps] == [
        "searchDepartments",
        "getTurnover",
        "getHeadcount",
        "calculate",
    ]
    assert all(s.ok for s in res.steps)
    assert res.steps[1].result["total"] == 3
    assert res.steps[3].result["result"] == 21.4
    # the tool results really reached the model
    last_messages = llm.calls[-1][0]
    assert any(m["role"] == "tool" and '"total": 14' in m["content"] for m in last_messages)


async def test_permission_denied_is_reported_not_bypassed(
    hrm_app: Any, hrm_client: httpx.AsyncClient
) -> None:
    llm = ScriptedLLM(
        [
            LLMResponse(None, [ToolCall("c1", "getSalaryCost", {"department_id": "d2"})]),
            LLMResponse("Bạn không có quyền xem chi phí lương.", []),
        ]
    )
    agent = Agent(llm, sources=[source(hrm_client, hrm_app.openapi())])
    res = await agent.ask("lương phòng kỹ thuật?", auth_token="staff-token")
    step = res.steps[0]
    assert not step.ok and "not allowed" in step.result
    assert "780" not in str(llm.calls[-1][0])


async def test_denied_tools_are_invisible_to_llm(
    hrm_app: Any, hrm_client: httpx.AsyncClient
) -> None:
    from apigent import Policy

    llm = ScriptedLLM(
        [
            LLMResponse(None, [ToolCall("c1", "getSalaryCost", {})]),
            LLMResponse("ok", []),
        ]
    )
    agent = Agent(
        llm, sources=[source(hrm_client, hrm_app.openapi())], policy=Policy(deny=["getSalaryCost"])
    )
    res = await agent.ask("x", auth_token="manager-token")
    offered = [t["function"]["name"] for t in llm.calls[0][1]]
    assert "getSalaryCost" not in offered
    assert not res.steps[0].ok and "does not exist" in res.steps[0].result


async def test_max_turns_stops_loop() -> None:
    llm = ScriptedLLM(
        [
            LLMResponse(None, [ToolCall(f"c{i}", "calculate", {"expression": "1+1"})])
            for i in range(3)
        ]
    )
    agent = Agent(llm, max_turns=2)
    res = await agent.ask("loop forever")
    assert res.stopped == "max_turns" and res.turns == 2


async def test_server_chat(hrm_app: Any, hrm_client: httpx.AsyncClient) -> None:
    from apigent.server import create_app

    llm = ScriptedLLM(
        [
            LLMResponse(None, [ToolCall("c1", "getHeadcount", {})]),
            LLMResponse("Phòng bạn có 25 người.", []),
        ]
    )
    agent = Agent(llm, sources=[source(hrm_client, hrm_app.openapi())])
    app = create_app(agent)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/chat",
            json={"question": "phòng tôi bao nhiêu người"},
            headers={"Authorization": "Bearer staff-token"},
        )
    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == "Phòng bạn có 25 người."
    assert body["steps"][0]["name"] == "getHeadcount" and body["steps"][0]["ok"]
