# Requirements Document

## Introduction

NoFishyBusiness is a locally-hosted aquarium information web application built as a college proof-of-concept project. It targets aquarium hobbyists — both beginners and experienced keepers — who want accurate, AI-assisted guidance on fish care, tank setup, water chemistry, and maintenance. The application uses a FastAPI backend, a Streamlit frontend, a SQLite knowledge base, and OpenAI's API (gpt-4o-mini) as the LLM engine. A RAG (Retrieval-Augmented Generation) pipeline grounds all AI responses in a curated local aquarium knowledge base, restricting the LLM to aquarium-related topics only. The project must be runnable locally by cloning the repo, installing dependencies, and adding an OpenAI API key — no cloud services or external databases required.

---

## Glossary

- **App**: The NoFishyBusiness web application as a whole.
- **Backend**: The FastAPI Python server that handles API requests, RAG retrieval, and LLM calls.
- **Frontend**: The Streamlit Python UI that the user interacts with in a browser.
- **LLM**: The OpenAI large language model (gpt-4o-mini) used to generate responses.
- **RAG_Pipeline**: The Retrieval-Augmented Generation system that retrieves relevant aquarium knowledge from the local database before passing context to the LLM.
- **Knowledge_Base**: The local SQLite database containing curated aquarium facts, species data, care guides, and water chemistry information.
- **User**: An aquarium hobbyist (beginner or experienced) using the App in a browser.
- **API_Key**: The user-supplied OpenAI API key stored in a local `.env` file.
- **Eval_Suite**: The `eval/` directory containing the evaluation script and labeled test cases.
- **Volume_Calculator**: The tool that computes tank water volume in gallons and the resulting water weight.
- **Species_Tool**: The tool that returns fish species information including behavior, compatible tank mates, water quality parameters, tank size requirements, and maintenance notes.
- **Maintenance_Guide**: The tool that provides guidance on the nitrogen cycle, feeding quantities, and routine tank upkeep.
- **Setup_Guide**: The tool that recommends beginner-friendly fish, plants, and aquascaping ideas for a new tank.
- **Chemistry_Analyzer**: The AI-powered tool that accepts text descriptions of water parameters and returns a danger assessment with corrective recommendations.
- **Image_Scanner**: The AI-powered tool that accepts a fish or plant image and returns species identification, illness indicators, and general care information.
- **AI_Assistant**: The conversational AI interface that answers free-form aquarium questions using the RAG_Pipeline and suggests relevant App sections.
- **Topic_Guard**: The system component that detects and rejects non-aquarium-related queries before they reach the LLM.
- **Token_Budget**: The per-request maximum token limit enforced to prevent runaway OpenAI API costs.

---

## Requirements

### Requirement 1: Local Setup and Runability

**User Story:** As a grader, I want to clone the repo, follow the README, and run the App locally without any cloud accounts or external databases, so that I can evaluate the project on my own machine.

#### Acceptance Criteria

1. THE App SHALL be runnable by executing a single command (e.g., `streamlit run frontend/app.py`) after installing dependencies from `requirements.txt` and adding `OPENAI_API_KEY` to a `.env` file copied from `.env.example`.
2. THE App SHALL include a `.env.example` file containing only the `OPENAI_API_KEY` variable set to the placeholder value `your-openai-api-key-here`.
3. THE `requirements.txt` SHALL list all Python dependencies with pinned version numbers using the `==` operator (e.g., `fastapi==0.111.0`).
4. THE Knowledge_Base SHALL be a single SQLite file committed to the repository at a documented path so no external database setup is required.
5. THE `README.md` SHALL contain numbered, step-by-step setup and run instructions covering: creating a virtual environment, activating it, installing from `requirements.txt`, copying `.env.example` to `.env` and inserting the API key, and the exact run command.
6. IF the `OPENAI_API_KEY` environment variable is missing or empty at startup, THEN THE Backend SHALL print an error message that includes the text "OPENAI_API_KEY" and exit with a non-zero status code rather than starting with a broken configuration.
7. IF the `.env` file is absent or malformed such that environment variables cannot be loaded, THEN THE Backend SHALL print an error message describing the configuration problem and exit with a non-zero status code rather than starting with a broken configuration.

---

### Requirement 2: Web Application UI

**User Story:** As a User, I want a browser-based interface with clear inputs, visible loading states, readable outputs, and informative error messages, so that I can interact with the App without needing technical knowledge.

