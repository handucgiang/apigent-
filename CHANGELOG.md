# Changelog

## [Unreleased]

### Added
- Agent loop with parallel tool calls, turn and tool-call limits.
- `@tool` decorator and `ToolRegistry`.
- `OpenAPISource`: tools generated from OpenAPI 3.x (GET only), description overrides.
- OpenAI-compatible LLM adapter with presets for OpenAI, Groq, Gemini, Anthropic, OpenRouter, Ollama.
- `Policy` (allow/deny/by_role), `Transform` (truncate, mask, drop), built-in `calculate` tool.
- YAML config, CLI (`ask`, `tools`, `eval`, `serve`), FastAPI server.
- HRM demo API with eval set.
