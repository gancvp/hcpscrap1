import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from medicosdoc_scraper import run_specialties


def _load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_directories(entries: List[Dict[str, Any]]) -> None:
    for entry in entries:
        if "url" not in entry:
            raise ValueError("Each directory entry must include a 'url'.")
        if "specialties" not in entry or not isinstance(entry["specialties"], list):
            raise ValueError("Each directory entry must include a 'specialties' list.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run medicosdoc scraper using a JSON config."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON config file listing directories and specialties.",
    )
    args = parser.parse_args()

    config = _load_config(args.config)
    directories = config.get("directories") or []
    _validate_directories(directories)

    output_format = config.get("output_format", "json")
    max_pages = config.get("max_pages")
    output_dir = config.get("output_dir")
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    for entry in directories:
        url = entry["url"]
        specialties = entry["specialties"]
        run_specialties(
            url=url,
            specialties=specialties,
            output_dir=output_dir,
            output_format=output_format,
            max_pages=max_pages,
        )


if __name__ == "__main__":
    main()
