"""
backend/main.py

FastAPI application entry point for NoFishyBusiness.

Startup (lifespan) validates:
  1. OPENAI_API_KEY is set and non-empty.
  2. knowledge_base/aquarium.db exists and is readable.
  3. Topic Guard vocabulary is loaded from the knowledge base.

If any check fails the process prints a descriptive error and exits with
status code 1 so the operator knows exactly what to fix before retrying.
"""

import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_path() -> str:
    """Return the absolute path to knowledge_base/aquarium.db.

    The path is resolved relative to the *project root* (one level above the
    backend/ package directory) so it works regardless of the working directory
    from which uvicorn is launched.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "knowledge_base", "aquarium.db")


# ---------------------------------------------------------------------------
# Lifespan — startup validation
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks before the server begins accepting requests.

    Checks (in order):
      1. OPENAI_API_KEY environment variable is set and non-empty.
      2. knowledge_base/aquarium.db exists and is readable.
      3. Topic Guard vocabulary can be loaded from the knowledge base.

    Any failure prints a descriptive message to stdout and calls sys.exit(1).
    """
    # Load .env file if present (no-op when the variable is already set)
    load_dotenv()

    # 1. Verify OPENAI_API_KEY ------------------------------------------------
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(
            "Error: OPENAI_API_KEY environment variable is missing or empty. "
            "Copy .env.example to .env and set your key before starting the server."
        )
        sys.exit(1)

    # 2. Verify knowledge_base/aquarium.db exists and is readable -------------
    db = _db_path()
    if not os.path.isfile(db):
        print(
            f"Error: knowledge_base/aquarium.db not found at '{db}'. "
            "Run 'python knowledge_base/seed.py' to create and populate the database."
        )
        sys.exit(1)

    # Quick readability check — open the file in binary mode
    try:
        with open(db, "rb") as fh:
            fh.read(16)  # read the SQLite magic header bytes
    except OSError as exc:
        print(f"Error: knowledge_base/aquarium.db is not readable: {exc}")
        sys.exit(1)

    # 3. Load Topic Guard vocabulary ------------------------------------------
    # topic_guard is imported here (rather than at module level) so that the
    # module can be imported in tests without triggering the full startup path.
    try:
        from backend import topic_guard  # noqa: F401 — side-effect: loads vocab
    except Exception as exc:  # pragma: no cover
        print(f"Error: Failed to load Topic Guard vocabulary: {exc}")
        sys.exit(1)

    # All checks passed — hand control to the application
    yield


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="NoFishyBusiness Aquarium API",
    description="AI-assisted aquarium information backend.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Route imports
# ---------------------------------------------------------------------------

