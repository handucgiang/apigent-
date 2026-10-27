# Roadmap

## Phase 0 — Foundation (week 1)
- [x] Repo, license, README, CI
- [x] `examples/hrm-demo` fake API + seed data
- [x] First eval set (10 questions; grow to 20)

## Phase 1 — MVP v0.1 (weeks 2–4)
- [x] Tool registry + `@tool`
- [x] Agent loop (parallel calls, limits, error handling)
- [x] OpenAI-compatible adapter (OpenAI, Groq, Gemini, Ollama...)
- [x] Forward the user's `auth_token` on every call
- [x] `apigent eval`
- [ ] Run the eval against a real model and tune the default prompt
- [ ] Publish 0.1.0 to PyPI

## Phase 2 — OpenAPI & server v0.2 (weeks 5–8)
- [x] Tools from OpenAPI 3.x, include/exclude, overrides
- [x] Transform: truncate, mask, drop; `calculate` tool
- [x] `POST /chat`
- [ ] `POST /chat/stream` (SSE)
- [ ] Conversation memory (in-memory, Redis)
- [ ] Docker image + compose with hrm-demo
- [ ] `apigent lint`: flag tools with weak descriptions

## Phase 3 — Integrations v0.3 (weeks 9–12)
- [ ] Embeddable chat widget (`<script>`)
- [ ] Expose tools as an MCP server
- [ ] OpenTelemetry tracing + audit log
- [ ] Docs site (MkDocs) + 2-minute demo video
- [ ] Public launch

## Towards v1.0
RAG router for document questions, GraphQL sources, admin console, multi-tenant config,
write operations with explicit user confirmation.
