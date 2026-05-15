# NoFishyBusiness

An AI-assisted aquarium information site, containing various features for the user to interact with:

    General LLM (OpenAI API).
    Water chemistry analysis.
    Fish / Plant Image scanner.
    Tank maintenance guide.
    Tank setup guide.
    Species informant.
    Water Volume Calculator


---

## Prerequisites

- **Python 3** 
- **An OpenAI API key** — [platform.openai.com](https://platform.openai.com)

---

## Setup

### 0. Clone the Repo

```
git clone https://github.com/Hectorthe3rd/NoFishyBusiness.git
```

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your OpenAI API key

Copy `.env.example` to `.env`:

- **Windows:** `copy .env.example .env`
- **macOS/Linux:** `cp .env.example .env`

Open `.env` and replace the placeholder with your real key:

```
OPENAI_API_KEY=sk-...
```

### 3. Launch the app

### Windows

Double-click **`start.bat`** in the project folder.

Or from a terminal (Command Prompt or PowerShell):

```cmd
.\start.bat
```

### macOS / Linux

```bash
bash start.sh
```

### Manual startup (any OS)

If the launcher scripts don't work, open **two terminals** in the project folder:

**Terminal 1 — Backend:**
```bash
python -m uvicorn backend.main:app --port 8000
```

**Terminal 2 — Frontend:**
```bash
python -m streamlit run frontend/app.py
```

Then open **http://localhost:8501** in your browser.

> **Windows note:** If `python` gives a "not found" error, use the full path:
> `C:\Users\<YourName>\AppData\Local\Programs\Python\Python311\python.exe`

---

## Running Tests

```cmd
pytest tests/ --ignore=tests/test_properties.py
```

> If `pytest` isn't found, use the full path:
> `C:\Users\<YourName>\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/ --ignore=tests/test_properties.py`

## Running the Evaluation Suite

With the backend running (started via `start.bat` or manually):

**Windows:**
```cmd
.\eval.bat
```

**With options:**
```cmd
.\eval.bat --live      # include LLM tests (costs API credits)
.\eval.bat --report    # save results to eval/test_results.md
```

**macOS / Linux:**
```bash
python3 eval/eval.py
python3 eval/eval.py --live --report
```

> **Note:** The eval suite requires the backend to be running first.

## Adding your own documents to the knowledge base

Drop `.txt`, `.md`, or `.pdf` files into `knowledge_base/documents/`, or add URLs to `knowledge_base/documents/links.txt`, then run:

```bash
python knowledge_base/ingest.py
```

See `knowledge_base/documents/README.md` for the full format and examples.

---

## Project Structure

```
NoFishyBusiness/
├── backend/           # FastAPI backend — API routes, RAG pipeline, tools
│   └── tools/         # Individual tool implementations (species, chemistry, etc.)
├── frontend/          # Streamlit frontend
│   └── pages/         # One page per tool
├── knowledge_base/    # SQLite database and seed script
├── eval/              # Evaluation script and labeled test cases
├── tests/             # Unit and property-based tests
├── start.bat          # One-click launcher (Windows)
├── start.ps1          # PowerShell launcher (Windows)
├── start.sh           # Launcher (macOS / Linux)
├── .env.example       # API key template
└── requirements.txt   # Pinned Python dependencies
```
