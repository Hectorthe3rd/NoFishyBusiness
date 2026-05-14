"""
knowledge_base/ingest.py
─────────────────────────────────────────────────────────────────────────────
Document and URL ingestion script for NoFishyBusiness.

Reads files AND web links from knowledge_base/documents/ and loads them into
the SQLite knowledge base so the RAG pipeline can retrieve them.

Supported sources:
    .txt  — plain text files
    .md   — Markdown files (loaded as plain text)
    .pdf  — PDF documents (requires: pip install pypdf)
    links.txt — one URL per line; each page is fetched and its text extracted

Usage:
    python knowledge_base/ingest.py

Place your documents in:
    knowledge_base/documents/

To add web links, create or edit:
    knowledge_base/documents/links.txt

Format — one entry per line using curly-brace syntax:
    {Description: https://example.com/article}
    {fish_betta care guide: https://www.aquariumcoop.com/blogs/aquarium/betta-fish-care}

The description before the colon becomes the record label.
If the description starts with a valid category (e.g. "fish_", "plant_"),
it is used to tag the record. Otherwise the category defaults to "document".

File naming convention for documents (optional but recommended):
    <category>_<name>.ext
    e.g.  fish_betta_care.txt
          chemistry_ammonia_guide.md
          maintenance_nitrogen_cycle.pdf

Each file/page is split into ~400-word chunks so long documents stay within
the FTS5 and token budget limits.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import re                               # 
import sys                              # 
import time
from urllib.parse import urlparse

# Add project root to path so seed.py helpers are importable
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from knowledge_base.seed import create_schema, insert_record, DEFAULT_DB_PATH

# ── Configuration ─────────────────────────────────────────────────────────────

DOCUMENTS_DIR  = os.path.join(_HERE, "documents")   # Folder for local files
LINKS_FILE     = os.path.join(DOCUMENTS_DIR, "links.txt")  # URL list file

# Valid categories for tagging records
VALID_CATEGORIES = {
    "fish", "plant", "chemistry", "maintenance",
    "disease", "aquascaping", "document"
}

CHUNK_SIZE_WORDS = 400   # Target words per DB record chunk

# Polite delay between web requests (seconds) — avoids hammering servers
REQUEST_DELAY = 1.0

# HTTP headers to send with web requests — some sites block default Python UA
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NoFishyBusiness-Ingest/1.0; "
        "+https://github.com/NoFishyBusiness)"
    )
}


# ── Text extraction — local files ─────────────────────────────────────────────

def _read_txt(path: str) -> str:
    """Read a plain text or Markdown file and return its full content."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    """Extract text from a PDF using pypdf. Returns empty string if unavailable."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"  [SKIP] {os.path.basename(path)} — install pypdf to read PDFs:")
        print("         pip install pypdf")
        return ""
    reader = PdfReader(path)
    pages = [page.extract_text() for page in reader.pages if page.extract_text()]
    return "\n\n".join(pages)


