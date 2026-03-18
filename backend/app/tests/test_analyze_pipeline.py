from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal, init_db
from app.main import app
from app.models.entities import Contact, GeneratedEmail, Job, Resume, SearchCache, SendLog
from app.schemas.api import ContactCandidate

client = TestClient(app)


def _reset_tables() -> None:
    init_db()
    with SessionLocal() as db:
        for model in [SendLog, GeneratedEmail, Contact, Resume, Job, SearchCache]:
            db.execute(delete(model))
        db.commit()


def test_analyze_pipeline_with_mocked_search_and_ollama(monkeypatch) -> None:
    _reset_tables()

    def fake_discover_contacts(job_summary, db, settings):
        return (
            [
                ContactCandidate(
                    full_name="Jamie Carter",
                    title="Senior Recruiter",
                    location="Austin, TX",
                    company=job_summary.company_name,
                    profile_url="https://www.linkedin.com/in/jamie-carter-acme",
                    public_email="jamie.carter@example.com",
                    source_urls=["https://www.linkedin.com/in/jamie-carter-acme"],
                    evidence=["Austin, TX", "Public LinkedIn snippet"],
                    is_us_based=True,
                )
            ],
            ["Mocked discovery executed."],
        )

    def fake_generate_emails_for_contacts(contacts, resume_summary, job_summary, settings):
        return [
            {
                "contact_id": contacts[0].id,
                "subject": f"{job_summary.position} at {job_summary.company_name}",
                "body": "Hi Jamie, I’m reaching out about the backend role at Acme. I recently built recruiter tooling in FastAPI and React, plus an embedding-based ranking service. Those projects line up well with the role’s need for product-minded engineering and local AI workflows. If helpful, I’d appreciate a short conversation to learn where the team is hiring and whether my background could be relevant. Thanks for your time.",
                "status": "generated",
                "model_name": "mock-ollama",
                "prompt_version": "email_v1",
                "warnings": [],
            }
        ]

    monkeypatch.setattr("app.api.routes.discover_contacts", fake_discover_contacts)
    monkeypatch.setattr("app.api.routes.generate_emails_for_contacts", fake_generate_emails_for_contacts)

    resume_path = Path(__file__).resolve().parents[2] / "sample_data" / "sample_resume.txt"
    with resume_path.open("rb") as handle:
        response = client.post(
            "/api/analyze",
            data={
                "company_name": "Acme",
                "position": "Backend Engineer",
                "job_description": "Build internal recruiter systems with Python, FastAPI, React, and NLP.",
            },
            files={"resume_file": ("sample_resume.txt", handle, "text/plain")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["normalized_job_summary"]["company_name"] == "Acme"
    assert len(payload["contacts"]) == 1
    assert payload["generated_emails"][0]["status"] == "generated"
    assert "Mocked discovery executed." in payload["warnings"]
