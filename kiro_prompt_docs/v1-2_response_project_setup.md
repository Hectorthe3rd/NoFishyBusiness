## V1 — Initial Implementation

**What was built and why:**

NoFishyBusiness is a locally-hosted aquarium information web app. The goal was a proof-of-concept that uses a FastAPI backend, a Streamlit frontend, a local SQLite knowledge base, and OpenAI's gpt-4o-mini to answer aquarium questions. All AI responses are grounded through a RAG (Retrieval-Augmented Generation) pipeline so the LLM only answers from curated local data, not general training knowledge.

**Architecture decisions made:**

- **Separate backend and frontend processes** — FastAPI handles all AI logic and API routes; Streamlit handles only the UI. This keeps concerns separated and lets the eval suite call the backend directly without a browser.
- **SQLite + FTS5 for RAG** — no external vector database needed. FTS5 full-text search is built into SQLite, keeping the project fully local with no cloud dependencies.
- **Topic Guard** — a keyword-vocabulary classifier that intercepts every query before it reaches the LLM. Queries with no aquarium terms are refused outright; mixed queries are forwarded with a system instruction to stay on-topic.
- **Token budget enforcement** — every OpenAI call is capped at `max_tokens=1500` output and 2000 tokens of RAG context to prevent runaway API costs.

**Files generated (V1):**

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, lifespan startup validation, all 8 route registrations |
| `backend/models.py` | Pydantic models for all request/response types |
| `backend/rag.py` | FTS5 retrieval pipeline, `RAGError` exception |
| `backend/topic_guard.py` | Aquarium topic classifier with vocabulary loaded from DB |
| `backend/token_budget.py` | `count_tokens` and `truncate_context` using tiktoken |
| `backend/logger.py` | Structured JSON logging to `backend/app.log` |
| `backend/assistant.py` | Conversational AI with session history and RAG |
| `backend/tools/volume.py` | Pure math volume/weight calculator |
| `backend/tools/species.py` | Fish care sheet lookup via RAG + LLM |
| `backend/tools/maintenance.py` | Nitrogen cycle and maintenance guide |
| `backend/tools/setup.py` | Beginner tank setup recommendations |
| `backend/tools/chemistry.py` | Water parameter classification with corrective actions |
| `backend/tools/image_scanner.py` | Vision API species ID and health assessment |
| `knowledge_base/seed.py` | DB schema creation + 43 seeded records (24 fish, 7 plants, 5 chemistry, 5 disease, 1 nitrogen cycle, 1 aquascaping) |
| `frontend/app.py` | Streamlit entry point, sidebar navigation, shared error handler |
| `frontend/pages/*.py` | 7 tool pages (volume, species, maintenance, setup, chemistry, image_scanner, assistant) |
| `eval/eval.py` | Evaluation runner — health check, iterate test cases, print PASS/FAIL |
| `eval/test_cases.json` | 12 labeled test cases covering all required categories |
| `tests/` | 74 passing tests: unit, integration, and property-based (Hypothesis) |
| `requirements.txt` | All pinned dependencies |
| `README.md` | Numbered setup and run instructions |

**Rejected alternative:** A single-process Streamlit app with inline OpenAI calls was considered but rejected because it would make the eval suite impossible to run independently and would mix UI and AI logic.


