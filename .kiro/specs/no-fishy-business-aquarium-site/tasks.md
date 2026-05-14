# Implementation Plan: NoFishyBusiness Aquarium Information App

## Overview

This plan breaks the NoFishyBusiness application into incremental coding tasks that build from the project skeleton and shared infrastructure up through each tool, the frontend, and finally the evaluation suite. Each task builds on the previous ones and ends with all components wired together. Property-based tests (Hypothesis) and unit/integration tests are included as optional sub-tasks throughout.

---

## Tasks

- [x] 1. Project scaffold and configuration
  - Create the full directory structure: `backend/`, `backend/tools/`, `frontend/`, `frontend/pages/`, `knowledge_base/`, `eval/`, `tests/`
  - Create `requirements.txt` with all pinned dependencies: `fastapi==0.111.0`, `uvicorn`, `streamlit`, `openai`, `python-dotenv`, `tiktoken`, `hypothesis`, `pytest`, `requests`, `Pillow`
  - Create `.env.example` with `OPENAI_API_KEY=your-openai-api-key-here`
  - Create `README.md` with numbered setup and run instructions (venv creation, activation, pip install, .env copy, run commands)
  - Create `backend/models.py` with all Pydantic models: `KBRecord`, `VolumeRequest`, `VolumeResponse`, `SpeciesRequest`, `MaintenanceRequest`, `SetupRequest`, `ChemistryRequest`, `AssistantRequest`, `ErrorResponse`
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 14.2, 14.3, 14.4_

- [x] 2. Knowledge base schema and seed data
  - [x] 2.1 Create `knowledge_base/aquarium.db` schema
    - Write `knowledge_base/seed.py` that creates `kb_records` table, `kb_fts` FTS5 virtual table, and the three sync triggers (INSERT, DELETE)
    - Implement `insert_record(db_path, species_name, category, content)` and `get_record_by_id(db_path, record_id)` helper functions used by seed and tests
    - _Requirements: 1.4, 12.5, 12.6_

  - [x] 2.2 Write property test for KB round-trip integrity
    - **Property 14: Knowledge Base Round-Trip Integrity**
    - **Validates: Requirements 12.6**

  - [x] 2.3 Seed the knowledge base with required content
    - Add ≥20 freshwater fish species care sheets (category: "fish")
    - Add ≥5 water chemistry parameter records with safe/caution/danger thresholds (category: "chemistry")
    - Add 1 nitrogen cycle record covering all three stages (category: "maintenance")
    - Add ≥5 common disease and treatment records (category: "disease")
    - Add ≥5 beginner plant species records (category: "plant")
    - Add ≥1 aquascaping basics record (category: "aquascaping")
    - Run `seed.py` to populate `aquarium.db` and commit the database file
    - _Requirements: 4.4, 12.4_

  - [x] 2.4 Write unit tests for malformed record skipping
    - Test that records missing `species_name`, `category`, or `content` are skipped and logged during indexing
    - **Validates: Requirements 12.5 (Property 16)**

- [x] 3. Shared backend infrastructure
  - [x] 3.1 Implement `backend/logger.py`
    - Write `log_llm_call(prompt_tokens, completion_tokens, total_tokens)` — appends JSON line to `backend/app.log` with UTC timestamp
    - Write `log_error(error_type, detail)` — appends JSON error line to `backend/app.log` with UTC timestamp
    - _Requirements: 11.3, 11.4_

  - [x] 3.2 Write unit tests for logger
    - Test that `log_llm_call` writes correct JSON fields (`event`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `ts`)
    - Test that `log_error` writes correct JSON fields (`event`, `error_type`, `detail`, `ts`)
    - _Requirements: 11.4_

  - [x] 3.3 Implement `backend/token_budget.py`
    - Write `count_tokens(text: str) -> int` using `tiktoken` with `cl100k_base` encoding
    - Write `truncate_context(context: str, max_tokens: int = 2000) -> str` — truncates to fit within `max_tokens`, always returns a string, never raises
    - _Requirements: 11.2_

  - [x] 3.4 Write property test for context truncation budget
    - **Property 13: Context Truncation Stays Within Budget**
    - **Validates: Requirements 11.2**

  - [x] 3.5 Implement `backend/rag.py`
    - Write `retrieve(query: str, top_k: int = 3) -> list[KBRecord]`
    - Execute FTS5 MATCH query against `kb_fts`, return up to `top_k` records
    - Raise `RAGError` on any `sqlite3.Error`; return empty list if no records match
    - _Requirements: 12.1, 12.2, 12.3, 12.7_

  - [x] 3.6 Write unit tests for RAG pipeline
    - Test that empty FTS5 result returns empty list
    - Test that a database error raises `RAGError` (not a partial result)
    - _Requirements: 12.3, 12.7_

  - [x] 3.7 Implement `backend/topic_guard.py`
    - Write `check_topic(query: str) -> TopicResult` with `status: "allowed" | "refused" | "ambiguous"` and `message` field
    - Load vocabulary from `kb_records` (`species_name` + `category` fields) plus hardcoded seed terms at startup
    - Implement three-way logic: no aquarium terms → refused; only aquarium terms → allowed; mixed → ambiguous
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 3.8 Write property tests for Topic Guard
    - **Property 10: Topic Guard Rejects Non-Aquarium Queries**
    - **Validates: Requirements 10.1, 10.2**
    - **Property 11: Topic Guard Forwards Ambiguous Queries with System Instruction**
    - **Validates: Requirements 10.3**

  - [x] 3.9 Write unit tests for Topic Guard
    - Test that a pure aquarium query returns `allowed`
    - Test that a pure off-topic query returns `refused` without making any LLM call
    - _Requirements: 10.1, 10.2_