from fastapi import UploadFile, File  # noqa: E402
from backend.tools.volume import calculate_volume  # noqa: E402
from backend.tools.species import get_species_info  # noqa: E402
from backend.tools.maintenance import get_maintenance_guide  # noqa: E402
from backend.tools.setup import get_setup_guide  # noqa: E402
from backend.tools.chemistry import analyze_chemistry  # noqa: E402
from backend.tools.image_scanner import scan_image  # noqa: E402
from backend.assistant import get_assistant_reply  # noqa: E402
from backend.models import VolumeRequest, VolumeResponse, SpeciesRequest, MaintenanceRequest, SetupRequest, ChemistryRequest, AssistantRequest  # noqa: E402


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health check")
def health():
    """Return a simple liveness indicator.

    Used by the evaluation suite to verify the backend is reachable before
    running tests.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Volume Calculator
# ---------------------------------------------------------------------------


@app.post("/volume", response_model=VolumeResponse, summary="Volume Calculator")
def volume(request: VolumeRequest):
    """Compute aquarium water volume and weight from tank dimensions.

    Accepts length, width, and depth in inches (all must be > 0).
    Returns volume in US gallons and water weight in pounds.
    Non-positive values are rejected automatically by Pydantic (HTTP 422).
    """
    result = calculate_volume(request.length, request.width, request.depth)
    return result


# ---------------------------------------------------------------------------
# Species Tool
# ---------------------------------------------------------------------------


@app.post("/species", summary="Species Tool")
def species(request: SpeciesRequest):
    """Return a structured care sheet for the requested fish species.

    Retrieves relevant records from the knowledge base via RAG, then calls
    the OpenAI API to produce a structured JSON care sheet.

    Returns 404 if the species is not found in the knowledge base,
    503 if the knowledge base is unavailable, or 502 on OpenAI API errors.
    """
    return get_species_info(request.species_name)


# ---------------------------------------------------------------------------
# Standard error response helper
# ---------------------------------------------------------------------------

def error_response(message: str, error_type: str, status_code: int) -> JSONResponse:
    """Build a consistent JSON error response.

    All error responses across the API share this structure::

        {
            "message": "Human-readable error description",
            "error_type": "validation_error | not_found | api_error | rag_error | topic_refused"
        }

    Args:
        message:    Human-readable description of what went wrong.
        error_type: Machine-readable error category string.
        status_code: HTTP status code to return.

    Returns:
        A :class:`fastapi.responses.JSONResponse` with the given status code.
    """
    return JSONResponse(
        status_code=status_code,
        content={"message": message, "error_type": error_type},
    )


# ---------------------------------------------------------------------------
# Maintenance Guide
# ---------------------------------------------------------------------------


@app.post("/maintenance", summary="Maintenance Guide")
def maintenance(request: MaintenanceRequest):
    """Generate a maintenance guide for the given tank and fish load.

    Accepts tank size in gallons, fish count, and an optional list of fish
    species names.  Returns a structured guide covering the nitrogen cycle,
    feeding schedule, and weekly/monthly maintenance tasks.

    On RAG failure returns HTTP 503.  On OpenAI failure returns HTTP 502.
    """
    return get_maintenance_guide(request.tank_gallons, request.fish_count, request.fish_species)


# ---------------------------------------------------------------------------
# Setup Guide
# ---------------------------------------------------------------------------


@app.post("/setup", summary="Setup Guide")
def setup(request: SetupRequest):
    """Generate a beginner-friendly tank setup guide.

    Accepts tank size in gallons and experience level (beginner/intermediate/
    advanced).  Returns fish recommendations, plant recommendations, and an
    aquascaping idea grounded in the knowledge base.

    On RAG failure returns HTTP 503.  On OpenAI failure returns HTTP 502.
    """
    return get_setup_guide(request.tank_gallons, request.experience_level)


# ---------------------------------------------------------------------------
# Image Scanner
# ---------------------------------------------------------------------------


@app.post("/image-scan", summary="Image Scanner")
async def image_scan(file: UploadFile = File(...)):
    """Identify aquatic species and assess health from an uploaded image.

    Accepts a JPEG or PNG image file (multipart/form-data) not exceeding
    10 MB.  Returns species identification, confidence level, care summary,
    and health assessment.

    Returns 400 on validation errors (wrong type, too large, corrupt image).
    Returns 502 on OpenAI API errors.
    """
    file_bytes = await file.read()
    return scan_image(file_bytes, file.content_type)


# ---------------------------------------------------------------------------
# Chemistry Analyzer
# ---------------------------------------------------------------------------


@app.post("/chemistry", summary="Chemistry Analyzer")
def chemistry(request: ChemistryRequest):
    """Analyze water chemistry parameters from a text description and optional image.

    Accepts a text description of water test results and an optional
    base64-encoded image of a test strip.  Returns a classification of each
    recognized parameter (safe / caution / danger) with corrective actions
    and a summary.

    Returns 200 with error_type "topic_refused" if the query is off-topic.
    Returns 200 with error_type "no_parameters" if no parameter values are found.
    Returns 503 on RAG failure.  Returns 502 on OpenAI API errors.
    """
    return analyze_chemistry(request.description, request.image_base64)


# ---------------------------------------------------------------------------
# AI Assistant
# ---------------------------------------------------------------------------


@app.post("/assistant", summary="AI Assistant")
def assistant(request: AssistantRequest):
    """Generate a conversational reply grounded in the knowledge base.

    Accepts the user's message and conversation history (last 5 pairs).
    Runs topic filtering, RAG retrieval, and an OpenAI call to produce a
    reply and an optional suggested app section.

    Returns a refusal message if the topic is not aquarium-related.
    Returns an "insufficient information" message if RAG finds no records.
    Returns a "temporarily unavailable" message on OpenAI errors.
    """
    return get_assistant_reply(request.message, request.history)
