from app.schemas.api import ContactCandidate
from app.services.contact_discovery import deduplicate_contacts
from app.services.contact_ranker import is_recruiter_like_title


def test_recruiter_title_matching() -> None:
    assert is_recruiter_like_title("Senior Recruiter") is True
    assert is_recruiter_like_title("Talent Acquisition Partner") is True
    assert is_recruiter_like_title("Engineering Manager") is False


def test_contact_deduplication_keeps_best_variant() -> None:
    contacts = [
        ContactCandidate(
            full_name="Jamie Carter",
            title="Recruiter",
            location="Austin, TX",
            company="Acme",
            profile_url="https://www.linkedin.com/in/jamie-carter",
            source_urls=["https://www.linkedin.com/in/jamie-carter"],
            evidence=["Austin, TX"],
            public_email=None,
            score=60,
            is_us_based=True,
        ),
        ContactCandidate(
            full_name="Jamie Carter",
            title="Senior Recruiter",
            location="Austin, TX",
            company="Acme",
            profile_url="https://www.linkedin.com/in/jamie-carter-acme",
            source_urls=[
                "https://www.linkedin.com/in/jamie-carter-acme",
                "https://acme.com/team/jamie-carter",
            ],
            evidence=["Austin, TX", "Acme careers page"],
            public_email="jamie.carter@acme.com",
            score=80,
            is_us_based=True,
        ),
    ]
    deduped = deduplicate_contacts(contacts)
    assert len(deduped) == 1
    assert deduped[0].public_email == "jamie.carter@acme.com"