def extract_text_from_file(path: str) -> str:
    """Dispatch to the correct reader based on file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        return _read_txt(path)
    elif ext == ".pdf":
        return _read_pdf(path)
    return ""   # Unsupported — caller will skip


# ── Text extraction — web URLs ────────────────────────────────────────────────

def fetch_url(url: str) -> tuple[str, str]:
    """
    Fetch a web page and extract its readable text content.

    Uses requests to download the HTML and BeautifulSoup to strip tags,
    navigation, ads, and boilerplate — keeping only the main article text.

    Returns:
        (page_title, plain_text) — both strings.
        Returns ("", "") on any error.
    """
    try:
        import requests
    except ImportError:
        print("  [ERROR] requests not installed. Run: pip install requests")
        return "", ""

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("  [ERROR] beautifulsoup4 not installed. Run: pip install beautifulsoup4")
        return "", ""

    try:
        print(f"  [FETCH] {url}")
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        resp.raise_for_status()   # Raise on 4xx/5xx responses
    except Exception as exc:
        print(f"  [ERROR] Could not fetch {url}: {exc}")
        return "", ""

    # Parse the HTML
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract the page title
    title_tag = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else urlparse(url).netloc

    # Remove elements that are never useful content:
    # scripts, styles, navigation, headers, footers, ads, sidebars
    for tag in soup(["script", "style", "nav", "header", "footer",
                    "aside", "form", "button", "iframe", "noscript",
                    "meta", "link", "figure"]):
        tag.decompose()   # Remove the tag and its children from the tree

    # Try to find the main content area first (common article containers)
    main_content = (
        soup.find("article") or
        soup.find("main") or
        soup.find(id=re.compile(r"content|main|article|body", re.I)) or
        soup.find(class_=re.compile(r"content|main|article|post|entry", re.I)) or
        soup.find("body") or
        soup
    )

    # Extract text with newlines between block elements
    text = main_content.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace and blank lines
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]   # Remove empty lines
    clean_text = "\n\n".join(lines)

    return page_title, clean_text


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS) -> list[str]:
    """
    Split text into chunks of approximately chunk_size words.

    Splits on paragraph boundaries to keep related sentences together.
    Falls back to word-count splitting for very long paragraphs.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_words = []
    current_count = 0

    for para in paragraphs:
        para_words = para.split()
        if current_count + len(para_words) > chunk_size and current_words:
            chunks.append(" ".join(current_words))
            current_words = []
            current_count = 0
        current_words.extend(para_words)
        current_count += len(para_words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks if chunks else [text[:2000]]


# ── Filename / label parsing ──────────────────────────────────────────────────

def parse_label(label: str) -> tuple[str, str]:
    """
    Extract (category, species_name) from a label string.

    The label can be:
    - A filename without extension:  "fish_betta_care"
    - A free-form label:             "fish_betta care guide"
    - Just a name:                   "betta care"

    Convention: first word before underscore is the category if it's valid.
    """
    label = label.strip()
    parts = label.split("_", 1)

    if len(parts) == 2 and parts[0].lower() in VALID_CATEGORIES:
        category     = parts[0].lower()
        species_name = parts[1].replace("_", " ")
    else:
        category     = "document"
        species_name = label.replace("_", " ")

    return category, species_name


def parse_filename(filename: str) -> tuple[str, str]:
    """Extract (category, species_name) from a local filename."""
    return parse_label(os.path.splitext(filename)[0])



# ── URL list parsing ──────────────────────────────────────────────────────────

def parse_links_file(links_path: str) -> list[tuple[str, str]]:     # Link Extraction
    """
    Parse links.txt and return a list of (url, label) tuples.

    Expected format — one entry per line using curly-brace syntax:
        {Description: https://example.com/article}
        {fish_betta care guide: https://www.aquariumcoop.com/blogs/aquarium/betta-fish-care}

    Lines starting with # are comments and are ignored.
    Blank lines are also ignored.
    Entries without a valid http/https URL are skipped with a warning.

    The description before the colon becomes the record label, which is then
    parsed by parse_label() to extract a category and species_name.
    """
    if not os.path.isfile(links_path):
        return []

    entries = []
    with open(links_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex matches everything inside { ... }, capturing label and URL.
    # Uses non-greedy match so each pair of braces is its own entry.
    # group(1) = description/label, group(2) = URL
    matches = re.findall(r"\{(.*?):\s*(https?://.*?)\}", content)

    for label, url in matches:
        label = label.strip()
        url   = url.strip()

        # Strip any trailing inline comment (e.g. "https://... # some note")
        url = url.split("#")[0].strip()                             # Ignore comments.

        if not url.startswith(("http://", "https://")):             # 
            print(f"  [SKIP] Invalid URL for {label!r}: {url!r}")   # 
            continue

        entries.append((url, label))

    return entries


# ── Main ingestion logic ──────────────────────────────────────────────────────

def ingest_documents(db_path: str = DEFAULT_DB_PATH, docs_dir: str = DOCUMENTS_DIR) -> None:
    """
    Ingest all local files and web links into the knowledge base.

    Processing order:
    1. Scan docs_dir for .txt, .md, .pdf files (skips links.txt itself)
    2. Read links.txt and fetch each URL
    3. Chunk all text and insert into kb_records
    """
    create_schema(db_path)
    os.makedirs(docs_dir, exist_ok=True)

    total_inserted = 0
    total_skipped  = 0

    # ── Phase 1: Local files ──────────────────────────────────────────────
    files = sorted([
        f for f in os.listdir(docs_dir)
        if os.path.isfile(os.path.join(docs_dir, f))
        and f.lower() != "links.txt"      # Handled separately
        and f.lower() != "readme.md"      # Skip the instructions file
    ])

    if files:
        print(f"[ingest] Processing {len(files)} local file(s)...")
        for filename in files:
            filepath = os.path.join(docs_dir, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext not in (".txt", ".md", ".pdf"):
                print(f"  [SKIP] {filename} — unsupported type ({ext})")
                continue

            print(f"  [READ] {filename}")
            text = extract_text_from_file(filepath)

            if not text.strip():
                print(f"  [SKIP] {filename} — no text extracted")
                total_skipped += 1
                continue

            category, species_name = parse_filename(filename)
            chunks = chunk_text(text)
            print(f"         → category={category!r}, name={species_name!r}, chunks={len(chunks)}")

            for i, chunk in enumerate(chunks):
                name = species_name if len(chunks) == 1 else f"{species_name} (part {i+1})"
                row_id = insert_record(db_path, name, category, chunk)
                if row_id != -1:
                    total_inserted += 1
                else:
                    total_skipped += 1
    else:
        print("[ingest] No local files found.")

    # ── Phase 2: Web links ────────────────────────────────────────────────
    link_entries = parse_links_file(LINKS_FILE)

    if link_entries:
        print(f"\n[ingest] Processing {len(link_entries)} URL(s) from links.txt...")
        for idx, (url, label) in enumerate(link_entries):

            # Fetch the page
            page_title, text = fetch_url(url)

            if not text.strip():
                print(f"  [SKIP] {url} — no text extracted")
                total_skipped += 1
                # Polite delay even on failure
                if idx < len(link_entries) - 1:
                    time.sleep(REQUEST_DELAY)
                continue

            # Determine category and name
            if label:
                # User provided a label — parse it
                category, species_name = parse_label(label)
            else:
                # Derive from page title and domain
                domain = urlparse(url).netloc.replace("www.", "")
                species_name = f"{page_title} ({domain})"[:100]   # Cap length
                category = "document"

            chunks = chunk_text(text)
            print(f"         → category={category!r}, name={species_name!r}, chunks={len(chunks)}")

            for i, chunk in enumerate(chunks):
                # Include the source URL in the content so the LLM can reference it
                source_note = f"[Source: {url}]\n\n" if i == 0 else ""
                name = species_name if len(chunks) == 1 else f"{species_name} (part {i+1})"
                row_id = insert_record(db_path, name, category, source_note + chunk)
                if row_id != -1:
                    total_inserted += 1
                else:
                    total_skipped += 1

            # Polite delay between requests
            if idx < len(link_entries) - 1:
                time.sleep(REQUEST_DELAY)
    else:
        print("\n[ingest] No links.txt found or file is empty.")
        print(f"         Create {LINKS_FILE} with one URL per line to ingest web pages.")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n[ingest] Done. Inserted: {total_inserted}, Skipped: {total_skipped}")
    print(f"[ingest] Database: {db_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(" NoFishyBusiness — Knowledge Base Ingestion")
    print("=" * 60)
    print(f"Documents folder : {DOCUMENTS_DIR}")
    print(f"Links file       : {LINKS_FILE}")
    print(f"Database         : {DEFAULT_DB_PATH}")
    print()
    ingest_documents()