- [x] 4. FastAPI backend — core app and startup
  - [x] 4.1 Create `backend/main.py` with FastAPI app and lifespan startup validation
    - Implement `lifespan` context manager: check `OPENAI_API_KEY` is set and non-empty, verify `knowledge_base/aquarium.db` exists and is readable, load Topic Guard vocabulary
    - If any check fails: print descriptive error including "OPENAI_API_KEY" where applicable and call `sys.exit(1)`
    - Register `GET /health` endpoint returning `{"status": "ok"}`
    - Define the standard error response format (`message`, `error_type`)
    - _Requirements: 1.6, 1.7, 10.5_

  - [x] 4.2 Write unit tests for startup validation
    - Test that missing `OPENAI_API_KEY` causes `sys.exit(1)` with message containing "OPENAI_API_KEY"
    - Test that missing `aquarium.db` causes `sys.exit(1)`
    - _Requirements: 1.6, 1.7_

- [x] 5. Volume Calculator tool
  - [x] 5.1 Implement `backend/tools/volume.py`
    - Write `calculate_volume(length, width, depth) -> dict` using formula `round((l * w * d) / 231.0, 2)` for gallons and `round(gallons * 8.34, 2)` for weight
    - Register `POST /volume` in `backend/main.py` using `VolumeRequest` / `VolumeResponse` Pydantic models (non-positive values rejected by `Field(gt=0)`)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 5.2 Write property tests for Volume Calculator
    - **Property 1: Volume and Weight Calculation Correctness**
    - **Validates: Requirements 3.1, 3.2**
    - **Property 2: Non-Positive Dimension Rejection**
    - **Validates: Requirements 3.3**

  - [x] 5.3 Write unit tests for Volume Calculator
    - Test non-numeric input returns 422 from Pydantic
    - Test zero dimension returns validation error
    - Test valid input returns both `volume_gallons` and `weight_pounds` in the same response
    - _Requirements: 3.3, 3.4, 3.5_

- [x] 6. Species Tool
  - [x] 6.1 Implement `backend/tools/species.py`
    - Write `get_species_info(species_name: str) -> dict` that calls `rag.retrieve(species_name)`, returns 404 `not_found` if empty, otherwise calls OpenAI with `max_tokens=1500` and returns structured species response
    - Register `POST /species` in `backend/main.py`
    - Wrap OpenAI call in try/except for `openai.OpenAIError` subclasses; log errors via `logger.log_error`; log successful calls via `logger.log_llm_call`
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 11.1, 11.3, 11.4_

  - [x] 6.2 Write property test for Species response completeness
    - **Property 3: Species Response Completeness**
    - **Validates: Requirements 4.1**
    - **Property 4: Unknown Species Returns Not-Found**
    - **Validates: Requirements 4.3**

  - [x] 6.3 Write unit tests for Species Tool
    - Test known species returns all required fields (behavior, compatible_tank_mates, temperature_f, ph, hardness_dgh, min_tank_gallons, difficulty, maintenance_notes)
    - Test unknown species returns 404 with `error_type: "not_found"` and no LLM call
    - Test RAG failure returns error without LLM call
    - _Requirements: 4.1, 4.3, 4.5_

