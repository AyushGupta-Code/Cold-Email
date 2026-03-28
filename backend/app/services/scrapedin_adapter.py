from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.schemas.api import ContactEvidence, JobSummary
from app.utils.text import normalize_company_name, normalize_whitespace

SCRAPEDIN_DATASET_COLUMNS = {
    "first_name": {"first name", "firstname", "first_name"},
    "last_name": {"last name", "lastname", "last_name"},
    "occupation": {"occupation", "headline", "title"},
    "location": {"location", "city"},
    "industry": {"industry"},
    "profile_url": {"profile url", "profile_url", "linkedin", "linkedin url"},
    "picture_url": {"picture url", "picture_url", "image", "avatar"},
}


def load_scrapedin_contacts(dataset_path: str, job_summary: JobSummary) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not dataset_path.strip():
        return [], ["ScrapedIn mode enabled but SCRAPEDIN_DATASET_PATH is empty."]

    path = Path(dataset_path).expanduser()
    if not path.exists():
        return [], [f"ScrapedIn dataset not found at: {path}"]

    suffix = path.suffix.casefold()
    try:
        if suffix == ".json":
            rows = _read_json_rows(path)
        elif suffix in {".csv", ".tsv"}:
            rows = _read_delimited_rows(path, delimiter="\t" if suffix == ".tsv" else ",")
        elif suffix in {".xlsx", ".xls"}:
            rows = _read_excel_rows(path)
        else:
            return [], [f"Unsupported ScrapedIn dataset extension '{path.suffix}'. Use .csv, .tsv, .xlsx, or .json."]
    except Exception as exc:
        return [], [f"Failed to parse ScrapedIn dataset {path}: {exc}"]

    contacts = _normalize_rows(rows, job_summary)
    if not contacts:
        warnings.append("ScrapedIn dataset loaded, but no recruiter-like contacts matched the requested company and position.")
    return contacts, warnings


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [row for row in payload["rows"] if isinstance(row, dict)]
    return []


def _read_delimited_rows(path: Path, *, delimiter: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]


def _read_excel_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import openpyxl
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("openpyxl is required to read .xlsx ScrapedIn exports") from exc

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    preferred_names = {"dataset", "data"}
    sheet = next((ws for ws in workbook.worksheets if ws.title.casefold() in preferred_names), workbook.worksheets[0])
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [normalize_whitespace(str(value or "")) for value in rows[0]]
    output: list[dict[str, Any]] = []
    for row_values in rows[1:]:
        row_dict = {headers[index]: row_values[index] for index in range(min(len(headers), len(row_values)))}
        output.append(row_dict)
    return output


def _normalize_rows(rows: list[dict[str, Any]], job_summary: JobSummary) -> list[dict[str, Any]]:
    target_company = normalize_company_name(job_summary.company_name).casefold()
    normalized: list[dict[str, Any]] = []
    seen_profiles: set[str] = set()

    for raw in rows:
        row = _canonicalize_columns(raw)
        full_name = normalize_whitespace(f"{row.get('first_name', '')} {row.get('last_name', '')}")
        title = normalize_whitespace(str(row.get("occupation") or ""))
        location = normalize_whitespace(str(row.get("location") or ""))
        profile_url = normalize_whitespace(str(row.get("profile_url") or ""))
        picture_url = normalize_whitespace(str(row.get("picture_url") or ""))
        if not full_name or not title or not profile_url:
            continue
        if profile_url in seen_profiles:
            continue

        combined = normalize_whitespace(" ".join([full_name, title, location, str(raw)]))
        row_company = _extract_company_from_headline(title)
        normalized_company = normalize_company_name(row_company or "").casefold()
        if target_company and normalized_company and target_company not in normalized_company and normalized_company not in target_company:
            if target_company not in combined.casefold():
                continue
        if not _looks_like_recruiter_title(title):
            continue

        seen_profiles.add(profile_url)
        normalized.append(
            {
                "name": full_name,
                "title": title,
                "company": row_company or job_summary.company_name,
                "location": location or None,
                "profile_url": profile_url,
                "public_email": None,
                "picture_url": picture_url or None,
                "evidence": [
                    ContactEvidence(
                        source_url=profile_url,
                        source_type="search_snippet",
                        quoted_text=normalize_whitespace(f"{full_name} - {title} - {location}"),
                    ).model_dump()
                ],
            }
        )

    return normalized


def _canonicalize_columns(row: dict[str, Any]) -> dict[str, Any]:
    normalized_map: dict[str, str] = {}
    for key in row:
        normalized_key = normalize_whitespace(str(key)).casefold()
        normalized_map[normalized_key] = key

    output: dict[str, Any] = {}
    for canonical, aliases in SCRAPEDIN_DATASET_COLUMNS.items():
        output[canonical] = ""
        for alias in aliases:
            if alias in normalized_map:
                output[canonical] = row.get(normalized_map[alias])
                break
    return output


def _extract_company_from_headline(headline: str) -> str | None:
    clean = normalize_whitespace(headline)
    if not clean:
        return None
    lower = clean.casefold()
    for splitter in (" at ", " @ "):
        if splitter in lower:
            index = lower.find(splitter)
            return normalize_whitespace(clean[index + len(splitter) :]) or None
    return None


def _looks_like_recruiter_title(title: str) -> bool:
    lowered = normalize_whitespace(title).casefold()
    signals = ("recruit", "talent acquisition", "sourcer", "staffing", "hiring manager", "campus", "university")
    return any(signal in lowered for signal in signals)
