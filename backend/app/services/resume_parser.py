from __future__ import annotations

from io import BytesIO
import re

import pdfplumber
from docx import Document

from app.schemas.api import ResumeSummary
from app.utils.text import normalize_line_list, normalize_whitespace, sentence_split, truncate_text, unique_preserve_order

SECTION_HEADERS = {
    "education": "education",
    "skills": "skills",
    "technical skills": "skills",
    "projects": "projects",
    "experience": "experience",
    "professional experience": "experience",
    "work experience": "experience",
}


def parse_resume_bytes(filename: str, content: bytes) -> tuple[str, ResumeSummary, list[str]]:
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
    warnings: list[str] = []

    if extension == "pdf":
        raw_text = _parse_pdf(content)
    elif extension == "docx":
        raw_text = _parse_docx(content)
    elif extension in {"txt", "md"}:
        raw_text = _parse_txt(content)
    else:
        raise ValueError("Unsupported resume format. Please upload PDF, DOCX, or TXT.")

    raw_text = raw_text.replace("\x00", " ")
    if not raw_text.strip():
        raise ValueError("Resume parsing produced no text.")

    summary = _build_resume_summary(raw_text)
    if not summary.name:
        warnings.append("Could not confidently detect the candidate name from the resume.")
    return raw_text, summary, warnings


def _parse_pdf(content: bytes) -> str:
    with pdfplumber.open(BytesIO(content)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def _parse_docx(content: bytes) -> str:
    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _parse_txt(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _build_resume_summary(raw_text: str) -> ResumeSummary:
    lines = normalize_line_list(raw_text.splitlines())
    sections: dict[str, list[str]] = {"education": [], "skills": [], "projects": [], "experience": []}
    current_section: str | None = None

    for line in lines:
        lowered = line.lower().rstrip(":")
        if lowered in SECTION_HEADERS:
            current_section = SECTION_HEADERS[lowered]
            continue
        if current_section:
            sections[current_section].append(line)

    name = _extract_name(lines)
    skills = _extract_skills(sections["skills"], raw_text)
    projects = unique_preserve_order(sections["projects"])[:6]
    education = unique_preserve_order(sections["education"])[:6]
    experience = _extract_experience_bullets(sections["experience"], raw_text)

    return ResumeSummary(
        name=name,
        education=education,
        skills=skills,
        projects=projects,
        experience_bullets=experience,
        raw_text_excerpt=truncate_text(raw_text, 800),
    )


def _extract_name(lines: list[str]) -> str | None:
    for line in lines[:5]:
        if re.fullmatch(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3}", line):
            return line
    return None


def _extract_skills(skill_lines: list[str], raw_text: str) -> list[str]:
    source = "\n".join(skill_lines) if skill_lines else raw_text
    pieces = re.split(r"[,|\n/]+", source)
    cleaned = [normalize_whitespace(piece) for piece in pieces]
    skills = [
        value
        for value in cleaned
        if 1 < len(value) <= 40 and re.search(r"[A-Za-z]", value) and value.lower() not in SECTION_HEADERS
    ]
    return unique_preserve_order(skills)[:20]


def _extract_experience_bullets(experience_lines: list[str], raw_text: str) -> list[str]:
    bullets = [
        line.lstrip("-• ").strip()
        for line in experience_lines
        if len(line) > 20 and (line.startswith(("-", "•")) or re.search(r"\b(built|shipped|led|implemented|created|developed)\b", line.lower()))
    ]
    if not bullets:
        bullets = [
            sentence
            for sentence in sentence_split(raw_text)
            if len(sentence) > 35 and re.search(r"\b(built|shipped|led|implemented|created|developed)\b", sentence.lower())
        ]
    return unique_preserve_order(bullets)[:8]