#### Acceptance Criteria

1. THE Frontend SHALL render all user-facing tools and the AI_Assistant inside a web browser without requiring any command-line interaction after startup.
2. WHEN the User submits a form or query, THE Frontend SHALL display a loading indicator and SHALL remove that indicator when the Backend returns either a successful response or an error response.
3. WHEN the Backend returns a successful response, THE Frontend SHALL display the output with labeled fields rather than raw data structures (e.g., "Volume: 40.00 gallons" not `{"volume": 40.0}`).
4. WHEN the Backend returns an error response containing a parseable error object with at least a `message` field, THE Frontend SHALL display the `message` value in a labeled error section rather than a raw JSON string.
5. IF the Frontend encounters a rendering error while attempting to display a response, THEN THE Frontend SHALL display a fallback message informing the User that the result could not be displayed and suggesting they retry.
6. IF the Backend returns an unstructured error (e.g., a 500 response with no parseable body), THEN THE Frontend SHALL display a human-readable error message that does not expose raw stack traces or internal system details.
7. WHEN the User selects a tool from the navigation, THE Frontend SHALL display that tool's interface without reloading the entire page, allowing navigation between the Volume_Calculator, Species_Tool, Maintenance_Guide, Setup_Guide, Chemistry_Analyzer, Image_Scanner, and AI_Assistant.

---

### Requirement 3: Tank Water Volume Calculator

**User Story:** As a User, I want to enter my tank's dimensions and get the water volume in gallons and the total water weight, so that I can plan stocking levels and equipment needs.

#### Acceptance Criteria

1. WHEN the User provides tank length, width, and water depth in inches, THE Volume_Calculator SHALL compute the water volume in US gallons using the exact formula `(length × width × depth) ÷ 231.0`, rounded to two decimal places.
2. WHEN the User provides tank length, width, and water depth in inches, THE Volume_Calculator SHALL compute the total water weight in pounds rounded to two decimal places, using 8.34 pounds per US gallon for freshwater.
3. IF the User enters a non-positive value for any dimension, THEN THE Volume_Calculator SHALL display a validation error naming the invalid field and SHALL NOT perform the calculation.
4. IF the User enters a non-numeric value for any dimension, THEN THE Volume_Calculator SHALL display a validation error naming the invalid field and SHALL NOT perform the calculation.
5. WHEN the Volume_Calculator produces a valid result, THE Frontend SHALL display both the volume in gallons and the weight in pounds together in the same result view.

---

### Requirement 4: Fish Species Information

**User Story:** As a User, I want to look up a fish species by name and get detailed care information, so that I can decide whether it suits my tank.

#### Acceptance Criteria

1. WHEN the User submits a fish species name, THE Species_Tool SHALL return the species' typical behavior, compatible tank mates, required water quality parameters (temperature range in °F, pH range, hardness range in dGH), minimum tank size in gallons, and maintenance difficulty level (easy / moderate / advanced).
2. WHEN the User submits a fish species name, THE RAG_Pipeline SHALL retrieve relevant records from the Knowledge_Base before the LLM generates the response, and THE Species_Tool SHALL block LLM response generation until RAG retrieval completes successfully.
3. IF the submitted species name does not match any record in the Knowledge_Base, THEN THE Species_Tool SHALL return a message stating the species was not found and SHALL NOT generate an LLM response for that query.
4. THE Knowledge_Base SHALL contain care sheet records for at least 20 common freshwater aquarium fish species at initial deployment.
5. IF the RAG_Pipeline fails to retrieve records for a species query, THEN THE Species_Tool SHALL return an error message and SHALL NOT attempt to generate an LLM response.

---

### Requirement 5: Tank Maintenance Guide

**User Story:** As a User, I want guidance on the nitrogen cycle and feeding quantities for my tank, so that I can keep my fish healthy.

#### Acceptance Criteria

