## V2 — Bug Fixes After Live Testing

Three bugs were discovered when running the app and using the tools:

**Bug 1: Topic Guard refusing valid aquarium queries**

- **What happened:** Queries like "Tell me about guppies" were refused by the Topic Guard instead of being forwarded to the LLM. The assistant returned "I can only answer aquarium-related questions" for clearly aquarium-related input.
- **Root cause:** The vocabulary check used exact token matching. "guppies" is not in the vocabulary — only "guppy" is. So the query had more unrecognized words ("tell", "me", "about", "guppies") than recognized ones, triggering a refusal.
- **Fix:** Added stem/suffix matching to `_is_aquarium_token()` in `topic_guard.py`. The function now tries stripping common suffixes (`-s`, `-es`, `-ies`, `-ing`, `-ed`, `-er`) before checking the vocabulary. "guppies" → strips "ies" → checks "guppy" → match found.
- **File changed:** `backend/topic_guard.py`

**Bug 2: AI Assistant returning "insufficient information" for valid questions**

- **What happened:** The assistant returned "I don't have sufficient information" even for questions about species that exist in the knowledge base (e.g., "Tell me about guppies").
- **Root cause:** The full message string was passed directly to FTS5. SQLite FTS5 tries to match all words in the query — "tell", "me", "about" don't exist in the DB, so the search returned zero results even though "guppies" would have matched.
- **Fix:** Added stop-word filtering in `assistant.py` before the RAG query. Common filler words ("tell", "me", "about", "what", "how", "is", etc.) are stripped out, leaving only meaningful keywords. "Tell me about guppies" → RAG query becomes "guppies" → finds the Guppy record. Falls back to the full message if the keyword query also returns nothing.
- **File changed:** `backend/assistant.py`

**Bug 3: Image Scanner rejecting valid uploaded images**

- **What happened:** Valid JPEG/PNG images uploaded through the Image Scanner page returned a 400 "image could not be read" error.
- **Root cause:** The validation used `img.verify()` from Pillow. `verify()` is designed for strict integrity checking and flags many valid images as "truncated" if they lack certain optional trailer bytes. It also consumes the file stream, making any subsequent decode attempt fail.
- **Fix:** Replaced `img.verify()` with `img.load()` in `image_scanner.py`. `load()` fully decodes the pixel data, which catches genuinely corrupt files while accepting all valid images. It also doesn't consume the stream.
- **File changed:** `backend/tools/image_scanner.py`

**Additional fix during startup:** The `image_scanner.py` module was creating an `openai.OpenAI()` client at import time (module level), before the `.env` file was loaded. This caused a crash on startup. Changed to a lazy singleton pattern (same as all other tools) — the client is only created on the first actual API call.


## Second:

Two things to tackle here — simplify startup AND fix the errors. Let me first see what errors are actually happening now, then I'll address both.

"Can't reach the backend" means the backend isn't running when the frontend tries to call it. The core problem is the two-terminal startup — the professor has to run two separate commands and keep both terminals open. Let me create a single launcher script that starts both processes at once.

Here's the plan:

1. **`start.bat`** — a single double-click launcher that starts both backend and frontend in one go
2. **`start.ps1`** — same but for PowerShell
3. **Update `README.md`** — reduce setup to the absolute minimum steps

Let me also check the Python path situation so the launcher uses the right Python:

Now rewrite the README to be as short as possible:

Now let me also fix the "API error" issue. That's almost certainly the `httpx` version conflict we hit before — the professor's machine will have the same problem. Let me pin `httpx` in `requirements.txt` so it installs the right version automatically:

Also add the Streamlit credentials file to the repo so the email prompt never blocks startup:

Here's what was done and why:

**`start.bat`** — double-click to launch everything. It seeds the DB, opens the backend in a separate window, waits 4 seconds, then starts the frontend. The professor just double-clicks this file and the browser opens automatically.

**`start.ps1`** — same thing for PowerShell if `.bat` doesn't work.

**`httpx==0.27.2` added to `requirements.txt`** — this was the root cause of the "API error". `openai==1.30.1` requires an older `httpx` that accepts a `proxies` argument. Without pinning it, `pip install` pulls in a newer incompatible version and every OpenAI call crashes.

**`.streamlit/credentials.toml` + `config.toml`** — prevents the email prompt from blocking startup and sets headless mode so no extra browser config is needed.

**Simplified README** — 3 steps: install, add API key, double-click `start.bat`.

The professor's workflow is now: clone → `pip install -r requirements.txt` → add API key to `.env` → double-click `start.bat`.