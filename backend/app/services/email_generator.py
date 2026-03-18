from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests

from app.core.config import Settings
from app.schemas.api import ContactCandidate, GeneratedEmailPayload, JobSummary, ResumeSummary
from app.utils.text import truncate_text, unique_preserve_order, word_overlap_score

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
PROMPT_VERSION = "email_v1"


@lru_cache(maxsize=1)
def _get_sentence_transformer_class():
    # Defer the optional dependency import so API startup does not block on torch.
    try:  # pragma: no cover - dependency availability depends on environment
        from sentence_transformers import SentenceTransformer
    except Exception:  # pragma: no cover
        return None
    return SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model(model_name: str):
    sentence_transformer = _get_sentence_transformer_class()
    if sentence_transformer is None:
        return None
    try:
        return sentence_transformer(model_name)
    except Exception:
        return None


def select_relevant_resume_points(
    resume_summary: ResumeSummary,
    job_summary: JobSummary,
    settings: Settings,
    top_k: int = 4,
) -> list[str]:
    candidates = unique_preserve_order(
        [f"Skill: {skill}" for skill in resume_summary.skills]
        + [f"Project: {project}" for project in resume_summary.projects]
        + [f"Experience: {bullet}" for bullet in resume_summary.experience_bullets]
    )
    if not candidates:
        return []

    target = f"{job_summary.position}\n{job_summary.concise_summary}\n{', '.join(job_summary.important_skills)}"
    model = get_embedding_model(settings.semantic_model)
    if model is None:
        ranked = sorted(candidates, key=lambda item: word_overlap_score(item, target), reverse=True)
        return ranked[:top_k]

    try:  # pragma: no cover - model availability depends on environment
        embeddings = model.encode(candidates + [target], normalize_embeddings=True)
        target_vector = embeddings[-1]
        scores = []
        for index, item in enumerate(candidates):
            similarity = float((embeddings[index] * target_vector).sum())
            scores.append((similarity, item))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scores[:top_k]]
    except Exception:
        ranked = sorted(candidates, key=lambda item: word_overlap_score(item, target), reverse=True)
        return ranked[:top_k]


def generate_emails_for_contacts(
    contacts: list[ContactCandidate],
    resume_summary: ResumeSummary,
    job_summary: JobSummary,
    settings: Settings,
) -> list[GeneratedEmailPayload]:
    generated: list[GeneratedEmailPayload] = []
    for contact in contacts:
        generated.append(generate_email_for_contact(contact, resume_summary, job_summary, settings))
    return generated


def generate_email_for_contact(
    contact: ContactCandidate,
    resume_summary: ResumeSummary,
    job_summary: JobSummary,
    settings: Settings,
) -> GeneratedEmailPayload:
    highlights = select_relevant_resume_points(resume_summary, job_summary, settings)
    context = {
        "contact_name": contact.full_name,
        "contact_title": contact.title,
        "company_name": job_summary.company_name,
        "position": job_summary.position,
        "job_summary": job_summary.concise_summary,
        "resume_name": resume_summary.name or "The candidate",
        "resume_highlights": "\n".join(f"- {item}" for item in highlights) or "- Relevant experience was parsed but no high-confidence highlights were selected.",
    }
    system_prompt = _load_prompt("email_v1_system.txt")
    user_prompt = _load_prompt("email_v1_user.txt").format(**context)

    ok, message, raw_response = test_ollama_connection(settings.ollama_base_url, settings.ollama_model)
    if not ok:
        return GeneratedEmailPayload(
            contact_id=contact.id,
            subject=f"{job_summary.position} at {job_summary.company_name}",
            body="Email generation is unavailable because Ollama could not be reached. You can still review contacts and draft manually.",
            status="unavailable",
            model_name=settings.ollama_model,
            prompt_version=PROMPT_VERSION,
            warnings=[message],
        )

    try:
        response = requests.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {"temperature": settings.ollama_temperature},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return _parse_ollama_email_payload(
            payload.get("response", ""),
            contact_id=contact.id,
            model_name=settings.ollama_model,
        )
    except Exception as exc:
        return GeneratedEmailPayload(
            contact_id=contact.id,
            subject=f"{job_summary.position} at {job_summary.company_name}",
            body="Ollama returned an error. Draft generation failed gracefully so contacts are still available.",
            status="error",
            model_name=settings.ollama_model,
            prompt_version=PROMPT_VERSION,
            warnings=[str(exc), raw_response],
        )


def _parse_ollama_email_payload(raw: str, *, contact_id: int | None, model_name: str) -> GeneratedEmailPayload:
    cleaned = raw.strip().strip("`")
    cleaned = cleaned.replace("json\n", "", 1) if cleaned.lower().startswith("json\n") else cleaned
    if cleaned.startswith("{"):
        try:
            payload = json.loads(cleaned)
            return GeneratedEmailPayload(
                contact_id=contact_id,
                subject=truncate_text(payload.get("subject", "").strip(), 140) or "Quick intro",
                body=truncate_text(payload.get("body", "").strip(), 1600),
                status="generated",
                model_name=model_name,
                prompt_version=PROMPT_VERSION,
                warnings=[],
            )
        except json.JSONDecodeError:
            pass

    subject = "Quick intro"
    body = cleaned
    for line in cleaned.splitlines():
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
            body = cleaned.split(line, 1)[1].strip()
            break
    return GeneratedEmailPayload(
        contact_id=contact_id,
        subject=truncate_text(subject, 140),
        body=truncate_text(body, 1600),
        status="generated",
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
        warnings=["The model response was not strict JSON; a fallback parser was used."],
    )


def test_ollama_connection(base_url: str, model_name: str) -> tuple[bool, str, str]:
    try:
        response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        models = [item.get("name", "") for item in payload.get("models", [])]
        if model_name and not any(model_name in item for item in models):
            return False, f"Ollama is reachable but model '{model_name}' is not pulled locally.", json.dumps({"models": models})
        return True, "Ollama is reachable.", json.dumps({"models": models})
    except Exception as exc:
        return False, f"Unable to reach Ollama at {base_url}: {exc}", ""


def _load_prompt(filename: str) -> str:
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")