1. WHEN the User requests a maintenance guide for a given tank size in gallons and fish load (number of fish), THE Maintenance_Guide SHALL return an explanation covering all three nitrogen cycle stages (ammonia spike, nitrite spike, nitrate accumulation) relevant to that tank.
2. WHEN the User provides the number and species of fish in their tank, THE Maintenance_Guide SHALL return recommended daily feeding quantities expressed in a measurable unit (e.g., pinches, grams, or seconds of feeding) and a feeding frequency of 1–3 times per day.
3. THE Maintenance_Guide SHALL include a checklist with at least two weekly tasks (e.g., partial water change of 10–25%, parameter testing) and at least two monthly tasks (e.g., filter media rinse, full parameter test).
4. WHEN the RAG_Pipeline retrieves maintenance content, THE Maintenance_Guide SHALL use only Knowledge_Base content to generate the response and SHALL NOT introduce information absent from the retrieved context.
5. IF the RAG_Pipeline returns no records for a maintenance query, THEN THE Maintenance_Guide SHALL return a message stating that no maintenance information was found for the given inputs and SHALL NOT generate an LLM response.

---

### Requirement 6: Tank Setup Guide

**User Story:** As a beginner User, I want a guided recommendation for setting up a new tank, so that I can start the hobby with confidence.

#### Acceptance Criteria

1. WHEN the User provides a tank size between 1 and 500 gallons and selects "beginner" experience level, THE Setup_Guide SHALL recommend at least three fish species that are rated easy difficulty in the Knowledge_Base and whose minimum tank size requirement does not exceed the provided tank size.
2. WHEN the User provides a tank size between 1 and 500 gallons, THE Setup_Guide SHALL recommend at least two aquatic plant species that are rated easy difficulty in the Knowledge_Base and are suitable for the provided tank size.
3. WHEN the User provides a tank size between 1 and 500 gallons, THE Setup_Guide SHALL provide at least one aquascaping layout idea that describes substrate type, hardscape placement, and at least two plant zones.
4. THE Setup_Guide SHALL use the RAG_Pipeline to retrieve all fish, plant, and aquascaping records before generating recommendations, and SHALL NOT include species or layouts absent from the retrieved context.
5. IF the RAG_Pipeline returns no beginner-rated records matching the provided tank size, THEN THE Setup_Guide SHALL return a message stating that no matching beginner recommendations were found rather than generating unsupported suggestions.

---

### Requirement 7: Water Chemistry Analysis

**User Story:** As a User, I want to describe my water test results in text and receive a danger assessment with corrective actions, so that I can fix water quality problems before they harm my fish.

#### Acceptance Criteria

1. WHEN the User submits a text description containing at least one recognizable water parameter value (ammonia in ppm, nitrite in ppm, nitrate in ppm, pH as a decimal, or temperature in °F), THE Chemistry_Analyzer SHALL classify each provided parameter as safe, caution, or danger based on standard freshwater aquarium thresholds stored in the Knowledge_Base.
2. WHEN any parameter is classified as caution or danger, THE Chemistry_Analyzer SHALL return at least one specific corrective action for each affected parameter (e.g., "Perform a 25% water change to reduce ammonia").
3. WHEN the User uploads an image of a water test strip or test kit result, THE Chemistry_Analyzer SHALL extract visible parameter readings from the image using the LLM's vision capability and process them as text input before classification.
4. IF the User's input does not contain any recognizable water parameter values, THEN THE Chemistry_Analyzer SHALL return a message asking the User to provide specific parameter readings (e.g., ammonia, nitrite, pH) rather than generating a generic response.
5. WHEN the Chemistry_Analyzer requires Knowledge_Base data, THE RAG_Pipeline SHALL retrieve threshold and recommendation data before generating the LLM response, and THE Chemistry_Analyzer SHALL block LLM response generation until RAG retrieval completes successfully.
6. IF the Knowledge_Base is unavailable or the RAG_Pipeline fails, THEN THE Chemistry_Analyzer SHALL return an error message stating that the analysis service is unavailable and SHALL NOT attempt to classify parameters.

---

### Requirement 8: Fish and Plant Image Scanner

**User Story:** As a User, I want to upload a photo of a fish or plant and receive species identification and health information, so that I can identify unknown specimens or spot illness early.

#### Acceptance Criteria

