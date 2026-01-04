# MedicosDoc Directory Scraper

Small Python utility to pull doctor entries from medicosdoc.com directory pages and filter them by specialty. Works with any country-specific directory URL and can output JSON or CSV.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python3 medicosdoc_scraper.py \
  --url https://medicosdoc.com/en/medical-directory-colombia \
  --specialty "Gynecologist" \
  --format json \
  --max-pages 2 \
  --provider medicosdoc \
  --output gynecologists.json

### Multiple specialties via config

```bash
python3 run_from_config.py --config config.sample.json
```

`config.sample.json` shows the shape:

```json
{
  "output_dir": "outputs",
  "output_format": "json",
  "max_pages": 2,
  "directories": [
    {
      "url": "https://medicosdoc.com/en/medical-directory-colombia",
      "specialties": ["Gynecologist", "Oncologist"],
      "provider": "medicosdoc"
    },
    {
      "url": "https://medicosdoc.com/en/medical-directory-mexico",
      "specialties": ["Orthopedist"]
    }
  ]
}
```

Outputs are written per specialty and country slug, e.g. `outputs/medical-directory-colombia-gynecologist.json`.

## Extending to new directory patterns

- Providers live in code as subclasses of `BaseDirectoryProvider`.
- Implement `can_handle(url, html)`, `fetch_doctors(...)`, `doctor_specialty(...)`, and `to_record(...)`.
- Register your provider by adding it to the `providers` list passed to `DirectoryScraper` (or include it in a factory) and optionally expose its name so configs can force it via `"provider": "<name>"` or `--provider <name>`.
- The CLI and `run_specialties` use `DirectoryScraper`, which picks the first provider whose `can_handle` returns `True` after inspecting the initial HTML.
```

Flags:
- `--url` (required): Country directory page to scrape.
- `--specialty` (required): Specialty name to match (case and accent insensitive).
- `--format`: `json` (default) or `csv`.
- `--output`: Optional path; prints to stdout if omitted.
- `--max-pages`: Optional limit to reduce fetch time during testing.

## Tests

```bash
pytest
```