- [x] 7. Maintenance Guide tool
  - [x] 7.1 Implement `backend/tools/maintenance.py`
    - Write `get_maintenance_guide(tank_gallons, fish_count, fish_species) -> dict` that calls `rag.retrieve`, returns not-found message if empty, otherwise calls OpenAI with `max_tokens=1500`
    - Response must include `nitrogen_cycle` (covering all 3 stages), `feeding` (quantity + frequency), `weekly_tasks` (≥2), `monthly_tasks` (≥2)
    - Register `POST /maintenance` in `backend/main.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1_

  - [x] 7.2 Write property test for Maintenance Guide completeness
    - **Property 5: Maintenance Response Completeness**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [x] 7.3 Write unit tests for Maintenance Guide
    - Test that RAG returns no records → not-found message, no LLM call
    - Test that response contains all four required top-level fields
    - _Requirements: 5.4, 5.5_

- [x] 8. Setup Guide tool
  - [x] 8.1 Implement `backend/tools/setup.py`
    - Write `get_setup_guide(tank_gallons, experience_level) -> dict` that calls `rag.retrieve`, returns not-found message if no beginner records match, otherwise calls OpenAI with `max_tokens=1500`
    - Response must include `fish_recommendations` (≥3 easy-rated), `plant_recommendations` (≥2 easy-rated), `aquascaping_idea` (substrate, hardscape, plant_zones)
    - Register `POST /setup` in `backend/main.py`; validate `experience_level` with `Field(pattern="^(beginner|intermediate|advanced)$")`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1_

  - [x] 8.2 Write property test for Setup Guide completeness
    - **Property 6: Setup Guide Response Completeness**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x] 8.3 Write unit tests for Setup Guide
    - Test that RAG returns no beginner records → not-found message, no LLM call
    - Test that fish recommendations all have `difficulty: "easy"` and `min_tank_gallons ≤ tank_gallons`
    - _Requirements: 6.1, 6.5_

- [x] 9. Chemistry Analyzer tool
  - [x] 9.1 Implement `backend/tools/chemistry.py`
    - Write `analyze_chemistry(description: str, image_base64: str | None) -> dict`
    - Run `topic_guard.check_topic(description)` first; return refusal if refused
    - Call `rag.retrieve(description)` for threshold data; return error if RAG fails
    - If input contains no recognizable parameter values, return prompt message (no LLM call)
    - Call OpenAI with `max_tokens=1500`; if `image_base64` provided, include as vision input
    - Response: `parameters` list (each with `name`, `value`, `status`, `corrective_action`) and `summary`
    - Register `POST /chemistry` in `backend/main.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 10.4, 11.1_

  - [x] 9.2 Write property tests for Chemistry Analyzer
    - **Property 7: Water Parameter Classification Coverage**
    - **Validates: Requirements 7.1**
    - **Property 8: Corrective Action Presence for Non-Safe Parameters**
    - **Validates: Requirements 7.2**

  - [x] 9.3 Write unit tests for Chemistry Analyzer
    - Test input with no recognizable parameters returns prompt message, no LLM call
    - Test that every "caution" or "danger" parameter has a non-null, non-empty `corrective_action`
    - Test that Topic Guard refusal prevents LLM call
    - Test that RAG failure returns 503 error
    - _Requirements: 7.1, 7.2, 7.4, 7.6_

- [x] 10. Image Scanner tool
  - [x] 10.1 Implement `backend/tools/image_scanner.py`
    - Write `scan_image(file_bytes: bytes, content_type: str) -> dict`
    - Validate content type is `image/jpeg` or `image/png`; return 400 if not
    - Validate file size ≤ 10 MB; return 400 if exceeded
    - Validate image is not corrupt (attempt decode with Pillow); return 400 if corrupt
    - Call OpenAI vision API (`gpt-4o-mini` with image input) with `max_tokens=1500`
    - If species cannot be identified, set `species_name: null` and `confidence: "inconclusive"`
    - Register `POST /image-scan` in `backend/main.py` as `multipart/form-data`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 11.1_

  - [x] 10.2 Write property test for Image Scanner response structure
    - **Property 9: Image Scanner Response Structure**
    - **Validates: Requirements 8.1, 8.2, 8.5**

  - [x] 10.3 Write unit tests for Image Scanner
    - Test non-JPEG/PNG file returns 400 with `error_type: "validation_error"`
    - Test file exceeding 10 MB returns 400 with `error_type: "validation_error"`
    - Test corrupt image returns 400
    - Test that when `species_name` is null, `confidence` is "inconclusive"
    - _Requirements: 8.3, 8.4, 8.5, 8.6_

