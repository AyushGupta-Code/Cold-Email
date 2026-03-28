from pathlib import Path

from app.schemas.api import JobSummary
from app.services.scrapedin_adapter import load_scrapedin_contacts


def test_load_scrapedin_contacts_from_csv_filters_to_recruiter_company(tmp_path: Path) -> None:
    dataset = tmp_path / "scrapedin_dataset.csv"
    dataset.write_text(
        """first name,last name,occupation,location,profile URL,picture URL
Jamie,Carter,Senior Recruiter at Acme,"Austin, TX",https://www.linkedin.com/in/jamie-carter,https://img.example/jamie.jpg
Chris,Stone,Software Engineer at Acme,"Seattle, WA",https://www.linkedin.com/in/chris-stone,https://img.example/chris.jpg
Priya,Shah,Talent Acquisition Partner at OtherCorp,"New York, NY",https://www.linkedin.com/in/priya-shah,https://img.example/priya.jpg
""",
        encoding="utf-8",
    )

    job_summary = JobSummary(
        company_name="Acme",
        normalized_company_name="Acme",
        position="Backend Engineer",
        job_description="Build APIs.",
        concise_summary="Backend role",
        important_skills=["Python"],
        keywords=["python"],
    )

    contacts, warnings = load_scrapedin_contacts(str(dataset), job_summary)

    assert warnings == []
    assert len(contacts) == 1
    assert contacts[0]["name"] == "Jamie Carter"
    assert contacts[0]["title"] == "Senior Recruiter at Acme"
    assert contacts[0]["profile_url"] == "https://www.linkedin.com/in/jamie-carter"