1. WHEN the User uploads a valid JPEG or PNG image file not exceeding 10 MB, THE Image_Scanner SHALL return the most likely species name, a confidence indicator (high / medium / low), and a care summary covering feeding, water parameters, and compatibility in no more than 5 sentences.
2. WHEN the User uploads an image of a fish or plant, THE Image_Scanner SHALL assess visible signs of illness or injury and return either a list of observed indicators or a statement confirming that no visible issues were detected.
3. IF the uploaded file is not a JPEG or PNG, THEN THE Image_Scanner SHALL return a validation error specifying that only JPEG and PNG formats are accepted.
4. IF the uploaded file exceeds 10 MB, THEN THE Image_Scanner SHALL return a validation error specifying the 10 MB size limit.
5. IF the Image_Scanner cannot identify the species at any confidence level, THEN THE Image_Scanner SHALL return a message stating that identification was inconclusive rather than fabricating a species name; health assessment SHALL still be attempted independently.
6. IF the uploaded image is corrupt, unreadable, or does not depict an aquatic organism, THEN THE Image_Scanner SHALL return an error message describing the issue and SHALL NOT attempt species identification or health assessment.
7. THE Image_Scanner SHALL use the LLM's vision capability (gpt-4o-mini with image input) to perform identification and health assessment.

---

### Requirement 9: Conversational AI Assistant

**User Story:** As a User, I want to ask free-form aquarium questions in a chat interface and receive accurate answers with links to relevant App sections, so that I can get personalized guidance without navigating the site manually.

#### Acceptance Criteria