- [x] 11. AI Assistant tool
  - [x] 11.1 Implement `backend/assistant.py`
    - Write `get_assistant_reply(message: str, history: list[dict]) -> dict`
    - Run `topic_guard.check_topic(message)` first; return refusal if refused
    - Call `rag.retrieve(message)` for context; if empty, respond with "insufficient information" message
    - Truncate context via `token_budget.truncate_context(context, 2000)`
    - Prepend `history` (last 10 items = 5 pairs) to LLM messages array
    - Call OpenAI with `max_tokens=1500`; include `suggested_section` in response when relevant
    - Register `POST /assistant` in `backend/main.py`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.4, 11.1, 11.2_

  - [x] 11.2 Write unit tests for AI Assistant
    - Test that RAG returns no records → "insufficient information" response, no LLM call
    - Test that LLM API failure returns error message containing "temporarily unavailable"
    - Test that Topic Guard refusal prevents LLM call
    - _Requirements: 9.5, 9.6_

- [x] 12. Checkpoint — backend complete
  - Ensure all tests pass, ask the user if questions arise.
  - Verify `GET /health` returns `{"status": "ok"}`
  - Verify all eight endpoints are registered in `backend/main.py`
  - Verify `backend/app.log` receives entries for LLM calls and errors

- [x] 13. Integration tests for backend wiring
  - [x] 13.1 Write integration tests with mocked OpenAI client
    - Test that RAG is called before OpenAI in every LLM-powered tool (`/species`, `/maintenance`, `/setup`, `/chemistry`, `/assistant`)
    - Test that Topic Guard is invoked on every `/assistant` and `/chemistry` request
    - Test that `max_tokens=1500` is present in every mocked OpenAI call
    - Test that `backend/app.log` receives an entry for every mocked LLM call
    - _Requirements: 4.2, 5.4, 6.4, 7.5, 9.1, 10.4, 11.1, 11.4, 12.1, 12.2_

  - [x] 13.2 Write property test for Token Budget on all LLM calls
    - **Property 12: Token Budget Enforcement on All LLM Calls**
    - **Validates: Requirements 11.1**

  - [x] 13.3 Write property test for RAG context verbatim inclusion
    - **Property 15: RAG Context Included Verbatim in LLM Prompt**
    - **Validates: Requirements 12.2**

- [x] 14. Streamlit frontend — navigation and shared patterns
  - [x] 14.1 Create `frontend/app.py` with sidebar navigation
    - Set up Streamlit multi-page app structure with sidebar links to all seven tool pages
    - Implement shared error-handling helper: parse `{"message": ..., "error_type": ...}` from backend responses; display `st.error(message)` on HTTP errors; display fallback message on rendering errors; display "Could not reach the backend" on `requests.RequestException`
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7_

- [x] 15. Frontend tool pages
  - [x] 15.1 Create `frontend/pages/volume.py`
    - Render three numeric inputs (length, width, depth in inches)
    - On submit: show `st.spinner("Loading...")`, POST to `/volume`, display labeled output ("Volume: X gallons", "Weight: X pounds")
    - _Requirements: 2.2, 2.3, 3.5_

  - [x] 15.2 Create `frontend/pages/species.py`
    - Render species name text input
    - On submit: show spinner, POST to `/species`, display all care sheet fields with labels
    - _Requirements: 2.2, 2.3, 4.1_

  - [x] 15.3 Create `frontend/pages/maintenance.py`
    - Render inputs for tank gallons, fish count, and fish species list
    - On submit: show spinner, POST to `/maintenance`, display nitrogen cycle, feeding, weekly tasks, monthly tasks with labels
    - _Requirements: 2.2, 2.3, 5.1, 5.2, 5.3_

  - [x] 15.4 Create `frontend/pages/setup.py`
    - Render inputs for tank gallons and experience level selector (beginner/intermediate/advanced)
    - On submit: show spinner, POST to `/setup`, display fish recommendations, plant recommendations, and aquascaping idea with labels
    - _Requirements: 2.2, 2.3, 6.1, 6.2, 6.3_

  - [x] 15.5 Create `frontend/pages/chemistry.py`
    - Render text area for parameter description and optional image upload widget
    - On submit: encode image to base64 if provided, show spinner, POST to `/chemistry`, display parameter table (name, value, status, corrective action) and summary
    - _Requirements: 2.2, 2.3, 7.1, 7.2, 7.3_

  - [x] 15.6 Create `frontend/pages/image_scanner.py`
    - Render file uploader accepting JPEG and PNG
    - On submit: show spinner, POST to `/image-scan` as multipart/form-data, display species name, confidence, care summary, and health assessment with labels
    - _Requirements: 2.2, 2.3, 8.1, 8.2_

  - [x] 15.7 Create `frontend/pages/assistant.py`
    - Render chat input and message history display
    - Manage `st.session_state.history` (last 10 items = 5 pairs); append user message, POST to `/assistant` with history, append assistant reply, trim to 10 items
    - Display `suggested_section` as a tip when present
    - _Requirements: 2.2, 2.3, 9.2, 9.3, 9.4_

