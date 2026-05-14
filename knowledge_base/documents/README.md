# Knowledge Base Documents

Drop your reference files here and add web links to `links.txt`, then run the ingestion script.

## How to ingest

```bash
python knowledge_base/ingest.py
```

---

## Adding web links

Edit `links.txt` — one entry per line using curly-brace syntax:

```
{Guppy: https://en.wikipedia.org/wiki/Guppy}
{Betta Fish: https://en.wikipedia.org/wiki/Siamese_fighting_fish}
{fish_betta care guide: https://www.aquariumcoop.com/blogs/aquarium/betta-fish-care}
{maintenance_nitrogen cycle: https://en.wikipedia.org/wiki/Nitrogen_cycle}
```

**Format:** `{Description: URL}`

The description before the `:` becomes the record name. If it starts with a valid category prefix (e.g. `fish_`, `plant_`, `maintenance_`), that category is applied automatically. Otherwise the category defaults to `document`.

---

## Adding local files

Supported formats:

| Format | Extension |
|--------|-----------|
| Plain text | `.txt` |
| Markdown | `.md` |
| PDF | `.pdf` (requires `pip install pypdf`) |

**Naming convention** — `<category>_<name>.ext`:

```
fish_betta_care_guide.txt
chemistry_ammonia_thresholds.md
maintenance_water_change_schedule.pdf
disease_ich_treatment.txt
plant_java_fern_guide.md
aquascaping_dutch_style.txt
```

Valid categories: `fish`, `plant`, `chemistry`, `maintenance`, `disease`, `aquascaping`

If the filename doesn't match the pattern, the category defaults to `document`.

---

## Notes

- Long documents and web pages are automatically split into ~400-word chunks
- The script is safe to run multiple times — it adds new records each run
- To fully reset the knowledge base: delete `aquarium.db`, then run `seed.py` followed by `ingest.py`
- Photos/images are not directly supported — copy the text description instead
- The script waits 1 second between web requests to avoid overloading servers