1. WHEN the User submits a free-form aquarium question, THE AI_Assistant SHALL retrieve relevant context from the Knowledge_Base via the RAG_Pipeline before generating a response.
2. WHEN the AI_Assistant generates a response, THE AI_Assistant SHALL include at least one suggestion naming a relevant App section (e.g., "Try the Species Tool for more details") when a relevant section exists for the topic.
3. WHILE a session is active (defined as the period from the User's first message until the browser tab is closed or the page is reloaded), THE AI_Assistant SHALL retain and include the last 5 user–assistant message pairs as context in each subsequent LLM call.
4. WHEN the User submits a follow-up question that references a prior answer in the same session, THE AI_Assistant SHALL produce a response that directly addresses the referenced prior content without asking the User to repeat it.
5. IF the RAG_Pipeline returns no relevant records for a question, THEN THE AI_Assistant SHALL respond stating that it does not have sufficient information on that topic rather than generating an unsupported answer.
6. IF the LLM API call fails during response generation, THEN THE AI_Assistant SHALL display an error message informing the User that the assistant is temporarily unavailable and SHALL NOT display a partial or empty response.

---

### Requirement 10: Topic Restriction (Aquarium-Only Responses)

**User Story:** As a project owner, I want the LLM to refuse non-aquarium questions, so that the App stays focused and does not misuse the OpenAI API budget.

#### Acceptance Criteria

1. WHEN the User submits a query that the Topic_Guard classifies as unrelated to aquariums, fish, aquatic plants, or water chemistry, THE Topic_Guard SHALL return a message stating that only aquarium-related questions are supported and SHALL NOT forward the query to the LLM.
2. IF a query contains no terms that match (exactly or partially) the aquarium topic vocabulary defined in the Knowledge_Base, THEN THE Topic_Guard SHALL classify the query as non-aquarium-related and return the refusal message without forwarding to the LLM.
3. IF a query contains at least one aquarium-related term alongside terms whose primary subject is outside the aquarium domain (ambiguous query), THEN THE Topic_Guard SHALL forward the query to the LLM with a system instruction to answer only if the question is aquarium-related and to decline otherwise.
4. THE Topic_Guard SHALL operate on every query submitted to the AI_Assistant and the Chemistry_Analyzer before any LLM call is made.
5. IF the Knowledge_Base is unavailable and the Topic_Guard cannot load the aquarium topic vocabulary, THEN THE Topic_Guard SHALL return an error message stating that the topic filter is unavailable and SHALL NOT forward the query to the LLM.

---

### Requirement 11: Token Budget Enforcement

**User Story:** As a project owner, I want each API call to stay within a defined token limit, so that a single session cannot generate unexpectedly large OpenAI charges.

#### Acceptance Criteria

1. THE Backend SHALL enforce a maximum of 1500 output tokens per LLM API call across all tools and the AI_Assistant by setting the `max_tokens` parameter on every OpenAI API request.
2. THE Backend SHALL truncate RAG_Pipeline context passed to the LLM to a maximum of 2000 tokens per request before constructing the prompt, and SHALL proceed with the truncated context rather than rejecting the request.
3. IF any LLM API call fails (including rate limit errors, quota errors, network errors, or invalid API key errors), THEN THE Backend SHALL return a user-facing message that includes the phrase "API error" and the error type, and SHALL write an entry to the local log file containing the error type and a UTC timestamp.
4. THE Backend SHALL write an entry to the local log file for every LLM API call containing the prompt token count, completion token count, total token count, and a UTC timestamp; error events from criterion 3 SHALL be written to the same log file.

---

### Requirement 12: RAG Pipeline

**User Story:** As a project owner, I want all LLM responses grounded in the local Knowledge_Base, so that the App produces accurate aquarium information rather than hallucinated facts.

#### Acceptance Criteria

1. WHEN a query is received by any LLM-powered tool, THE RAG_Pipeline SHALL retrieve the top-3 most relevant Knowledge_Base records using SQLite FTS5 full-text search before constructing the LLM prompt; if fewer than 3 records exist, all available records SHALL be retrieved.
2. THE RAG_Pipeline SHALL include the verbatim text of all retrieved records in the LLM system prompt, instructing the LLM to base its answer only on the provided context.
3. IF FTS5 returns zero records for a query, THEN THE RAG_Pipeline SHALL return an empty result set and the calling tool SHALL instruct the LLM to state that it does not have sufficient information rather than answering from general training data.
4. THE Knowledge_Base SHALL be pre-populated with aquarium knowledge covering at least: fish species care sheets (≥20 species), water chemistry parameters and thresholds, nitrogen cycle stages, common diseases and treatments (≥5 diseases), beginner plant species (≥5 species), and aquascaping basics.
5. THE RAG_Pipeline SHALL parse each Knowledge_Base record into a structured format containing at minimum: species name (or topic name), category, and content text before indexing for FTS5 search; malformed records that are missing any of these three fields SHALL be skipped and logged.
6. FOR ALL valid Knowledge_Base records, inserting a record and then retrieving it by its primary key SHALL return a record where the species name, category, and content text fields are identical to the inserted values.
7. IF the RAG_Pipeline encounters a database error during retrieval, THEN THE RAG_Pipeline SHALL return an error to the calling tool and SHALL NOT return a partial result set.

---

### Requirement 13: Evaluation Suite

**User Story:** As a grader, I want a runnable evaluation script with labeled test cases that measure AI behavior, so that I can verify the App's AI quality objectively.

#### Acceptance Criteria

1. THE Eval_Suite SHALL contain an `eval/` directory with an evaluation script (`eval/eval.py`) and a test case file (`eval/test_cases.json` or `eval/test_cases.py`) containing at least 10 labeled test cases.
2. WHEN the evaluation script is run and the Backend is reachable, THE Eval_Suite SHALL execute each test case against the Backend and print one line per test case in the format `[PASS|FAIL] <test_name> (<label>): <reason>`, followed by a summary line showing total passed and total failed counts; the script SHALL exit with a non-zero status code if any test fails.
3. THE Eval_Suite SHALL include test cases covering at minimum: at least 3 correct aquarium answer cases, at least 2 correct off-topic refusal cases, at least 1 correct "not found" response for an unknown species, and at least 1 water chemistry assessment case.
4. EACH test case SHALL include an input query, an expected behavior label (e.g., "should answer", "should refuse", "should return species info"), and a pass/fail assertion that checks for the presence or absence of a specified keyword or phrase in the Backend response.
5. IF the Backend is not reachable when the evaluation script is run, THEN THE Eval_Suite SHALL print an error message stating that the Backend could not be reached and exit with a non-zero status code without attempting to run any test cases.

---

### Requirement 14: Project Report and Submission Artifacts

**User Story:** As a student, I want all required submission artifacts present and complete, so that I receive full credit on the professor's rubric.

#### Acceptance Criteria

1. THE App repository SHALL contain a `REPORT.md` file with four sections in order: Section 5A (what and why, 200–250 words), Section 5B (at least 3 iteration subsections labeled V1, V2, V3 of 75–150 words each, each containing Change, Motivating example, Delta, and Conclusion), Section 6 (code walkthrough of 200–300 words with at least 2 file:line references, one design decision, and one rejected alternative), and Section 7 (AI disclosure and safety of 150–250 words covering 2–3 AI assistant failures with recovery and 1 safety risk with mitigation).
2. THE App repository SHALL contain a `requirements.txt` with all Python dependencies pinned using the `==` operator.
3. THE App repository SHALL contain a `.env.example` file with only the `OPENAI_API_KEY` variable.
4. THE App repository SHALL contain source code organized so that the Backend, Frontend, Knowledge_Base, and Eval_Suite each reside in their own top-level directory named `backend/`, `frontend/`, `knowledge_base/`, and `eval/` respectively.