- [x] 16. Checkpoint — frontend complete
  - Ensure all tests pass, ask the user if questions arise.
  - Manually verify each page renders inputs, shows spinner on submit, and displays labeled output
  - Verify navigation between pages does not reload the entire browser page

- [x] 17. Evaluation suite
  - [x] 17.1 Create `eval/test_cases.json` with ≥10 labeled test cases
    - Include ≥3 correct aquarium answer cases (e.g., species lookup, nitrogen cycle question)
    - Include ≥2 correct off-topic refusal cases (e.g., "What is the capital of France?")
    - Include ≥1 "not found" case for an unknown species
    - Include ≥1 water chemistry assessment case
    - Each case: `input`, `expected_label`, `assert_keyword` (or `assert_absent_keyword`)
    - _Requirements: 13.1, 13.3, 13.4_

  - [x] 17.2 Create `eval/eval.py` evaluation runner
    - Call `GET /health` first; if unreachable, print error and exit with non-zero status
    - Iterate test cases, call appropriate backend endpoint, evaluate pass/fail assertion
    - Print one line per test: `[PASS|FAIL] <test_name> (<label>): <reason>`
    - Print summary line: `Passed: X / Total: Y`
    - Exit with non-zero status if any test fails
    - _Requirements: 13.1, 13.2, 13.4, 13.5_

  - [x] 17.3 Write unit tests for eval runner
    - Test that unreachable backend causes non-zero exit without running test cases
    - Test that a failing assertion produces `[FAIL]` output and non-zero exit
    - _Requirements: 13.2, 13.5_

- [x] 18. Final checkpoint — full system wired
  - Ensure all tests pass, ask the user if questions arise.
  - Run `python knowledge_base/seed.py` and verify `aquarium.db` is populated
  - Verify `uvicorn backend.main:app --reload --port 8000` starts without errors
  - Verify `streamlit run frontend/app.py` opens in browser and all seven tool pages are accessible
  - Verify `python eval/eval.py` runs against the live backend and prints pass/fail results

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 12, 16, 18) ensure incremental validation at major milestones
- Property tests use Hypothesis with `@settings(max_examples=100)` and the tag format `# Feature: no-fishy-business-aquarium-site, Property N: <text>`
- Unit tests and integration tests use `pytest` with mocked OpenAI client and real SQLite (in-memory or temp file)
- The backend and frontend are separate processes — start backend first, then frontend
- `backend/app.log` is gitignored; `knowledge_base/aquarium.db` is committed to the repo

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "3.1", "3.3", "3.5", "3.7", "4.1"] },
    { "id": 1, "tasks": ["2.2", "2.3", "3.2", "3.4", "3.6", "3.8", "3.9", "4.2"] },
    { "id": 2, "tasks": ["2.4", "5.1", "6.1", "7.1", "8.1", "9.1", "10.1", "11.1"] },
    { "id": 3, "tasks": ["5.2", "5.3", "6.2", "6.3", "7.2", "7.3", "8.2", "8.3", "9.2", "9.3", "10.2", "10.3", "11.2"] },
    { "id": 4, "tasks": ["13.1", "14.1"] },
    { "id": 5, "tasks": ["13.2", "13.3", "15.1", "15.2", "15.3", "15.4", "15.5", "15.6", "15.7"] },
    { "id": 6, "tasks": ["17.1"] },
    { "id": 7, "tasks": ["17.2"] },
    { "id": 8, "tasks": ["17.3"] }
  ]
}
```
