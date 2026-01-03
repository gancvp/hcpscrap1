import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


def _normalize_text(value: str) -> str:
    """Lowercase and strip accents for lenient comparisons."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower().strip()


def _slugify(value: str) -> str:
    """Filesystem-safe slug based on normalized text."""
    return "-".join(part for part in _normalize_text(value).split() if part) or "unknown"


class MedicosDocScraper:
    """Scrapes medicosdoc.com directory pages and filters by specialty."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def fetch_doctors(
        self, directory_url: str, max_pages: Optional[int] = None
    ) -> Iterable[Dict[str, Any]]:
        """Yield raw doctor entries from a directory URL."""
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        initial_html = self._get_html(directory_url)
        build_id, path_part, first_page = self._parse_initial_payload(
            directory_url, initial_html
        )
        total_pages = int(first_page.get("totalPages", 1))

        yield from first_page.get("data", [])

        pages_to_fetch = total_pages if max_pages is None else min(total_pages, max_pages)
        for page in range(2, pages_to_fetch + 1):
            for doctor in self._fetch_page(directory_url, build_id, path_part, page):
                yield doctor

    def filter_by_specialty(
        self, doctors: Iterable[Dict[str, Any]], specialty: str
    ) -> List[Dict[str, Any]]:
        """Return doctor entries that match the given specialty."""
        target = _normalize_text(specialty)
        matches: List[Dict[str, Any]] = []
        print("Total doctors:", len(doctors))
        for doctor in doctors:
            specialty_name = self._doctor_specialty(doctor)
            if not specialty_name:
                continue
            if target in _normalize_text(specialty_name):
                matches.append(doctor)
        return matches

    def to_record(self, doctor: Dict[str, Any], directory_url: str) -> Dict[str, Any]:
        """Normalize fields for output."""
        head = doctor.get("Headquarters") or {}
        specialty_data = (doctor.get("SubSpecialties") or {}).get("Specialty") or {}
        specialty = (
            specialty_data.get("SpecialityNameEnglish")
            or specialty_data.get("SpecialityName")
            or ""
        )
        base_root = self._base_root(directory_url)
        return {
            "id": doctor.get("ShortId") or doctor.get("_id"),
            "name": self._build_name(doctor),
            "specialty": specialty,
            "city": (head.get("CityId") or {}).get("Name"),
            "address": head.get("Address"),
            "medical_center": head.get("MedicalCenter"),
            "office": head.get("Office"),
            "highlighted_services": doctor.get("HighlightedServicesEnglish")
            or doctor.get("HighlightedServices"),
            "consult_value": doctor.get("ConsultValue"),
            "premium": bool(doctor.get("Premium")),
            "rating_average": (doctor.get("RatingsSummary") or {}).get("averageRating"),
            "rating_count": (doctor.get("RatingsSummary") or {}).get("numberOfRatings"),
            "photo_url": urljoin(base_root, doctor.get("Photos") or ""),
        }

    def _fetch_page(
        self, directory_url: str, build_id: str, path_part: str, page: int
    ) -> List[Dict[str, Any]]:
        parsed = urlparse(directory_url)
        data_path = f"/_next/data/{build_id}/{path_part}.json"
        data_url = urlunparse((parsed.scheme, parsed.netloc, data_path, "", "", ""))
        response = self.session.get(data_url, params={"page": page}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["pageProps"]["directoryDoctors"]["data"]
        except KeyError as exc:
            raise RuntimeError(f"Unexpected response shape for page {page}") from exc

    def _get_html(self, url: str) -> str:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def _parse_initial_payload(
        self, directory_url: str, html: str
    ) -> Tuple[str, str, Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        data_tag = soup.find("script", id="__NEXT_DATA__")
        if not data_tag or not data_tag.string:
            raise RuntimeError("Could not locate __NEXT_DATA__ on the page.")
        next_payload = json.loads(data_tag.string)
        build_id = next_payload.get("buildId")
        if not build_id:
            raise RuntimeError("Could not find buildId; site layout may have changed.")

        path_part = self._data_path(directory_url)
        directory_data = (
            next_payload.get("props", {})
            .get("pageProps", {})
            .get("directoryDoctors", {})
        )
        if not directory_data:
            raise RuntimeError("Directory data missing from initial payload.")
        return build_id, path_part, directory_data

    @staticmethod
    def _data_path(directory_url: str) -> str:
        parsed = urlparse(directory_url)
        path = parsed.path.lstrip("/")
        if path.endswith("/"):
            path = path[:-1]
        return path or "index"

    @staticmethod
    def _doctor_specialty(doctor: Dict[str, Any]) -> str:
        specialty_data = (doctor.get("SubSpecialties") or {}).get("Specialty") or {}
        return specialty_data.get("SpecialityNameEnglish") or specialty_data.get(
            "SpecialityName"
        )

    @staticmethod
    def _build_name(doctor: Dict[str, Any]) -> str:
        first = (doctor.get("Name") or "").strip()
        last = (doctor.get("LastName") or "").strip()
        return f"{first} {last}".strip()

    @staticmethod
    def _base_root(directory_url: str) -> str:
        parsed = urlparse(directory_url)
        return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def write_output(
    records: List[Dict[str, Any]], output_format: str, destination: Optional[str]
) -> None:
    if output_format == "json":
        output = json.dumps(records, indent=2, ensure_ascii=False)
        if destination:
            with open(destination, "w", encoding="utf-8") as handle:
                handle.write(output)
        else:
            sys.stdout.write(output + "\n")
    else:
        fieldnames = [
            "id",
            "name",
            "specialty",
            "city",
            "address",
            "medical_center",
            "office",
            "highlighted_services",
            "consult_value",
            "premium",
            "rating_average",
            "rating_count",
            "photo_url",
        ]
        if destination:
            stream = open(destination, "w", newline="", encoding="utf-8")
            close_stream = True
        else:
            stream = sys.stdout
            close_stream = False
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        if close_stream:
            stream.close()


def run_specialties(
    url: str,
    specialties: List[str],
    output_dir: Optional[str] = None,
    output_format: str = "json",
    max_pages: Optional[int] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch doctors once, then filter and write outputs per specialty."""
    scraper = MedicosDocScraper()
    doctors = list(scraper.fetch_doctors(url, max_pages=max_pages))
    records_by_specialty: Dict[str, List[Dict[str, Any]]] = {}

    output_path = Path(output_dir) if output_dir else None
    if output_path:
        output_path.mkdir(parents=True, exist_ok=True)

    url_slug = _slugify(urlparse(url).path.rsplit("/", 1)[-1] or "directory")
    for specialty in specialties:
        filtered = scraper.filter_by_specialty(doctors, specialty)
        records = [scraper.to_record(doc, url) for doc in filtered]
        records_by_specialty[specialty] = records

        destination = None
        if output_path:
            destination = output_path / f"{url_slug}-{_slugify(specialty)}.{output_format}"
            destination = str(destination)

        write_output(records, output_format, destination)

    return records_by_specialty


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Scrape medicosdoc.com directories for doctors by specialty."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Directory URL, e.g. https://medicosdoc.com/en/medical-directory-colombia",
    )
    parser.add_argument("--specialty", required=True, help="Specialty to filter.")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "csv"],
        default="json",
        help="Output format (json or csv).",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        help="Optional path to write results. Defaults to stdout.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit number of pages to fetch (useful for quick tests).",
    )
    args = parser.parse_args(argv)

    scraper = MedicosDocScraper()
    doctors = list(scraper.fetch_doctors(args.url, max_pages=args.max_pages))
    filtered = scraper.filter_by_specialty(doctors, args.specialty)
    records = [scraper.to_record(doc, args.url) for doc in filtered]
    write_output(records, args.output_format, args.output_path)


if __name__ == "__main__":
    main()
