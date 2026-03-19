from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.contact_discovery import discover_contacts
from app.services.job_profile import build_job_profile
from app.services.resume_parser import parse_resume_bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run only the contact-search pipeline against local inputs.")
    parser.add_argument("--company", required=True, help="Target company name")
    parser.add_argument("--position", required=True, help="Target role or position")
    parser.add_argument("--job-description", help="Inline job description text")
    parser.add_argument("--job-description-file", help="Path to a text file containing the job description")
    parser.add_argument("--resume-file", help="Path to a local resume file (PDF, DOCX, TXT, or MD)")
    parser.add_argument("--resume-text", help="Inline parsed resume text or resume summary")
    parser.add_argument("--resume-text-file", help="Path to a text file containing parsed resume text or summary")
    return parser.parse_args()


def read_optional_text(value: str | None, file_path: str | None, label: str) -> str:
    if value:
        return value
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    raise ValueError(f"{label} is required")


def read_resume_payload(args: argparse.Namespace) -> tuple[str, bytes]:
    if args.resume_file:
        path = Path(args.resume_file)
        return path.name, path.read_bytes()

    resume_text = read_optional_text(args.resume_text, args.resume_text_file, "resume input")
    return "resume.txt", resume_text.encode("utf-8")


def main() -> int:
    args = parse_args()
    job_description = read_optional_text(args.job_description, args.job_description_file, "job description")
    resume_filename, resume_bytes = read_resume_payload(args)

    settings = get_settings()
    init_db()

    _, resume_summary, resume_warnings = parse_resume_bytes(resume_filename, resume_bytes)
    job_summary = build_job_profile(args.company, args.position, job_description)

    with SessionLocal() as db:
        response = discover_contacts(job_summary, resume_summary, db, settings)

    payload = response.model_dump()
    if resume_warnings:
        payload["warnings"] = resume_warnings + payload["warnings"]

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
