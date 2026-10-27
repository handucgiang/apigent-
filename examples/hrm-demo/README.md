# HRM demo

A fake HRM API (`hrm_api.py`, fake data) plus an apigent config and an eval set.

```bash
# from the repo root
uv sync
cd examples/hrm-demo
uv run uvicorn hrm_api:app --port 8001          # terminal 1

export GROQ_API_KEY=...                          # terminal 2
uv run apigent -c apigent.yaml tools
uv run apigent -c apigent.yaml ask "Tháng 9/2026 có bao nhiêu người nghỉ việc?" \
    --token "Bearer manager-token" --trace
uv run apigent -c apigent.yaml eval eval.yaml
uv run apigent -c apigent.yaml serve --port 8080
```

| Token | Who | Sees |
| --- | --- | --- |
| `Bearer manager-token` | HR manager | every department, salary cost |
| `Bearer staff-token` | Engineer in Kỹ thuật | own department only, no salary |

Try asking the staff token about another department's salary: the API returns 403 and the bot
says the user lacks permission. The LLM never decides access.
