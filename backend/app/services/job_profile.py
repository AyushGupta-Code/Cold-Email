from __future__ import annotations

import re

from app.schemas.api import JobSummary
from app.utils.text import normalize_company_name, normalize_whitespace, sentence_split, top_keywords, unique_preserve_order

TECH_PATTERNS = [
    r"\bPython\b",
    r"\bFastAPI\b",
    r"\bReact\b",
    r"\bTypeScript\b",
    r"\bJavaScript\b",
    r"\bNode\.js\b",
    r"\bSQL\b",
    r"\bSQLAlchemy\b",
    r"\bDocker\b",
    r"\bKubernetes\b",
    r"\bAWS\b",
    r"\bAzure\b",
    r"\bGCP\b",
    r"\bLLM\b",
    r"\bOllama\b",
    r"\bNLP\b",
    r"\bmachine learning\b",
    r"\bPyTorch\b",
    r"\bJava\b",
    r"\bC\+\+\b",
    r"\bC#\b",
]


def build_job_profile(company_name: str, position: str, job_description: str) -> JobSummary:
    clean_company = normalize_company_name(company_name)
    clean_position = normalize_whitespace(position)
    clean_description = normalize_whitespace(job_description)
    keywords = extract_keywords(clean_description)
    summary = summarize_job_description(clean_position, clean_description, keywords)
    return JobSummary(
        company_name=normalize_whitespace(company_name),
        normalized_company_name=clean_company,
        position=clean_position,
        job_description=clean_description,
        concise_summary=summary,
        important_skills=keywords[:10],
        keywords=keywords,
    )


def extract_keywords(job_description: str) -> list[str]:
    matches: list[str] = []
    for pattern in TECH_PATTERNS:
        match = re.search(pattern, job_description, flags=re.IGNORECASE)
        if match:
            matches.append(match.group(0))

    sentence_keywords = [word for word in top_keywords(job_description, limit=20) if len(word) > 2]
    combined = unique_preserve_order(matches + sentence_keywords)
    return combined[:15]


def summarize_job_description(position: str, description: str, keywords: list[str]) -> str:
    sentences = sentence_split(description)
    lead = " ".join(sentences[:2]) if sentences else description[:320]
    if keywords:
        return f"{position} role. {lead} Core themes: {', '.join(keywords[:6])}."
    return f"{position} role. {lead}"

