"""Ask the demo HRM API a question in plain Vietnamese.

1. uvicorn hrm_api:app --port 8001
2. export GROQ_API_KEY=...       (or set APIGENT_LLM, e.g. ollama/qwen2.5:7b)
3. python quickstart.py "Tháng 9/2026 phòng Kinh doanh nghỉ việc mấy người?"
"""

from __future__ import annotations

import asyncio
import os
import sys

from apigent import Agent, OpenAPISource
from apigent.agent import dump_trace


async def main(question: str) -> None:
    agent = Agent(
        os.getenv("APIGENT_LLM", "groq/openai/gpt-oss-120b"),
        sources=[
            OpenAPISource(
                "http://localhost:8001/openapi.json", include=["/reports/*", "/departments/*"]
            )
        ],
    )
    res = await agent.ask(question, auth_token=os.getenv("HRM_TOKEN", "Bearer manager-token"))
    print(res.answer)
    print("\n" + dump_trace(res))


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Công ty hiện có bao nhiêu nhân viên?"))
