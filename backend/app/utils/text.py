from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "that",
    "this",
    "from",
    "into",
    "your",
    "their",
    "have",
    "will",
    "about",
    "build",
    "role",
    "team",
    "using",
    "years",
    "year",
    "work",
    "plus",
    "across",
    "strong",
    "ability",
    "experience",
    "preferred",
    "required",
}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_line_list(lines: list[str]) -> list[str]:
    return [normalize_whitespace(line) for line in lines if normalize_whitespace(line)]


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = normalize_whitespace(value)
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def sentence_split(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalize_whitespace(text))
    return [part.strip() for part in parts if part.strip()]


def truncate_text(text: str, limit: int = 500) -> str:
    value = normalize_whitespace(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def normalize_company_name(company_name: str) -> str:
    normalized = normalize_whitespace(company_name)
    normalized = re.sub(r"\b(inc|llc|ltd|corp|corporation|co)\.?\b", "", normalized, flags=re.IGNORECASE)
    return normalize_whitespace(normalized)


def extract_email_addresses(text: str) -> list[str]:
    return unique_preserve_order(EMAIL_PATTERN.findall(text or ""))


def safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2)


def stable_cache_key(prefix: str, *parts: object) -> str:
    serialized = "||".join(
        json.dumps(part, ensure_ascii=True, sort_keys=True) if not isinstance(part, str) else normalize_whitespace(part)
        for part in parts
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def word_overlap_score(left: str, right: str) -> float:
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    return len(left_set & right_set) / max(len(right_set), 1)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9+#.]{2,}", (text or "").lower())
    return [token for token in tokens if token not in STOPWORDS]


def top_keywords(text: str, limit: int = 12) -> list[str]:
    tokens = tokenize(text)
    counts = Counter(tokens)
    ranked = [word for word, _ in counts.most_common(limit)]
    return ranked
